'''Compact R5 report over deterministic scored results.'''

from __future__ import annotations

from collections import defaultdict
import csv
import json
from pathlib import Path

from .config import InferenceConfig
from .scoring import verify_scored_results


def _summary(rows: list[dict[str, str]]) -> dict[str, object]:
    count = len(rows)
    correct = sum(int(row['correct']) for row in rows)
    abstained = sum(int(row['abstained']) for row in rows)
    return {
        'n': count,
        'accuracy': correct / count if count else None,
        'mean_token_f1': sum(float(row['token_f1']) for row in rows) / count if count else None,
        'abstention_rate': abstained / count if count else None,
        'mean_raw_score': sum(float(row['score']) for row in rows) / count if count else None,
        'estimated_cost_usd': sum(float(row['estimated_cost_usd'] or 0) for row in rows),
    }


def report_run(config: InferenceConfig) -> Path:
    verification = verify_scored_results(config)
    source = config.run.output_dir / 'scored_results.csv'
    with source.open('r', encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError('scored result file is empty')
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row['dataset_id'], row['R5'])].append(row)
    report = {
        'run_id': config.run.run_id,
        'parent_experiment_id': config.run.parent_experiment_id,
        'split': config.run.split,
        'completion_verification': verification,
        'overall': _summary(rows),
        'by_dataset_and_r5': {
            f'{dataset_id}:{level}': _summary(values)
            for (dataset_id, level), values in sorted(grouped.items())
        },
        'claim_limit': (
            'Raw-score report only. Fit and freeze a calibration model on the calibration split '
            'before reporting probability calibration or R7 results.'
        ),
    }
    target = config.run.output_dir / 'r5_report.json'
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return target
