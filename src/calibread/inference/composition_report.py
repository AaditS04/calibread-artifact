'''Chain-aware R5 composition reporting over cached inference outputs.'''

from __future__ import annotations

from collections import defaultdict
import csv
import hashlib
import json
from math import isfinite
from pathlib import Path
import random
from typing import Callable, Mapping, Sequence

from ..composition import composition_report
from ..correctness import exact_match
from ..io import read_jsonl, sha256_file
from ..schema import Example, GenerationRecord, WorkloadRecord
from .config import InferenceConfig
from .runner import verify_run_completeness


_EQUIVALENCE_BAND = (-0.05, 0.05)


def _percentile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError('cannot take a percentile of an empty sequence')
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = probability * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _interval(values: Sequence[float]) -> list[float] | None:
    if not values:
        return None
    return [_percentile(values, 0.025), _percentile(values, 0.975)]


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(',', ':')
    ).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _load_inputs(
    config: InferenceConfig,
) -> tuple[dict[str, Example], dict[str, tuple[str, WorkloadRecord]]]:
    examples: dict[str, Example] = {}
    workloads: dict[str, tuple[str, WorkloadRecord]] = {}
    for dataset in config.datasets:
        for value in read_jsonl(dataset.examples):
            example = Example.from_dict(value)
            if example.example_id in examples:
                raise ValueError(f'duplicate Example ID {example.example_id}')
            examples[example.example_id] = example
        for value in read_jsonl(dataset.workloads):
            workload = WorkloadRecord.from_dict(value)
            if workload.example_id in workloads:
                raise ValueError(f'duplicate WorkloadRecord ID {workload.example_id}')
            workloads[workload.example_id] = (dataset.dataset_id, workload)
    if set(examples) != set(workloads):
        missing_workloads = sorted(set(examples) - set(workloads))[:5]
        missing_examples = sorted(set(workloads) - set(examples))[:5]
        raise ValueError(
            'Example/WorkloadRecord identities differ; '
            f'missing workloads={missing_workloads}, missing examples={missing_examples}'
        )
    for identifier, example in examples.items():
        workload = workloads[identifier][1]
        workload_r5 = workload.dimensions['R5']
        example_r5 = example.dimension_values()['R5']
        if (
            workload.question != example.question
            or workload.accepted_answers != example.accepted_answers
            or workload_r5.raw != example_r5.raw
            or workload_r5.level != example_r5.level
        ):
            raise ValueError(
                f'Example/WorkloadRecord content mismatch for {identifier}'
            )
    return examples, workloads


