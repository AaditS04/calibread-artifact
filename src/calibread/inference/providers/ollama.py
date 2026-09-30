'''Strict local-only Ollama adapter using the native HTTP API.'''

from __future__ import annotations

import hashlib
import json
from math import isfinite
import os
import re
import time
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ..config import ProviderConfig
from ..types import InferenceRequest, InferenceResponse, ProviderError, ProviderFingerprint


_SHA256 = re.compile(r'^[0-9a-f]{64}$')
_HIDDEN_MODEL_CONTEXT = re.compile(r'^\s*(?:SYSTEM|MESSAGE)\s+', re.IGNORECASE | re.MULTILINE)


def _hash_text(value: object) -> str:
    if isinstance(value, str):
        encoded = value.encode('utf-8')
    else:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(',', ':'),
        ).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _optional_hash(value: object) -> str | None:
    if value in (None, '', [], {}):
        return None
    return _hash_text(value)


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return max(0, int(value))


class OllamaProvider:
    '''Call only a loopback Ollama server and pin each local model by digest.'''

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        override = os.environ.get('CALIBREAD_OLLAMA_BASE_URL', '').strip()
        if override:
            parsed = urlparse(override)
            if parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost'}:
                raise ProviderError('CALIBREAD_OLLAMA_BASE_URL must be an http loopback URL')
            base = override.rstrip('/')
        else:
            base = config.base_url.rstrip('/')
        self.api_root = base if base.endswith('/api') else f'{base}/api'
        self._fingerprints: dict[str, ProviderFingerprint] = {}

    @staticmethod
    def _http_error(error: HTTPError) -> ProviderError:
        retry_after = error.headers.get('Retry-After')
        body = error.read().decode('utf-8', 'replace')
        return ProviderError(
            f'Ollama HTTP {error.code}: {body[:1000]}',
            status_code=error.code,
            retryable=error.code in {408, 429, 500, 502, 503, 504},
            retry_after=float(retry_after) if retry_after and retry_after.isdigit() else None,
        )

    def _make_request(
        self,
        method: str,
        endpoint: str,
        body: Mapping[str, object] | None,
    ) -> Request:
        data = None if body is None else json.dumps(dict(body)).encode('utf-8')
        headers = {'Accept': 'application/json'}
        if data is not None:
            headers['Content-Type'] = 'application/json'
        return Request(
            f'{self.api_root}/{endpoint.lstrip(chr(47))}',
            data=data,
            headers=headers,
            method=method,
        )

    def _once(
        self,
        method: str,
        endpoint: str,
        body: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        request = self._make_request(method, endpoint, body)
        return self._open(request)

    def _open(self, request: Request) -> dict[str, object]:
        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                payload = json.load(response)
        except HTTPError as error:
            raise self._http_error(error) from error
        except json.JSONDecodeError as error:
            raise ProviderError('Ollama returned malformed JSON') from error
        except (URLError, TimeoutError, OSError) as error:
            raise ProviderError(
                f'cannot reach local Ollama API at {self.api_root}: {error}',
                retryable=True,
            ) from error
        return self._validate_payload(payload)

    @staticmethod
    def _validate_payload(payload: object) -> dict[str, object]:
        if not isinstance(payload, dict):
            raise ProviderError('Ollama returned a non-object response')
        message = payload.get('error')
        if isinstance(message, str) and message:
            raise ProviderError(f'Ollama error: {message}')
        return payload

    def _request(
        self,
        method: str,
        endpoint: str,
        body: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        for attempt in range(self.config.max_retries + 1):
            try:
                return self._once(method, endpoint, body)
            except ProviderError as error:
                if not error.retryable or attempt >= self.config.max_retries:
                    raise
                delay = error.retry_after
                if delay is None:
                    delay = min(10.0, 2.0**attempt)
                time.sleep(delay)
        raise AssertionError('unreachable retry state')

    @staticmethod
    def _model_names(value: Mapping[str, object]) -> set[str]:
        names: set[str] = set()
        for key in ('name', 'model'):
            text = value.get(key)
            if isinstance(text, str) and text.strip():
                names.add(text.strip())
        return names

    @staticmethod
    def _requested_names(model: str) -> set[str]:
        names = {model}
        if ':' not in model.rsplit('/', 1)[-1]:
            names.add(f'{model}:latest')
        return names

    def _find_model(
        self,
        model: str,
        models: list[object],
    ) -> tuple[dict[str, object], str]:
        requested = self._requested_names(model)
        matches = [
            value
            for value in models
            if isinstance(value, dict) and self._model_names(value).intersection(requested)
        ]
        if len(matches) != 1:
            available = sorted(
                name
                for value in models
                if isinstance(value, dict)
                for name in self._model_names(value)
            )
            raise ProviderError(
                f'{model!r} is not one exact local Ollama model; available: {available}'
            )
        match = matches[0]
        local_name = sorted(self._model_names(match).intersection(requested))[0]
        return match, local_name

    @staticmethod
    def _model_digest(model: Mapping[str, object]) -> str:
        digest = str(model.get('digest') or '').casefold()
        if digest.startswith('sha256:'):
            digest = digest.removeprefix('sha256:')
        if not _SHA256.fullmatch(digest):
            raise ProviderError('local Ollama model has no valid SHA-256 digest')
        return digest

    @staticmethod
    def _check_hidden_context(show: Mapping[str, object]) -> None:
        system = show.get('system')
        if isinstance(system, str) and system.strip():
            raise ProviderError('local Ollama model contains an embedded system prompt')
        if system not in (None, '') and not isinstance(system, str):
            raise ProviderError('Ollama returned malformed embedded system context')
        if show.get('messages') not in (None, []):
            raise ProviderError('local Ollama model contains embedded message history')
        modelfile = show.get('modelfile')
        if isinstance(modelfile, str) and _HIDDEN_MODEL_CONTEXT.search(modelfile):
            raise ProviderError('local Ollama Modelfile contains SYSTEM or MESSAGE context')
        if modelfile is not None and not isinstance(modelfile, str):
            raise ProviderError('Ollama returned a malformed Modelfile')

    def preflight(self, model: str) -> ProviderFingerprint:
        lowered = model.casefold()
        if 'cloud' in lowered:
            raise ProviderError('Ollama cloud models are forbidden for local-only inference')
        cached = self._fingerprints.get(model)
        if cached is not None:
            return cached
        version_payload = self._request('GET', 'version')
        version = version_payload.get('version')
        if not isinstance(version, str) or not version.strip():
            raise ProviderError('Ollama /api/version omitted its runtime version')
        tags_payload = self._request('GET', 'tags')
        models = tags_payload.get('models')
        if not isinstance(models, list):
            raise ProviderError('Ollama /api/tags omitted its local model list')
        tag, local_name = self._find_model(model, models)
        digest = self._model_digest(tag)
        show = self._request('POST', 'show', {'model': local_name})
        self._check_hidden_context(show)
        fingerprint = self._build_fingerprint(
            model, local_name, digest, version.strip(), tag, show
        )
        self._fingerprints[model] = fingerprint
        return fingerprint

    def _model_metadata(
        self,
        local_name: str,
        digest: str,
        version: str,
        tag: Mapping[str, object],
        show: Mapping[str, object],
    ) -> dict[str, object]:
        details = tag.get('details')
        if not isinstance(details, dict):
            details = show.get('details') if isinstance(show.get('details'), dict) else {}
        return {
            'identity_strength': 'local_content_digest',
            'ollama_version': version,
            'api_base_url': self.api_root,
            'local_model_name': local_name,
            'model_digest_sha256': digest,
            'model_size_bytes': _integer(tag.get('size')),
            'model_modified_at': str(tag.get('modified_at') or ''),
            'model_details': dict(details),
            'capabilities': list(show.get('capabilities') or []),
            'template_sha256': _optional_hash(show.get('template')),
            'parameters_sha256': _optional_hash(show.get('parameters')),
            'modelfile_sha256': _optional_hash(show.get('modelfile')),
            'model_info_sha256': _optional_hash(show.get('model_info')),
            'embedded_context_checked': True,
        }

    def _build_fingerprint(
        self,
        requested: str,
        local_name: str,
        digest: str,
        version: str,
        tag: Mapping[str, object],
        show: Mapping[str, object],
    ) -> ProviderFingerprint:
        metadata = self._model_metadata(local_name, digest, version, tag, show)
        metadata['closed_book'] = {
            'loopback_api': True,
            'local_model_digest_verified': True,
            'cloud_models_forbidden': True,
            'embedded_system_or_history': False,
            'tools': [],
            'images': False,
            'rag_context': False,
        }
        return ProviderFingerprint(
            requested_model=requested,
            model_snapshot_id=f'ollama:{local_name}@sha256:{digest}',
            provider_name='ollama-local',
            metadata=metadata,
        )

    @staticmethod
    def _options(request: InferenceRequest) -> dict[str, object]:
        options: dict[str, object] = {
            'temperature': request.temperature,
            'num_predict': request.max_tokens,
            'seed': request.decoding_seed,
        }
        if request.num_ctx is not None:
            options['num_ctx'] = request.num_ctx
        return options

    def _payload(self, request: InferenceRequest) -> dict[str, object]:
        if not isinstance(request.system_prompt, str) or not isinstance(request.user_prompt, str):
            raise ValueError('Ollama prompts must be strings')
        payload: dict[str, object] = {
            'model': request.model,
            'messages': [
                {'role': 'system', 'content': request.system_prompt},
                {'role': 'user', 'content': request.user_prompt},
            ],
            'tools': [],
            'stream': False,
            'think': False,
            'keep_alive': self.config.keep_alive,
            'options': self._options(request),
        }
        if request.require_logprobs:
            payload['logprobs'] = True
            payload['top_logprobs'] = request.top_logprobs
        return payload

    @staticmethod
    def _message(payload: Mapping[str, object]) -> str:
        if payload.get('done') is False:
            raise ProviderError('non-streaming Ollama response was not complete')
        message = payload.get('message')
        if not isinstance(message, dict) or not isinstance(message.get('content'), str):
            raise ProviderError('Ollama response has no text message content')
        if message.get('tool_calls'):
            raise ProviderError('closed-book Ollama response unexpectedly used a tool')
        text = message['content'].strip()
        if not text:
            raise ProviderError('Ollama response text is empty')
        return text

    @staticmethod
    def _token_logprobs(payload: Mapping[str, object]) -> list[float]:
        values: list[float] = []
        raw = payload.get('logprobs')
        if not isinstance(raw, list):
            return values
        for token in raw:
            value = token.get('logprob') if isinstance(token, dict) else None
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            score = float(value)
            if isfinite(score):
                values.append(score)
        return values

    def _validate_returned_model(
        self,
        payload: Mapping[str, object],
        request: InferenceRequest,
        fingerprint: ProviderFingerprint,
    ) -> None:
        local_name = str(fingerprint.metadata.get('local_model_name') or request.model)
        returned = str(payload.get('model') or local_name)
        expected = self._requested_names(local_name).union(self._requested_names(request.model))
        if returned not in expected:
            raise ProviderError(
                f'Ollama returned unexpected model tag {returned!r}; expected {local_name!r}'
            )

    @staticmethod
    def _generation_metadata(
        payload: Mapping[str, object],
        fingerprint: ProviderFingerprint,
        usable: bool,
    ) -> dict[str, object]:
        return {
            'confidence_usable': usable,
            'ollama_version': fingerprint.metadata.get('ollama_version'),
            'model_digest_sha256': fingerprint.metadata.get('model_digest_sha256'),
            'ollama_created_at': str(payload.get('created_at') or ''),
            'ollama_total_duration_ns': _integer(payload.get('total_duration')),
            'ollama_load_duration_ns': _integer(payload.get('load_duration')),
            'ollama_prompt_eval_duration_ns': _integer(payload.get('prompt_eval_duration')),
            'ollama_eval_duration_ns': _integer(payload.get('eval_duration')),
            'closed_book_local_only': True,
            'closed_book_tools_sent': [],
            'closed_book_rag_context_sent': False,
            'closed_book_images_sent': False,
        }

    @staticmethod
    def _score(
        request: InferenceRequest,
        payload: Mapping[str, object],
    ) -> tuple[float, str, bool]:
        logprobs = OllamaProvider._token_logprobs(payload)
        if request.require_logprobs and not logprobs:
            raise ProviderError('local Ollama model did not return required logprobs')
        if not logprobs:
            return 0.0, 'unavailable_constant_zero', False
        return (
            sum(logprobs) / len(logprobs),
            'mean_generated_token_log_probability',
            True,
        )

    @staticmethod
    def _request_id(
        fingerprint: ProviderFingerprint,
        request: InferenceRequest,
        payload: Mapping[str, object],
        text: str,
    ) -> str:
        created = str(payload.get('created_at') or '')
        material = f'{fingerprint.model_snapshot_id}:{request.example_id}:{created}:{text}'
        return 'ollama-' + hashlib.sha256(material.encode('utf-8')).hexdigest()[:24]

    def generate(self, request: InferenceRequest) -> InferenceResponse:
        fingerprint = self.preflight(request.model)
        payload = self._request('POST', 'chat', self._payload(request))
        text = self._message(payload)
        self._validate_returned_model(payload, request, fingerprint)
        score, score_source, usable = self._score(request, payload)
        finish_reason = str(
            payload.get('done_reason') or ('stop' if payload.get('done') else '')
        )
        return InferenceResponse(
            text=text,
            requested_model=request.model,
            returned_model=fingerprint.model_snapshot_id,
            request_id=self._request_id(fingerprint, request, payload, text),
            score=score,
            score_source=score_source,
            prompt_tokens=_integer(payload.get('prompt_eval_count')),
            completion_tokens=_integer(payload.get('eval_count')),
            provider_name='ollama-local',
            finish_reason=finish_reason,
            metadata=self._generation_metadata(payload, fingerprint, usable),
        )
