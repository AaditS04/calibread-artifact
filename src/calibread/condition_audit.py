'''Audit whether model-specific R1/R3 condition records can be frozen.'''

from __future__ import annotations

import argparse
import json
from pathlib import Path
import tomllib
from typing import Mapping, Sequence


def _condition_counts(path: Path) -> dict[str, int]:
    counts = {'records': 0, 'r1_proxy_present': 0, 'r3_date_present': 0, 'both_present': 0}
    with path.open('r', encoding='utf-8') as stream:
        for line in stream:
            value = json.loads(line)
            if not isinstance(value, Mapping):
                continue
            counts['records'] += 1
            r1 = value.get('R1', {})
            r3 = value.get('R3', {})
            has_r1 = isinstance(r1, Mapping) and r1.get('proxy_value') is not None
            has_r3 = isinstance(r3, Mapping) and bool(r3.get('event_date') or r3.get('event_date_proxy'))
            counts['r1_proxy_present'] += int(has_r1)
            counts['r3_date_present'] += int(has_r3)
            counts['both_present'] += int(has_r1 and has_r3)
    return counts


def audit_readiness(
    config_path: str | Path = Path('configs/pilot.toml'),
    processed_root: str | Path = Path('data/processed'),
) -> dict[str, object]:
    with Path(config_path).open('rb') as stream:
        config = tomllib.load(stream)
    models = config.get('models', {})
    if not isinstance(models, Mapping):
        raise ValueError('config models must be a table')
    identifiers = [
        str(value)
        for key in ('family_slots', 'full_suite_family_ids')
        for value in models.get(key, [])
    ]
    unresolved_models = sorted({value for value in identifiers if 'tbd' in value.casefold()})
    dimensions = config.get('dimensions', {})
    r1 = dimensions.get('R1', {}) if isinstance(dimensions, Mapping) else {}
    mapping_hash = r1.get('level_mapping_manifest_hash') if isinstance(r1, Mapping) else None
    unresolved_r1_mapping = not mapping_hash or 'tbd' in str(mapping_hash).casefold()
    datasets: dict[str, object] = {}
    root = Path(processed_root)
    if root.is_dir():
        for seed_path in sorted(root.glob('*/condition_seeds.jsonl')):
            datasets[seed_path.parent.name] = _condition_counts(seed_path)
    complete_seed_count = sum(int(value['both_present']) for value in datasets.values())
    blockers: list[str] = []
    if unresolved_models:
        blockers.append('model snapshot identifiers are still placeholders')
    if unresolved_r1_mapping:
        blockers.append('R1 cutpoint mapping hash is not frozen')
    if complete_seed_count == 0:
        blockers.append('no seed currently contains both an R1 proxy and an R3 date')
    return {
        'config': str(config_path),
        'model_identifiers': sorted(set(identifiers)),
        'unresolved_model_identifiers': unresolved_models,
        'r1_mapping_hash': mapping_hash,
        'datasets': datasets,
        'complete_seed_count': complete_seed_count,
        'blockers': blockers,
        'freeze_ready': not blockers,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Audit R1/R3 model-condition readiness')
    parser.add_argument('--config', type=Path, default=Path('configs/pilot.toml'))
    parser.add_argument('--processed-root', type=Path, default=Path('data/processed'))
    parser.add_argument('--output', type=Path, default=Path('data/processed/CONDITION_READINESS.json'))
    args = parser.parse_args(argv)
    report = audit_readiness(args.config, args.processed_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report['freeze_ready'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
