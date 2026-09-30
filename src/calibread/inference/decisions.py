'''Post-hoc R7 answer/abstain decisions over frozen calibrated outputs.'''

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from ..dimensions import R7_THRESHOLD_LEVELS
from ..io import sha256_file
from .calibration import (
    _csv_text,
    _freeze_json,
    _freeze_text,
    load_calibrated_run,
)
from .config import InferenceConfig


R7_THRESHOLDS: tuple[float, ...] = tuple(R7_THRESHOLD_LEVELS)


def decide_r7(
    config: InferenceConfig,
    calibrator_path: str | Path,
    *,
    thresholds: Sequence[float] = R7_THRESHOLDS,
) -> Path:
    '''Write every frozen point-answer R7 policy without another model call.'''

    normalized_thresholds = tuple(float(value) for value in thresholds)
    if normalized_thresholds != R7_THRESHOLDS:
        raise ValueError(
            'the confirmatory R7 decision artifact requires thresholds '
            '0.50, 0.70, 0.90, 0.95, and 0.99 in that order'
        )
    rows, bundle = load_calibrated_run(config, calibrator_path)
    derived: list[dict[str, object]] = []
    for row in rows:
        supported = row['calibration_supported'] == '1'
        answer = row['raw_answer'].strip()
        model_abstained = row.get('normalized_answer', '').strip() == 'abstain'
        confidence = float(row['calibrated_confidence']) if supported else None
        for threshold in normalized_thresholds:
            if not supported:
                action = 'abstain'
                reason = 'unsupported_calibration_group'
            elif not answer:
                action = 'abstain'
                reason = 'empty_model_answer'
            elif model_abstained:
                action = 'abstain'
                reason = 'model_emitted_abstain'
            elif confidence is not None and confidence >= threshold:
                action = 'answer'
                reason = 'threshold_accepted'
            else:
                action = 'abstain'
                reason = 'below_threshold'
            derived.append(
                {
                    'run_id': row['run_id'],
                    'generation_id': row['generation_id'],
                    'example_id': row['example_id'],
                    'model_snapshot_id': row['model_snapshot_id'],
                    'evaluation_track': row['evaluation_track'],
                    'condition_hash': row['condition_hash'],
                    'condition_table_hash': row['condition_table_hash'],
                    'dataset_id': row['dataset_id'],
                    'split': row['split'],
                    'chain_id': row.get('chain_id', ''),
                    'R5': row['R5'],
                    'raw_answer': answer,
                    'correct': row['correct'],
                    'raw_score': row['raw_score'],
                    'raw_score_source': row['score_source'],
                    'calibrated_confidence': (
                        row['calibrated_confidence'] if supported else ''
                    ),
                    'threshold': f'{threshold:.2f}',
                    'R7': R7_THRESHOLD_LEVELS[threshold],
                    'action': action,
                    'decision_answer': answer if action == 'answer' else '',
                    'decision_correct': row['correct'] if action == 'answer' else '',
                    'reason': reason,
                    'calibration_supported': int(supported),
                    'calibration_group': row['calibration_group'],
                    'calibration_group_support_count': row[
                        'calibration_group_support_count'
                    ],
                    'score_kind': row['calibrated_score_kind'] if supported else '',
                    'score_source': (
                        row['calibrated_score_source'] if supported else ''
                    ),
                    'normalization_contract': (
                        row['calibrated_normalization_contract'] if supported else ''
                    ),
                    'calibrator_id': bundle.calibrator_id,
                    'calibrator_object_sha256': bundle.sha256,
                }
            )
    fields = (
        'run_id', 'generation_id', 'example_id', 'model_snapshot_id',
        'evaluation_track', 'condition_hash', 'condition_table_hash',
        'dataset_id', 'split',
        'chain_id', 'R5', 'raw_answer', 'correct', 'raw_score',
        'raw_score_source',
        'calibrated_confidence', 'threshold', 'R7', 'action',
        'decision_answer', 'decision_correct', 'reason',
        'calibration_supported', 'calibration_group',
        'calibration_group_support_count', 'score_kind', 'score_source',
        'normalization_contract', 'calibrator_id', 'calibrator_object_sha256',
    )
    target = config.run.output_dir / 'r7_decisions.csv'
    _freeze_text(target, _csv_text(derived, fields))
    manifest: Mapping[str, object] = {
        'schema_version': 1,
        'run_id': config.run.run_id,
        'split': config.run.split,
        'policy': 'open_ended_point_answer_or_abstain',
        'thresholds': list(normalized_thresholds),
        'input_rows': len(rows),
        'decision_rows': len(derived),
        'calibrated_results_sha256': sha256_file(
            config.run.output_dir / 'calibrated_results.csv'
        ),
        'calibrator_id': bundle.calibrator_id,
        'calibrator_object_sha256': bundle.sha256,
        'condition_table_hash': rows[0]['condition_table_hash'] if rows else None,
        'r7_decisions_sha256': sha256_file(target),
        'claim_limit': (
            'Open-ended generations support point answer/abstain policies only; '
            'these rows do not claim finite-label prediction-set coverage.'
        ),
    }
    _freeze_json(config.run.output_dir / 'R7_DECISION_MANIFEST.json', manifest)
    return target


__all__ = ['R7_THRESHOLDS', 'decide_r7']
