'''Dataset selection, cost planning, resumable generation, and run manifests.'''

from __future__ import annotations

from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import errno
import hashlib
import json
from math import isfinite
import os
from pathlib import Path
from time import perf_counter
from typing import BinaryIO, Mapping

from ..io import read_jsonl, sha256_file
from ..schema import Example, GenerationRecord, WorkloadRecord
from .config import InferenceConfig, R5_LEVELS
from .providers import InferenceProvider, MockProvider, OllamaProvider, OpenRouterProvider
from .types import InferenceRequest, ProviderError, ProviderFingerprint


class RunDirectoryLockedError(RuntimeError):
    '''Raised when another live process owns an inference run directory.'''


class _RunDirectoryLock:
    '''Dependency-free, non-blocking process lock for one run output directory.

    The lock file is deliberately persistent. Removing it after unlocking would
    introduce an inode-replacement race on POSIX. OS locking, rather than file
    age or PID probing, makes a lock left by a crashed process immediately safe
    to reuse.
    '''

    filename = '.calibread-inference.lock'

    def __init__(self, output_dir: Path, run_id: str) -> None:
        self.path = output_dir / self.filename
        self.run_id = run_id
        self._handle: BinaryIO | None = None

    def __enter__(self) -> '_RunDirectoryLock':
        file_descriptor = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        handle = os.fdopen(file_descriptor, 'r+b', buffering=0)
        self._handle = handle
        try:
            # Windows byte-range locks require the byte to exist first.
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b'\x00')
                os.fsync(handle.fileno())
            handle.seek(0)
            self._lock_nonblocking(handle)
        except OSError as error:
            if not self._is_contention(error):
                handle.close()
                self._handle = None
                raise
            owner = self._owner_description(handle)
            handle.close()
            self._handle = None
            detail = f' ({owner})' if owner else ''
            raise RunDirectoryLockedError(
                'inference output directory is locked by another live process: '
                f'{self.path}{detail}'
            ) from None

        try:
            owner = {
                'pid': os.getpid(),
                'run_id': self.run_id,
                'acquired_at_utc': datetime.now(timezone.utc).isoformat(),
            }
            encoded = json.dumps(owner, sort_keys=True).encode('utf-8')
            handle.seek(0)
            handle.write(b'\x00' + encoded + b'\n')
            handle.truncate()
            os.fsync(handle.fileno())
        except BaseException:
            try:
                handle.seek(0)
                self._unlock(handle)
            finally:
                handle.close()
                self._handle = None
            raise
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        handle = self._handle
        self._handle = None
        if handle is None:
            return False
        release_error: OSError | None = None
        try:
            # Keep the first byte/inode but clear owner metadata on clean exit.
            handle.seek(0)
            handle.write(b'\x00')
            handle.truncate()
            os.fsync(handle.fileno())
        except OSError as error:
            release_error = error
        try:
            handle.seek(0)
            self._unlock(handle)
        except OSError as error:
            release_error = release_error or error
        finally:
            # Closing also releases the OS lock if explicit unlock failed.
            handle.close()
        if release_error is not None and exc_type is None:
            raise release_error
        return False

    @staticmethod
    def _lock_nonblocking(handle: BinaryIO) -> None:
        if os.name == 'nt':
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _unlock(handle: BinaryIO) -> None:
        if os.name == 'nt':
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _is_contention(error: OSError) -> bool:
        return error.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK} or getattr(
            error, 'winerror', None
        ) in {32, 33, 36}

    @staticmethod
    def _owner_description(handle: BinaryIO) -> str:
        try:
            handle.seek(1)
            raw = handle.read().decode('utf-8').strip()
            owner = json.loads(raw)
            if not isinstance(owner, dict):
                return ''
            details = []
            for key in ('pid', 'run_id', 'acquired_at_utc'):
                if key in owner:
                    details.append(f'{key}={owner[key]!r}')
            return ', '.join(details)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return ''


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _r5_level(example: Example) -> str:
    dimensions = example.dimension_values()
    if 'R5' not in dimensions:
        raise ValueError(f'{example.example_id} has no R5 dimension')
    return dimensions['R5'].level


def _r5_raw(example: Example) -> int:
    dimensions = example.dimension_values()
    if 'R5' not in dimensions:
        raise ValueError(f'{example.example_id} has no R5 dimension')
    return int(dimensions['R5'].raw)


def _chain_id(example: Example) -> str:
    value = example.metadata.get('chain_id')
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{example.example_id} has no nonempty chain_id')
    return value.strip()


def _shuffled_key(config: InferenceConfig, dataset_id: str, identifier: str) -> str:
    return hashlib.sha256(
        f'{config.run.seed}:{dataset_id}:{identifier}'.encode('utf-8')
    ).hexdigest()


def _all_examples(
    config: InferenceConfig,
) -> tuple[list[tuple[str, Example]], dict[str, tuple[str, Example]]]:
    rows: list[tuple[str, Example]] = []
    index: dict[str, tuple[str, Example]] = {}
    for dataset in config.datasets:
        for value in read_jsonl(dataset.examples):
            example = Example.from_dict(value)
            if example.example_id in index:
                raise ValueError(
                    f'configured datasets contain duplicate example ID {example.example_id!r}'
                )
            item = (dataset.dataset_id, example)
            rows.append(item)
            index[example.example_id] = item
    return rows, index


