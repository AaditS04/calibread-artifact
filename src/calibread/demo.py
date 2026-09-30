"""Run a deterministic end-to-end CalibRead smoke experiment."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Mapping, Sequence

from .config import load_study_config
from .dimensions import DIMENSION_REGISTRY

from .conformal import (
    GroupConformalClassifier,
    SplitConformalClassifier,
    empirical_coverage,
)
from .metrics import (
    area_under_risk_coverage_curve,
    brier_score,
    expected_calibration_error,
    prediction_set_efficiency,
    risk_coverage_curve,
    selective_report,
)


def _synthetic_rows(
    random_state: random.Random,
    counts: Sequence[tuple[str, int]],
    *,
    base_by_group: Mapping[str, float] | None = None,
) -> tuple[list[list[float]], list[int], list[str]]:
    rows: list[list[float]] = []
    labels: list[int] = []
    groups: list[str] = []
    for group, count in counts:
        base = (
            base_by_group[group]
            if base_by_group is not None
            else 0.66 if group == 'head' else 0.42
        )
        for _ in range(count):
            label = random_state.randrange(3)
            true_probability = min(0.94, max(0.08, base + random_state.uniform(-0.25, 0.25)))
            remainder = (1.0 - true_probability) / 2.0
            probabilities = [remainder, remainder, remainder]
            probabilities[label] = true_probability
            rows.append(probabilities)
            labels.append(label)
            groups.append(group)
    return rows, labels, groups


def _coverage_by_group(
    prediction_sets: Sequence[frozenset[int]],
    labels: Sequence[int],
    groups: Sequence[str],
) -> dict[str, float]:
    report: dict[str, float] = {}
    for group in dict.fromkeys(groups):
        indices = [index for index, value in enumerate(groups) if value == group]
        report[group] = empirical_coverage(
            [prediction_sets[index] for index in indices],
            [labels[index] for index in indices],
        )
    return report


_DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / 'configs' / 'pilot.toml'


def _configured_panels(
    config: Mapping[str, object], per_level: int
) -> tuple[list[tuple[str, int]], dict[str, float]]:
    '''Build small synthetic groups for every configured R1--R6 level.'''

    if per_level < 1:
        raise ValueError('per_level must be positive')
    dimensions = config['dimensions']
    if not isinstance(dimensions, Mapping):
        raise ValueError('validated config is missing dimensions')
    counts: list[tuple[str, int]] = []
    bases: dict[str, float] = {}
    for code in tuple(DIMENSION_REGISTRY)[:6]:
        table = dimensions[code]
        if not isinstance(table, Mapping):
            raise ValueError(f'validated config is missing {code}')
        levels = table['levels']
        if not isinstance(levels, list):
            raise ValueError(f'validated config has invalid {code} levels')
        for index, level in enumerate(levels):
            group = f'{code}={level}'
            counts.append((group, per_level))
            bases[group] = 0.76 - 0.10 * index
    return counts, bases


def run_demo(
    seed: int = 7,
    alpha: float = 0.1,
    *,
    config_path: str | Path = _DEFAULT_CONFIG,
    calibration_per_level: int = 12,
    test_per_level: int = 6,
) -> dict[str, object]:
    '''Exercise every configured R1--R7 level with synthetic data only.'''

    config = load_study_config(config_path)
    random_state = random.Random(seed)
    calibration_counts, calibration_bases = _configured_panels(
        config, calibration_per_level
    )
    test_counts, test_bases = _configured_panels(config, test_per_level)
    calibration_rows, calibration_labels, calibration_groups = _synthetic_rows(
        random_state, calibration_counts, base_by_group=calibration_bases
    )
    test_rows, test_labels, test_groups = _synthetic_rows(
        random_state, test_counts, base_by_group=test_bases
    )
    global_model = SplitConformalClassifier.fit(
        calibration_rows, calibration_labels, alpha=alpha
    )
    group_model = GroupConformalClassifier.fit(
        calibration_rows,
        calibration_labels,
        calibration_groups,
        alpha=alpha,
        min_group_size=calibration_per_level,
    )
    global_sets = global_model.predict_many(test_rows)
    group_sets = group_model.predict_many(test_rows, test_groups)
    confidences = [max(row) for row in test_rows]
    correctness = [
        int(max(range(len(row)), key=row.__getitem__) == label)
        for row, label in zip(test_rows, test_labels)
    ]
    global_group_coverage = _coverage_by_group(global_sets, test_labels, test_groups)
    mondrian_group_coverage = _coverage_by_group(group_sets, test_labels, test_groups)
    curve = risk_coverage_curve(confidences, correctness)
    dimension_tables = config['dimensions']
    if not isinstance(dimension_tables, Mapping):
        raise ValueError('validated config is missing dimensions')
    dimension_levels: dict[str, list[str]] = {}
    for code in DIMENSION_REGISTRY:
        table = dimension_tables[code]
        if not isinstance(table, Mapping) or not isinstance(table['levels'], list):
            raise ValueError(f'validated config has invalid {code} table')
        dimension_levels[code] = list(table['levels'])
    r7_table = dimension_tables['R7']
    if not isinstance(r7_table, Mapping) or not isinstance(r7_table['thresholds'], list):
        raise ValueError('validated config has invalid R7 thresholds')
    r7_policy: dict[str, dict[str, object]] = {}
    for level, threshold_value in zip(
        dimension_levels['R7'], r7_table['thresholds']
    ):
        report = selective_report(confidences, correctness, float(threshold_value))
        r7_policy[level] = {
            'threshold': report.threshold,
            'accepted': report.accepted,
            'answer_rate': report.coverage,
            'risk': report.risk,
        }
    study = config['study']
    scope = config['scope']
    if not isinstance(study, Mapping) or not isinstance(scope, Mapping):
        raise ValueError('validated config is missing study or scope')
    interactions = scope.get(
        'confirmatory_interactions', scope.get('interactions', [])
    )
    return {
        'artifact_kind': 'synthetic_r1_r7_software_smoke',
        'research_evidence': False,
        'study': study.get('name'),
        'dimensions_exercised': list(DIMENSION_REGISTRY),
        'dimension_levels': dimension_levels,
        'interactions_registered': interactions,
        'r7_policy': r7_policy,
        "seed": seed,
        "alpha": alpha,
        "calibration_size": len(calibration_rows),
        "test_size": len(test_rows),
        "global": {
            "threshold": global_model.threshold,
            "coverage": empirical_coverage(global_sets, test_labels),
            "group_coverage": global_group_coverage,
            "worst_group_coverage": min(global_group_coverage.values()),
            **prediction_set_efficiency(global_sets),
        },
        "mondrian": {
            "thresholds": dict(group_model.thresholds),
            "coverage": empirical_coverage(group_sets, test_labels),
            "group_coverage": mondrian_group_coverage,
            "worst_group_coverage": min(mondrian_group_coverage.values()),
            **prediction_set_efficiency(group_sets),
        },
        "point_confidence": {
            "accuracy": sum(correctness) / len(correctness),
            "brier": brier_score(confidences, correctness),
            "ece": expected_calibration_error(confidences, correctness),
            "aurc": area_under_risk_coverage_curve(curve),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run the synthetic experiment command."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument('--alpha', type=float, default=0.1)
    parser.add_argument('--config', type=Path, default=_DEFAULT_CONFIG)
    parser.add_argument('--calibration-per-level', type=int, default=12)
    parser.add_argument('--test-per-level', type=int, default=6)
    arguments = parser.parse_args(argv)
    print(
        json.dumps(
            run_demo(
                seed=arguments.seed,
                alpha=arguments.alpha,
                config_path=arguments.config,
                calibration_per_level=arguments.calibration_per_level,
                test_per_level=arguments.test_per_level,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
