'''OpenRouter Chat Completions adapter using only the Python standard library.'''

from __future__ import annotations

import json
from math import isfinite
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from ..config import ProviderConfig
from ..types import InferenceRequest, InferenceResponse, ProviderError, ProviderFingerprint


class OpenRouterProvider:
    def __init__(
        self,
        config: ProviderConfig,
        *,
        max_http_attempts: int | None = None,
        pinned_provider_order: tuple[str, ...] = (),
        required_parameters: tuple[str, ...] = (),
    ) -> None:
        self.config = config
        self.api_key = os.environ.get(config.api_key_env, '').strip()
        if not self.api_key:
            raise ValueError(f'missing API key environment variable {config.api_key_env}')
        self.max_http_attempts = max_http_attempts
        self.pinned_provider_order = pinned_provider_order
        self.required_parameters = required_parameters
        self.http_attempts = 0
        self._last_http_attempt_started: float | None = None
        self._model_snapshot_id: str | None = None

    @staticmethod
    def _normalized_provider(value: str) -> str:
        return value.strip().casefold()

    @staticmethod
    def _retry_after(value: str | None) -> float | None:
        if value is None:
            return None
        try:
            parsed = float(value)
        except ValueError:
            return None
        return parsed if isfinite(parsed) and parsed >= 0 else None

    def _before_http_attempt(self) -> None:
        if (
            self.max_http_attempts is not None
            and self.http_attempts >= self.max_http_attempts
        ):
            raise ProviderError(
                'OpenRouter per-invocation HTTP-attempt cap reached; resume later '
                'without changing the run',
                stop_invocation=True,
                request_sent=False,
            )
        now = time.monotonic()
        if self._last_http_attempt_started is not None:
            remaining = (
                self.config.minimum_interval_seconds
                - (now - self._last_http_attempt_started)
            )
            if remaining > 0:
                time.sleep(remaining)
                now = time.monotonic()
        self._last_http_attempt_started = now
        self.http_attempts += 1

    def _catalog_fingerprint(self, model: str) -> ProviderFingerprint:
        try:
            author, slug = model.split('/', 1)
        except ValueError as error:
            raise ProviderError('OpenRouter model slug must contain author/model') from error
        request = Request(
            f'{self.config.base_url.rstrip(chr(47))}/models/'
            f'{quote(author, safe=")}/{quote(slug, safe=")}/endpoints',
            headers={'Authorization': f'Bearer {self.api_key}'},
            method='GET',
        )
        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                payload = json.load(response)
        except HTTPError as error:
            body = error.read().decode('utf-8', 'replace')
            raise ProviderError(
                f'OpenRouter endpoint-catalog HTTP {error.code}: {body[:1000]}',
                status_code=error.code,
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            raise ProviderError(f'OpenRouter endpoint-catalog preflight failed: {error}') from error
        data = payload.get('data') if isinstance(payload, dict) else None
        endpoints = data.get('endpoints') if isinstance(data, dict) else None
        if not isinstance(endpoints, list):
            raise ProviderError('OpenRouter endpoint catalog has no endpoint list')
        expected = {
            self._normalized_provider(value) for value in self.pinned_provider_order
        }
        matches: list[dict[str, object]] = []
        for value in endpoints:
            if not isinstance(value, dict):
                continue
            identities = {
                self._normalized_provider(str(value.get('tag') or '')),
                self._normalized_provider(str(value.get('provider_name') or '')),
            }
            if expected & identities:
                matches.append(value)
        if len(matches) != 1:
            raise ProviderError(
                'OpenRouter preflight did not resolve exactly one pinned endpoint'
            )
        endpoint = matches[0]
        parameters = endpoint.get('supported_parameters')
        supported = {
            str(value) for value in parameters
        } if isinstance(parameters, list) else set()
        missing = sorted(set(self.required_parameters) - supported)
        if missing:
            raise ProviderError(
                'pinned OpenRouter endpoint is missing required parameters: '
                + ', '.join(missing)
            )
        pricing = endpoint.get('pricing')
        if not isinstance(pricing, dict):
            raise ProviderError('pinned OpenRouter endpoint has no pricing metadata')
        try:
            prompt_price = float(pricing.get('prompt'))
            completion_price = float(pricing.get('completion'))
        except (TypeError, ValueError) as error:
            raise ProviderError('pinned OpenRouter endpoint has invalid pricing') from error
        if model.casefold().endswith(':free') and (
            prompt_price != 0 or completion_price != 0
        ):
            raise ProviderError('pinned OpenRouter :free endpoint is no longer free')
        endpoint_name = str(endpoint.get('name') or '')
        snapshot_id = (
            endpoint_name.split(' | ', 1)[1].strip()
            if ' | ' in endpoint_name
            else model
        )
        self._model_snapshot_id = snapshot_id
        return ProviderFingerprint(
            requested_model=model,
            model_snapshot_id=snapshot_id,
            provider_name='openrouter',
            metadata={
                'identity_strength': 'provider_catalog_endpoint_plus_response',
                'catalog_model_id': str(data.get('id') or model),
                'catalog_created': data.get('created'),
                'endpoint_name': endpoint_name,
                'endpoint_provider_name': str(endpoint.get('provider_name') or ''),
                'endpoint_tag': str(endpoint.get('tag') or ''),
                'endpoint_quantization': str(endpoint.get('quantization') or ''),
                'endpoint_context_length': endpoint.get('context_length'),
                'endpoint_max_completion_tokens': endpoint.get('max_completion_tokens'),
                'supported_parameters': sorted(supported),
                'required_parameters': list(self.required_parameters),
                'prompt_price_per_token': prompt_price,
                'completion_price_per_token': completion_price,
                'closed_book': {
                    'tools': [],
                    'web_plugin_explicitly_disabled': True,
                },
            },
        )

    def preflight(self, model: str) -> ProviderFingerprint:
        if model.casefold().endswith(':free'):
            return self._catalog_fingerprint(model)
        self._model_snapshot_id = model
        return ProviderFingerprint(
            requested_model=model,
            model_snapshot_id=model,
            provider_name='openrouter',
            metadata={
                'identity_strength': 'provider_reported_per_response',
                'closed_book': {
                    'tools': [],
                    'web_plugin_explicitly_disabled': True,
                },
            },
        )

    def _payload(self, request: InferenceRequest) -> dict[str, object]:
        payload: dict[str, object] = {
            'model': request.model,
            'messages': [
                {'role': 'system', 'content': request.system_prompt},
                {'role': 'user', 'content': request.user_prompt},
            ],
            'temperature': request.temperature,
            'max_tokens': request.max_tokens,
            'seed': request.decoding_seed,
            'stream': False,
            'tools': [],
            'plugins': [{'id': 'web', 'enabled': False}],
            'provider': {
                'allow_fallbacks': request.allow_fallbacks,
                'require_parameters': request.require_parameters,
                'data_collection': request.data_collection,
            },
        }
        if request.provider_order:
            payload['provider']['order'] = list(request.provider_order)  # type: ignore[index]
        if request.require_logprobs:
            payload['logprobs'] = True
            payload['top_logprobs'] = request.top_logprobs
        if request.reasoning_effort is not None:
            payload['reasoning'] = {'effort': request.reasoning_effort}
        return payload

    def _once(self, request: InferenceRequest) -> InferenceResponse:
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'X-Title': self.config.app_title,
        }
        if self.config.http_referer:
            headers['HTTP-Referer'] = self.config.http_referer
        http_request = Request(
            f'{self.config.base_url.rstrip(chr(47))}/chat/completions',
            data=json.dumps(self._payload(request)).encode('utf-8'),
            headers=headers,
            method='POST',
        )
        self._before_http_attempt()
        try:
            with urlopen(http_request, timeout=self.config.timeout_seconds) as response:
                payload = json.load(response)
        except HTTPError as error:
            retry_after = error.headers.get('Retry-After')
            body = error.read().decode('utf-8', 'replace')
            raise ProviderError(
                f'OpenRouter HTTP {error.code}: {body[:1000]}',
                status_code=error.code,
                retryable=error.code in {408, 429, 500, 502, 503, 504},
                retry_after=self._retry_after(retry_after),
                stop_invocation=error.code in {402, 429},
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            raise ProviderError(str(error), retryable=True) from error
        if not isinstance(payload, dict):
            raise ProviderError('OpenRouter returned a non-object response')
        choices = payload.get('choices')
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ProviderError(f'OpenRouter response has no usable choice: {payload}')
        choice = choices[0]
        message = choice.get('message')
        if not isinstance(message, dict) or not isinstance(message.get('content'), str):
            raise ProviderError('OpenRouter choice has no text content')
        if message.get('tool_calls'):
            raise ProviderError('closed-book OpenRouter response unexpectedly used a tool')
        if message.get('annotations'):
            raise ProviderError('closed-book OpenRouter response unexpectedly returned citations')
        token_logprobs: list[float] = []
        logprobs = choice.get('logprobs')
        if isinstance(logprobs, dict) and isinstance(logprobs.get('content'), list):
            for token in logprobs['content']:
                if isinstance(token, dict) and isinstance(token.get('logprob'), (int, float)):
                    value = float(token['logprob'])
                    if isfinite(value):
                        token_logprobs.append(value)
        if request.require_logprobs and not token_logprobs:
            raise ProviderError('selected OpenRouter endpoint did not return required logprobs')
        score = sum(token_logprobs) / len(token_logprobs) if token_logprobs else 0.0
        score_source = (
            'mean_generated_token_log_probability'
            if token_logprobs
            else 'unavailable_constant_zero'
        )
        usage = payload.get('usage') if isinstance(payload.get('usage'), dict) else {}
        server_tool_use = usage.get('server_tool_use')
        if isinstance(server_tool_use, dict) and server_tool_use.get('web_search_requests'):
            raise ProviderError('closed-book OpenRouter response used web search')
        upstream_provider = str(payload.get('provider') or '').strip()
        if request.provider_order:
            expected_providers = {
                self._normalized_provider(value) for value in request.provider_order
            }
            if self._normalized_provider(upstream_provider) not in expected_providers:
                raise ProviderError(
                    'OpenRouter response did not use the pinned upstream provider'
                )
        native_cost = usage.get('cost')
        if request.model.casefold().endswith(':free') and native_cost is not None:
            try:
                normalized_cost = float(native_cost)
            except (TypeError, ValueError) as error:
                raise ProviderError('OpenRouter returned an invalid native cost') from error
            if not isfinite(normalized_cost) or normalized_cost != 0:
                raise ProviderError('OpenRouter :free response reported nonzero native cost')
        raw_returned_model = str(payload.get('model') or request.model)
        return InferenceResponse(
            text=message['content'].strip(),
            requested_model=request.model,
            returned_model=self._model_snapshot_id or raw_returned_model,
            request_id=str(payload.get('id') or ''),
            score=score,
            score_source=score_source,
            prompt_tokens=int(usage.get('prompt_tokens') or 0),
            completion_tokens=int(usage.get('completion_tokens') or 0),
            # ``provider_name`` identifies the adapter/service used by the run.
            # OpenRouter's optional top-level ``provider`` value is the routed
            # upstream host, so preserve it separately instead of making run
            # completeness depend on an unstable or absent response field.
            provider_name='openrouter',
            finish_reason=str(choice.get('finish_reason') or ''),
            metadata={
                'confidence_usable': bool(token_logprobs),
                'native_usage_cost': native_cost,
                'closed_book_tools_sent': [],
                'closed_book_web_plugin_disabled': True,
                'upstream_provider_name': upstream_provider,
                'provider_returned_model': raw_returned_model,
            },
        )

    def generate(self, request: InferenceRequest) -> InferenceResponse:
        for attempt in range(self.config.max_retries + 1):
            try:
                return self._once(request)
            except ProviderError as error:
                if (
                    error.stop_invocation
                    or not error.retryable
                    or attempt >= self.config.max_retries
                ):
                    raise
                delay = error.retry_after if error.retry_after is not None else min(60.0, 2.0**attempt)
                time.sleep(delay)
        raise AssertionError('unreachable retry state')