def _all_workloads(config: InferenceConfig) -> dict[str, WorkloadRecord]:
    index: dict[str, WorkloadRecord] = {}
    for dataset in config.datasets:
        for value in read_jsonl(dataset.workloads):
            workload = WorkloadRecord.from_dict(value)
            if workload.example_id in index:
                raise ValueError(
                    'configured datasets contain duplicate workload ID '
                    f'{workload.example_id!r}'
                )
            index[workload.example_id] = workload
    return index


def _independent_selection(
    config: InferenceConfig,
    rows: list[tuple[str, Example]],
) -> list[tuple[str, Example]]:
    selected: list[tuple[str, Example]] = []
    for dataset in config.datasets:
        eligible = [
            row
            for dataset_id, row in rows
            if dataset_id == dataset.dataset_id
            and row.split == config.run.split
            and _r5_level(row) in config.run.include_levels
        ]
        eligible.sort(
            key=lambda row: _shuffled_key(config, dataset.dataset_id, row.example_id)
        )
        if config.run.limit_per_level is not None:
            counts: Counter[str] = Counter()
            limited: list[Example] = []
            for row in eligible:
                level = _r5_level(row)
                if counts[level] < config.run.limit_per_level:
                    limited.append(row)
                    counts[level] += 1
            eligible = limited
        selected.extend((dataset.dataset_id, row) for row in eligible)
    return selected


def _chain_complete_selection(
    config: InferenceConfig,
    rows: list[tuple[str, Example]],
    example_index: Mapping[str, tuple[str, Example]],
) -> list[tuple[str, Example]]:
    split_rows = [item for item in rows if item[1].split == config.run.split]
    # Chain identifiers are only guaranteed to be unique inside one source.
    # Namespace them by configured dataset so an innocuous value such as
    # ``chain-1`` cannot merge two unrelated benchmark chains. Cross-dataset
    # atomic dependencies are added explicitly from constituent_example_ids
    # below, rather than inferred from a coincidentally equal chain_id.
    chains: dict[tuple[str, str], list[tuple[str, Example]]] = defaultdict(list)
    for item in split_rows:
        chains[(item[0], _chain_id(item[1]))].append(item)

    # A chain is owned by the dataset containing its deepest member. This keeps
    # per-dataset limits meaningful when a composite and its materialized atomic
    # questions are stored in separate configured datasets.
    units_by_owner: dict[
        str, list[tuple[str, list[tuple[str, Example]], tuple[str, ...]]]
    ] = defaultdict(list)
    for (source_dataset_id, chain_id), members in chains.items():
        relevant_levels = tuple(
            level
            for level in R5_LEVELS
            if level in config.run.include_levels
            and any(_r5_level(example) == level for _, example in members)
        )
        if not relevant_levels:
            continue
        maximum_depth = max(_r5_raw(example) for _, example in members)
        owner = min(
            dataset_id
            for dataset_id, example in members
            if _r5_raw(example) == maximum_depth
        )
        namespaced_chain_id = f'{source_dataset_id}:{chain_id}'
        units_by_owner[owner].append(
            (namespaced_chain_id, members, relevant_levels)
        )

    selected_ids: set[str] = set()
    selected: list[tuple[str, Example]] = []
    for owner in sorted(units_by_owner):
        units = units_by_owner[owner]
        units.sort(key=lambda item: _shuffled_key(config, owner, item[0]))
        unit_counts: Counter[str] = Counter()
        for _, members, relevant_levels in units:
            if config.run.limit_per_level is not None and not any(
                unit_counts[level] < config.run.limit_per_level
                for level in relevant_levels
            ):
                continue
            for level in relevant_levels:
                unit_counts[level] += 1
            for item in members:
                if item[1].example_id not in selected_ids:
                    selected.append(item)
                    selected_ids.add(item[1].example_id)

    workloads = _all_workloads(config)
    pending = [example.example_id for _, example in selected]
    cursor = 0
    while cursor < len(pending):
        example_id = pending[cursor]
        cursor += 1
        item = example_index[example_id]
        example = item[1]
        workload = workloads.get(example_id)
        if workload is None:
            raise ValueError(
                f'chain_complete selection requires a workload for {example_id}'
            )
        if int(workload.dimensions['R5'].raw) <= 1:
            continue
        for constituent_id in workload.constituent_example_ids:
            constituent = example_index.get(constituent_id)
            if constituent is None:
                raise ValueError(
                    f'{example_id} constituent {constituent_id!r} is absent from '
                    'the configured example datasets'
                )
            if constituent[1].split != config.run.split:
                raise ValueError(
                    f'{example_id} constituent {constituent_id!r} has split '
                    f'{constituent[1].split!r}, expected {config.run.split!r}'
                )
            if constituent_id not in workloads:
                raise ValueError(
                    f'{example_id} constituent {constituent_id!r} has no configured workload'
                )
            if constituent_id not in selected_ids:
                selected.append(constituent)
                selected_ids.add(constituent_id)
                pending.append(constituent_id)

    level_order = {level: index for index, level in enumerate(R5_LEVELS)}
    selected.sort(
        key=lambda item: (
            level_order[_r5_level(item[1])],
            _shuffled_key(config, item[0], item[1].example_id),
        )
    )
    return selected


