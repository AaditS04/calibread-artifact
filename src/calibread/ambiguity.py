"""R4 validity and semantic-idempotency diagnostics over interpretation labels."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Hashable, Iterable, Sequence


@dataclass(frozen=True)
class AmbiguityReport:
    response_count: int
    valid_response_rate: float
    unique_response_classes: int
    pairwise_idempotency: float | None

    def to_dict(self) -> dict[str, int | float | None]:
        return asdict(self)


def ambiguity_report(
    response_classes: Sequence[Hashable],
    valid_interpretation_classes: Iterable[Hashable],
) -> AmbiguityReport:
    """Evaluate repeated/paraphrased answers against audited interpretation classes."""

    if not response_classes:
        raise ValueError("response_classes must not be empty")
    valid = set(valid_interpretation_classes)
    if not valid:
        raise ValueError("valid_interpretation_classes must not be empty")
    counts = Counter(response_classes)
    total = len(response_classes)
    pair_count = total * (total - 1) // 2
    agreeing_pairs = sum(count * (count - 1) // 2 for count in counts.values())
    return AmbiguityReport(
        response_count=total,
        valid_response_rate=sum(value in valid for value in response_classes) / total,
        unique_response_classes=len(counts),
        pairwise_idempotency=(
            None if pair_count == 0 else agreeing_pairs / pair_count
        ),
    )
