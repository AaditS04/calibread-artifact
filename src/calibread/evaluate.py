"""Evaluate cached answer confidence/correctness rows from CSV."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from itertools import product
from math import isfinite
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .dimensions import R7_THRESHOLD_LEVELS, r7_from_threshold

from .metrics import (
    adaptive_calibration_error,
    area_under_risk_coverage_curve,
    binary_log_loss,
    brier_score,
    correctness_auroc,
    expected_calibration_error,
    group_reliability_report,
    RiskCoveragePoint,
    risk_coverage_curve,
    selective_report,
)


R7_POLICY_COLUMN = "r7_policy_level"


_REPORT_LINKAGE_FIELDS = (
    'run_id',
    'model_snapshot_id',
    'evaluation_track',
    'condition_table_hash',
    'calibration_object_hash',
)


def _validated_report_identity(
    rows: Sequence[Mapping[str, str]],
    *,
    legacy_identity_input: bool,
    legacy_probability_input: bool,
) -> dict[str, object]:
    '''Validate that one report represents one model/run/scoring contract.'''

    identity: dict[str, object] = {
        'validation_mode': (
            'legacy_missing_linkage_allowed'
            if legacy_identity_input
            else 'strict'
        ),
        'legacy_identity_input': legacy_identity_input,
    }
    missing_linkage: dict[str, int] = {}
    for field in _REPORT_LINKAGE_FIELDS:
        row_values = [str(row.get(field, '') or '').strip() for row in rows]
        nonempty = sorted({value for value in row_values if value})
        if len(nonempty) > 1:
            raise ValueError(
                f'one report requires exactly one {field}; found heterogeneous values'
            )
        missing = sum(not value for value in row_values)
        if missing and not legacy_identity_input:
            raise ValueError(
                f'{field} must be nonempty on every row; '
                'use legacy_identity_input only for audited legacy files'
            )
        if missing:
            missing_linkage[field] = missing
        identity[field] = nonempty[0] if nonempty else None

    condition_hashes = [
        str(row.get('condition_hash', '') or '').strip() for row in rows
    ]
    missing_condition_hashes = sum(not value for value in condition_hashes)
    if missing_condition_hashes and not legacy_identity_input:
        raise ValueError(
            'condition_hash must be nonempty on every row; '
            'use legacy_identity_input only for audited legacy files'
        )
    if missing_condition_hashes:
        missing_linkage['condition_hash'] = missing_condition_hashes
    identity['condition_hash_count'] = len(
        {value for value in condition_hashes if value}
    )
    identity['condition_hashes_complete'] = missing_condition_hashes == 0

    kinds = [str(row.get('score_kind', '') or '').strip() for row in rows]
    if not any(kinds):
        if not legacy_probability_input:
            raise ValueError('score_kind must be nonempty on every row')
        score_kind = 'legacy_probability_assumption'
    else:
        if any(not value for value in kinds):
            raise ValueError('score_kind must be nonempty on every row')
        unique_kinds = set(kinds)
        if len(unique_kinds) != 1:
            raise ValueError(
                'one report requires exactly one score_kind; '
                'found heterogeneous values'
            )
        score_kind = kinds[0]

    sources = [str(row.get('score_source', '') or '').strip() for row in rows]
    if not any(sources):
        if not legacy_probability_input:
            raise ValueError('score_source must be nonempty on every row')
        score_source = 'legacy_confidence'
    else:
        if any(not value for value in sources):
            raise ValueError('score_source must be nonempty on every row')
        unique_sources = set(sources)
        if len(unique_sources) != 1:
            raise ValueError(
                'one report requires exactly one score_source; '
                'found heterogeneous values'
            )
        score_source = sources[0]

    optional_scoring: dict[str, str | None] = {}
    for field in ('calibrator_id', 'normalization_contract'):
        row_values = [str(row.get(field, '') or '').strip() for row in rows]
        nonempty = sorted({value for value in row_values if value})
        if len(nonempty) > 1:
            raise ValueError(
                f'one report requires at most one {field}; '
                'found heterogeneous values'
            )
        if nonempty and any(not value for value in row_values):
            raise ValueError(
                f'{field} must be nonempty on every row or absent on every row'
            )
        optional_scoring[field] = nonempty[0] if nonempty else None

    if score_kind == 'legacy_probability_assumption':
        optional_scoring['calibrator_id'] = 'legacy_unspecified'
    if score_kind in {'probability', 'legacy_probability'} and not optional_scoring[
        'calibrator_id'
    ]:
        raise ValueError('probability rows require calibrator_id on every row')

    identity.update(
        {
            'score_kind': score_kind,
            'score_source': score_source,
            'calibrator_id': optional_scoring['calibrator_id'],
            'normalization_contract': optional_scoring[
                'normalization_contract'
            ],
            'missing_linkage_counts': missing_linkage,
        }
    )
    return identity


def _canonical_policy_grid(thresholds: Sequence[float] | None) -> tuple[tuple[float, str], ...]:
    values = tuple(R7_THRESHOLD_LEVELS) if thresholds is None else tuple(float(value) for value in thresholds)
    if not values:
        raise ValueError("thresholds must not be empty")
    if len(set(values)) != len(values):
        raise ValueError("thresholds must be unique")
    result: list[tuple[float, str]] = []
    for threshold in values:
        result.append((threshold, r7_from_threshold(threshold).level))
    return tuple(result)


def _score_semantics(
    rows: Sequence[Mapping[str, str]],
    *,
    legacy_probability_input: bool,
) -> tuple[
    str,
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    str,
    bool,
]:
    kinds = [str(row.get("score_kind", "") or "").strip() for row in rows]
    if not any(kinds):
        if not legacy_probability_input:
            raise ValueError(
                "rows must declare score_kind, score_source, and calibrator_id; "
                "use legacy_probability_input only for audited legacy probability files"
            )
        return (
            "probability",
            ("legacy_confidence",),
            ("legacy_unspecified",),
            (),
            "legacy_probability_assumption",
            True,
        )
    if any(not kind for kind in kinds):
        raise ValueError("score_kind must be present on every row")
    unique_kinds = set(kinds)
    declared_legacy = unique_kinds == {"legacy_probability"}
    if declared_legacy and not legacy_probability_input:
        raise ValueError(
            "legacy_probability rows require legacy_probability_input=True"
        )
    if len(unique_kinds) != 1 or not unique_kinds <= {
        "raw",
        "probability",
        "legacy_probability",
    }:
        raise ValueError("one report must contain only raw scores or only probability scores")
    kind = "probability" if declared_legacy else kinds[0]
    sources = tuple(
        sorted({str(row.get("score_source", "") or "").strip() for row in rows})
    )
    if not sources or any(not source for source in sources):
        raise ValueError("score_source must be declared on every row")
    calibrators = tuple(
        sorted({str(row.get("calibrator_id", "") or "").strip() for row in rows})
    )
    if kind == "probability" and (not calibrators or any(not item for item in calibrators)):
        raise ValueError(
            "probability rows require calibrator_id on every row (use 'identity' if applicable)"
        )
    row_normalizers = [
        str(row.get("normalization_contract", "") or "").strip() for row in rows
    ]
    if kind == "raw" and any(row_normalizers) and any(
        not item for item in row_normalizers
    ):
        raise ValueError(
            "normalization_contract must be declared on every raw row or on none"
        )
    normalizers = tuple(sorted({item for item in row_normalizers if item}))
    policy_eligible = kind == "probability" or bool(normalizers)
    return (
        kind,
        sources,
        tuple(item for item in calibrators if item),
        normalizers,
        (
            "legacy_probability_assumption"
            if declared_legacy
            else (
                "declared_probability"
                if kind == "probability"
                else "raw_score_metrics_withheld"
            )
        ),
        policy_eligible,
    )


def _raw_score_auroc(scores: Sequence[float], correctness: Sequence[int]) -> float:
    positives = sum(correctness)
    negatives = len(correctness) - positives
    if positives == 0 or negatives == 0:
        raise ValueError("AUROC requires at least one correct and one incorrect example")
    ranked = sorted(zip(scores, correctness))
    positive_rank_sum = 0.0
    start = 0
    while start < len(ranked):
        end = start + 1
        while end < len(ranked) and ranked[end][0] == ranked[start][0]:
            end += 1
        average_rank = (start + 1 + end) / 2.0
        positive_rank_sum += average_rank * sum(
            label for _, label in ranked[start:end]
        )
        start = end
    return (positive_rank_sum - positives * (positives + 1) / 2.0) / (
        positives * negatives
    )


def _raw_risk_coverage_curve(
    scores: Sequence[float], correctness: Sequence[int]
) -> list[RiskCoveragePoint]:
    by_score: dict[float, list[int]] = {}
    for score, correct in zip(scores, correctness):
        by_score.setdefault(score, []).append(correct)
    accepted = 0
    errors = 0
    total = len(scores)
    points: list[RiskCoveragePoint] = []
    for score in sorted(by_score, reverse=True):
        bucket = by_score[score]
        accepted += len(bucket)
        errors += sum(1 - correct for correct in bucket)
        points.append(
            RiskCoveragePoint(
                threshold=score,
                coverage=accepted / total,
                risk=errors / accepted,
                accepted=accepted,
            )
        )
    return points


def _reliability_report(
    confidences: Sequence[float],
    correctness: Sequence[int],
    groups: Sequence[str],
    *,
    n_bins: int,
    thresholds: Sequence[float],
    probability_valued: bool,
) -> dict[object, dict[str, object]]:
    if probability_valued:
        report = group_reliability_report(
            confidences,
            correctness,
            groups,
            n_bins=n_bins,
            thresholds=thresholds,
        )
        for values in report.values():
            values["probability_metrics_status"] = "computed"
        return report

    report: dict[object, dict[str, object]] = {}
    for group in dict.fromkeys(groups):
        indices = [index for index, value in enumerate(groups) if value == group]
        group_confidences = [confidences[index] for index in indices]
        group_correctness = [correctness[index] for index in indices]
        positives = sum(group_correctness)
        curve = _raw_risk_coverage_curve(group_confidences, group_correctness)
        report[group] = {
            "count": len(indices),
            "accuracy": positives / len(indices),
            "brier": None,
            "log_loss": None,
            "ece": None,
            "ace": None,
            "auroc": (
                _raw_score_auroc(group_confidences, group_correctness)
                if 0 < positives < len(indices)
                else None
            ),
            "aurc": area_under_risk_coverage_curve(curve),
            "selective": [
                asdict(selective_report(group_confidences, group_correctness, threshold))
                for threshold in thresholds
            ],
            "probability_metrics_status": "withheld_raw_score",
        }
    return report


def _parse_correct(value: str) -> int:
    normalized = str(value).strip().casefold()
    if normalized in {"1", "true", "yes"}:
        return 1
    if normalized in {"0", "false", "no"}:
        return 0
    raise ValueError(f"correct must be one of 0/1/false/true/no/yes, got {value!r}")


def _requested_columns(
    group_column: str, group_columns: Sequence[str] | None
) -> tuple[str, ...]:
    supplied = (group_column,) if group_columns is None else tuple(group_columns)
    normalized = tuple(str(column).strip() for column in supplied)
    if not normalized or any(not column for column in normalized):
        raise ValueError("at least one nonempty group column is required")
    if len(set(normalized)) != len(normalized):
        raise ValueError("group columns must not contain duplicates")
    return normalized


def _requested_interactions(
    interactions: Sequence[Sequence[str]],
) -> tuple[tuple[str, ...], ...]:
    normalized = tuple(tuple(str(column).strip() for column in item) for item in interactions)
    if any(len(item) < 2 for item in normalized):
        raise ValueError("each interaction must contain at least two columns")
    if any(any(not column for column in item) for item in normalized):
        raise ValueError("interaction columns must not be empty")
    if any(len(set(item)) != len(item) for item in normalized):
        raise ValueError("an interaction cannot repeat a column")
    if len(set(normalized)) != len(normalized):
        raise ValueError("interactions must not contain duplicates")
    return normalized


def _validated_expected_levels(
    expected_levels: Mapping[str, Sequence[str]] | None,
    available_columns: Sequence[str],
    policy_levels: Sequence[str],
) -> dict[str, tuple[str, ...]]:
    if expected_levels is None:
        return {}
    available = set(available_columns) | {R7_POLICY_COLUMN}
    normalized: dict[str, tuple[str, ...]] = {}
    for raw_column, raw_levels in expected_levels.items():
        column = str(raw_column).strip()
        if not column or column not in available:
            raise ValueError(f"expected levels reference unavailable column {column!r}")
        if isinstance(raw_levels, (str, bytes)):
            raise ValueError(f"expected levels for {column!r} must be a sequence")
        levels = tuple(str(level).strip() for level in raw_levels)
        if not levels or any(not level for level in levels):
            raise ValueError(f"expected levels for {column!r} must be nonempty")
        if len(set(levels)) != len(levels):
            raise ValueError(f"expected levels for {column!r} must be unique")
        if column == R7_POLICY_COLUMN:
            unknown = set(levels) - set(policy_levels)
            if unknown:
                raise ValueError(
                    "expected R7 levels are outside the evaluated policy grid: "
                    + ", ".join(sorted(unknown))
                )
        normalized[column] = levels
    return normalized


def _validated_floor(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _check_level_floors(
    values_by_column: Mapping[str, Sequence[str]],
    expected_levels: Mapping[str, Sequence[str]],
    *,
    minimum_level_count: int,
    total_count: int,
) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for column, levels in expected_levels.items():
        if column == R7_POLICY_COLUMN:
            level_counts = {level: total_count for level in levels}
        else:
            observed = values_by_column[column]
            level_counts = {level: observed.count(level) for level in levels}
        insufficient = {
            level: count
            for level, count in level_counts.items()
            if count < minimum_level_count
        }
        if insufficient:
            rendered = ", ".join(
                f"{column}={level} ({count})"
                for level, count in insufficient.items()
            )
            raise ValueError(
                f"expected-level floor {minimum_level_count} not met: {rendered}"
            )
        counts[column] = level_counts
    return counts


def _interaction_labels(
    columns: Sequence[str],
    values_by_column: Mapping[str, Sequence[str]],
    count: int,
) -> list[str]:
    return [
        "|".join(
            f"{column}={values_by_column[column][index]}" for column in columns
        )
        for index in range(count)
    ]


def _policy_group_report(
    confidences: Sequence[float],
    correctness: Sequence[int],
    policy_grid: Sequence[tuple[float, str]],
    *,
    n_bins: int,
    probability_valued: bool,
) -> dict[str, dict[str, object]]:
    base = _reliability_report(
        confidences,
        correctness,
        ["all"] * len(confidences),
        n_bins=n_bins,
        thresholds=[threshold for threshold, _ in policy_grid],
        probability_valued=probability_valued,
    )["all"]
    result: dict[str, dict[str, object]] = {}
    for threshold, level in policy_grid:
        selective = asdict(selective_report(confidences, correctness, threshold))
        values = dict(base)
        values["selective"] = [selective]
        values["policy_level"] = level
        values["threshold"] = threshold
        values["action_counts"] = {
            "answer": selective["accepted"],
            "set": 0,
            "abstain": selective["total"] - selective["accepted"],
        }
        result[level] = values
    return result


def _policy_interaction_report(
    columns: Sequence[str],
    confidences: Sequence[float],
    correctness: Sequence[int],
    values_by_column: Mapping[str, Sequence[str]],
    policy_grid: Sequence[tuple[float, str]],
    *,
    n_bins: int,
    probability_valued: bool,
) -> dict[str, dict[str, object]]:
    base_columns = tuple(column for column in columns if column != R7_POLICY_COLUMN)
    cell_indices: dict[tuple[str, ...], list[int]] = {}
    for index in range(len(confidences)):
        cell = tuple(values_by_column[column][index] for column in base_columns)
        cell_indices.setdefault(cell, []).append(index)

    result: dict[str, dict[str, object]] = {}
    for cell, indices in cell_indices.items():
        cell_confidences = [confidences[index] for index in indices]
        cell_correctness = [correctness[index] for index in indices]
        base = _reliability_report(
            cell_confidences,
            cell_correctness,
            ["cell"] * len(indices),
            n_bins=n_bins,
            thresholds=[threshold for threshold, _ in policy_grid],
            probability_valued=probability_valued,
        )["cell"]
        base_values = dict(zip(base_columns, cell))
        for threshold, level in policy_grid:
            label_values = dict(base_values)
            label_values[R7_POLICY_COLUMN] = level
            label = "|".join(f"{column}={label_values[column]}" for column in columns)
            selective = asdict(
                selective_report(cell_confidences, cell_correctness, threshold)
            )
            values = dict(base)
            values["selective"] = [selective]
            values["policy_level"] = level
            values["threshold"] = threshold
            values["input_example_count"] = len(indices)
            values["action_counts"] = {
                "answer": selective["accepted"],
                "set": 0,
                "abstain": selective["total"] - selective["accepted"],
            }
            result[label] = values
    return result


def _check_interaction_floors(
    interactions: Sequence[Sequence[str]],
    values_by_column: Mapping[str, Sequence[str]],
    expected_levels: Mapping[str, Sequence[str]],
    policy_levels: Sequence[str],
    *,
    minimum_interaction_count: int,
    total_count: int,
) -> dict[str, dict[str, int]]:
    diagnostics: dict[str, dict[str, int]] = {}
    for columns in interactions:
        base_columns = tuple(
            column for column in columns if column != R7_POLICY_COLUMN
        )
        if any(column in expected_levels for column in base_columns):
            base_cells = tuple(
                product(
                    *[
                        tuple(
                            expected_levels.get(
                                column,
                                tuple(dict.fromkeys(values_by_column[column])),
                            )
                        )
                        for column in base_columns
                    ]
                )
            )
        else:
            base_cells = tuple(
                dict.fromkeys(
                    tuple(values_by_column[column][index] for column in base_columns)
                    for index in range(total_count)
                )
            )
        r7_levels: tuple[str | None, ...] = (
            tuple(expected_levels.get(R7_POLICY_COLUMN, policy_levels))
            if R7_POLICY_COLUMN in columns
            else (None,)
        )
        cell_counts: dict[str, int] = {}
        for base_cell, r7_level in product(base_cells, r7_levels):
            base_requirements = {
                column: level
                for column, level in zip(base_columns, base_cell)
            }
            count = sum(
                all(
                    values_by_column[column][index] == level
                    for column, level in base_requirements.items()
                )
                for index in range(total_count)
            )
            label_values = dict(base_requirements)
            if r7_level is not None:
                label_values[R7_POLICY_COLUMN] = r7_level
            label = "|".join(
                f"{column}={label_values[column]}" for column in columns
            )
            cell_counts[label] = count
        insufficient = {
            label: count
            for label, count in cell_counts.items()
            if count < minimum_interaction_count
        }
        if insufficient:
            rendered = ", ".join(
                f"{label} ({count})" for label, count in insufficient.items()
            )
            raise ValueError(
                f"interaction floor {minimum_interaction_count} not met: {rendered}"
            )
        diagnostics["*".join(columns)] = cell_counts
    return diagnostics


def evaluate_rows(
    rows: Iterable[Mapping[str, str]],
    *,
    n_bins: int = 10,
    threshold: float = 0.7,
    thresholds: Sequence[float] | None = None,
    group_column: str = "group",
    group_columns: Sequence[str] | None = None,
    interactions: Sequence[Sequence[str]] = (),
    legacy_probability_input: bool = False,
    legacy_identity_input: bool = False,
    expected_levels: Mapping[str, Sequence[str]] | None = None,
    minimum_level_count: int = 1,
    minimum_interaction_count: int = 1,
) -> dict[str, object]:
    """Compute global, per-dimension, crossed, and R7 policy metrics.

    One invocation reports exactly one run, model snapshot, evaluation track,
    condition table, calibration object, and scoring contract. ``condition_hash``
    remains per-example and may vary. Probability calibration metrics are computed
    only for rows that explicitly declare
    probability-valued scores. Arbitrary finite raw scores retain ranking metrics; R7 and
    selective-risk metrics additionally require a declared normalization contract. The R7
    policy grid is swept from each cached row internally, never from duplicated CSV rows.
    """

    materialized = list(rows)
    if not materialized:
        raise ValueError("rows must not be empty")
    report_identity = _validated_report_identity(
        materialized,
        legacy_identity_input=legacy_identity_input,
        legacy_probability_input=legacy_probability_input,
    )
    if isinstance(n_bins, bool) or not isinstance(n_bins, int) or n_bins < 1:
        raise ValueError("n_bins must be a positive integer")
    (
        score_kind,
        score_sources,
        calibrator_ids,
        normalization_contracts,
        probability_status,
        policy_eligible,
    ) = _score_semantics(materialized, legacy_probability_input=legacy_probability_input)
    probability_valued = score_kind == "probability"
    minimum_level_count = _validated_floor(
        minimum_level_count, "minimum_level_count"
    )
    minimum_interaction_count = _validated_floor(
        minimum_interaction_count, "minimum_interaction_count"
    )
    selected_columns = _requested_columns(group_column, group_columns)
    selected_interactions = _requested_interactions(interactions)
    r7_requested = (
        thresholds is not None
        or R7_POLICY_COLUMN in selected_columns
        or any(R7_POLICY_COLUMN in item for item in selected_interactions)
        or bool(expected_levels and R7_POLICY_COLUMN in expected_levels)
    )
    if r7_requested and not policy_eligible:
        raise ValueError(
            "R7 evaluation requires probability scores or raw scores with an "
            "explicit normalization_contract on every row"
        )
    policy_grid = _canonical_policy_grid(thresholds) if policy_eligible else ()
    policy_thresholds = tuple(value for value, _ in policy_grid)
    policy_levels = tuple(level for _, level in policy_grid)
    required_columns = tuple(
        dict.fromkeys(
            tuple(column for column in selected_columns if column != R7_POLICY_COLUMN)
            + tuple(column for item in selected_interactions for column in item)
        )
    )
    required_columns = tuple(
        column for column in required_columns if column != R7_POLICY_COLUMN
    )
    strict_columns = (
        set(required_columns)
        if group_columns is not None
        else {
            column
            for item in selected_interactions
            for column in item
            if column != R7_POLICY_COLUMN
        }
    )
    confidences: list[float] = []
    correctness: list[int] = []
    values_by_column: dict[str, list[str]] = {
        column: [] for column in required_columns
    }
    example_ids: set[str] = set()
    for index, row in enumerate(materialized, start=2):
        if any(field not in row for field in ("example_id", "confidence", "correct")):
            raise ValueError("CSV must contain example_id, confidence, and correct columns")
        example_id = str(row["example_id"]).strip()
        if not example_id:
            raise ValueError(f"invalid CSV row {index}: example_id must not be empty")
        if example_id in example_ids:
            raise ValueError(f"invalid CSV row {index}: duplicate example_id {example_id!r}")
        example_ids.add(example_id)
        try:
            score = float(row["confidence"])
            if not isfinite(score):
                raise ValueError("confidence must be finite")
            if (probability_valued or policy_eligible) and not 0.0 <= score <= 1.0:
                raise ValueError(
                    "probability and normalized policy scores must lie in [0, 1]"
                )
            confidences.append(score)
            correctness.append(_parse_correct(row["correct"]))
        except (TypeError, ValueError) as error:
            raise ValueError(f"invalid CSV row {index}: {error}") from error
        for column in required_columns:
            if column in strict_columns and column not in row:
                raise ValueError(f"invalid CSV row {index}: missing group column {column!r}")
            raw_group = row.get(column, "all")
            if column in strict_columns and not str(raw_group or "").strip():
                raise ValueError(f"invalid CSV row {index}: empty group column {column!r}")
            value = str(raw_group or "all").strip()
            values_by_column[column].append(value or "all")

    normalized_expected = _validated_expected_levels(
        expected_levels, required_columns, policy_levels
    )
    level_counts = _check_level_floors(
        values_by_column,
        normalized_expected,
        minimum_level_count=minimum_level_count,
        total_count=len(confidences),
    )
    interaction_counts = _check_interaction_floors(
        selected_interactions,
        values_by_column,
        normalized_expected,
        policy_levels,
        minimum_interaction_count=minimum_interaction_count,
        total_count=len(confidences),
    )

    curve = (
        risk_coverage_curve(confidences, correctness)
        if probability_valued
        else _raw_risk_coverage_curve(confidences, correctness)
    )
    positives = sum(correctness)
    group_reports: dict[str, object] = {}
    for column in selected_columns:
        if column == R7_POLICY_COLUMN:
            group_reports[column] = _policy_group_report(
                confidences,
                correctness,
                policy_grid,
                n_bins=n_bins,
                probability_valued=probability_valued,
            )
        else:
            group_reports[column] = _reliability_report(
                confidences,
                correctness,
                values_by_column[column],
                n_bins=n_bins,
                thresholds=policy_thresholds,
                probability_valued=probability_valued,
            )

    interaction_reports: dict[str, object] = {}
    for columns in selected_interactions:
        name = "*".join(columns)
        if R7_POLICY_COLUMN in columns:
            interaction_reports[name] = _policy_interaction_report(
                columns,
                confidences,
                correctness,
                values_by_column,
                policy_grid,
                n_bins=n_bins,
                probability_valued=probability_valued,
            )
        else:
            labels = _interaction_labels(
                columns, values_by_column, len(confidences)
            )
            interaction_reports[name] = _reliability_report(
                confidences,
                correctness,
                labels,
                n_bins=n_bins,
                thresholds=policy_thresholds,
                probability_valued=probability_valued,
            )

    policy_frontier: list[dict[str, object]] = []
    for policy_threshold, policy_level in policy_grid:
        values = asdict(
            selective_report(confidences, correctness, policy_threshold)
        )
        values["policy_level"] = policy_level
        values["action_counts"] = {
            "answer": values["accepted"],
            "set": 0,
            "abstain": values["total"] - values["accepted"],
        }
        policy_frontier.append(values)

    brier = (
        brier_score(confidences, correctness) if probability_valued else None
    )
    log_loss = (
        binary_log_loss(confidences, correctness) if probability_valued else None
    )
    ece = (
        expected_calibration_error(confidences, correctness, n_bins=n_bins)
        if probability_valued
        else None
    )
    ace = (
        adaptive_calibration_error(confidences, correctness, n_bins=n_bins)
        if probability_valued
        else None
    )
    return {
        'report_identity': report_identity,
        "count": len(confidences),
        "accuracy": positives / len(correctness),
        "brier": brier,
        "log_loss": log_loss,
        "ece": ece,
        "ace": ace,
        "auroc": (
            (
                correctness_auroc(confidences, correctness)
                if probability_valued
                else _raw_score_auroc(confidences, correctness)
            )
            if 0 < positives < len(correctness)
            else None
        ),
        "aurc": area_under_risk_coverage_curve(curve),
        "selective": (
            asdict(selective_report(confidences, correctness, threshold))
            if policy_eligible
            else None
        ),
        "group_column": selected_columns[0],
        "groups": group_reports[selected_columns[0]],
        "group_reports": group_reports,
        "interactions": interaction_reports,
        "policy_frontier": policy_frontier,
        "score_semantics": {
            "kind": score_kind,
            "sources": score_sources,
            "calibrator_ids": calibrator_ids,
            "normalization_contracts": normalization_contracts,
            "probability_metrics_status": probability_status,
            "policy_metrics_status": (
                "computed_probability"
                if probability_valued
                else (
                    "computed_normalized_raw"
                    if policy_eligible
                    else "withheld_raw_score_without_normalization"
                )
            ),
        },
        "probability_metrics_status": probability_status,
        "policy_metrics_status": (
            "computed_probability"
            if probability_valued
            else (
                "computed_normalized_raw"
                if policy_eligible
                else "withheld_raw_score_without_normalization"
            )
        ),
        "coverage_checks": {
            "minimum_level_count": minimum_level_count,
            "minimum_interaction_count": minimum_interaction_count,
            "expected_level_counts": level_counts,
            "expected_interaction_counts": interaction_counts,
        },
    }


def _interaction_argument(value: str) -> tuple[str, ...]:
    columns = tuple(part.strip() for part in value.split(","))
    if len(columns) < 2 or any(not column for column in columns):
        raise argparse.ArgumentTypeError(
            "interaction must be two or more comma-separated column names"
        )
    return columns


def _expected_level_argument(value: str) -> tuple[str, tuple[str, ...]]:
    column, separator, raw_levels = value.partition("=")
    levels = tuple(part.strip() for part in raw_levels.split(","))
    if not separator or not column.strip() or not levels or any(not level for level in levels):
        raise argparse.ArgumentTypeError(
            "expected level must be COLUMN=LEVEL1,LEVEL2"
        )
    if len(set(levels)) != len(levels):
        raise argparse.ArgumentTypeError("expected levels must not contain duplicates")
    return column.strip(), levels


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "csv_path",
        type=Path,
        help="CSV with cached scores, correctness, and declared score semantics",
    )
    parser.add_argument("--output", type=Path, help="optional JSON report path")
    parser.add_argument("--bins", type=int, default=10, help="number of calibration bins")
    parser.add_argument(
        "--threshold",
        dest="thresholds",
        action="append",
        type=float,
        help="frozen R7 threshold; repeat to override the complete canonical grid",
    )
    parser.add_argument(
        "--group-column",
        dest="group_columns",
        action="append",
        help="grouping column; repeat to report multiple dimensions",
    )
    parser.add_argument(
        "--interaction",
        action="append",
        type=_interaction_argument,
        default=[],
        help="comma-separated columns to cross; may be repeated",
    )
    parser.add_argument(
        "--expect-level",
        action="append",
        type=_expected_level_argument,
        default=[],
        help="required coverage as COLUMN=LEVEL1,LEVEL2; may be repeated",
    )
    parser.add_argument(
        "--minimum-level-count",
        type=int,
        default=1,
        help="minimum rows required for every explicitly expected level",
    )
    parser.add_argument(
        "--minimum-interaction-count",
        type=int,
        default=1,
        help="minimum rows required for every checked interaction cell",
    )
    parser.add_argument(
        "--legacy-probability-input",
        action="store_true",
        help="audit-only compatibility path for files lacking score semantics",
    )
    parser.add_argument(
        '--legacy-identity-input',
        action='store_true',
        help=(
            'audit-only compatibility path for missing run/linkage fields; '
            'mixed scoring identities remain forbidden'
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the calibread-evaluate command."""

    arguments = _parser().parse_args(argv)
    expected_levels: dict[str, tuple[str, ...]] = {}
    for column, levels in arguments.expect_level:
        if column in expected_levels:
            raise ValueError(f"expected levels repeat column {column!r}")
        expected_levels[column] = levels
    with arguments.csv_path.open("r", encoding="utf-8", newline="") as handle:
        report = evaluate_rows(
            csv.DictReader(handle),
            n_bins=arguments.bins,
            threshold=arguments.thresholds[0] if arguments.thresholds else 0.7,
            thresholds=arguments.thresholds,
            group_columns=arguments.group_columns,
            interactions=arguments.interaction,
            legacy_probability_input=arguments.legacy_probability_input,
            legacy_identity_input=arguments.legacy_identity_input,
            expected_levels=expected_levels or None,
            minimum_level_count=arguments.minimum_level_count,
            minimum_interaction_count=arguments.minimum_interaction_count,
        )
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if arguments.output:
        arguments.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
