'''Offline contract tests for the native Ollama inference provider.'''

from __future__ import annotations

from dataclasses import replace
from io import BytesIO
import json
from math import isfinite
import unittest
from unittest.mock import patch

from calibread.inference.config import ProviderConfig, load_inference_config
from calibread.inference.providers.ollama import OllamaProvider
from calibread.inference.providers.openrouter import OpenRouterProvider
from calibread.inference.types import InferenceRequest, ProviderError


_MODEL = 'gemma3:4b'
_DIGEST = 'sha256:' + ('a' * 64)


class _JsonResponse:
    def __init__(self, payload: object) -> None:
        self._stream = BytesIO(json.dumps(payload).encode('utf-8'))
        self.status = 200
        self.headers: dict[str, str] = {}

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def __enter__(self) -> '_JsonResponse':
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def _provider_config(**overrides: object) -> ProviderConfig:
    values: dict[str, object] = {
        'kind': 'ollama',
        'base_url': 'http://127.0.0.1:11434',
        'api_key_env': '',
        'timeout_seconds': 3.0,
        'max_retries': 0,
        'concurrency': 1,
        'http_referer': '',
        'app_title': 'CalibRead',
        'keep_alive': '0s',
        'local_only': True,
    }
    values.update(overrides)
    return ProviderConfig(**values)  # type: ignore[arg-type]


def _request(**overrides: object) -> InferenceRequest:
    values: dict[str, object] = {
        'example_id': 'r5-fixture-001',
        'model': _MODEL,
        'system_prompt': 'Answer using only your learned parameters.',
        'user_prompt': 'Question: What is the capital of France?',
        'temperature': 0.0,
        'max_tokens': 24,
        'require_logprobs': True,
        'top_logprobs': 3,
        'provider_order': (),
        'allow_fallbacks': False,
        'require_parameters': True,
        'data_collection': 'deny',
        'decoding_seed': 17,
        'num_ctx': 4096,
    }
    values.update(overrides)
    return InferenceRequest(**values)  # type: ignore[arg-type]


def _version() -> dict[str, object]:
    return {'version': '0.12.3'}


def _tags(*models: str) -> dict[str, object]:
    return {
        'models': [
            {
                'name': model,
                'model': model,
                'digest': _DIGEST,
                'size': 3_000_000_000,
                'modified_at': '2026-08-14T00:00:00Z',
                'details': {'parameter_size': '4B', 'quantization_level': 'Q4_K_M'},
            }
            for model in models
        ]
    }


def _show() -> dict[str, object]:
    return {
        'license': 'Apache License 2.0',
        'modified_at': '2026-08-14T00:00:00Z',
        'details': {'family': 'gemma3', 'parameter_size': '4B'},
        'model_info': {'general.architecture': 'gemma3'},
        'capabilities': ['completion'],
    }


