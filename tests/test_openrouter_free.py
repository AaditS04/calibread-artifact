'''Offline safety tests for the pinned OpenRouter free-model gate.'''

from __future__ import annotations

from dataclasses import replace
from email.message import Message
from io import BytesIO
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from calibread.inference.config import ProviderConfig, load_inference_config
from calibread.inference.providers.openrouter import OpenRouterProvider
from calibread.inference.types import InferenceRequest, ProviderError


_MODEL = 'google/gemma-4-26b-a4b-it:free'
_SNAPSHOT = 'google/gemma-4-26b-a4b-it-20260403:free'


class _JsonResponse:
    def __init__(self, payload: object) -> None:
        self._stream = BytesIO(json.dumps(payload).encode('utf-8'))
        self.headers: dict[str, str] = {}

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def __enter__(self) -> '_JsonResponse':
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def _provider_config(**overrides: object) -> ProviderConfig:
    values: dict[str, object] = {
        'kind': 'openrouter',
        'base_url': 'https://openrouter.ai/api/v1',
        'api_key_env': 'OPENROUTER_API_KEY',
        'timeout_seconds': 3.0,
        'max_retries': 0,
        'concurrency': 1,
        'http_referer': '',
        'app_title': 'CalibRead test',
        'local_only': False,
        'minimum_interval_seconds': 0.0,
    }
    values.update(overrides)
    return ProviderConfig(**values)  # type: ignore[arg-type]


def _request(**overrides: object) -> InferenceRequest:
    values: dict[str, object] = {
        'example_id': 'fixture-r5-001',
        'model': _MODEL,
        'system_prompt': 'Answer briefly.',
        'user_prompt': 'Question: What is the capital of France?',
        'temperature': 0.0,
        'max_tokens': 16,
        'require_logprobs': True,
        'top_logprobs': 1,
        'decoding_seed': 7,
        'provider_order': ('darkbloom',),
        'allow_fallbacks': False,
        'require_parameters': True,
        'data_collection': 'allow',
        'reasoning_effort': 'none',
    }
    values.update(overrides)
    return InferenceRequest(**values)  # type: ignore[arg-type]


def _completion(*, provider: str = 'Darkbloom', cost: object = 0) -> dict[str, object]:
    return {
        'id': 'gen-fixture',
        'model': _MODEL,
        'provider': provider,
        'choices': [{
            'message': {'role': 'assistant', 'content': 'Paris'},
            'finish_reason': 'stop',
            'logprobs': {'content': [{'token': 'Paris', 'logprob': -0.2}]},
        }],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 1, 'cost': cost},
    }


def _catalog() -> dict[str, object]:
    required = [
        'max_tokens', 'temperature', 'seed', 'tools', 'logprobs',
        'top_logprobs', 'reasoning',
    ]
    return {'data': {
        'id': _MODEL,
        'created': 1775227989,
        'endpoints': [
            {
                'name': f'Darkbloom | {_SNAPSHOT}',
                'provider_name': 'Darkbloom',
                'tag': 'darkbloom',
                'quantization': 'unknown',
                'context_length': 131072,
                'max_completion_tokens': 32768,
                'pricing': {'prompt': '0', 'completion': '0'},
                'supported_parameters': required,
            },
            {
                'name': 'Google AI Studio | ignored',
                'provider_name': 'Google AI Studio',
                'tag': 'google-ai-studio',
                'pricing': {'prompt': '0', 'completion': '0'},
                'supported_parameters': ['max_tokens'],
            },
        ],
    }}


