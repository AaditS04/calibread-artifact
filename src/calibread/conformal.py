"""Finite-sample split-conformal helpers for finite-label CalibRead experiments."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import ceil, inf, isfinite
from typing import Hashable, Iterable, Mapping, Sequence


def conformal_quantile(nonconformity_scores: Iterable[float], alpha: float) -> float:
    """Return the finite-sample corrected split-conformal threshold.

    The order statistic is ``ceil((n + 1) * (1 - alpha))``. If that order statistic exceeds
    the calibration sample size, ``inf`` is returned, corresponding to the full prediction set.
    """

    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must lie strictly between 0 and 1")
    scores = [float(score) for score in nonconformity_scores]
    if not scores:
        raise ValueError("nonconformity_scores must not be empty")
    if any(not isfinite(score) for score in scores):
        raise ValueError("nonconformity_scores must contain only finite values")
    rank = ceil((len(scores) + 1) * (1.0 - alpha))
    if rank > len(scores):
        return inf
    return sorted(scores)[rank - 1]


def true_label_nonconformity(
    probability_rows: Sequence[Sequence[float]], true_labels: Sequence[int]
) -> list[float]:
    """Return ``1 - p(true_label)`` for each finite-label calibration example."""

    if len(probability_rows) != len(true_labels):
        raise ValueError("probability_rows and true_labels must have the same length")
    if not probability_rows:
        raise ValueError("probability_rows must not be empty")
    class_count = len(probability_rows[0])
    scores: list[float] = []
    for probabilities, label in zip(probability_rows, true_labels):
        _validate_probability_row(probabilities)
        if len(probabilities) != class_count:
            raise ValueError("all probability rows must have the same class cardinality")
        if label < 0 or label >= len(probabilities):
            raise ValueError("true label is outside its probability row")
        scores.append(1.0 - float(probabilities[label]))
    return scores


def _validate_probability_row(probabilities: Sequence[float]) -> None:
    if not probabilities:
        raise ValueError("probability rows must not be empty")
    values = [float(value) for value in probabilities]
    if any(not isfinite(value) or value < 0.0 or value > 1.0 for value in values):
        raise ValueError("probabilities must be finite and lie in [0, 1]")
    if abs(sum(values) - 1.0) > 1e-6:
        raise ValueError("each probability row must sum to 1")


def finite_label_prediction_set(
    probabilities: Sequence[float], threshold: float
) -> frozenset[int]:
    """Return labels whose ``1 - probability`` does not exceed ``threshold``."""

    _validate_probability_row(probabilities)
    if threshold != inf and (
        not isfinite(threshold) or threshold < 0.0 or threshold > 1.0
    ):
        raise ValueError("threshold must lie in [0, 1] or equal infinity")
    return frozenset(
        index
        for index, probability in enumerate(probabilities)
        if 1.0 - float(probability) <= threshold
    )


def empirical_coverage(
    prediction_sets: Sequence[Iterable[int]], true_labels: Sequence[int]
) -> float:
    """Return the fraction of prediction sets containing their declared true label."""

    if len(prediction_sets) != len(true_labels):
        raise ValueError("prediction_sets and true_labels must have the same length")
    if not prediction_sets:
        raise ValueError("prediction_sets must not be empty")
    covered = sum(
        int(label in set(prediction_set))
        for prediction_set, label in zip(prediction_sets, true_labels)
    )
    return covered / len(true_labels)


def group_conformal_quantiles(
    nonconformity_scores: Sequence[float],
    groups: Sequence[Hashable],
    alpha: float,
    *,
    min_group_size: int = 1,
) -> dict[Hashable, float]:
    """Calibrate separate thresholds for predeclared groups (Mondrian split conformal).

    This supports group-marginal coverage only when calibration and future examples are
    exchangeable within each group. It does not provide arbitrary per-query conditional coverage.
    """

    if len(nonconformity_scores) != len(groups):
        raise ValueError("nonconformity_scores and groups must have the same length")
    if min_group_size < 1:
        raise ValueError("min_group_size must be at least 1")
    grouped: dict[Hashable, list[float]] = defaultdict(list)
    for score, group in zip(nonconformity_scores, groups):
        try:
            hash(group)
        except TypeError as error:
            raise ValueError("groups must contain only hashable values") from error
        grouped[group].append(float(score))
    if not grouped:
        raise ValueError("groups must not be empty")

    thresholds: dict[Hashable, float] = {}
    for group, scores in grouped.items():
        if len(scores) < min_group_size:
            raise ValueError(
                f"group {group!r} has {len(scores)} calibration examples; "
                f"minimum is {min_group_size}"
            )
        thresholds[group] = conformal_quantile(scores, alpha)
    return thresholds


def apply_group_prediction_sets(
    probability_rows: Sequence[Sequence[float]],
    groups: Sequence[Hashable],
    thresholds: Mapping[Hashable, float],
) -> list[frozenset[int]]:
    """Apply precomputed group thresholds to finite-label probability rows."""

    if len(probability_rows) != len(groups):
        raise ValueError("probability_rows and groups must have the same length")
    class_count = len(probability_rows[0]) if probability_rows else None
    result: list[frozenset[int]] = []
    for probabilities, group in zip(probability_rows, groups):
        if len(probabilities) != class_count:
            raise ValueError("all probability rows must have the same class cardinality")
        if group not in thresholds:
            raise KeyError(f"no calibrated threshold for group {group!r}")
        result.append(finite_label_prediction_set(probabilities, thresholds[group]))
    return result


@dataclass(frozen=True)
class SplitConformalClassifier:
    """Fitted finite-label split-conformal predictor."""

    alpha: float
    threshold: float
    class_count: int

    @classmethod
    def fit(
        cls,
        probability_rows: Sequence[Sequence[float]],
        true_labels: Sequence[int],
        *,
        alpha: float,
    ) -> "SplitConformalClassifier":
        scores = true_label_nonconformity(probability_rows, true_labels)
        return cls(
            alpha=float(alpha),
            threshold=conformal_quantile(scores, alpha),
            class_count=len(probability_rows[0]),
        )

    def predict(self, probabilities: Sequence[float]) -> frozenset[int]:
        if len(probabilities) != self.class_count:
            raise ValueError(
                f"expected {self.class_count} class probabilities, got {len(probabilities)}"
            )
        return finite_label_prediction_set(probabilities, self.threshold)

    def predict_many(
        self, probability_rows: Sequence[Sequence[float]]
    ) -> list[frozenset[int]]:
        return [self.predict(probabilities) for probabilities in probability_rows]


@dataclass(frozen=True)
class GroupConformalClassifier:
    """Fitted Mondrian predictor with explicit errors for unseen groups."""

    alpha: float
    thresholds: Mapping[Hashable, float]
    class_count: int
    min_group_size: int = 1

    @classmethod
    def fit(
        cls,
        probability_rows: Sequence[Sequence[float]],
        true_labels: Sequence[int],
        groups: Sequence[Hashable],
        *,
        alpha: float,
        min_group_size: int = 1,
    ) -> "GroupConformalClassifier":
        if len(probability_rows) != len(groups):
            raise ValueError("probability_rows and groups must have the same length")
        scores = true_label_nonconformity(probability_rows, true_labels)
        thresholds = group_conformal_quantiles(
            scores, groups, alpha, min_group_size=min_group_size
        )
        return cls(
            alpha=float(alpha),
            thresholds=dict(thresholds),
            class_count=len(probability_rows[0]),
            min_group_size=min_group_size,
        )

    def predict(
        self, probabilities: Sequence[float], group: Hashable
    ) -> frozenset[int]:
        if group not in self.thresholds:
            raise KeyError(f"no calibrated threshold for unseen group {group!r}")
        if len(probabilities) != self.class_count:
            raise ValueError(
                f"expected {self.class_count} class probabilities, got {len(probabilities)}"
            )
        return finite_label_prediction_set(probabilities, self.thresholds[group])

    def predict_many(
        self,
        probability_rows: Sequence[Sequence[float]],
        groups: Sequence[Hashable],
    ) -> list[frozenset[int]]:
        if len(probability_rows) != len(groups):
            raise ValueError("probability_rows and groups must have the same length")
        return [
            self.predict(probabilities, group)
            for probabilities, group in zip(probability_rows, groups)
        ]