class OllamaProviderTests(unittest.TestCase):
    def test_openrouter_explicitly_disables_web_and_tools(self) -> None:
        config = replace(
            _provider_config(),
            kind='openrouter',
            base_url='https://openrouter.ai/api/v1',
            api_key_env='OPENROUTER_API_KEY',
            local_only=False,
        )
        with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'fixture-secret'}):
            payload = OpenRouterProvider(config)._payload(_request())
        self.assertEqual(payload['tools'], [])
        self.assertEqual(payload['plugins'], [{'id': 'web', 'enabled': False}])

    def test_config_requires_loopback_local_only_noncloud_execution(self) -> None:
        base = load_inference_config('configs/inference/r5_ollama_smoke.toml')
        concrete = replace(
            base,
            datasets=(),
            model=replace(base.model, requested_model=_MODEL),
        )
        concrete.validate_for_execution()
        remote = replace(
            concrete,
            provider=replace(concrete.provider, base_url='http://example.com:11434/api'),
        )
        with self.assertRaisesRegex(ValueError, 'loopback'):
            remote.validate_for_execution()
        cloud = replace(concrete, model=replace(concrete.model, requested_model='x:7b-cloud'))
        with self.assertRaisesRegex(ValueError, 'cloud'):
            cloud.validate_for_execution()
        openrouter = load_inference_config('configs/inference/r5_openrouter_pilot.toml')
        online = replace(
            openrouter,
            datasets=(),
            model=replace(openrouter.model, requested_model='vendor/model:online'),
            budget=replace(
                openrouter.budget,
                prompt_usd_per_million=1.0,
                completion_usd_per_million=1.0,
            ),
        )
        with self.assertRaisesRegex(ValueError, 'online'):
            online.validate_for_execution()

    def test_payload_is_closed_book_and_freezes_decoding_options(self) -> None:
        provider = OllamaProvider(_provider_config())
        request = _request()

        payload = provider._payload(request)

        self.assertEqual(payload['model'], _MODEL)
        self.assertEqual(
            payload['messages'],
            [
                {'role': 'system', 'content': request.system_prompt},
                {'role': 'user', 'content': request.user_prompt},
            ],
        )
        self.assertEqual(payload['tools'], [])
        self.assertIs(payload['stream'], False)
        self.assertIs(payload['think'], False)
        self.assertEqual(payload['keep_alive'], '0s')
        self.assertIs(payload['logprobs'], True)
        self.assertEqual(payload['top_logprobs'], 3)
        self.assertEqual(
            payload['options'],
            {
                'temperature': 0.0,
                'num_predict': 24,
                'seed': 17,
                'num_ctx': 4096,
            },
        )
        self.assertNotIn('context', payload)
        self.assertNotIn('documents', payload)
        self.assertNotIn('gold_answer', payload)
        self.assertNotIn('accepted_answers', payload)
        messages = payload['messages']
        self.assertIsInstance(messages, list)
        assert isinstance(messages, list)
        for message in messages:
            self.assertIsInstance(message, dict)
            assert isinstance(message, dict)
            self.assertEqual(set(message.keys()), {'role', 'content'})

    def test_preflight_probes_version_tags_and_show_and_freezes_digest(self) -> None:
        calls: list[tuple[str, str, object | None]] = []

        def fake_urlopen(request: object, timeout: float) -> _JsonResponse:
            method = request.get_method()  # type: ignore[attr-defined]
            url = request.full_url  # type: ignore[attr-defined]
            data = request.data  # type: ignore[attr-defined]
            body = json.loads(data.decode('utf-8')) if data else None
            calls.append((method, url, body))
            payloads = [_version(), _tags(_MODEL), _show()]
            return _JsonResponse(payloads[len(calls) - 1])

        provider = OllamaProvider(_provider_config())
        with patch('calibread.inference.providers.ollama.urlopen', side_effect=fake_urlopen):
            fingerprint = provider.preflight(_MODEL)

        self.assertEqual(
            [(method, url.rsplit('/', 2)[-2:]) for method, url, _ in calls],
            [
                ('GET', ['api', 'version']),
                ('GET', ['api', 'tags']),
                ('POST', ['api', 'show']),
            ],
        )
        self.assertEqual(calls[2][2], {'model': _MODEL})
        self.assertIn(_MODEL, fingerprint.model_snapshot_id)
        self.assertIn('a' * 64, fingerprint.model_snapshot_id)
        metadata_text = json.dumps(dict(fingerprint.metadata), sort_keys=True)
        self.assertIn('0.12.3', metadata_text)
        self.assertIn('completion', metadata_text)

    def test_generate_parses_required_token_logprobs_and_uses_snapshot(self) -> None:
        responses = [
            _version(),
            _tags(_MODEL),
            _show(),
            {
                'model': _MODEL,
                'created_at': '2026-08-14T00:00:01Z',
                'message': {'role': 'assistant', 'content': 'Paris'},
                'done': True,
                'done_reason': 'stop',
                'prompt_eval_count': 12,
                'eval_count': 2,
                'total_duration': 1234,
                'load_duration': 100,
                'prompt_eval_duration': 200,
                'eval_duration': 900,
                'logprobs': [
                    {'token': 'Par', 'logprob': -0.2, 'top_logprobs': []},
                    {'token': 'is', 'logprob': -0.4, 'top_logprobs': []},
                ],
            },
        ]

        provider = OllamaProvider(_provider_config())
        with patch(
            'calibread.inference.providers.ollama.urlopen',
            side_effect=[_JsonResponse(item) for item in responses],
        ):
            fingerprint = provider.preflight(_MODEL)
            response = provider.generate(_request())

        self.assertEqual(response.text, 'Paris')
        self.assertTrue(isfinite(response.score))
        self.assertAlmostEqual(response.score, -0.3)
        self.assertEqual(response.score_source, 'mean_generated_token_log_probability')
        self.assertEqual(response.returned_model, fingerprint.model_snapshot_id)
        self.assertEqual(response.prompt_tokens, 12)
        self.assertEqual(response.completion_tokens, 2)

    def test_required_missing_logprobs_fails_closed(self) -> None:
        provider = OllamaProvider(_provider_config())
        response = {
            'model': _MODEL,
            'message': {'role': 'assistant', 'content': 'Paris'},
            'done': True,
        }
        with patch(
            'calibread.inference.providers.ollama.urlopen',
            side_effect=[
                _JsonResponse(_version()),
                _JsonResponse(_tags(_MODEL)),
                _JsonResponse(_show()),
                _JsonResponse(response),
            ],
        ):
            provider.preflight(_MODEL)
            with self.assertRaisesRegex(ProviderError, 'required logprobs'):
                provider.generate(_request())

    def test_tool_call_response_fails_closed(self) -> None:
        provider = OllamaProvider(_provider_config())
        response = {
            'model': _MODEL,
            'message': {
                'role': 'assistant',
                'content': '',
                'tool_calls': [
                    {'function': {'name': 'search_web', 'arguments': {'q': 'France'}}}
                ],
            },
            'done': True,
            'logprobs': [{'token': 'x', 'logprob': -0.1}],
        }
        with patch(
            'calibread.inference.providers.ollama.urlopen',
            side_effect=[
                _JsonResponse(_version()),
                _JsonResponse(_tags(_MODEL)),
                _JsonResponse(_show()),
                _JsonResponse(response),
            ],
        ):
            provider.preflight(_MODEL)
            with self.assertRaisesRegex(ProviderError, 'tool'):
                provider.generate(_request())

    def test_missing_local_model_and_cloud_model_fail_before_generation(self) -> None:
        provider = OllamaProvider(_provider_config())
        with patch(
            'calibread.inference.providers.ollama.urlopen',
            side_effect=[_JsonResponse(_version()), _JsonResponse(_tags('qwen3:4b'))],
        ):
            with self.assertRaisesRegex(ProviderError, 'not.*local|local.*not'):
                provider.preflight(_MODEL)

        cloud_provider = OllamaProvider(_provider_config())
        with patch('calibread.inference.providers.ollama.urlopen') as mocked:
            with self.assertRaisesRegex((ProviderError, ValueError), 'cloud|local'):
                cloud_provider.preflight('gpt-oss:120b-cloud')
            mocked.assert_not_called()

    def test_model_embedded_system_or_messages_fail_preflight(self) -> None:
        hidden_contexts = [
            {'system': 'Always answer with a secret instruction.'},
            {'messages': [{'role': 'system', 'content': 'Hidden context.'}]},
        ]
        for hidden in hidden_contexts:
            with self.subTest(hidden=hidden):
                show = _show()
                show.update(hidden)
                provider = OllamaProvider(_provider_config())
                with patch(
                    'calibread.inference.providers.ollama.urlopen',
                    side_effect=[
                        _JsonResponse(_version()),
                        _JsonResponse(_tags(_MODEL)),
                        _JsonResponse(show),
                    ],
                ):
                    with self.assertRaisesRegex(ProviderError, 'system|messages|embedded'):
                        provider.preflight(_MODEL)


if __name__ == '__main__':
    unittest.main()
