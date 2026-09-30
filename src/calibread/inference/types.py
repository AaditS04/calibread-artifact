'''Typed boundary between the inference runner and model providers.'''

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class InferenceRequest:
    example_id: str
    model: str
    system_prompt: str
    user_prompt: str
    temperature: float
    max_tokens: int
    require_logprobs: bool
    top_logprobs: int
    decoding_seed: int = 0
    num_ctx: int | None = None
    provider_order: tuple[str, ...] = ()
    allow_fallbacks: bool = False
    require_parameters: bool = True
    data_collection: str = 'deny'
    reasoning_effort: str | None = None


@dataclass(frozen=True)
class InferenceResponse:
    text: str
    requested_model: str
    returned_model: str
    request_id: str
    score: float
    score_source: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    provider_name: str = ''
    finish_reason: str = ''
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderFingerprint:
    '''Provider/model identity frozen before a run starts.'''

    requested_model: str
    model_snapshot_id: str
    provider_name: str
    metadata: Mapping[str, object] = field(default_factory=dict)


class ProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
        retry_after: float | None = None,
        stop_invocation: bool = False,
        request_sent: bool = True,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable
        self.retry_after = retry_after
        self.stop_invocation = stop_invocation
        self.request_sent = request_sent