def _read_scored(
    path: Path, config: InferenceConfig
) -> dict[str, dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f'missing scored results: {path}')
    with path.open('r', encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    required = {
        'run_id', 'generation_id', 'example_id', 'dataset_id',
        'model_snapshot_id', 'split', 'raw_answer', 'correct', 'score',
        'score_kind', 'score_source',
    }
    if not rows or not required <= set(rows[0]):
        raise ValueError(f'scored results must contain {sorted(required)}')
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        identifier = row['example_id']
        if identifier in result:
            raise ValueError(f'duplicate scored result for {identifier}')
        if row['correct'] not in {'0', '1'}:
            raise ValueError(f'invalid correctness value for {identifier}')
        if row['run_id'] != config.run.run_id or row['split'] != config.run.split:
            raise ValueError(f'scored run/split identity mismatch for {identifier}')
        if row['score_kind'] != 'raw' or not row['score_source'].strip():
            raise ValueError(f'invalid raw-score identity for {identifier}')
        if not row['score'].strip() or not isfinite(float(row['score'])):
            raise ValueError(f'invalid raw score for {identifier}')
        result[identifier] = row
    return result


def _read_calibrated(
    path: Path | None, config: InferenceConfig
) -> tuple[dict[str, float], dict[str, object]]:
    if path is None:
        return {}, {}
    if not path.is_file():
        raise FileNotFoundError(f'missing calibrated results: {path}')
    manifest_path = path.parent / 'CALIBRATED_RESULTS_MANIFEST.json'
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f'missing CALIBRATED_RESULTS_MANIFEST.json beside {path}'
        )
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if not isinstance(manifest, Mapping):
        raise ValueError('CALIBRATED_RESULTS_MANIFEST.json must contain an object')
    if manifest.get('schema_version') != 1:
        raise ValueError('unsupported calibrated-results manifest schema')
    artifact_hash_field = {
        'calibrated_results.csv': 'calibrated_results_sha256',
        'calibrated_evaluation.csv': 'calibrated_evaluation_sha256',
    }.get(path.name)
    if artifact_hash_field is None:
        raise ValueError(
            'calibrated input must be calibrated_results.csv or '
            'calibrated_evaluation.csv'
        )
    if manifest.get(artifact_hash_field) != sha256_file(path):
        raise ValueError('calibrated results hash does not match its frozen manifest')
    if (
        manifest.get('run_id') != config.run.run_id
        or manifest.get('split') != config.run.split
    ):
        raise ValueError('calibrated results manifest has the wrong run or split')
    with path.open('r', encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError('calibrated result file is empty')
    expected_rows_field = (
        'input_rows'
        if path.name == 'calibrated_results.csv'
        else 'supported_rows'
    )
    expected_rows = manifest.get(expected_rows_field)
    if (
        isinstance(expected_rows, bool)
        or not isinstance(expected_rows, int)
        or expected_rows != len(rows)
    ):
        raise ValueError('calibrated row count does not match its frozen manifest')
    confidence_field = (
        'calibrated_confidence'
        if 'calibrated_confidence' in rows[0]
        else 'confidence'
        if 'confidence' in rows[0]
        else None
    )
    if confidence_field is None or 'example_id' not in rows[0]:
        raise ValueError(
            'calibrated results require example_id and calibrated_confidence'
        )
    calibrated_kind_field = (
        'calibrated_score_kind'
        if 'calibrated_score_kind' in rows[0]
        else 'score_kind'
    )
    calibrated_source_field = (
        'calibrated_score_source'
        if 'calibrated_score_source' in rows[0]
        else 'score_source'
    )
    required_identity = {
        calibrated_kind_field,
        calibrated_source_field,
        'calibrator_id',
        'condition_table_hash',
    }
    if not required_identity <= set(rows[0]):
        raise ValueError('calibrated results lack probability-score identity fields')
    object_hash_field = (
        'calibration_object_hash'
        if 'calibration_object_hash' in rows[0]
        else 'calibrator_object_sha256'
        if 'calibrator_object_sha256' in rows[0]
        else None
    )
    if object_hash_field is None:
        raise ValueError('calibrated results lack a calibrator object hash')

    confidences: dict[str, float] = {}
    calibrator_ids: set[str] = set()
    object_hashes: set[str] = set()
    score_sources: set[str] = set()
    condition_table_hashes: set[str] = set()
    for row in rows:
        identifier = row['example_id']
        if identifier in confidences:
            raise ValueError(f'duplicate calibrated result for {identifier}')
        if row.get('calibration_supported', '1') != '1':
            raise ValueError(
                'composition probabilities require calibration support for every row'
            )
        if row.get('run_id', config.run.run_id) != config.run.run_id:
            raise ValueError(f'calibrated run identity mismatch for {identifier}')
        if row.get('split', config.run.split) != config.run.split:
            raise ValueError(f'calibrated split identity mismatch for {identifier}')
        if row.get(calibrated_kind_field) != 'probability':
            raise ValueError(
                f'calibrated result is not a probability for {identifier}'
            )
        raw_confidence = row[confidence_field].strip()
        confidence = float(raw_confidence) if raw_confidence else float('nan')
        if not isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise ValueError(f'calibrated confidence outside [0, 1] for {identifier}')
        confidences[identifier] = confidence
        calibrator_ids.add(row.get('calibrator_id', '').strip())
        object_hashes.add(row.get(object_hash_field, '').strip())
        score_sources.add(row.get(calibrated_source_field, '').strip())
        condition_table_hashes.add(row.get('condition_table_hash', '').strip())
    if (
        len(calibrator_ids) != 1
        or '' in calibrator_ids
        or len(object_hashes) != 1
        or '' in object_hashes
        or len(score_sources) != 1
        or '' in score_sources
        or len(condition_table_hashes) != 1
        or '' in condition_table_hashes
    ):
        raise ValueError('calibrated results mix or omit calibration identities')
    calibrator_id = next(iter(calibrator_ids))
    object_hash = next(iter(object_hashes))
    if (
        manifest.get('calibrator_id') != calibrator_id
        or manifest.get('calibrator_object_sha256') != object_hash
        or manifest.get('condition_table_hash')
        != next(iter(condition_table_hashes))
    ):
        raise ValueError('calibrated row identity does not match its frozen manifest')
    return confidences, {
        'calibrator_id': calibrator_id,
        'calibration_object_hash': object_hash,
        'score_source': next(iter(score_sources)),
        'condition_table_hash': next(iter(condition_table_hashes)),
        'calibrated_results_manifest_sha256': sha256_file(manifest_path),
    }


def _clusters(observations: Sequence[dict[str, object]]) -> dict[str, str]:
    '''Return connected-component IDs for chains sharing any atomic probe.'''

    parent = list(range(len(observations)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(first: int, second: int) -> None:
        left, right = find(first), find(second)
        if left != right:
            parent[max(left, right)] = min(left, right)

    atom_owner: dict[str, int] = {}
    for index, observation in enumerate(observations):
        for atom_id in observation['constituent_ids']:  # type: ignore[union-attr]
            identifier = str(atom_id)
            if identifier in atom_owner:
                union(index, atom_owner[identifier])
            else:
                atom_owner[identifier] = index
    components: dict[int, list[str]] = defaultdict(list)
    for index, observation in enumerate(observations):
        components[find(index)].append(str(observation['chain_id']))
    component_ids = {
        root: 'r5cc:' + _canonical_hash(sorted(chain_ids))[:20]
        for root, chain_ids in components.items()
    }
    return {
        str(observation['chain_id']): component_ids[find(index)]
        for index, observation in enumerate(observations)
    }


def _metrics(rows: Sequence[dict[str, object]]) -> dict[str, object]:
    atom_correctness = [row['atom_correctness'] for row in rows]
    chain_correctness = [row['chain_correct'] for row in rows]
    has_confidence = all(row.get('atom_confidences') is not None for row in rows)
    atom_confidences = (
        [row['atom_confidences'] for row in rows] if has_confidence else None
    )
    report = composition_report(
        atom_correctness,  # type: ignore[arg-type]
        chain_correctness,  # type: ignore[arg-type]
        atom_confidences,  # type: ignore[arg-type]
    ).to_dict()
    atom_values = [
        int(value)
        for row in rows
        for value in row['atom_correctness']  # type: ignore[union-attr]
    ]
    depths = [int(row['depth']) for row in rows]
    mean_depth = sum(depths) / len(depths)
    atomic_accuracy = sum(atom_values) / len(atom_values)
    observed_error = 1.0 - float(report['chain_accuracy'])
    atomic_error = 1.0 - atomic_accuracy
    factorized_error = sum(
        1.0 - (1.0 - atomic_error) ** depth for depth in depths
    ) / len(depths)
    residual = observed_error - factorized_error
    report.update(
        {
            'atomic_probe_occurrences': len(atom_values),
            'unique_atomic_probes': len(
                {
                    str(identifier)
                    for row in rows
                    for identifier in row['constituent_ids']  # type: ignore[union-attr]
                }
            ),
            'mean_depth': mean_depth,
            'atomic_accuracy': atomic_accuracy,
            'observed_chain_error': observed_error,
            'factorized_predicted_error': factorized_error,
            'factorized_residual': residual,
            'factorized_equivalence_band': list(_EQUIVALENCE_BAND),
            'factorized_within_equivalence_band': (
                _EQUIVALENCE_BAND[0] <= residual <= _EQUIVALENCE_BAND[1]
            ),
            'empirical_atom_error_union_bound': sum(
                min(1.0, depth * atomic_error) for depth in depths
            ) / len(depths),
        }
    )
    return report


def _bootstrap_intervals(
    rows: Sequence[dict[str, object]], *, samples: int, seed: int
) -> dict[str, list[float] | None]:
    if samples < 1:
        raise ValueError('bootstrap_samples must be positive')
    by_cluster: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_cluster[str(row['cluster_id'])].append(row)
    clusters = sorted(by_cluster)
    random_state = random.Random(seed)
    draws: dict[str, list[float]] = defaultdict(list)
    extractors: Mapping[str, Callable[[dict[str, object]], float | None]] = {
        'chain_accuracy': lambda value: float(value['chain_accuracy']),
        'all_atoms_correct_rate': lambda value: float(value['all_atoms_correct_rate']),
        'synthesis_loss': lambda value: (
            None if value['synthesis_loss'] is None else float(value['synthesis_loss'])
        ),
        'factorized_residual': lambda value: float(value['factorized_residual']),
        'product_calibration_gap': lambda value: (
            None
            if value['product_calibration_gap'] is None
            else float(value['product_calibration_gap'])
        ),
    }
    for _ in range(samples):
        sampled: list[dict[str, object]] = []
        for _ in clusters:
            sampled.extend(by_cluster[random_state.choice(clusters)])
        metrics = _metrics(sampled)
        for name, extractor in extractors.items():
            value = extractor(metrics)
            if value is not None:
                draws[name].append(value)
    return {name: _interval(draws.get(name, [])) for name in extractors}


def build_composition_report(
    config: InferenceConfig,
    *,
    calibrated_path: Path | None = None,
    bootstrap_samples: int = 2000,
) -> Path:
    '''Build the frozen R5 chain report without making new model calls.'''

    run_verification = verify_run_completeness(config)
    examples, workloads = _load_inputs(config)
    scored_path = config.run.output_dir / 'scored_results.csv'
    scored = _read_scored(scored_path, config)
    generations = [
        GenerationRecord.from_dict(value)
        for value in read_jsonl(config.run.output_dir / 'generations.jsonl')
    ]
    generations_by_id = {value.example_id: value for value in generations}
    if len(generations_by_id) != len(generations):
        raise ValueError('complete generation cache contains duplicate example IDs')
    if set(scored) != set(generations_by_id):
        raise ValueError(
            'scored results do not match the complete generation cache'
        )
    for identifier, row in scored.items():
        generation = generations_by_id[identifier]
        dataset_id, _workload = workloads[identifier]
        expected_correct = int(
            exact_match(generation.raw_text.strip(), examples[identifier].accepted_answers)
        )
        if (
            row['generation_id'] != generation.generation_id
            or row['model_snapshot_id'] != generation.model_snapshot_id
            or row['dataset_id'] != dataset_id
            or row['raw_answer'] != generation.raw_text.strip()
            or float(row['score']) != generation.score
            or row['score_source'] != generation.score_source
            or int(row['correct']) != expected_correct
        ):
            raise ValueError(
                f'scored result does not match its generation and gold data: '
                f'{identifier}'
            )
    confidences, calibration_identity = _read_calibrated(
        calibrated_path, config
    )
    if confidences and set(confidences) != set(scored):
        raise ValueError('calibrated and scored result identities differ')

    observations: list[dict[str, object]] = []
    for example_id, chain_row in scored.items():
        if example_id not in workloads or example_id not in examples:
            raise ValueError(f'scored example {example_id} is absent from configured inputs')
        dataset_id, workload = workloads[example_id]
        depth = int(workload.dimensions['R5'].raw)
        if depth < 2:
            continue
        constituents = tuple(workload.constituent_example_ids)
        if len(constituents) != depth:
            raise ValueError(f'chain {example_id} has an invalid constituent count')
        missing = [identifier for identifier in constituents if identifier not in scored]
        if missing:
            raise ValueError(
                f'chain-complete R5 report requires every atom for {example_id}; '
                f'missing {missing[:5]}'
            )
        non_atomic = [
            identifier
            for identifier in constituents
            if int(workloads[identifier][1].dimensions['R5'].raw) != 1
        ]
        if non_atomic:
            raise ValueError(
                f'chain {example_id} contains non-atomic constituents: '
                f'{non_atomic[:5]}'
            )
        wrong_split = [
            identifier
            for identifier in constituents
            if examples[identifier].split != examples[example_id].split
        ]
        if wrong_split:
            raise ValueError(
                f'chain {example_id} crosses data splits through constituents: '
                f'{wrong_split[:5]}'
            )
        atom_correctness = [int(scored[item]['correct']) for item in constituents]
        observations.append(
            {
                'chain_id': workload.chain_id or example_id,
                'composite_example_id': example_id,
                'dataset_id': dataset_id,
                'split': examples[example_id].split,
                'level': workload.dimensions['R5'].level,
                'depth': depth,
                'constituent_ids': constituents,
                'atom_correctness': atom_correctness,
                'all_atoms_correct': int(all(atom_correctness)),
                'chain_correct': int(chain_row['correct']),
                'atom_confidences': (
                    [confidences[item] for item in constituents]
                    if confidences
                    else None
                ),
                'chain_confidence': confidences.get(example_id),
            }
        )
    if not observations:
        raise ValueError('no complete multi-hop chains are present in scored results')
    if any(row['split'] != config.run.split for row in observations):
        raise ValueError('composition rows do not match the configured split')
    chain_ids = [str(row['chain_id']) for row in observations]
    if len(chain_ids) != len(set(chain_ids)):
        raise ValueError('composition inputs contain duplicate chain IDs')

    cluster_ids = _clusters(observations)
    for row in observations:
        row['cluster_id'] = cluster_ids[str(row['chain_id'])]

    groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in observations:
        groups[(str(row['dataset_id']), str(row['level']))].append(row)

    seed = config.run.seed
    report_groups: dict[str, object] = {}
    for index, ((dataset_id, level), rows) in enumerate(sorted(groups.items())):
        values = _metrics(rows)
        values['cluster_count'] = len({str(row['cluster_id']) for row in rows})
        values['confidence_intervals_95'] = _bootstrap_intervals(
            rows, samples=bootstrap_samples, seed=seed + index
        )
        report_groups[f'{dataset_id}:{level}'] = values

    overall = _metrics(observations)
    overall['cluster_count'] = len({str(row['cluster_id']) for row in observations})
    overall['confidence_intervals_95'] = _bootstrap_intervals(
        observations, samples=bootstrap_samples, seed=seed + len(groups)
    )
    report = {
        'report_version': 1,
        'run_id': config.run.run_id,
        'parent_experiment_id': getattr(config.run, 'parent_experiment_id', None),
        'split': config.run.split,
        'run_verification': run_verification,
        'scored_results': str(scored_path),
        'scored_results_sha256': sha256_file(scored_path),
        'calibrated_results': None if calibrated_path is None else str(calibrated_path),
        'calibrated_results_sha256': (
            None if calibrated_path is None else sha256_file(calibrated_path)
        ),
        'calibration_identity': calibration_identity,
        'bootstrap': {
            'samples': bootstrap_samples,
            'seed': seed,
            'unit': 'connected_component_of_chains_sharing_atomic_probes',
        },
        'overall': overall,
        'by_dataset_and_r5': report_groups,
        'claim_limits': [
            'Factorized and union-bound values are diagnostics, not independence facts or guarantees.',
            'SOCRATES and MuSiQue must be interpreted separately because source and depth are confounded.',
            'Synthesis loss is descriptive because conditioning on all atoms correct selects examples.',
        ],
    }
    target = config.run.output_dir / 'r5_composition_report.json'
    temporary = target.with_name(f'.{target.name}.tmp')
    temporary.write_text(
        json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n'
    )
    temporary.replace(target)

    audit_path = config.run.output_dir / 'r5_chain_results.csv'
    with audit_path.open('w', encoding='utf-8', newline='') as stream:
        fields = (
            'chain_id', 'composite_example_id', 'dataset_id', 'split', 'R5', 'depth',
            'cluster_id', 'constituent_example_ids', 'atom_correctness',
            'all_atoms_correct', 'chain_correct', 'atom_confidences', 'chain_confidence',
        )
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in sorted(observations, key=lambda value: str(value['chain_id'])):
            writer.writerow(
                {
                    'chain_id': row['chain_id'],
                    'composite_example_id': row['composite_example_id'],
                    'dataset_id': row['dataset_id'],
                    'split': row['split'],
                    'R5': row['level'],
                    'depth': row['depth'],
                    'cluster_id': row['cluster_id'],
                    'constituent_example_ids': json.dumps(row['constituent_ids']),
                    'atom_correctness': json.dumps(row['atom_correctness']),
                    'all_atoms_correct': row['all_atoms_correct'],
                    'chain_correct': row['chain_correct'],
                    'atom_confidences': (
                        ''
                        if row['atom_confidences'] is None
                        else json.dumps(row['atom_confidences'])
                    ),
                    'chain_confidence': (
                        '' if row['chain_confidence'] is None else row['chain_confidence']
                    ),
                }
            )
    return target