class OpenRouterFreeTests(unittest.TestCase):
    def test_committed_gate_is_truthful_and_rate_safe(self) -> None:
        config = load_inference_config(
            'configs/inference/r5_openrouter_gemma4_26b_free_gate.toml'
        )
        config.validate_for_execution()
        self.assertEqual(config.model.provider_order, ('darkbloom',))
        self.assertEqual(config.model.reasoning_effort, 'none')
        self.assertEqual(config.provider.minimum_interval_seconds, 3.1)
        self.assertEqual(config.budget.max_requests, 40)

        random_router = replace(
            config, datasets=(),
            model=replace(config.model, requested_model='openrouter/free'),
        )
        with self.assertRaisesRegex(ValueError, 'concrete non-moving'):
            random_router.validate_for_execution()
        unpinned = replace(
            config, datasets=(), model=replace(config.model, provider_order=()),
        )
        with self.assertRaisesRegex(ValueError, 'pinned provider'):
            unpinned.validate_for_execution()
        unsafe_cap = replace(
            config, datasets=(), budget=replace(config.budget, max_requests=41),
        )
        with self.assertRaisesRegex(ValueError, '40'):
            unsafe_cap.validate_for_execution()
        fake_price = replace(
            config, datasets=(),
            budget=replace(config.budget, prompt_usd_per_million=0.01),
        )
        with self.assertRaisesRegex(ValueError, 'zero frozen'):
            fake_price.validate_for_execution()

    def test_preflight_freezes_pinned_catalog_endpoint(self) -> None:
        required = tuple(_catalog()['data']['endpoints'][0]['supported_parameters'])
        with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'fixture-secret'}):
            provider = OpenRouterProvider(
                _provider_config(), max_http_attempts=40,
                pinned_provider_order=('darkbloom',),
                required_parameters=required,
            )
        with patch(
            'calibread.inference.providers.openrouter.urlopen',
            return_value=_JsonResponse(_catalog()),
        ):
            fingerprint = provider.preflight(_MODEL)
        self.assertEqual(fingerprint.model_snapshot_id, _SNAPSHOT)
        self.assertEqual(fingerprint.metadata['endpoint_tag'], 'darkbloom')
        self.assertEqual(fingerprint.metadata['prompt_price_per_token'], 0.0)
        self.assertIn('logprobs', fingerprint.metadata['supported_parameters'])
        self.assertEqual(provider.http_attempts, 0)

    def test_payload_freezes_seed_reasoning_and_closed_book_controls(self) -> None:
        with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'fixture-secret'}):
            provider = OpenRouterProvider(_provider_config())
        payload = provider._payload(_request())
        self.assertEqual(payload['seed'], 7)
        self.assertEqual(payload['reasoning'], {'effort': 'none'})
        self.assertEqual(payload['tools'], [])
        self.assertEqual(payload['plugins'], [{'id': 'web', 'enabled': False}])
        self.assertEqual(payload['provider']['order'], ['darkbloom'])

    def test_http_cap_stops_before_an_extra_call(self) -> None:
        with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'fixture-secret'}):
            provider = OpenRouterProvider(
                _provider_config(), max_http_attempts=1,
                pinned_provider_order=('darkbloom',),
            )
        with patch(
            'calibread.inference.providers.openrouter.urlopen',
            return_value=_JsonResponse(_completion()),
        ) as mocked:
            provider.generate(_request())
            with self.assertRaisesRegex(ProviderError, 'attempt cap') as raised:
                provider.generate(_request(example_id='fixture-r5-002'))
        self.assertEqual(provider.http_attempts, 1)
        self.assertEqual(mocked.call_count, 1)
        self.assertTrue(raised.exception.stop_invocation)
        self.assertFalse(raised.exception.request_sent)

    def test_429_stops_without_retrying(self) -> None:
        headers = Message()
        headers['Retry-After'] = '60.5'
        error = HTTPError('x', 429, 'limited', headers, BytesIO(b'{}'))
        with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'fixture-secret'}):
            provider = OpenRouterProvider(
                _provider_config(max_retries=3), max_http_attempts=40,
            )
        with patch(
            'calibread.inference.providers.openrouter.urlopen', side_effect=error,
        ) as mocked:
            with self.assertRaises(ProviderError) as raised:
                provider.generate(_request())
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(provider.http_attempts, 1)
        self.assertTrue(raised.exception.stop_invocation)
        self.assertEqual(raised.exception.retry_after, 60.5)

    def test_free_response_rejects_route_or_cost_drift(self) -> None:
        cases = (
            (_completion(provider='Google AI Studio'), 'pinned upstream'),
            (_completion(cost=0.01), 'nonzero native cost'),
        )
        for response, pattern in cases:
            with self.subTest(pattern=pattern):
                with patch.dict(
                    'os.environ', {'OPENROUTER_API_KEY': 'fixture-secret'}
                ):
                    provider = OpenRouterProvider(
                        _provider_config(), max_http_attempts=1,
                    )
                with patch(
                    'calibread.inference.providers.openrouter.urlopen',
                    return_value=_JsonResponse(response),
                ):
                    with self.assertRaisesRegex(ProviderError, pattern):
                        provider.generate(_request())

    def test_minimum_interval_applies_to_every_attempt(self) -> None:
        with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'fixture-secret'}):
            provider = OpenRouterProvider(
                _provider_config(minimum_interval_seconds=3.1),
                max_http_attempts=3,
            )
        with (
            patch(
                'calibread.inference.providers.openrouter.time.monotonic',
                side_effect=[0.0, 1.0, 3.1],
            ),
            patch('calibread.inference.providers.openrouter.time.sleep') as sleep,
        ):
            provider._before_http_attempt()
            provider._before_http_attempt()
        sleep.assert_called_once_with(2.1)
        self.assertEqual(provider.http_attempts, 2)


if __name__ == '__main__':
    unittest.main()
