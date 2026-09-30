from __future__ import annotations

from typing import Protocol

from ..types import InferenceRequest, InferenceResponse, ProviderFingerprint


class InferenceProvider(Protocol):
    def preflight(self, model: str) -> ProviderFingerprint:
        ...

    def generate(self, request: InferenceRequest) -> InferenceResponse:
        ...