def _selected_examples(config: InferenceConfig) -> list[tuple[str, Example]]:
    rows, example_index = _all_examples(config)
    selected = (
        _chain_complete_selection(config, rows, example_index)
        if config.run.chain_complete
        else _independent_selection(config, rows)
    )
    identities = [row.example_id for _, row in selected]
    if len(identities) != len(set(identities)):
        raise ValueError('selected datasets contain duplicate example IDs')
    return selected


def _selection_metadata(selected: list[tuple[str, Example]]) -> dict[str, object]:
    identities = [example.example_id for _, example in selected]
    chain_ids: list[str] = []
    seen_chains: set[str] = set()
    chain_members: dict[str, list[str]] = defaultdict(list)
    for _, example in selected:
        chain_id = _chain_id(example)
        if chain_id not in seen_chains:
            chain_ids.append(chain_id)
            seen_chains.add(chain_id)
        chain_members[chain_id].append(example.example_id)
    membership = [
        {
            'chain_id': chain_id,
            'example_ids': sorted(member_ids),
        }
        for chain_id, member_ids in sorted(chain_members.items())
    ]
    return {
        'selected_example_count': len(identities),
        'selected_chain_count': len(chain_ids),
        'selected_example_ids_sha256': _canonical_hash(identities),
        'selected_chain_ids_sha256': _canonical_hash(chain_ids),
        'selected_chain_membership_sha256': _canonical_hash(membership),
    }


