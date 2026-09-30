'''Deterministic answer scoring and CSV export for cached generations.'''

from __future__ import annotations

from collections import Counter
import csv
from pathlib import Path

from ..correctness import exact_match, normalize_answer
from ..io import read_jsonl, sha256_file
from ..schema import Example, GenerationRecord
from .config import InferenceConfig
from .runner import verify_run_completeness


_SCORED_FIELDS = (
    'run_id', 'generation_id', 'example_id', 'dataset_id', 'model_snapshot_id',
    'split', 'chain_id', 'R5', 'raw_answer', 'normalized_answer', 'correct',
    'token_f1', 'score', 'score_kind', 'score_source', 'abstained',
    'latency_ms', 'prompt_tokens', 'completion_tokens', 'estimated_cost_usd',
)


def _token_f1(prediction: str, references: tuple[str, ...]) -> float:
    predicted = normalize_answer(prediction).split()
    if not predicted:
        return 0.0
    best = 0.0
    for reference in references:
        expected = normalize_answer(reference).split()
        overlap = sum((Counter(predicted) & Counter(expected)).values())
        if overlap:
            precision = overlap / len(predicted)
            recall = overlap / len(expected)
            best = max(best, 2 * precision * recall / (precision + recall))
    return best


def score_run(config: InferenceConfig) -> Path:
    verify_run_completeness(config)
    examples: dict[str, tuple[str, Example]] = {}
    for dataset in config.datasets:
        for value in read_jsonl(dataset.examples):
            example = Example.from_dict(value)
            examples[example.example_id] = (dataset.dataset_id, example)
    generations = [
        GenerationRecord.from_dict(value)
        for value in read_jsonl(config.run.output_dir / 'generations.jsonl')
    ]
    target = config.run.output_dir / 'scored_results.csv'
    with target.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=_SCORED_FIELDS)
        writer.writeheader()
        for generation in generations:
            if generation.example_id not in examples:
                raise ValueError(f'unknown generation example {generation.example_id}')
            dataset_id, example = examples[generation.example_id]
            answer = generation.raw_text.strip()
            writer.writerow(
                {
                    'run_id': generation.run_id,
                    'generation_id': generation.generation_id,
                    'example_id': generation.example_id,
                    'dataset_id': dataset_id,
                    'model_snapshot_id': generation.model_snapshot_id,
                    'split': example.split,
                    'chain_id': example.metadata.get('chain_id', ''),
                    'R5': example.dimension_values()['R5'].level,
                    'raw_answer': answer,
                    'normalized_answer': normalize_answer(answer),
                    'correct': int(exact_match(answer, example.accepted_answers)),
                    'token_f1': _token_f1(answer, example.accepted_answers),
                    'score': generation.score,
                    'score_kind': generation.score_kind,
                    'score_source': generation.score_source,
                    'abstained': int(normalize_answer(answer) == 'abstain'),
                    'latency_ms': generation.metadata.get('latency_ms', ''),
                    'prompt_tokens': generation.metadata.get('prompt_tokens', ''),
                    'completion_tokens': generation.metadata.get('completion_tokens', ''),
                    'estimated_cost_usd': generation.metadata.get('estimated_cost_usd', ''),
                }
            )
    return target


def verify_scored_results(config: InferenceConfig) -> dict[str, object]:
    '''Validate the deterministic scored artifact against generations and gold.'''

    completion = verify_run_completeness(config)
    examples: dict[str, tuple[str, Example]] = {}
    for dataset in config.datasets:
        for value in read_jsonl(dataset.examples):
            example = Example.from_dict(value)
            if example.example_id in examples:
                raise ValueError(f'duplicate configured example {example.example_id}')
            examples[example.example_id] = (dataset.dataset_id, example)
    generations = {
        record.example_id: record
        for record in (
            GenerationRecord.from_dict(value)
            for value in read_jsonl(config.run.output_dir / 'generations.jsonl')
        )
    }
    source = config.run.output_dir / 'scored_results.csv'
    if not source.is_file():
        raise FileNotFoundError(f'missing scored result file: {source}')
    with source.open('r', encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream)
        fields = set(reader.fieldnames or ())
        missing_fields = set(_SCORED_FIELDS) - fields
        if missing_fields:
            raise ValueError(
                f'scored result file is missing fields: {sorted(missing_fields)}'
            )
        rows = list(reader)
    identifiers = [row['example_id'] for row in rows]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError('scored result file contains duplicate example IDs')
    if set(identifiers) != set(generations):
        raise ValueError('scored result identities do not match frozen generations')
    for row in rows:
        generation = generations[row['example_id']]
        dataset_id, example = examples[generation.example_id]
        answer = generation.raw_text.strip()
        exact = int(exact_match(answer, example.accepted_answers))
        expected_text = {
            'run_id': generation.run_id,
            'generation_id': generation.generation_id,
            'dataset_id': dataset_id,
            'model_snapshot_id': generation.model_snapshot_id,
            'split': example.split,
            'chain_id': str(example.metadata.get('chain_id', '')),
            'R5': example.dimension_values()['R5'].level,
            'raw_answer': answer,
            'normalized_answer': normalize_answer(answer),
            'score_kind': generation.score_kind,
            'score_source': generation.score_source,
        }
        for name, expected in expected_text.items():
            if row[name] != expected:
                raise ValueError(
                    f'scored row {generation.example_id} has incorrect {name}'
                )
        expected_int = {
            'correct': exact,
            'abstained': int(normalize_answer(answer) == 'abstain'),
        }
        for name, expected in expected_int.items():
            if int(row[name]) != expected:
                raise ValueError(
                    f'scored row {generation.example_id} has incorrect {name}'
                )
        expected_float = {
            'token_f1': _token_f1(answer, example.accepted_answers),
            'score': generation.score,
        }
        for name, expected in expected_float.items():
            if abs(float(row[name]) - float(expected)) > 1e-12:
                raise ValueError(
                    f'scored row {generation.example_id} has incorrect {name}'
                )
        for name in (
            'latency_ms',
            'prompt_tokens',
            'completion_tokens',
            'estimated_cost_usd',
        ):
            expected = generation.metadata.get(name, '')
            if expected == '':
                matches = row[name] == ''
            else:
                try:
                    matches = abs(float(row[name]) - float(expected)) <= 1e-12
                except (TypeError, ValueError):
                    matches = False
            if not matches:
                raise ValueError(
                    f'scored row {generation.example_id} has incorrect {name}'
                )
    return {
        **completion,
        'scored': len(rows),
        'scored_results_sha256': sha256_file(source),
    }
