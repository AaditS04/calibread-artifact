'''Dependency-free fitting, freezing, and application of R5 calibrators.'''

from __future__ import annotations

from collections import Counter
import csv
from dataclasses import dataclass
import hashlib
import json
from math import fsum, isclose, isfinite
import os
from pathlib import Path
import tempfile
from typing import Iterable, Mapping, Sequence

from ..correctness import exact_match, normalize_answer
from ..io import read_jsonl, sha256_file
from ..metrics import (
    adaptive_calibration_error,
    binary_log_loss,
    brier_score,
    correctness_auroc,
    expected_calibration_error,
)
from ..schema import Example, GenerationRecord
from .config import InferenceConfig
from .runner import verify_run_completeness


CALIBRATOR_SCHEMA_VERSION = 1
CALIBRATED_RESULTS_SCHEMA_VERSION = 1
_CALIBRATOR_FILENAME = 'CALIBRATOR.json'


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
        allow_nan=False,
    ).encode('utf-8')


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _json_text(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + '\n'


def _freeze_text(path: Path, value: str) -> None:
    '''Create an immutable derived artifact, accepting an identical rerun.'''

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding='utf-8') == value:
            return
        raise FileExistsError(
            f'frozen artifact already exists with different content: {path}'
        )
    handle, temporary_name = tempfile.mkstemp(
        prefix=f'.{path.name}.', suffix='.tmp', dir=path.parent, text=True
    )
    try:
        with os.fdopen(handle, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _freeze_json(path: Path, value: Mapping[str, object]) -> None:
    _freeze_text(path, _json_text(dict(value)))


def _csv_text(rows: Sequence[Mapping[str, object]], fields: Sequence[str]) -> str:
    from io import StringIO

    stream = StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, '') for field in fields})
    return stream.getvalue()


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f'missing scored artifact: {path}')
    with path.open('r', encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(f'CSV artifact is empty: {path}')
    return rows


def fit_weighted_isotonic(
    scores: Iterable[float],
    correctness: Iterable[bool | int],
    weights: Iterable[float] | None = None,
) -> tuple[dict[str, float | int], ...]:
    '''Fit a nondecreasing weighted isotonic mapping with deterministic PAVA.

    Tied scores are combined before the pool-adjacent-violators algorithm is
    applied.  Returned blocks are sufficient to reproduce predictions without
    NumPy, SciPy, or scikit-learn.
    '''

    score_values = [float(value) for value in scores]
    label_values: list[int] = []
    for value in correctness:
        if value in (True, 1):
            label_values.append(1)
        elif value in (False, 0):
            label_values.append(0)
        else:
            raise ValueError('correctness must contain only booleans or 0/1 values')
    weight_values = (
        [1.0] * len(score_values)
        if weights is None
        else [float(value) for value in weights]
    )
    if not score_values:
        raise ValueError('isotonic fitting requires at least one observation')
    if len(score_values) != len(label_values) or len(score_values) != len(weight_values):
        raise ValueError('scores, correctness, and weights must have equal length')
    if not all(isfinite(value) for value in score_values):
        raise ValueError('scores must contain only finite values')
    if not all(isfinite(value) and value > 0.0 for value in weight_values):
        raise ValueError('weights must contain only finite positive values')

    observations = sorted(
        zip(score_values, label_values, weight_values),
        key=lambda value: (value[0], value[1], value[2]),
    )
    tied: list[dict[str, float | int]] = []
    start = 0
    while start < len(observations):
        end = start + 1
        while end < len(observations) and observations[end][0] == observations[start][0]:
            end += 1
        group = observations[start:end]
        total_weight = fsum(value[2] for value in group)
        positive_weight = fsum(value[1] * value[2] for value in group)
        tied.append(
            {
                'lower_score': group[0][0],
                'upper_score': group[0][0],
                'weight': total_weight,
                'positive_weight': positive_weight,
                'observation_count': len(group),
            }
        )
        start = end

    blocks: list[dict[str, float | int]] = []
    for value in tied:
        blocks.append(dict(value))
        while len(blocks) >= 2:
            left = blocks[-2]
            right = blocks[-1]
            left_mean = float(left['positive_weight']) / float(left['weight'])
            right_mean = float(right['positive_weight']) / float(right['weight'])
            if left_mean <= right_mean:
                break
            merged = {
                'lower_score': float(left['lower_score']),
                'upper_score': float(right['upper_score']),
                'weight': fsum((float(left['weight']), float(right['weight']))),
                'positive_weight': fsum(
                    (float(left['positive_weight']), float(right['positive_weight']))
                ),
                'observation_count': int(left['observation_count'])
                + int(right['observation_count']),
            }
            blocks[-2:] = [merged]

    result: list[dict[str, float | int]] = []
    for block in blocks:
        result.append(
            {
                'lower_score': float(block['lower_score']),
                'upper_score': float(block['upper_score']),
                'prediction': float(block['positive_weight']) / float(block['weight']),
                'weight': float(block['weight']),
                'positive_weight': float(block['positive_weight']),
                'observation_count': int(block['observation_count']),
            }
        )
    return tuple(result)


def r5_level_balanced_weights(
    levels: Iterable[str],
) -> tuple[tuple[float, ...], dict[str, object]]:
    '''Return inverse-frequency weights for a uniform observed-R5 target mixture.'''

    values = [str(value).strip() for value in levels]
    if not values or any(not value for value in values):
        raise ValueError('R5 levels must be a nonempty sequence of nonempty strings')
    counts = Counter(values)
    observation_count = len(values)
    level_count = len(counts)
    unscaled = [
        observation_count / (level_count * counts[level]) for level in values
    ]
    scale = observation_count / fsum(unscaled)
    per_level = {
        level: (observation_count / (level_count * count)) * scale
        for level, count in sorted(counts.items())
    }
    weights = tuple(per_level[level] for level in values)
    summary: dict[str, object] = {
        'scheme': 'inverse_r5_level_frequency',
        'target_mixture': 'uniform_over_observed_r5_levels',
        'normalization': 'sum_of_example_weights_equals_support_count',
        'observed_level_counts': dict(sorted(counts.items())),
        'per_example_weight_by_level': per_level,
        'observed_level_count': level_count,
        'total_weight': fsum(weights),
    }
    return weights, summary


def predict_isotonic(
    blocks: Sequence[Mapping[str, object]], score: float
) -> float:
    '''Apply frozen PAVA blocks with clipping and linear gap interpolation.'''

    value = float(score)
    if not isfinite(value):
        raise ValueError('raw score must be finite')
    if not blocks:
        raise ValueError('isotonic calibrator has no fitted blocks')
    normalized = [
        (
            float(block['lower_score']),
            float(block['upper_score']),
            float(block['prediction']),
        )
        for block in blocks
    ]
    if value <= normalized[0][0]:
        return normalized[0][2]
    for index, (lower, upper, prediction) in enumerate(normalized):
        if lower <= value <= upper:
            return prediction
        if value < lower:
            prior_upper = normalized[index - 1][1]
            prior_prediction = normalized[index - 1][2]
            fraction = (value - prior_upper) / (lower - prior_upper)
            return prior_prediction + fraction * (prediction - prior_prediction)
    return normalized[-1][2]


def _resolve_calibrator_path(path: str | Path) -> Path:
    target = Path(path)
    if target.is_dir() or (not target.suffix and target.name != _CALIBRATOR_FILENAME):
        target = target / _CALIBRATOR_FILENAME
    return target


@dataclass(frozen=True)
class FrozenCalibrator:
    path: Path
    sha256: str
    payload: Mapping[str, object]

    @property
    def calibrator_id(self) -> str:
        return str(self.payload['calibrator_id'])

    @property
    def condition_sha256(self) -> str:
        return str(self.payload['condition_identity_sha256'])

    @property
    def raw_score_source(self) -> str:
        return str(self.payload['raw_score_source'])

    def predict(self, score: float) -> float:
        parameters = self.payload['fitted_parameters']
        if not isinstance(parameters, Mapping):
            raise ValueError('invalid fitted_parameters in calibrator')
        blocks = parameters.get('blocks')
        if not isinstance(blocks, list):
            raise ValueError('invalid fitted block list in calibrator')
        return predict_isotonic(blocks, score)

    def group_support(self, dataset_id: str, r5_level: str) -> int:
        groups = self.payload.get('supported_groups')
        if not isinstance(groups, list):
            raise ValueError('invalid supported_groups in calibrator')
        for group in groups:
            if (
                isinstance(group, Mapping)
                and group.get('dataset_id') == dataset_id
                and group.get('R5') == r5_level
            ):
                return int(group['count'])
        return 0


def load_calibrator(path: str | Path) -> FrozenCalibrator:
    source = _resolve_calibrator_path(path)
    if not source.is_file():
        raise FileNotFoundError(f'missing calibrator: {source}')
    payload = json.loads(source.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError('CALIBRATOR.json must contain a JSON object')
    if payload.get('schema_version') != CALIBRATOR_SCHEMA_VERSION:
        raise ValueError('unsupported calibrator schema version')
    if payload.get('method') != 'weighted_isotonic_pava':
        raise ValueError('unsupported calibrator method')
    if payload.get('calibration_split') != 'calibration':
        raise ValueError('calibrator was not fitted on the calibration split')
    identity = payload.get('calibrator_identity_sha256')
    calibrator_id = payload.get('calibrator_id')
    base = dict(payload)
    base.pop('calibrator_identity_sha256', None)
    base.pop('calibrator_id', None)
    expected_identity = _canonical_hash(base)
    if identity != expected_identity:
        raise ValueError('calibrator identity hash does not match its contents')
    if calibrator_id != f'r5-isotonic-{expected_identity[:20]}':
        raise ValueError('calibrator_id does not match its frozen contents')
    bundle = FrozenCalibrator(source, sha256_file(source), payload)
    _validate_calibrator_payload(bundle)
    manifest_path = source.parent / 'CALIBRATION_MANIFEST.json'
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f'missing CALIBRATION_MANIFEST.json beside calibrator: {manifest_path}'
        )
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if not isinstance(manifest, Mapping):
        raise ValueError('CALIBRATION_MANIFEST.json must contain an object')
    if (
        manifest.get('calibrator_id') != bundle.calibrator_id
        or manifest.get('calibrator_object_sha256') != bundle.sha256
        or manifest.get('condition_identity_sha256') != bundle.condition_sha256
    ):
        raise ValueError('calibration manifest does not match CALIBRATOR.json')
    return bundle


def _validate_calibrator_payload(bundle: FrozenCalibrator) -> None:
    payload = bundle.payload
    for field in ('raw_score_source', 'model_snapshot_id', 'condition_identity_sha256'):
        if not isinstance(payload.get(field), str) or not str(payload[field]).strip():
            raise ValueError(f'calibrator {field} must be a nonempty string')
    support_count = payload.get('support_count')
    if isinstance(support_count, bool) or not isinstance(support_count, int) or support_count < 2:
        raise ValueError('calibrator support_count must be an integer of at least two')
    class_support = payload.get('class_support')
    if not isinstance(class_support, Mapping):
        raise ValueError('calibrator class_support must be an object')
    correct = class_support.get('correct')
    incorrect = class_support.get('incorrect')
    if (
        isinstance(correct, bool)
        or not isinstance(correct, int)
        or isinstance(incorrect, bool)
        or not isinstance(incorrect, int)
        or correct < 1
        or incorrect < 1
        or correct + incorrect != support_count
    ):
        raise ValueError('calibrator class support is inconsistent')
    groups = payload.get('supported_groups')
    if not isinstance(groups, list) or not groups:
        raise ValueError('calibrator supported_groups must be a nonempty list')
    seen_groups: set[tuple[str, str]] = set()
    group_total = 0
    level_counts: Counter[str] = Counter()
    for group in groups:
        if not isinstance(group, Mapping):
            raise ValueError('calibrator support group must be an object')
        key = (str(group.get('dataset_id', '')), str(group.get('R5', '')))
        count = group.get('count')
        if (
            not all(key)
            or key in seen_groups
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 1
        ):
            raise ValueError('calibrator contains an invalid support group')
        seen_groups.add(key)
        group_total += count
        level_counts[key[1]] += count
    if group_total != support_count:
        raise ValueError('calibrator group support does not sum to support_count')

    weighting = payload.get('weighting')
    if not isinstance(weighting, Mapping):
        raise ValueError('calibrator weighting must be an object')
    if (
        weighting.get('scheme') != 'inverse_r5_level_frequency'
        or weighting.get('target_mixture') != 'uniform_over_observed_r5_levels'
        or weighting.get('observed_level_counts') != dict(sorted(level_counts.items()))
        or weighting.get('observed_level_count') != len(level_counts)
    ):
        raise ValueError('calibrator R5 weighting identity is inconsistent')
    per_level = weighting.get('per_example_weight_by_level')
    if not isinstance(per_level, Mapping) or set(per_level) != set(level_counts):
        raise ValueError('calibrator per-level weights are inconsistent')
    for level, count in level_counts.items():
        expected = support_count / (len(level_counts) * count)
        if not isclose(float(per_level[level]), expected, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError('calibrator per-level weight is not inverse-frequency')
    total_weight = float(weighting.get('total_weight', float('nan')))
    if not isclose(total_weight, float(support_count), rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError('calibrator weights are not normalized to support_count')

    parameters = payload.get('fitted_parameters')
    blocks = parameters.get('blocks') if isinstance(parameters, Mapping) else None
    if not isinstance(blocks, list) or not blocks:
        raise ValueError('calibrator has no fitted isotonic blocks')
    prior_upper: float | None = None
    prior_prediction: float | None = None
    observation_total = 0
    fitted_weight_total = 0.0
    for block in blocks:
        if not isinstance(block, Mapping):
            raise ValueError('isotonic block must be an object')
        lower = float(block['lower_score'])
        upper = float(block['upper_score'])
        prediction = float(block['prediction'])
        weight = float(block['weight'])
        positive_weight = float(block['positive_weight'])
        observations = block.get('observation_count')
        if not all(isfinite(value) for value in (lower, upper, prediction, weight, positive_weight)):
            raise ValueError('isotonic block contains a non-finite value')
        if (
            lower > upper
            or weight <= 0.0
            or not 0.0 <= positive_weight <= weight
            or not 0.0 <= prediction <= 1.0
            or abs(prediction - positive_weight / weight) > 1e-12
            or isinstance(observations, bool)
            or not isinstance(observations, int)
            or observations < 1
        ):
            raise ValueError('isotonic block parameters are inconsistent')
        if prior_upper is not None and lower <= prior_upper:
            raise ValueError('isotonic blocks overlap or are not sorted')
        if prior_prediction is not None and prediction < prior_prediction:
            raise ValueError('isotonic predictions are not nondecreasing')
        prior_upper = upper
        prior_prediction = prediction
        observation_total += observations
        fitted_weight_total = fsum((fitted_weight_total, weight))
    if observation_total != support_count:
        raise ValueError('isotonic block observations do not sum to support_count')
    if not isclose(fitted_weight_total, total_weight, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError('isotonic block weights do not match frozen weighting')
    score_range = payload.get('training_score_range')
    if not isinstance(score_range, Mapping):
        raise ValueError('calibrator training_score_range must be an object')
    if (
        float(score_range.get('minimum')) != float(blocks[0]['lower_score'])
        or float(score_range.get('maximum')) != float(blocks[-1]['upper_score'])
    ):
        raise ValueError('calibrator score range does not match fitted blocks')


def _condition_payload(manifest: Mapping[str, object], score_source: str) -> dict[str, object]:
    return {
        'provider_kind': manifest.get('provider_kind'),
        'requested_model': manifest.get('requested_model'),
        'prompt': {
            'template_id': manifest.get('prompt_template_id'),
            'system': manifest.get('prompt_system'),
            'user_template': manifest.get('prompt_user_template'),
        },
        'decoding': manifest.get('decoding'),
        'routing': manifest.get('routing'),
        'closed_book': manifest.get('closed_book'),
        'raw_score_source': score_source,
    }


def _validate_run_inputs(
    config: InferenceConfig,
) -> tuple[list[dict[str, str]], dict[str, object], dict[str, object]]:
    verify_run_completeness(config)
    output = config.run.output_dir
    manifest_path = output / 'RUN_MANIFEST.json'
    if not manifest_path.is_file():
        raise FileNotFoundError(f'missing run manifest: {manifest_path}')
    manifest_value = json.loads(manifest_path.read_text(encoding='utf-8'))
    if not isinstance(manifest_value, dict):
        raise ValueError('RUN_MANIFEST.json must contain an object')
    manifest: dict[str, object] = manifest_value
    if manifest.get('run_id') != config.run.run_id or manifest.get('split') != config.run.split:
        raise ValueError('config run identity does not match RUN_MANIFEST.json')
    current_config_hash = sha256_file(config.path)
    if manifest.get('config_sha256') != current_config_hash:
        raise ValueError('config file hash does not match the frozen run manifest')
    if manifest.get('requested_model') != config.model.requested_model:
        raise ValueError('requested model does not match the frozen run manifest')
    expected_prompt = (
        manifest.get('prompt_template_id'),
        manifest.get('prompt_system'),
        manifest.get('prompt_user_template'),
    )
    actual_prompt = (
        config.prompt.template_id,
        config.prompt.system,
        config.prompt.user_template,
    )
    if expected_prompt != actual_prompt:
        raise ValueError('prompt identity does not match the frozen run manifest')

    manifest_datasets = manifest.get('datasets')
    if not isinstance(manifest_datasets, list):
        raise ValueError('run manifest has no dataset identities')
    by_dataset = {
        str(value.get('dataset_id')): value
        for value in manifest_datasets
        if isinstance(value, Mapping)
    }
    for dataset in config.datasets:
        frozen = by_dataset.get(dataset.dataset_id)
        if frozen is None:
            raise ValueError(f'dataset {dataset.dataset_id} is absent from run manifest')
        if frozen.get('examples_sha256') != sha256_file(dataset.examples):
            raise ValueError(f'example input hash changed for {dataset.dataset_id}')
        if frozen.get('workloads_sha256') != sha256_file(dataset.workloads):
            raise ValueError(f'workload input hash changed for {dataset.dataset_id}')

    scored_path = output / 'scored_results.csv'
    rows = _read_csv(scored_path)
    required = {
        'run_id', 'generation_id', 'example_id', 'dataset_id', 'model_snapshot_id',
        'split', 'R5', 'raw_answer', 'correct', 'score', 'score_kind', 'score_source',
    }
    missing = required - set(rows[0])
    if missing:
        raise ValueError(f'scored_results.csv is missing columns: {sorted(missing)}')
    plan = manifest.get('plan')
    if not isinstance(plan, Mapping) or isinstance(plan.get('requests'), bool):
        raise ValueError('run manifest has no valid planned request count')
    planned = int(plan['requests'])
    if len(rows) != planned:
        raise ValueError(
            f'scored run is incomplete: expected {planned} rows, found {len(rows)}'
        )
    example_ids = [row['example_id'] for row in rows]
    generation_ids = [row['generation_id'] for row in rows]
    if len(example_ids) != len(set(example_ids)):
        raise ValueError('scored run contains duplicate example IDs')
    if len(generation_ids) != len(set(generation_ids)):
        raise ValueError('scored run contains duplicate generation IDs')
    selection = manifest.get('selection')
    if isinstance(selection, Mapping):
        if int(selection.get('selected_example_count', -1)) != len(example_ids):
            raise ValueError('scored rows do not match manifest selection count')
        if selection.get('selected_example_ids_sha256') != _canonical_hash(example_ids):
            raise ValueError('scored row identities do not match manifest selection hash')
    if {row['run_id'] for row in rows} != {config.run.run_id}:
        raise ValueError('scored rows contain a mixed or incorrect run_id')
    if {row['split'] for row in rows} != {config.run.split}:
        raise ValueError('scored rows contain a mixed or incorrect split')
    if {row['score_kind'] for row in rows} != {'raw'}:
        raise ValueError('calibration requires one uniformly raw score kind')
    score_sources = {row['score_source'].strip() for row in rows}
    if len(score_sources) != 1 or not next(iter(score_sources)):
        raise ValueError('scored rows contain a mixed or blank raw score source')
    models = {row['model_snapshot_id'].strip() for row in rows}
    if len(models) != 1 or not next(iter(models)):
        raise ValueError('scored rows contain mixed or blank model identities')
    provider_fingerprint = manifest.get('provider_fingerprint')
    if not isinstance(provider_fingerprint, Mapping):
        raise ValueError('run manifest has no provider fingerprint')
    frozen_snapshot = str(
        provider_fingerprint.get('model_snapshot_id', '') or ''
    ).strip()
    if not frozen_snapshot or models != {frozen_snapshot}:
        raise ValueError(
            'scored model snapshot does not match the frozen provider fingerprint'
        )
    for row in rows:
        if not row['score'].strip():
            raise ValueError('scored rows contain a missing raw score')
        score = float(row['score'])
        if not isfinite(score):
            raise ValueError('scored rows contain a non-finite raw score')
        if row['correct'] not in {'0', '1'}:
            raise ValueError('scored rows contain non-binary correctness')

    generations_path = output / 'generations.jsonl'
    if not generations_path.is_file():
        raise FileNotFoundError(f'missing generation cache: {generations_path}')
    generations = [
        GenerationRecord.from_dict(value) for value in read_jsonl(generations_path)
    ]
    if len(generations) != len(rows):
        raise ValueError('generation cache and scored results have different row counts')
    by_example = {value.example_id: value for value in generations}
    if set(by_example) != set(example_ids):
        raise ValueError('generation cache and scored results have different example IDs')
    if len(by_example) != len(generations):
        raise ValueError('generation cache contains duplicate example IDs')

    examples: dict[str, tuple[str, Example]] = {}
    for dataset in config.datasets:
        for value in read_jsonl(dataset.examples):
            example = Example.from_dict(value)
            if example.example_id in examples:
                raise ValueError('configured datasets contain duplicate example IDs')
            examples[example.example_id] = (dataset.dataset_id, example)
    for row in rows:
        generation = by_example[row['example_id']]
        source_example = examples.get(row['example_id'])
        if source_example is None:
            raise ValueError('scored row does not exist in the frozen example inputs')
        dataset_id, example = source_example
        if generation.run_id != row['run_id']:
            raise ValueError('generation/scored run identity mismatch')
        if generation.generation_id != row['generation_id']:
            raise ValueError('generation/scored generation identity mismatch')
        if generation.model_snapshot_id != row['model_snapshot_id']:
            raise ValueError('generation/scored model identity mismatch')
        if generation.score_source != row['score_source']:
            raise ValueError('generation/scored raw score source mismatch')
        if generation.score != float(row['score']):
            raise ValueError('generation/scored raw score mismatch')
        row['condition_hash'] = generation.condition_hash
        row['evaluation_track'] = generation.track
        answer = generation.raw_text.strip()
        if row['dataset_id'] != dataset_id or row['split'] != example.split:
            raise ValueError('scored row dataset/split identity mismatch')
        if row['R5'] != example.dimension_values()['R5'].level:
            raise ValueError('scored row R5 identity mismatch')
        if row.get('chain_id', '') != str(example.metadata.get('chain_id', '')):
            raise ValueError('scored row chain identity mismatch')
        if row['raw_answer'] != answer:
            raise ValueError('generation/scored answer mismatch')
        if (
            row.get('normalized_answer', normalize_answer(answer))
            != normalize_answer(answer)
        ):
            raise ValueError('scored row answer normalization mismatch')
        expected_correct = int(exact_match(answer, example.accepted_answers))
        if int(row['correct']) != expected_correct:
            raise ValueError('scored correctness does not match frozen gold answers')

    source = next(iter(score_sources))
    condition = _condition_payload(manifest, source)
    identity = {
        'config_sha256': current_config_hash,
        'run_manifest_sha256': sha256_file(manifest_path),
        'scored_results_sha256': sha256_file(scored_path),
        'generations_sha256': sha256_file(generations_path),
        'condition_payload': condition,
        'condition_identity_sha256': _canonical_hash(condition),
        'model_snapshot_id': next(iter(models)),
        'raw_score_source': source,
        'input_example_ids_sha256': _canonical_hash(sorted(example_ids)),
        'input_rows_sha256': _canonical_hash(
            sorted(
                (
                    {
                        'example_id': row['example_id'],
                        'dataset_id': row['dataset_id'],
                        'R5': row['R5'],
                        'score': float(row['score']),
                        'correct': int(row['correct']),
                    }
                    for row in rows
                ),
                key=lambda value: str(value['example_id']),
            )
        ),
        'condition_table': {
            'schema_version': 1,
            'kind': 'generation_condition_identity_table',
            'run_id': config.run.run_id,
            'split': config.run.split,
            'entries': sorted(
                (
                    {
                        'example_id': generation.example_id,
                        'generation_id': generation.generation_id,
                        'model_snapshot_id': generation.model_snapshot_id,
                        'evaluation_track': generation.track,
                        'condition_hash': generation.condition_hash,
                    }
                    for generation in generations
                ),
                key=lambda value: str(value['example_id']),
            ),
        },
    }
    return rows, manifest, identity


def _metric_summary(confidences: list[float], labels: list[int]) -> dict[str, object]:
    result: dict[str, object] = {
        'n': len(labels),
        'accuracy': sum(labels) / len(labels),
        'brier': brier_score(confidences, labels),
        'log_loss': binary_log_loss(confidences, labels),
        'ece_10': expected_calibration_error(confidences, labels, n_bins=10),
        'ace_10': adaptive_calibration_error(confidences, labels, n_bins=10),
    }
    try:
        result['correctness_auroc'] = correctness_auroc(confidences, labels)
    except ValueError:
        result['correctness_auroc'] = None
    return result


def fit_calibrator(
    config: InferenceConfig,
    calibrator_path: str | Path | None = None,
) -> Path:
    '''Fit and freeze a global isotonic calibrator on a complete calibration run.'''

    if config.run.split != 'calibration':
        raise ValueError('fit-calibrator is permitted only for run.split=calibration')
    rows, manifest, identity = _validate_run_inputs(config)
    scores = [float(row['score']) for row in rows]
    labels = [int(row['correct']) for row in rows]
    if len(rows) < 2 or len(set(labels)) < 2:
        raise ValueError(
            'calibration fitting requires at least two rows and both correctness classes'
        )
    weights, weighting = r5_level_balanced_weights(row['R5'] for row in rows)
    blocks = fit_weighted_isotonic(scores, labels, weights)
    group_counts = Counter((row['dataset_id'], row['R5']) for row in rows)
    base: dict[str, object] = {
        'schema_version': CALIBRATOR_SCHEMA_VERSION,
        'method': 'weighted_isotonic_pava',
        'monotonic_direction': 'nondecreasing',
        'interpolation': 'constant_within_blocks_linear_between_blocks_clipped_at_ends',
        'calibration_split': 'calibration',
        'support_count': len(rows),
        'class_support': {'correct': sum(labels), 'incorrect': len(labels) - sum(labels)},
        'minimum_group_support': 1,
        'weighting': weighting,
        'supported_groups': [
            {'dataset_id': dataset_id, 'R5': level, 'count': count}
            for (dataset_id, level), count in sorted(group_counts.items())
        ],
        'raw_score_kind': 'raw',
        'raw_score_source': identity['raw_score_source'],
        'model_snapshot_id': identity['model_snapshot_id'],
        'requested_model': manifest.get('requested_model'),
        'prompt_identity': {
            'template_id': manifest.get('prompt_template_id'),
            'system': manifest.get('prompt_system'),
            'user_template': manifest.get('prompt_user_template'),
        },
        'prompt_identity_sha256': _canonical_hash(
            {
                'template_id': manifest.get('prompt_template_id'),
                'system': manifest.get('prompt_system'),
                'user_template': manifest.get('prompt_user_template'),
            }
        ),
        'decoding_identity': manifest.get('decoding'),
        'decoding_identity_sha256': _canonical_hash(manifest.get('decoding')),
        'condition_identity_sha256': identity['condition_identity_sha256'],
        'input_example_ids_sha256': identity['input_example_ids_sha256'],
        'training_rows_sha256': identity['input_rows_sha256'],
        'training_score_range': {'minimum': min(scores), 'maximum': max(scores)},
        'fitted_parameters': {'blocks': list(blocks)},
        'source_artifacts': {
            'calibration_run_id': config.run.run_id,
            'config_sha256': identity['config_sha256'],
            'run_manifest_sha256': identity['run_manifest_sha256'],
            'scored_results_sha256': identity['scored_results_sha256'],
            'generations_sha256': identity['generations_sha256'],
            'software_calibration_py_sha256': sha256_file(Path(__file__)),
        },
    }
    calibrator_identity = _canonical_hash(base)
    payload = {
        **base,
        'calibrator_id': f'r5-isotonic-{calibrator_identity[:20]}',
        'calibrator_identity_sha256': calibrator_identity,
    }
    target = (
        config.run.output_dir / 'calibration' / _CALIBRATOR_FILENAME
        if calibrator_path is None
        else _resolve_calibrator_path(calibrator_path)
    )
    _freeze_json(target, payload)
    object_hash = sha256_file(target)
    manifest_payload = {
        'schema_version': 1,
        'calibrator_id': payload['calibrator_id'],
        'calibrator_object': target.name,
        'calibrator_object_sha256': object_hash,
        'calibration_run_id': config.run.run_id,
        'calibration_split': 'calibration',
        'support_count': len(rows),
        'condition_identity_sha256': identity['condition_identity_sha256'],
        'input_example_ids_sha256': identity['input_example_ids_sha256'],
        'training_rows_sha256': identity['input_rows_sha256'],
        'source_artifacts': payload['source_artifacts'],
    }
    _freeze_json(target.parent / 'CALIBRATION_MANIFEST.json', manifest_payload)
    confidences = [predict_isotonic(blocks, value) for value in scores]
    metrics = {
        'schema_version': 1,
        'calibrator_id': payload['calibrator_id'],
        'calibrator_object_sha256': object_hash,
        'evaluation_split': 'calibration',
        'evaluation_role': 'in_sample_fit_diagnostic_not_held_out_evidence',
        'overall': _metric_summary(confidences, labels),
    }
    _freeze_json(target.parent / 'calibration_metrics.json', metrics)
    return target


def calibrate_run(config: InferenceConfig, calibrator_path: str | Path) -> Path:
    '''Apply one frozen calibrator to a complete, condition-identical scored run.'''

    bundle = load_calibrator(calibrator_path)
    rows, _manifest, identity = _validate_run_inputs(config)
    if identity['condition_identity_sha256'] != bundle.condition_sha256:
        raise ValueError(
            'target model/prompt/decoding/score condition does not match calibrator'
        )
    if identity['model_snapshot_id'] != bundle.payload.get('model_snapshot_id'):
        raise ValueError('target model snapshot does not match calibrator')
    if identity['raw_score_source'] != bundle.raw_score_source:
        raise ValueError('target raw score source does not match calibrator')

    condition_table_value = identity.get('condition_table')
    if not isinstance(condition_table_value, Mapping):
        raise ValueError('target run has no validated condition identity table')
    condition_table_target = (
        config.run.output_dir / 'CONDITION_IDENTITY_MANIFEST.json'
    )
    _freeze_json(
        condition_table_target,
        {
            **condition_table_value,
            'source_run_manifest_sha256': identity['run_manifest_sha256'],
            'source_generations_sha256': identity['generations_sha256'],
        },
    )
    condition_table_hash = sha256_file(condition_table_target)
    calibrated_score_source = (
        'weighted_isotonic_pava(' + bundle.raw_score_source + ')'
    )
    calibration_contract = 'r5-level-balanced-weighted-isotonic-pava-v1'

    fields = list(rows[0]) + [
        'raw_score', 'calibrated_confidence', 'calibrated_score_kind',
        'calibrated_score_source', 'calibrated_normalization_contract',
        'calibrator_id', 'calibrator_object_sha256', 'calibration_supported',
        'calibration_group', 'calibration_group_support_count',
        'calibrator_condition_sha256', 'target_config_sha256',
        'target_input_example_ids_sha256', 'target_scored_results_sha256',
        'condition_table_hash',
    ]
    derived: list[dict[str, object]] = []
    for row in rows:
        support_count = bundle.group_support(row['dataset_id'], row['R5'])
        supported = support_count >= int(bundle.payload.get('minimum_group_support', 1))
        confidence = bundle.predict(float(row['score'])) if supported else ''
        derived.append(
            {
                **row,
                'raw_score': row['score'],
                'calibrated_confidence': confidence,
                'calibrated_score_kind': 'probability' if supported else '',
                'calibrated_score_source': (
                    calibrated_score_source if supported else ''
                ),
                'calibrated_normalization_contract': (
                    calibration_contract if supported else ''
                ),
                'calibrator_id': bundle.calibrator_id,
                'calibrator_object_sha256': bundle.sha256,
                'calibration_supported': int(supported),
                'calibration_group': f"{row['dataset_id']}:{row['R5']}",
                'calibration_group_support_count': support_count,
                'calibrator_condition_sha256': bundle.condition_sha256,
                'target_config_sha256': identity['config_sha256'],
                'target_input_example_ids_sha256': identity['input_example_ids_sha256'],
                'target_scored_results_sha256': identity['scored_results_sha256'],
                'condition_table_hash': condition_table_hash,
            }
        )
    target = config.run.output_dir / 'calibrated_results.csv'
    _freeze_text(target, _csv_text(derived, fields))
    evaluation_fields = (
        'example_id', 'confidence', 'correct', 'dataset_id', 'R5', 'chain_id',
        'run_id', 'split', 'model_snapshot_id', 'evaluation_track',
        'condition_table_hash',
        'calibration_object_hash', 'condition_hash', 'score_kind', 'score_source',
        'calibrator_id', 'normalization_contract',
    )
    evaluation_rows = [
        {
            'example_id': row['example_id'],
            'confidence': row['calibrated_confidence'],
            'correct': row['correct'],
            'dataset_id': row['dataset_id'],
            'R5': row['R5'],
            'chain_id': row.get('chain_id', ''),
            'run_id': row['run_id'],
            'split': row['split'],
            'model_snapshot_id': row['model_snapshot_id'],
            'evaluation_track': row['evaluation_track'],
            'condition_table_hash': condition_table_hash,
            'calibration_object_hash': bundle.sha256,
            'condition_hash': row['condition_hash'],
            'score_kind': 'probability',
            'score_source': calibrated_score_source,
            'calibrator_id': bundle.calibrator_id,
            'normalization_contract': calibration_contract,
        }
        for row in derived
        if row['calibration_supported'] == 1
    ]
    evaluation_target = config.run.output_dir / 'calibrated_evaluation.csv'
    _freeze_text(
        evaluation_target,
        _csv_text(evaluation_rows, evaluation_fields),
    )
    _freeze_json(
        config.run.output_dir / 'CALIBRATED_RESULTS_MANIFEST.json',
        {
            'schema_version': 1,
            'run_id': config.run.run_id,
            'split': config.run.split,
            'input_rows': len(rows),
            'supported_rows': len(evaluation_rows),
            'unsupported_rows': len(rows) - len(evaluation_rows),
            'target_scored_results_sha256': identity['scored_results_sha256'],
            'target_input_example_ids_sha256': identity['input_example_ids_sha256'],
            'condition_identity_sha256': bundle.condition_sha256,
            'condition_identity_manifest': condition_table_target.name,
            'condition_identity_manifest_sha256': condition_table_hash,
            'condition_table_hash': condition_table_hash,
            'calibrator_id': bundle.calibrator_id,
            'calibrator_object_sha256': bundle.sha256,
            'calibrated_results_sha256': sha256_file(target),
            'calibrated_evaluation_sha256': sha256_file(evaluation_target),
        },
    )
    return target


def load_calibrated_run(
    config: InferenceConfig, calibrator_path: str | Path
) -> tuple[list[dict[str, str]], FrozenCalibrator]:
    '''Load and strictly validate calibrated rows against current frozen inputs.'''

    bundle = load_calibrator(calibrator_path)
    target = calibrate_run(config, bundle.path)
    rows = _read_csv(target)
    expected_ids = {bundle.calibrator_id}
    expected_hashes = {bundle.sha256}
    condition_table_target = (
        config.run.output_dir / 'CONDITION_IDENTITY_MANIFEST.json'
    )
    if not condition_table_target.is_file():
        raise FileNotFoundError(
            f'missing condition identity manifest: {condition_table_target}'
        )
    expected_condition_table_hash = sha256_file(condition_table_target)
    if {row.get('calibrator_id', '') for row in rows} != expected_ids:
        raise ValueError('calibrated rows contain a mixed or incorrect calibrator_id')
    if {row.get('calibrator_object_sha256', '') for row in rows} != expected_hashes:
        raise ValueError('calibrated rows contain a mixed or incorrect calibrator hash')
    for row in rows:
        if row.get('condition_table_hash') != expected_condition_table_hash:
            raise ValueError(
                'calibrated row condition table hash does not match the frozen '
                'condition identity manifest'
            )
        supported = row.get('calibration_supported') == '1'
        confidence = row.get('calibrated_confidence', '')
        if supported:
            value = float(confidence)
            if not isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError('supported row has invalid calibrated confidence')
            if row.get('calibrated_score_kind') != 'probability':
                raise ValueError('supported row must declare probability score kind')
            if not row.get('calibrated_score_source', '').strip():
                raise ValueError('supported row has no calibrated score source')
            if not row.get('calibrated_normalization_contract', '').strip():
                raise ValueError('supported row has no calibration contract')
        elif confidence:
            raise ValueError('unsupported row must not contain calibrated confidence')
    return rows, bundle


__all__ = [
    'FrozenCalibrator',
    'calibrate_run',
    'fit_calibrator',
    'fit_weighted_isotonic',
    'load_calibrated_run',
    'load_calibrator',
    'predict_isotonic',
    'r5_level_balanced_weights',
]
