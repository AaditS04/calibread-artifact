"""Calibration and selective-prediction metrics used by CalibRead.

All functions are dependency-free so that cached experiment outputs can be audited on any machine.
Confidence is interpreted as an estimated probability that the emitted answer is correct.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from math import ceil, isfinite, log
from random import Random
from statistics import median
from typing import Hashable, Iterable, Sequence


def _as_float_list(values: Iterable[float], name: str) -> list[float]:
    result = [float(value) for value in values]
    if not result:
        raise ValueError(f"{name} must not be empty")
    if not all(isfinite(value) for value in result):
        raise ValueError(f"{name} must contain only finite values")
    return result


def _as_binary_list(values: Iterable[bool | int], name: str) -> list[int]:
    result: list[int] = []
    for value in values:
        if value in (True, 1):
            result.append(1)
        elif value in (False, 0):
            result.append(0)
        else:
            raise ValueError(f"{name} must contain only booleans or 0/1 values")
    if not result:
        raise ValueError(f"{name} must not be empty")
    return result


def _validated_pairs(
    confidences: Iterable[float], correctness: Iterable[bool | int]
) -> tuple[list[float], list[int]]:
    confidence_values = _as_float_list(confidences, "confidences")
    correct_values = _as_binary_list(correctness, "correctness")
    if len(confidence_values) != len(correct_values):
        raise ValueError("confidences and correctness must have the same length")
    if any(value < 0.0 or value > 1.0 for value in confidence_values):
        raise ValueError("confidences must lie in [0, 1]")
    return confidence_values, correct_values


@dataclass(frozen=True)
class ReliabilityBin:
    lower: float
    upper: float
    count: int
    mean_confidence: float
    accuracy: float
    absolute_gap: float


@dataclass(frozen=True)
class RiskCoveragePoint:
    threshold: float
    coverage: float
    risk: float
    accepted: int


@dataclass(frozen=True)
class SelectiveReport:
    threshold: float
    total: int
    accepted: int
    coverage: float
    risk: float | None
    accuracy: float | None


@dataclass(frozen=True)
class PairedAURCComparison:
    '''Empirical paired AURC comparison on a fixed evaluated workload.'''

    method_a_aurc: float
    method_b_aurc: float
    difference: float
    interval_lower: float
    interval_upper: float
    confidence: float
    n_resamples: int


def brier_score(confidences: Iterable[float], correctness: Iterable[bool | int]) -> float:
    """Return the mean squared error of correctness probabilities."""

    confidence_values, correct_values = _validated_pairs(confidences, correctness)
    squared_errors = [
        (confidence - correct) ** 2
        for confidence, correct in zip(confidence_values, correct_values)
    ]
    return sum(squared_errors) / len(squared_errors)


def reliability_bins(
    confidences: Iterable[float], correctness: Iterable[bool | int], n_bins: int = 10
) -> list[ReliabilityBin]:
    """Return non-empty fixed-width reliability bins.

    Bins are [i/B, (i+1)/B), except that confidence 1.0 belongs to the final bin.
    """

    if n_bins < 1:
        raise ValueError("n_bins must be at least 1")
    confidence_values, correct_values = _validated_pairs(confidences, correctness)
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for confidence, correct in zip(confidence_values, correct_values):
        index = min(int(confidence * n_bins), n_bins - 1)
        buckets[index].append((confidence, correct))

    result: list[ReliabilityBin] = []
    for index, bucket in enumerate(buckets):
        if not bucket:
            continue
        count = len(bucket)
        mean_confidence = sum(item[0] for item in bucket) / count
        accuracy = sum(item[1] for item in bucket) / count
        result.append(
            ReliabilityBin(
                lower=index / n_bins,
                upper=(index + 1) / n_bins,
                count=count,
                mean_confidence=mean_confidence,
                accuracy=accuracy,
                absolute_gap=abs(mean_confidence - accuracy),
            )
        )
    return result


def expected_calibration_error(
    confidences: Iterable[float], correctness: Iterable[bool | int], n_bins: int = 10
) -> float:
    """Return fixed-width expected calibration error (ECE).

    ECE is a descriptive, bin-dependent metric and should not be used as the sole reliability result.
    """

    confidence_values, correct_values = _validated_pairs(confidences, correctness)
    bins = reliability_bins(confidence_values, correct_values, n_bins=n_bins)
    total = len(confidence_values)
    return sum((item.count / total) * item.absolute_gap for item in bins)


def adaptive_calibration_error(
    confidences: Iterable[float], correctness: Iterable[bool | int], n_bins: int = 10
) -> float:
    """Return equal-count-bin calibration error."""

    if n_bins < 1:
        raise ValueError("n_bins must be at least 1")
    confidence_values, correct_values = _validated_pairs(confidences, correctness)
    pairs = sorted(zip(confidence_values, correct_values))
    bin_count = min(n_bins, len(pairs))
    result = 0.0
    for index in range(bin_count):
        start = index * len(pairs) // bin_count
        end = (index + 1) * len(pairs) // bin_count
        bucket = pairs[start:end]
        mean_confidence = sum(x for x, _ in bucket) / len(bucket)
        accuracy = sum(y for _, y in bucket) / len(bucket)
        result += len(bucket) / len(pairs) * abs(mean_confidence - accuracy)
    return result


def binary_log_loss(
    confidences: Iterable[float],
    correctness: Iterable[bool | int],
    *,
    epsilon: float = 1e-15,
) -> float:
    """Return binary cross-entropy for answer-correctness probabilities."""

    if not 0.0 < epsilon < 0.5:
        raise ValueError("epsilon must lie strictly between 0 and 0.5")
    confidence_values, correct_values = _validated_pairs(confidences, correctness)
    losses = []
    for confidence, correct in zip(confidence_values, correct_values):
        probability = min(max(confidence, epsilon), 1.0 - epsilon)
        losses.append(
            -(correct * log(probability) + (1 - correct) * log(1.0 - probability))
        )
    return sum(losses) / len(losses)


def correctness_auroc(
    confidences: Iterable[float], correctness: Iterable[bool | int]
) -> float:
    """Return tie-aware AUROC for ranking correct answers above errors."""

    confidence_values, correct_values = _validated_pairs(confidences, correctness)
    positives = sum(correct_values)
    negatives = len(correct_values) - positives
    if positives == 0 or negatives == 0:
        raise ValueError("AUROC requires at least one correct and one incorrect example")
    ranked = sorted(zip(confidence_values, correct_values))
    positive_rank_sum = 0.0
    start = 0
    while start < len(ranked):
        end = start + 1
        while end < len(ranked) and ranked[end][0] == ranked[start][0]:
            end += 1
        average_rank = (start + 1 + end) / 2.0
        positive_rank_sum += average_rank * sum(label for _, label in ranked[start:end])
        start = end
    return (positive_rank_sum - positives * (positives + 1) / 2.0) / (
        positives * negatives
    )


def candidate_oracle_recall(
    candidate_sets: Sequence[Iterable[Hashable]],
    true_labels: Sequence[Hashable],
) -> float:
    """Return how often the correct label is available to a candidate generator."""

    if len(candidate_sets) != len(true_labels):
        raise ValueError("candidate_sets and true_labels must have the same length")
    if not candidate_sets:
        raise ValueError("candidate_sets must not be empty")
    return sum(
        int(label in set(candidates))
        for candidates, label in zip(candidate_sets, true_labels)
    ) / len(true_labels)


def prediction_set_efficiency(
    prediction_sets: Sequence[Iterable[Hashable]],
) -> dict[str, float]:
    """Summarize prediction-set sizes; smaller nonempty sets are more efficient."""

    if not prediction_sets:
        raise ValueError("prediction_sets must not be empty")
    sizes = [len(set(prediction_set)) for prediction_set in prediction_sets]
    ordered_sizes = sorted(sizes)
    p90_size = ordered_sizes[ceil(0.90 * len(ordered_sizes)) - 1]
    return {
        'median_size': float(median(sizes)),
        'p90_size': float(p90_size),
        "mean_size": sum(sizes) / len(sizes),
        "singleton_rate": sum(size == 1 for size in sizes) / len(sizes),
        "empty_rate": sum(size == 0 for size in sizes) / len(sizes),
    }


def selective_report(
    confidences: Iterable[float],
    correctness: Iterable[bool | int],
    threshold: float,
) -> SelectiveReport:
    """Report error among answers whose confidence is at least ``threshold``."""

    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must lie in [0, 1]")
    confidence_values, correct_values = _validated_pairs(confidences, correctness)
    accepted_correct = [
        correct
        for confidence, correct in zip(confidence_values, correct_values)
        if confidence >= threshold
    ]
    accepted = len(accepted_correct)
    total = len(confidence_values)
    if accepted == 0:
        risk = None
        accuracy = None
    else:
        accuracy = sum(accepted_correct) / accepted
        risk = 1.0 - accuracy
    return SelectiveReport(
        threshold=float(threshold),
        total=total,
        accepted=accepted,
        coverage=accepted / total,
        risk=risk,
        accuracy=accuracy,
    )


def risk_coverage_curve(
    confidences: Iterable[float], correctness: Iterable[bool | int]
) -> list[RiskCoveragePoint]:
    """Return threshold-level risk/coverage points.

    Equal-confidence examples enter together, so the curve never depends on arbitrary tie ordering.
    Risk is the error rate among all answers accepted at or above the reported threshold.
    """

    confidence_values, correct_values = _validated_pairs(confidences, correctness)
    by_confidence: dict[float, list[int]] = defaultdict(list)
    for confidence, correct in zip(confidence_values, correct_values):
        by_confidence[confidence].append(correct)

    total = len(confidence_values)
    accepted = 0
    errors = 0
    points: list[RiskCoveragePoint] = []
    for threshold in sorted(by_confidence, reverse=True):
        bucket = by_confidence[threshold]
        accepted += len(bucket)
        errors += sum(1 - correct for correct in bucket)
        points.append(
            RiskCoveragePoint(
                threshold=threshold,
                coverage=accepted / total,
                risk=errors / accepted,
                accepted=accepted,
            )
        )
    return points


def area_under_risk_coverage_curve(points: Sequence[RiskCoveragePoint]) -> float:
    """Integrate the right-continuous threshold curve as a step function."""

    if not points:
        raise ValueError("points must not be empty")
    previous_coverage = 0.0
    area = 0.0
    for point in points:
        if point.coverage < previous_coverage:
            raise ValueError("points must be ordered by non-decreasing coverage")
        width = point.coverage - previous_coverage
        area += width * point.risk
        previous_coverage = point.coverage
    if abs(previous_coverage - 1.0) > 1e-12:
        raise ValueError("the final risk-coverage point must have coverage 1")
    return area


def paired_aurc_comparison(
    confidences_a: Sequence[float],
    confidences_b: Sequence[float],
    correctness: Sequence[bool | int],
    *,
    clusters: Sequence[Hashable] | None = None,
    confidence: float = 0.95,
    n_resamples: int = 2000,
    seed: int = 0,
) -> PairedAURCComparison:
    '''Compare two fixed-grid policies with a paired cluster bootstrap.

    Difference is AURC(A)-AURC(B); lower is better. This is empirical
    comparison on the supplied workload, not global Pareto optimality.
    '''

    a_values, labels = _validated_pairs(confidences_a, correctness)
    b_values, b_labels = _validated_pairs(confidences_b, correctness)
    if len(a_values) != len(b_values) or labels != b_labels:
        raise ValueError('paired policy inputs must be aligned')
    if not 0.0 < confidence < 1.0:
        raise ValueError('confidence must lie strictly between 0 and 1')
    if n_resamples < 2:
        raise ValueError('n_resamples must be at least 2')
    cluster_values: Sequence[Hashable] = (
        list(range(len(labels))) if clusters is None else clusters
    )
    if len(cluster_values) != len(labels):
        raise ValueError('clusters must align with policy inputs')
    members: dict[Hashable, list[int]] = defaultdict(list)
    for index, cluster in enumerate(cluster_values):
        try:
            hash(cluster)
        except TypeError as error:
            raise ValueError('cluster identifiers must be hashable') from error
        members[cluster].append(index)

    def aurc(values: Sequence[float], indices: Sequence[int]) -> float:
        curve = risk_coverage_curve(
            [values[index] for index in indices],
            [labels[index] for index in indices],
        )
        return area_under_risk_coverage_curve(curve)

    all_indices = list(range(len(labels)))
    aurc_a = aurc(a_values, all_indices)
    aurc_b = aurc(b_values, all_indices)
    random = Random(seed)
    cluster_ids = list(members)
    differences: list[float] = []
    for _ in range(n_resamples):
        sampled_indices: list[int] = []
        for _ in cluster_ids:
            sampled_indices.extend(members[random.choice(cluster_ids)])
        differences.append(
            aurc(a_values, sampled_indices) - aurc(b_values, sampled_indices)
        )
    differences.sort()
    tail = (1.0 - confidence) / 2.0
    lower_index = max(0, int(tail * n_resamples))
    upper_index = min(n_resamples - 1, int((1.0 - tail) * n_resamples) - 1)
    return PairedAURCComparison(
        method_a_aurc=aurc_a,
        method_b_aurc=aurc_b,
        difference=aurc_a - aurc_b,
        interval_lower=differences[lower_index],
        interval_upper=differences[upper_index],
        confidence=confidence,
        n_resamples=n_resamples,
    )


def group_reliability_report(
    confidences: Sequence[float],
    correctness: Sequence[bool | int],
    groups: Sequence[Hashable],
    *,
    n_bins: int = 10,
    thresholds: Sequence[float] = (0.5, 0.7, 0.9),
) -> dict[Hashable, dict[str, object]]:
    """Return calibration and selective-risk metrics for each predeclared group."""

    confidence_values, correct_values = _validated_pairs(confidences, correctness)
    if len(groups) != len(confidence_values):
        raise ValueError("groups must have the same length as confidences")
    indices: dict[Hashable, list[int]] = defaultdict(list)
    for index, group in enumerate(groups):
        try:
            hash(group)
        except TypeError as error:
            raise ValueError("groups must contain only hashable values") from error
        indices[group].append(index)

    report: dict[Hashable, dict[str, object]] = {}
    for group, group_indices in indices.items():
        group_confidences = [confidence_values[index] for index in group_indices]
        group_correctness = [correct_values[index] for index in group_indices]
        curve = risk_coverage_curve(group_confidences, group_correctness)
        report[group] = {
            "count": len(group_indices),
            "accuracy": sum(group_correctness) / len(group_correctness),
            "brier": brier_score(group_confidences, group_correctness),
            "log_loss": binary_log_loss(group_confidences, group_correctness),
            "ece": expected_calibration_error(
                group_confidences, group_correctness, n_bins=n_bins
            ),
            "ace": adaptive_calibration_error(
                group_confidences, group_correctness, n_bins=n_bins
            ),
            "auroc": (
                correctness_auroc(group_confidences, group_correctness)
                if 0 < sum(group_correctness) < len(group_correctness)
                else None
            ),
            "aurc": area_under_risk_coverage_curve(curve),
            "selective": [
                asdict(selective_report(group_confidences, group_correctness, threshold))
                for threshold in thresholds
            ],
        }
    return report
