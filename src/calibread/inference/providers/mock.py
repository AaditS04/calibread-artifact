'''Deterministic offline backend for smoke tests and pipeline development.'''

from __future__ import annotations

import hashlib
import re

from ..types import InferenceRequest, InferenceResponse, ProviderFingerprint


_MOCK_ANSWER = re.compile(r'MOCK_ANSWER=([^?\n]+)')


class MockProvider:
    def preflight(self, model: str) -> ProviderFingerprint:
        return ProviderFingerprint(
            requested_model=model,
            model_snapshot_id=model,
            provider_name='mock',
            metadata={
                'identity_strength': 'deterministic_test_fixture',
                'closed_book': {'network_access': False, 'tools': []},
            },
        )

    def generate(self, request: InferenceRequest) -> InferenceResponse:
        match = _MOCK_ANSWER.search(request.user_prompt)
        answer = match.group(1).strip() if match else 'mock answer'
        request_id = hashlib.sha256(
            f'{request.model}:{request.example_id}'.encode('utf-8')
        ).hexdigest()[:24]
        return InferenceResponse(
            text=answer,
            requested_model=request.model,
            returned_model=request.model,
            request_id=f'mock-{request_id}',
            score=-0.1,
            score_source='mock_mean_generated_token_log_probability',
            prompt_tokens=max(1, len(request.user_prompt.split())),
            completion_tokens=max(1, len(answer.split())),
            provider_name='mock',
            finish_reason='stop',
            metadata={'confidence_usable': True},
        )
