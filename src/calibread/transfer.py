"""R6 within-domain versus cross-domain calibration transfer diagnostics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence

from .metrics import brier_score, expected_calibration_error


@dataclass(frozen=True)
class DomainTransferReport:
    source_count: int
    target_count: int
    source_accuracy: float
    target_accuracy: float
    source_ece: float
    target_ece: float
    ece_increase: float
    source_brier: float
    target_brier: float
    brier_increase: float

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)


@dataclass(frozen=True)
class CalibrationTransferComparison:
    """Baseline-relative calibration gains within and across domains."""

    within_count: int
    cross_count: int
    within_baseline_ece: float
    within_calibrated_ece: float
    within_ece_improvement: float
    cross_baseline_ece: float
    cross_calibrated_ece: float
    cross_ece_improvement: float
    ece_transfer_advantage: float
    within_baseline_brier: float
    within_calibrated_brier: float
    within_brier_improvement: float
    cross_baseline_brier: float
    cross_calibrated_brier: float
    cross_brier_improvement: float
    brier_transfer_advantage: float

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)


def domain_transfer_report(
    source_confidences: Sequence[float],
    source_correctness: Sequence[bool | int],
    target_confidences: Sequence[float],
    target_correctness: Sequence[bool | int],
    *,
    n_bins: int = 10,
) -> DomainTransferReport:
    """Compare a frozen score/calibrator on its source and target domain outputs."""

    if len(source_confidences) != len(source_correctness) or not source_confidences:
        raise ValueError("source confidences/correctness must be nonempty and aligned")
    if len(target_confidences) != len(target_correctness) or not target_confidences:
        raise ValueError("target confidences/correctness must be nonempty and aligned")
    source_accuracy = sum(int(value) for value in source_correctness) / len(
        source_correctness
    )
    target_accuracy = sum(int(value) for value in target_correctness) / len(
        target_correctness
    )
    source_ece = expected_calibration_error(
        source_confidences, source_correctness, n_bins=n_bins
    )
    target_ece = expected_calibration_error(
        target_confidences, target_correctness, n_bins=n_bins
    )
    source_brier = brier_score(source_confidences, source_correctness)
    target_brier = brier_score(target_confidences, target_correctness)
    return DomainTransferReport(
        source_count=len(source_confidences),
        target_count=len(target_confidences),
        source_accuracy=source_accuracy,
        target_accuracy=target_accuracy,
        source_ece=source_ece,
        target_ece=target_ece,
        ece_increase=target_ece - source_ece,
        source_brier=source_brier,
        target_brier=target_brier,
        brier_increase=target_brier - source_brier,
    )


def calibration_transfer_comparison(
    within_baseline_confidences: Sequence[float],
    within_calibrated_confidences: Sequence[float],
    within_correctness: Sequence[bool | int],
    cross_baseline_confidences: Sequence[float],
    cross_calibrated_confidences: Sequence[float],
    cross_correctness: Sequence[bool | int],
    *,
    n_bins: int = 10,
) -> CalibrationTransferComparison:
    """Compare a domain calibrator with the same baseline on two held-out panels.

    The within-domain and cross-domain examples may differ, so this function never compares their
    raw ECE or Brier values as if difficulty were equal.  It first measures the calibrator's gain
    over an explicitly supplied baseline on each panel, then reports the difference between those
    gains.  Positive transfer-advantage values mean the calibrator helped more within domain.
    """

    panels = (
        (
            "within",
            within_baseline_confidences,
            within_calibrated_confidences,
            within_correctness,
        ),
        (
            "cross",
            cross_baseline_confidences,
            cross_calibrated_confidences,
            cross_correctness,
        ),
    )
    values: dict[str, float | int] = {}
    for name, baseline, calibrated, correctness in panels:
        if not correctness or len(baseline) != len(correctness) or len(calibrated) != len(correctness):
            raise ValueError(
                f"{name} baseline/calibrated confidences and correctness must be nonempty and aligned"
            )
        baseline_ece = expected_calibration_error(baseline, correctness, n_bins=n_bins)
        calibrated_ece = expected_calibration_error(calibrated, correctness, n_bins=n_bins)
        baseline_brier = brier_score(baseline, correctness)
        calibrated_brier = brier_score(calibrated, correctness)
        values[f"{name}_count"] = len(correctness)
        values[f"{name}_baseline_ece"] = baseline_ece
        values[f"{name}_calibrated_ece"] = calibrated_ece
        values[f"{name}_ece_improvement"] = baseline_ece - calibrated_ece
        values[f"{name}_baseline_brier"] = baseline_brier
        values[f"{name}_calibrated_brier"] = calibrated_brier
        values[f"{name}_brier_improvement"] = baseline_brier - calibrated_brier

    values["ece_transfer_advantage"] = (
        float(values["within_ece_improvement"])
        - float(values["cross_ece_improvement"])
    )
    values["brier_transfer_advantage"] = (
        float(values["within_brier_improvement"])
        - float(values["cross_brier_improvement"])
    )
    return CalibrationTransferComparison(**values)  # type: ignore[arg-type]