def _estimated_tokens(config: InferenceConfig, selected: list[tuple[str, Example]]) -> tuple[int, int]:
    prompt_tokens = 0
    for _, example in selected:
        user = config.prompt.user_template.format(question=example.question)
        prompt_tokens += max(1, (len(config.prompt.system) + len(user) + 3) // 4)
    return prompt_tokens, len(selected) * config.model.max_tokens


def _cost(config: InferenceConfig, prompt_tokens: int, completion_tokens: int) -> float:
    return (
        prompt_tokens * config.budget.prompt_usd_per_million
        + completion_tokens * config.budget.completion_usd_per_million
    ) / 1_000_000


def _provider(config: InferenceConfig) -> InferenceProvider:
    if config.provider.kind == 'mock':
        return MockProvider()
    if config.provider.kind == 'openrouter':
        required_parameters = ['max_tokens', 'temperature', 'seed', 'tools']
        if config.model.require_logprobs:
            required_parameters.extend(['logprobs', 'top_logprobs'])
        if config.model.reasoning_effort is not None:
            required_parameters.append('reasoning')
        return OpenRouterProvider(
            config.provider,
            max_http_attempts=config.budget.max_requests,
            pinned_provider_order=config.model.provider_order,
            required_parameters=tuple(required_parameters),
        )
    if config.provider.kind == 'ollama':
        return OllamaProvider(config.provider)
    raise ValueError(f'unsupported provider kind {config.provider.kind!r}')


def _fingerprint_dict(value: ProviderFingerprint) -> dict[str, object]:
    return {
        'requested_model': value.requested_model,
        'model_snapshot_id': value.model_snapshot_id,
        'provider_name': value.provider_name,
        'metadata': dict(value.metadata),
    }


def _manifest_status(split: str) -> str:
    return {
        'development': 'development_api_run',
        'calibration': 'calibration_api_run',
        'test': 'test_api_run',
    }[split]


def _required_human_audit_evidence(
    config: InferenceConfig,
) -> list[dict[str, str]]:
    '''Return frozen approval evidence or fail before any model request.

    Human review is intentionally never inferred from the presence of an audit
    sample. A required manifest must explicitly set checks.human_audit to
    ``approved`` after the review has happened.
    '''

    evidence: list[dict[str, str]] = []
    for path in config.run.required_human_audit_manifests:
        if not path.is_file():
            raise FileNotFoundError(f'missing required human-audit manifest: {path}')
        payload = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(payload, Mapping):
            raise ValueError(f'human-audit manifest must contain an object: {path}')
        checks = payload.get('checks')
        status = checks.get('human_audit') if isinstance(checks, Mapping) else None
        if status != 'approved':
            raise ValueError(
                f'human audit is not approved in {path}: found {status!r}; '
                'a person must review the audit sample and explicitly record approval'
            )
        outputs = payload.get('outputs')
        audit_output = (
            outputs.get('audit_sample.csv') if isinstance(outputs, Mapping) else None
        )
        if not isinstance(audit_output, Mapping):
            raise ValueError(f'{path} does not freeze audit_sample.csv output identity')
        audit_path = path.parent / 'audit_sample.csv'
        if not audit_path.is_file():
            raise FileNotFoundError(f'missing approved audit sample: {audit_path}')
        actual_digest = sha256_file(audit_path)
        actual_bytes = audit_path.stat().st_size
        if (
            audit_output.get('sha256') != actual_digest
            or audit_output.get('bytes') != actual_bytes
        ):
            raise ValueError(f'approved audit sample no longer matches {path}')
        review = payload.get('human_audit_review')
        if not isinstance(review, Mapping):
            raise ValueError(f'{path} has no human_audit_review attestation')
        for field in ('reviewer', 'protocol', 'reviewed_at_utc'):
            if not isinstance(review.get(field), str) or not str(review[field]).strip():
                raise ValueError(f'{path} audit attestation has no nonempty {field}')
        try:
            reviewed_at = datetime.fromisoformat(str(review['reviewed_at_utc']))
        except ValueError as error:
            raise ValueError(f'{path} audit timestamp is not valid ISO-8601') from error
        if reviewed_at.tzinfo is None:
            raise ValueError(f'{path} audit timestamp must include a timezone')
        if (
            review.get('status') != 'approved'
            or review.get('audit_sample_path') != 'audit_sample.csv'
            or review.get('audit_sample_sha256') != actual_digest
            or review.get('audit_sample_bytes') != actual_bytes
        ):
            raise ValueError(f'{path} audit attestation does not match audit_sample.csv')
        with audit_path.open('r', encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        if not rows or any(
            str(row.get('review_status', '')).strip().casefold() != 'approved'
            for row in rows
        ):
            raise ValueError(f'{path} audit sample contains an unapproved row')
        if review.get('reviewed_row_count') != len(rows):
            raise ValueError(f'{path} audit row count does not match attestation')
        evidence.append(
            {
                'path': str(path),
                'sha256': sha256_file(path),
                'status': 'approved',
                'audit_sample_sha256': actual_digest,
                'reviewer': str(review['reviewer']).strip(),
                'reviewed_at_utc': str(review['reviewed_at_utc']),
            }
        )
    return evidence


def plan_run(config: InferenceConfig) -> dict[str, object]:
    selected = _selected_examples(config)
    prompt_tokens, completion_tokens = _estimated_tokens(config, selected)
    counts = Counter((dataset_id, _r5_level(example)) for dataset_id, example in selected)
    selection = _selection_metadata(selected)
    return {
        'run_id': config.run.run_id,
        'parent_experiment_id': config.run.parent_experiment_id,
        'provider': config.provider.kind,
        'requested_model': config.model.requested_model,
        'split': config.run.split,
        'include_levels': list(config.run.include_levels),
        'chain_complete': config.run.chain_complete,
        'promotion_approved': config.run.promotion_approved,
        'required_human_audit_manifests': [
            str(path) for path in config.run.required_human_audit_manifests
        ],
        'requests': len(selected),
        'counts': {
            f'{dataset_id}:{level}': count
            for (dataset_id, level), count in sorted(counts.items())
        },
        'estimated_prompt_tokens': prompt_tokens,
        'maximum_completion_tokens': completion_tokens,
        'estimated_upper_cost_usd': _cost(config, prompt_tokens, completion_tokens),
        'max_requests': config.budget.max_requests,
        'max_http_attempts_per_invocation': config.budget.max_requests,
        'minimum_interval_seconds': config.provider.minimum_interval_seconds,
        'max_cost_usd': config.budget.max_cost_usd,
        'output_dir': str(config.run.output_dir),
        'selection': selection,
        **selection,
    }


def _append_jsonl(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(dict(value), ensure_ascii=False, sort_keys=True) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.tmp')
    temporary.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
        newline='\n',
    )
    os.replace(temporary, path)


def _completed(path: Path) -> tuple[set[str], set[str], float]:
    if not path.is_file():
        return set(), set(), 0.0
    ids: set[str] = set()
    models: set[str] = set()
    cost = 0.0
    for value in read_jsonl(path):
        record = GenerationRecord.from_dict(value)
        if record.example_id in ids:
            raise ValueError(f'duplicate cached generation for {record.example_id}')
        ids.add(record.example_id)
        models.add(record.model_snapshot_id)
        item_cost = float(record.metadata.get('estimated_cost_usd', 0))
        if not isfinite(item_cost) or item_cost < 0:
            raise ValueError(
                f'cached generation {record.example_id} has invalid estimated cost'
            )
        cost += item_cost
    return ids, models, cost


def _validate_cached_subset(
    config: InferenceConfig,
    path: Path,
    selected: list[tuple[str, Example]],
    fingerprint: ProviderFingerprint,
) -> None:
    '''Reject a stale or contaminated resume cache before making paid calls.'''

    expected = {
        example.example_id: (dataset_id, example)
        for dataset_id, example in selected
    }
    generation_ids: set[str] = set()
    for value in read_jsonl(path):
        record = GenerationRecord.from_dict(value)
        if record.generation_id in generation_ids:
            raise ValueError(f'duplicate cached generation ID {record.generation_id}')
        generation_ids.add(record.generation_id)
        item = expected.get(record.example_id)
        if item is None:
            raise ValueError(
                f'cached generation {record.example_id!r} is outside the frozen selection'
            )
        dataset_id, example = item
        expected_generation_id = (
            f'{config.run.run_id}:'
            f'{hashlib.sha256(record.example_id.encode()).hexdigest()[:24]}'
        )
        if record.run_id != config.run.run_id or record.generation_id != expected_generation_id:
            raise ValueError(f'cached generation {record.example_id} has wrong run identity')
        if record.track != 'open_ended_stress':
            raise ValueError(f'cached generation {record.example_id} has wrong track')
        if record.metadata.get('dataset_id') != dataset_id:
            raise ValueError(f'cached generation {record.example_id} has wrong dataset')
        if record.metadata.get('split') != config.run.split:
            raise ValueError(f'cached generation {record.example_id} has wrong split')
        if record.metadata.get('r5_level') != _r5_level(example):
            raise ValueError(f'cached generation {record.example_id} has wrong R5 level')
        if record.metadata.get('requested_model') != config.model.requested_model:
            raise ValueError(f'cached generation {record.example_id} has wrong requested model')
        if record.metadata.get('provider_name') != fingerprint.provider_name:
            raise ValueError(f'cached generation {record.example_id} has wrong provider')
        if (
            not config.model.allow_fallbacks
            and record.model_snapshot_id != fingerprint.model_snapshot_id
        ):
            raise ValueError(f'cached generation {record.example_id} has wrong model snapshot')


def verify_run_completeness(
    config: InferenceConfig,
    generations_path: str | Path | None = None,
) -> dict[str, object]:
    '''Fail closed unless generations exactly cover the frozen run selection.

    Scoring and reporting entry points can call this function before consuming
    any outputs. It detects missing, unexpected, and duplicate generations,
    stale manifests, split drift, and changed example/chain selections.
    '''

    selected = _selected_examples(config)
    selection = _selection_metadata(selected)
    expected = {
        example.example_id: (dataset_id, example)
        for dataset_id, example in selected
    }
    path = (
        Path(generations_path)
        if generations_path is not None
        else config.run.output_dir / 'generations.jsonl'
    )
    if not path.is_file():
        raise FileNotFoundError(f'missing generations artifact: {path}')

    observed: set[str] = set()
    generation_ids: set[str] = set()
    observed_order: list[str] = []
    returned_models: set[str] = set()
    provider_names: set[str] = set()
    requested_models: set[str] = set()
    for value in read_jsonl(path):
        record = GenerationRecord.from_dict(value)
        if record.example_id in observed:
            raise ValueError(f'duplicate generation for {record.example_id}')
        if record.generation_id in generation_ids:
            raise ValueError(f'duplicate generation ID {record.generation_id}')
        observed.add(record.example_id)
        generation_ids.add(record.generation_id)
        observed_order.append(record.example_id)
        returned_models.add(record.model_snapshot_id)
        provider_names.add(str(record.metadata.get('provider_name', '')))
        requested_models.add(str(record.metadata.get('requested_model', '')))
        expected_item = expected.get(record.example_id)
        if expected_item is None:
            continue
        expected_dataset_id, expected_example = expected_item
        if record.run_id != config.run.run_id:
            raise ValueError(
                f'generation {record.example_id} has run_id {record.run_id!r}, '
                f'expected {config.run.run_id!r}'
            )
        expected_generation_id = (
            f'{config.run.run_id}:'
            f'{hashlib.sha256(record.example_id.encode()).hexdigest()[:24]}'
        )
        if record.generation_id != expected_generation_id:
            raise ValueError(
                f'generation {record.example_id} has a noncanonical generation_id'
            )
        if record.track != 'open_ended_stress':
            raise ValueError(f'generation {record.example_id} has wrong evaluation track')
        if record.metadata.get('dataset_id') != expected_dataset_id:
            raise ValueError(f'generation {record.example_id} has wrong dataset metadata')
        if record.metadata.get('split') != config.run.split:
            raise ValueError(
                f'generation {record.example_id} has wrong split metadata'
            )
        if record.metadata.get('r5_level') != _r5_level(expected_example):
            raise ValueError(
                f'generation {record.example_id} has wrong R5 level metadata'
            )

    expected_ids = set(expected)
    missing = sorted(expected_ids - observed)
    unexpected = sorted(observed - expected_ids)
    if missing or unexpected:
        details: list[str] = []
        if missing:
            details.append(f'missing={missing[:10]!r}')
        if unexpected:
            details.append(f'unexpected={unexpected[:10]!r}')
        raise ValueError(
            'generation selection is incomplete or contaminated: ' + '; '.join(details)
        )

    manifest_path = config.run.output_dir / 'RUN_MANIFEST.json'
    if not manifest_path.is_file():
        raise FileNotFoundError(f'missing run manifest: {manifest_path}')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if not isinstance(manifest, Mapping):
        raise ValueError('RUN_MANIFEST.json must contain an object')
    if manifest.get('run_id') != config.run.run_id:
        raise ValueError('RUN_MANIFEST.json run_id does not match configuration')
    if manifest.get('config_sha256') != sha256_file(config.path):
        raise ValueError('RUN_MANIFEST.json config hash does not match configuration')
    if manifest.get('parent_experiment_id') != config.run.parent_experiment_id:
        raise ValueError('RUN_MANIFEST.json parent experiment does not match configuration')
    if manifest.get('promotion_approved', True) != config.run.promotion_approved:
        raise ValueError('RUN_MANIFEST.json promotion decision does not match configuration')
    if manifest.get('split') != config.run.split:
        raise ValueError('RUN_MANIFEST.json split does not match configuration')
    if manifest.get('status') != _manifest_status(config.run.split):
        raise ValueError('RUN_MANIFEST.json status does not match its split')
    if manifest.get('manifest_version') != 2:
        raise ValueError('RUN_MANIFEST.json has an unsupported manifest version')
    if manifest.get('provider_kind') != config.provider.kind:
        raise ValueError('RUN_MANIFEST.json provider kind does not match configuration')
    if manifest.get('requested_model') != config.model.requested_model:
        raise ValueError('RUN_MANIFEST.json requested model does not match configuration')
    if manifest.get('prompt_template_id') != config.prompt.template_id:
        raise ValueError('RUN_MANIFEST.json prompt template does not match configuration')
    if manifest.get('prompt_system') != config.prompt.system:
        raise ValueError('RUN_MANIFEST.json system prompt does not match configuration')
    if manifest.get('prompt_user_template') != config.prompt.user_template:
        raise ValueError('RUN_MANIFEST.json user prompt does not match configuration')
    if manifest.get('seed') != config.run.seed:
        raise ValueError('RUN_MANIFEST.json seed does not match configuration')
    expected_controls = {
        'include_levels': list(config.run.include_levels),
        'chain_complete': config.run.chain_complete,
        'limit_per_level': config.run.limit_per_level,
    }
    if manifest.get('selection_controls') != expected_controls:
        raise ValueError('RUN_MANIFEST.json selection controls do not match configuration')
    expected_decoding = {
        'temperature': config.model.temperature,
        'max_tokens': config.model.max_tokens,
        'require_logprobs': config.model.require_logprobs,
        'top_logprobs': config.model.top_logprobs,
        'decoding_seed': config.model.decoding_seed,
        'num_ctx': config.model.num_ctx,
        'reasoning_effort': config.model.reasoning_effort,
    }
    if manifest.get('decoding') != expected_decoding:
        raise ValueError('RUN_MANIFEST.json decoding does not match configuration')
    expected_rate_controls = {
        'max_http_attempts_per_invocation': config.budget.max_requests,
        'minimum_interval_seconds': config.provider.minimum_interval_seconds,
        'retries_count_toward_http_attempt_cap': True,
        'stop_invocation_on_http_status': [402, 429],
    }
    if manifest.get('rate_controls') != expected_rate_controls:
        raise ValueError('RUN_MANIFEST.json rate controls do not match configuration')
    expected_routing = {
        'provider_order': list(config.model.provider_order),
        'allow_fallbacks': config.model.allow_fallbacks,
        'require_parameters': config.model.require_parameters,
        'data_collection': config.model.data_collection,
    }
    if manifest.get('routing') != expected_routing:
        raise ValueError('RUN_MANIFEST.json routing does not match configuration')
    if manifest.get('human_audit_evidence') != _required_human_audit_evidence(config):
        raise ValueError('RUN_MANIFEST.json human-audit evidence does not match artifacts')
    fingerprint = manifest.get('provider_fingerprint')
    if not isinstance(fingerprint, Mapping):
        raise ValueError('RUN_MANIFEST.json is missing provider fingerprint')
    expected_snapshot = fingerprint.get('model_snapshot_id')
    expected_provider = fingerprint.get('provider_name')
    if not config.model.allow_fallbacks and returned_models != {expected_snapshot}:
        raise ValueError('generated model snapshot does not match provider fingerprint')
    if provider_names != {expected_provider}:
        raise ValueError('generation provider does not match provider fingerprint')
    if requested_models != {config.model.requested_model}:
        raise ValueError('generation requested model does not match configuration')
    expected_datasets = [
        {
            'dataset_id': value.dataset_id,
            'examples': str(value.examples),
            'examples_sha256': sha256_file(value.examples),
            'workloads': str(value.workloads),
            'workloads_sha256': sha256_file(value.workloads),
        }
        for value in config.datasets
    ]
    if manifest.get('datasets') != expected_datasets:
        raise ValueError('RUN_MANIFEST.json dataset identities do not match artifacts')
    manifest_selection = manifest.get('selection')
    if not isinstance(manifest_selection, Mapping):
        raise ValueError('RUN_MANIFEST.json is missing frozen selection metadata')
    for name, expected_value in selection.items():
        if manifest_selection.get(name) != expected_value:
            raise ValueError(
                f'RUN_MANIFEST.json selection mismatch for {name}'
            )

    return {
        'status': 'complete',
        'run_id': config.run.run_id,
        'parent_experiment_id': config.run.parent_experiment_id,
        'split': config.run.split,
        'selected': len(expected_ids),
        'observed': len(observed),
        **selection,
        'observed_example_ids_sha256': _canonical_hash(observed_order),
    }


def run_inference(config: InferenceConfig) -> dict[str, object]:
    config.validate_for_execution()
    plan = plan_run(config)
    if int(plan['requests']) > config.budget.max_requests:
        raise ValueError('planned requests exceed budget.max_requests')
    if float(plan['estimated_upper_cost_usd']) > config.budget.max_cost_usd:
        raise ValueError('estimated upper cost exceeds budget.max_cost_usd')
    if not config.run.promotion_approved:
        raise ValueError(
            'run is not approved for promotion after development diagnostics; '
            'create a new model condition and config instead of bypassing this gate'
        )
    human_audit_evidence = _required_human_audit_evidence(config)
    output = config.run.output_dir
    output.mkdir(parents=True, exist_ok=True)
    with _RunDirectoryLock(output, config.run.run_id):
        return _run_inference_exclusive(config, plan, human_audit_evidence, output)


def _run_inference_exclusive(
    config: InferenceConfig,
    plan: Mapping[str, object],
    human_audit_evidence: list[dict[str, str]],
    output: Path,
) -> dict[str, object]:
    provider = _provider(config)
    provider_fingerprint = provider.preflight(config.model.requested_model)
    generations_path = output / 'generations.jsonl'
    failures_path = output / 'failures.jsonl'
    if generations_path.exists() and not config.run.resume:
        raise FileExistsError('generations.jsonl exists and resume=false')
    completed, returned_models, actual_cost = _completed(generations_path)
    selected = _selected_examples(config)
    selected_ids = {row.example_id for _, row in selected}
    unexpected_cached = sorted(completed - selected_ids)
    if unexpected_cached:
        raise ValueError(
            'cached generations contain IDs outside the frozen selection: '
            f'{unexpected_cached[:10]!r}'
        )
    remaining = [(dataset, row) for dataset, row in selected if row.example_id not in completed]
    manifest_path = output / 'RUN_MANIFEST.json'
    existing_manifest: object | None = None
    created_at_utc = datetime.now(timezone.utc).isoformat()
    if manifest_path.is_file():
        existing_manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if isinstance(existing_manifest, dict):
            prior_created = existing_manifest.get('created_at_utc')
            if isinstance(prior_created, str) and prior_created:
                created_at_utc = prior_created
    provider_guards = provider_fingerprint.metadata.get('closed_book')
    if not isinstance(provider_guards, Mapping):
        provider_guards = {}
    manifest = {
        'manifest_version': 2,
        'status': _manifest_status(config.run.split),
        'run_id': config.run.run_id,
        'parent_experiment_id': config.run.parent_experiment_id,
        'promotion_approved': config.run.promotion_approved,
        'created_at_utc': created_at_utc,
        'config_path': str(config.path),
        'config_sha256': sha256_file(config.path),
        'provider_kind': config.provider.kind,
        'requested_model': config.model.requested_model,
        'provider_fingerprint': _fingerprint_dict(provider_fingerprint),
        'prompt_template_id': config.prompt.template_id,
        'prompt_system': config.prompt.system,
        'prompt_user_template': config.prompt.user_template,
        'split': config.run.split,
        'seed': config.run.seed,
        'selection_controls': {
            'include_levels': list(config.run.include_levels),
            'chain_complete': config.run.chain_complete,
            'limit_per_level': config.run.limit_per_level,
        },
        'selection': dict(plan['selection']),
        'human_audit_evidence': human_audit_evidence,
        'decoding': {
            'temperature': config.model.temperature,
            'max_tokens': config.model.max_tokens,
            'require_logprobs': config.model.require_logprobs,
            'top_logprobs': config.model.top_logprobs,
            'decoding_seed': config.model.decoding_seed,
            'num_ctx': config.model.num_ctx,
            'reasoning_effort': config.model.reasoning_effort,
        },
        'rate_controls': {
            'max_http_attempts_per_invocation': config.budget.max_requests,
            'minimum_interval_seconds': config.provider.minimum_interval_seconds,
            'retries_count_toward_http_attempt_cap': True,
            'stop_invocation_on_http_status': [402, 429],
        },
        'routing': {
            'provider_order': list(config.model.provider_order),
            'allow_fallbacks': config.model.allow_fallbacks,
            'require_parameters': config.model.require_parameters,
            'data_collection': config.model.data_collection,
        },
        'closed_book': {
            'dataset_fields_sent': ['question'],
            'hidden_dataset_fields': [
                'accepted_answers',
                'supporting_paragraphs',
                'decomposition',
                'intermediate_answers',
                'dataset_id',
                'r5_level',
            ],
            'tools': [],
            'rag_context': False,
            'web_search': False,
            'provider_guards': dict(provider_guards),
        },
        'datasets': [
            {
                'dataset_id': value.dataset_id,
                'examples': str(value.examples),
                'examples_sha256': sha256_file(value.examples),
                'workloads': str(value.workloads),
                'workloads_sha256': sha256_file(value.workloads),
            }
            for value in config.datasets
        ],
        'plan': plan,
        'condition_status': 'provisional_model_condition_hash; R1/R3 enrichment remains separate',
    }
    if existing_manifest is not None:
        if existing_manifest != manifest:
            raise ValueError('existing RUN_MANIFEST.json does not match this run configuration')
    else:
        _write_json(manifest_path, manifest)
    if completed:
        _validate_cached_subset(
            config,
            generations_path,
            selected,
            provider_fingerprint,
        )
    succeeded = 0
    failed = 0
    stop_reason: str | None = None
    for dataset_id, example in remaining:
        user_prompt = config.prompt.user_template.format(question=example.question)
        request = InferenceRequest(
            example_id=example.example_id,
            model=config.model.requested_model,
            system_prompt=config.prompt.system,
            user_prompt=user_prompt,
            temperature=config.model.temperature,
            max_tokens=config.model.max_tokens,
            require_logprobs=config.model.require_logprobs,
            top_logprobs=config.model.top_logprobs,
            decoding_seed=config.model.decoding_seed,
            num_ctx=config.model.num_ctx,
            provider_order=config.model.provider_order,
            allow_fallbacks=config.model.allow_fallbacks,
            require_parameters=config.model.require_parameters,
            data_collection=config.model.data_collection,
            reasoning_effort=config.model.reasoning_effort,
        )
        started = perf_counter()
        try:
            response = provider.generate(request)
            latency_ms = round((perf_counter() - started) * 1000, 3)
            if response.requested_model != config.model.requested_model:
                raise ValueError('provider response changed the requested model identity')
            if response.provider_name != provider_fingerprint.provider_name:
                raise ValueError('provider response identity does not match preflight')
            if (
                not config.model.allow_fallbacks
                and response.returned_model != provider_fingerprint.model_snapshot_id
            ):
                raise ValueError('provider response model snapshot does not match preflight')
            returned_models.add(response.returned_model)
            if len(returned_models) > 1 and not config.model.allow_fallbacks:
                raise ValueError(f'mixed returned models detected: {sorted(returned_models)}')
            estimated_cost = _cost(config, response.prompt_tokens, response.completion_tokens)
            if actual_cost + estimated_cost > config.budget.max_cost_usd:
                raise RuntimeError('actual accumulated cost would exceed budget.max_cost_usd')
            condition_hash = _canonical_hash(
                {
                    'example_id': example.example_id,
                    'model_snapshot_id': response.returned_model,
                    'status': 'provisional_r1_r3_unresolved',
                }
            )
            generation_id = f'{config.run.run_id}:{hashlib.sha256(example.example_id.encode()).hexdigest()[:24]}'
            record = GenerationRecord(
                generation_id=generation_id,
                run_id=config.run.run_id,
                example_id=example.example_id,
                model_snapshot_id=response.returned_model,
                condition_hash=condition_hash,
                track='open_ended_stress',
                raw_text=response.text,
                candidates=(response.text,),
                score=response.score,
                score_kind='raw',
                score_source=response.score_source,
                normalization_contract='raw-score-requires-calibration-v1',
                metadata={
                    'dataset_id': dataset_id,
                    'split': example.split,
                    'r5_level': _r5_level(example),
                    'requested_model': response.requested_model,
                    'returned_model': response.returned_model,
                    'provider_name': response.provider_name,
                    'provider_request_id': response.request_id,
                    'finish_reason': response.finish_reason,
                    'prompt_template_id': config.prompt.template_id,
                    'prompt_tokens': response.prompt_tokens,
                    'completion_tokens': response.completion_tokens,
                    'latency_ms': latency_ms,
                    'estimated_cost_usd': estimated_cost,
                    'condition_status': 'provisional_r1_r3_unresolved',
                    **dict(response.metadata),
                },
            )
            _append_jsonl(generations_path, record.to_dict())
            actual_cost += estimated_cost
            succeeded += 1
        except (ProviderError, ValueError, RuntimeError) as error:
            if (
                isinstance(error, ProviderError)
                and error.stop_invocation
                and not error.request_sent
            ):
                stop_reason = str(error)
                break
            failed += 1
            _append_jsonl(
                failures_path,
                {
                    'run_id': config.run.run_id,
                    'example_id': example.example_id,
                    'dataset_id': dataset_id,
                    'error_type': type(error).__name__,
                    'error': str(error),
                    'status_code': getattr(error, 'status_code', None),
                    'retryable': bool(getattr(error, 'retryable', False)),
                    'stop_invocation': bool(
                        getattr(error, 'stop_invocation', False)
                    ),
                    'request_sent': bool(getattr(error, 'request_sent', True)),
                    'created_at_utc': datetime.now(timezone.utc).isoformat(),
                },
            )
            if isinstance(error, RuntimeError) and 'budget' in str(error):
                stop_reason = str(error)
                break
            if isinstance(error, ProviderError) and (
                error.stop_invocation or not error.retryable
            ):
                stop_reason = str(error)
                break
    summary = {
        'run_id': config.run.run_id,
        'parent_experiment_id': config.run.parent_experiment_id,
        'split': config.run.split,
        'selected': len(selected),
        'previously_completed': len(completed),
        'attempted_this_invocation': succeeded + failed,
        'succeeded_this_invocation': succeeded,
        'failed_this_invocation': failed,
        'http_attempts_this_invocation': int(
            getattr(provider, 'http_attempts', 0)
        ),
        'max_http_attempts_per_invocation': config.budget.max_requests,
        'stop_reason': stop_reason,
        'remaining_after_invocation': len(selected) - len(completed) - succeeded,
        'estimated_accumulated_cost_usd': actual_cost,
        'returned_models': sorted(returned_models),
        'completion_status': (
            'complete'
            if len(selected) - len(completed) - succeeded == 0
            else 'incomplete'
        ),
        'selection': dict(plan['selection']),
    }
    _write_json(output / 'RUN_SUMMARY.json', summary)
    return summary
