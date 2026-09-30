'''Held-out probability-calibration and selective-risk reporting for R5.'''

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
import json
from pathlib import Path
from typing import Iterable

from ..io import sha256_file
from ..metrics import (
    adaptive_calibration_error,
    area_under_risk_coverage_curve,
    binary_log_loss,
    brier_score,
    correctness_auroc,
    expected_calibration_error,
    reliability_bins,
    risk_coverage_curve,
    selective_report,
)
from .calibration import _freeze_json, load_calibrated_run
from .config import InferenceConfig
from .decisions import R7_THRESHOLDS, decide_r7


def _raw_auroc(scores: Iterable[float], labels: Iterable[int]) -> float | None:
    values = list(zip((float(value) for value in scores), labels))
    positives = sum(label for _, label in values)
    negatives = len(values) - positives
    if positives == 0 or negatives == 0:
        return None
    ranked = sorted(values)
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


def _metrics(rows: list[dict[str, str]]) -> dict[str, object]:
    confidences = [float(row['calibrated_confidence']) for row in rows]
    raw_scores = [float(row['raw_score']) for row in rows]
    labels = [int(row['correct']) for row in rows]
    curve = risk_coverage_curve(confidences, labels)
    ece = expected_calibration_error(confidences, labels, n_bins=10)
    ace = adaptive_calibration_error(confidences, labels, n_bins=10)
    aurc = area_under_risk_coverage_curve(curve)
    result: dict[str, object] = {
        'n': len(rows),
        'correct': sum(labels),
        'accuracy': sum(labels) / len(labels),
        'mean_calibrated_confidence': sum(confidences) / len(confidences),
        'brier': brier_score(confidences, labels),
        'log_loss': binary_log_loss(confidences, labels),
        'ece': ece,
        'ece_10': ece,
        'ace': ace,
        'ace_10': ace,
        'raw_score_correctness_auroc': _raw_auroc(raw_scores, labels),
        'aurc': aurc,
        'risk_coverage_aurc': aurc,
        'risk_coverage_curve': [asdict(value) for value in curve],
        'reliability_bins_10': [
            asdict(value) for value in reliability_bins(confidences, labels, n_bins=10)
        ],
        'r7_thresholds': {
            f'{threshold:.2f}': asdict(
                selective_report(confidences, labels, threshold)
            )
            for threshold in R7_THRESHOLDS
        },
    }
    try:
        auroc = correctness_auroc(confidences, labels)
        result['correctness_auroc'] = auroc
        result['calibrated_correctness_auroc'] = auroc
    except ValueError:
        result['correctness_auroc'] = None
        result['calibrated_correctness_auroc'] = None
    return result


def calibration_report(
    config: InferenceConfig, calibrator_path: str | Path
) -> Path:
    '''Write a deterministic calibration report for one complete scored run.'''

    rows, bundle = load_calibrated_run(config, calibrator_path)
    decision_path = decide_r7(config, bundle.path)
    supported = [row for row in rows if row['calibration_supported'] == '1']
    if not supported:
        raise ValueError('no target rows belong to a calibration-supported group')
    unsupported_counts = Counter(
        row['calibration_group']
        for row in rows
        if row['calibration_supported'] != '1'
    )
    by_r5: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_dataset_r5: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in supported:
        by_r5[row['R5']].append(row)
        by_dataset_r5[f"{row['dataset_id']}:{row['R5']}"] .append(row)

    evaluation_role = {
        'development': 'development_diagnostic',
        'calibration': 'in_sample_fit_diagnostic_not_held_out_evidence',
        'test': 'held_out_test_evaluation',
    }[config.run.split]
    report: dict[str, object] = {
        'schema_version': 1,
        'run_id': config.run.run_id,
        'evaluation_split': config.run.split,
        'evaluation_role': evaluation_role,
        'calibrator_id': bundle.calibrator_id,
        'calibrator_method': bundle.payload['method'],
        'calibrator_object_sha256': bundle.sha256,
        'calibrator_condition_sha256': bundle.condition_sha256,
        'total_rows': len(rows),
        'supported_rows': len(supported),
        'unsupported_rows': len(rows) - len(supported),
        'unsupported_groups': dict(sorted(unsupported_counts.items())),
        'overall': _metrics(supported),
        'by_r5': {
            key: _metrics(value) for key, value in sorted(by_r5.items())
        },
        'by_dataset_and_r5': {
            key: _metrics(value) for key, value in sorted(by_dataset_r5.items())
        },
        'artifacts': {
            'calibrator': str(bundle.path),
            'calibrated_results': str(
                config.run.output_dir / 'calibrated_results.csv'
            ),
            'calibrated_results_sha256': sha256_file(
                config.run.output_dir / 'calibrated_results.csv'
            ),
            'r7_decisions': str(decision_path),
            'r7_decisions_sha256': sha256_file(decision_path),
        },
        'interpretation': (
            'Probability metrics use only groups observed by the frozen '
            'calibrator. Unsupported groups fail closed to abstention and are '
            'reported separately. Test results are held-out evidence only when '
            'evaluation_split is test and no choices were changed after unblinding.'
        ),
    }
    target = config.run.output_dir / 'calibration_report.json'
    _freeze_json(target, report)
    return target


__all__ = ['calibration_report']
