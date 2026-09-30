'''CLI and adapters for auditable CalibRead dataset preparation.'''

from __future__ import annotations

import argparse
import ast
from collections import Counter
import csv
import gzip
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import os
import re
from typing import Iterable, Mapping, Sequence
import zipfile

from .data_sources import REGISTRY_PATH, fetch_source, file_fingerprints, load_registry, source_spec
from .dimensions import DimensionValues, dimension_value, r4_from_interpretation_count, r5_from_hop_count, r6_from_specificity
from .io import sha256_file, write_jsonl
from .leakage import DEFAULT_DISJOINT_KEYS, assert_no_split_leakage, find_split_leakage, normalized_question_hash
from .schema import Example, WorkloadRecord
from .splits import assign_splits


def _hash_json(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _unique_strings(values: Iterable[object]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        rendered = str(value).strip()
        if rendered and rendered.casefold() not in seen:
            result.append(rendered)
            seen.add(rendered.casefold())
    return tuple(result)


def _parse_sequence(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return _unique_strings(value)
    text = str(value or '').strip()
    if not text:
        return ()
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(text)
        except (ValueError, SyntaxError, json.JSONDecodeError):
            continue
        if isinstance(parsed, (list, tuple)):
            return _unique_strings(parsed)
        if isinstance(parsed, str):
            return _unique_strings((parsed,))
    return _unique_strings((text,))


def _dimensions(hops: int) -> DimensionValues:
    return DimensionValues(
        {
            'R2': dimension_value('R2', 'medium', 'medium'),
            'R4': r4_from_interpretation_count(1),
            'R5': r5_from_hop_count(hops),
            'R6': r6_from_specificity(0.10, general_max=0.33, specialized_max=0.66),
        }
    )


def _workload(
    *,
    example_id: str,
    question: str,
    answers: Sequence[str],
    hops: int,
    chain_id: str,
    constituents: Sequence[str],
    provenance: Mapping[str, object],
) -> WorkloadRecord:
    accepted = _unique_strings(answers)
    interpretations = {'source_interpretation_1': accepted}
    chain_spec = {'chain_id': chain_id, 'constituents': list(constituents), 'hops': hops}
    return WorkloadRecord(
        example_id=example_id,
        question=question,
        accepted_answers=accepted,
        track='open_ended_stress',
        dimensions=_dimensions(hops),
        r4_annotation_hash=_hash_json(interpretations),
        r5_chain_spec_hash=_hash_json(chain_spec),
        interpretation_answers=interpretations,
        chain_id=chain_id,
        constituent_example_ids=tuple(constituents),
        domain_name='general_knowledge',
        missing_reasons={'R1': 'model_condition_record', 'R3': 'model_condition_record'},
        provenance=dict(provenance),
    )


def _example(workload: WorkloadRecord, lineage: Mapping[str, object]) -> Example:
    metadata = dict(lineage)
    metadata.update(
        {
            'question_hash': normalized_question_hash(workload.question),
            'track': workload.track,
            'domain_name': workload.domain_name,
            'source_provenance': dict(workload.provenance),
        }
    )
    example = Example(
        example_id=workload.example_id,
        question=workload.question,
        accepted_answers=workload.accepted_answers,
        group=workload.dimensions.crossed_group(('R2', 'R4', 'R5', 'R6')),
        metadata=metadata,
    )
    return example.with_dimension_values(workload.dimensions)


def _condition_seed(
    example_id: str,
    *,
    r1_proxy: object,
    r1_source: str,
    r1_unit: str,
    source_id: str,
) -> dict[str, object]:
    return {
        'example_id': example_id,
        'source_id': source_id,
        'status': 'requires_model_snapshot_enrichment',
        'R1': {
            'proxy_value': r1_proxy,
            'proxy_source': r1_source,
            'proxy_unit': r1_unit,
            'warning': 'Proxy only; bin thresholds must be frozen per model/corpus protocol.',
        },
        'R3': {
            'event_date': None,
            'model_cutoff_date': None,
            'warning': 'Cannot be assigned until both event date and model cutoff are known.',
        },
    }


def adapt_popqa(path: str | Path, limit: int | None = None) -> tuple[list[WorkloadRecord], list[Example], list[dict[str, object]], Counter[str]]:
    workloads: list[WorkloadRecord] = []
    examples: list[Example] = []
    seeds: list[dict[str, object]] = []
    exclusions: Counter[str] = Counter()
    with Path(path).open('r', encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream, delimiter='\t')
        for index, row in enumerate(reader):
            if limit is not None and len(workloads) >= limit:
                break
            source_row_id = str(row.get('id') or index).strip()
            question = str(row.get('question') or '').strip()
            answers = _unique_strings((*_parse_sequence(row.get('possible_answers')), row.get('obj', '')))
            if not question or not answers:
                exclusions['missing_question_or_answer'] += 1
                continue
            example_id = f'popqa:{source_row_id}'
            subject_id = str(row.get('subj_id') or row.get('s_uri') or row.get('subj') or source_row_id).strip()
            property_id = str(row.get('prop_id') or row.get('prop') or 'unknown_property').strip()
            object_id = str(row.get('obj_id') or row.get('o_uri') or row.get('obj') or 'unknown_object').strip()
            chain_id = f'popqa:chain:{source_row_id}'
            fact_id = f'popqa:fact:{subject_id}:{property_id}:{object_id}'
            workload = _workload(
                example_id=example_id,
                question=question,
                answers=answers,
                hops=1,
                chain_id=chain_id,
                constituents=(fact_id,),
                provenance={'source_id': 'popqa', 'source_row_id': source_row_id, 'adapter_version': 1},
            )
            lineage = {
                'entity_id': subject_id,
                'chain_id': chain_id,
                'template_id': f'popqa:property:{property_id}',
                'source_fact_id': fact_id,
            }
            workloads.append(workload)
            examples.append(_example(workload, lineage))
            popularity = str(row.get('s_pop') or '').strip()
            try:
                proxy: object = float(popularity)
            except ValueError:
                proxy = None
            seeds.append(
                _condition_seed(
                    example_id,
                    r1_proxy=proxy,
                    r1_source='PopQA subject popularity field s_pop',
                    r1_unit='upstream popularity score',
                    source_id='popqa',
                )
            )
    return workloads, examples, seeds, exclusions


def _socrates_answers(row: Mapping[str, str], entity: str, relation_value: str) -> tuple[str, ...]:
    return _unique_strings(
        (
            row.get(f'{entity}.value', ''),
            relation_value,
            *_parse_sequence(row.get(f'{entity}.minimal_aliases', '')),
            *_parse_sequence(row.get(f'{entity}.aliases', '')),
        )
    )


def _number_or_none(value: object) -> int | float | None:
    text = str(value or '').strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def adapt_socrates(path: str | Path, limit: int | None = None) -> tuple[list[WorkloadRecord], list[Example], list[dict[str, object]], Counter[str]]:
    workloads: list[WorkloadRecord] = []
    examples: list[Example] = []
    seeds: list[dict[str, object]] = []
    exclusions: Counter[str] = Counter()
    csv.field_size_limit(50_000_000)
    with Path(path).open('r', encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        accepted_source_rows = 0
        for index, row in enumerate(reader):
            if limit is not None and accepted_source_rows >= limit:
                break
            uid = str(row.get('uid') or index).strip()
            chain_id = f'socrates:chain:{uid}'
            r1_id = f'socrates:{uid}:r1'
            r2_id = f'socrates:{uid}:r2'
            composed_id = f'socrates:{uid}:composed'
            questions = (
                str(row.get('r1(e1).prompt') or '').strip(),
                str(row.get('r2(e2).prompt') or '').strip(),
                str(row.get('r2(r1(e1)).prompt') or '').strip(),
            )
            answers_r1 = _socrates_answers(row, 'e2', str(row.get('r1.value') or ''))
            answers_r2 = _socrates_answers(row, 'e3', str(row.get('r2.value') or ''))
            if not all(questions) or not answers_r1 or not answers_r2:
                exclusions['missing_question_or_answer'] += 1
                continue
            fact1 = f'socrates:fact:{uid}:r1'
            fact2 = f'socrates:fact:{uid}:r2'
            definitions = (
                (r1_id, questions[0], answers_r1, 1, (fact1,), str(row.get('r1.template_id') or 'r1'), fact1, row.get('wimbd.dolma17(e1,e2)')),
                (r2_id, questions[1], answers_r2, 1, (fact2,), str(row.get('r2.template_id') or 'r2'), fact2, row.get('wimbd.dolma17(e2,e3)')),
                (composed_id, questions[2], answers_r2, 2, (r1_id, r2_id), str(row.get('mu.template_id') or row.get('tid') or 'composed'), (fact1, fact2), row.get('wimbd.dolma(e1,e2,e3)')),
            )
            entity_ids = _unique_strings(
                (row.get('e1.wikidata_qid', ''), row.get('e2.wikidata_qid', ''), row.get('e3.wikidata_qid', ''))
            ) or (f'socrates:entity-set:{uid}',)
            for example_id, question, answers, hops, constituents, template, facts, proxy_raw in definitions:
                workload = _workload(
                    example_id=example_id,
                    question=question,
                    answers=answers,
                    hops=hops,
                    chain_id=chain_id,
                    constituents=constituents,
                    provenance={'source_id': 'socrates_v1', 'source_row_id': uid, 'adapter_version': 1},
                )
                lineage = {
                    'entity_id': entity_ids,
                    'chain_id': chain_id,
                    'template_id': f'socrates:template:{template}',
                    'source_fact_id': facts,
                }
                workloads.append(workload)
                examples.append(_example(workload, lineage))
                seeds.append(
                    _condition_seed(
                        example_id,
                        r1_proxy=_number_or_none(proxy_raw),
                        r1_source='SOCRATES WIMBD co-occurrence field',
                        r1_unit='upstream corpus co-occurrence count',
                        source_id='socrates_v1',
                    )
                )
            accepted_source_rows += 1
    return workloads, examples, seeds, exclusions


def adapt_streamingqa(path: str | Path, limit: int | None = None) -> tuple[list[WorkloadRecord], list[Example], list[dict[str, object]], Counter[str]]:
    '''Convert StreamingQA while preserving publication timestamps as R3 proxies.'''

    workloads: list[WorkloadRecord] = []
    examples: list[Example] = []
    seeds: list[dict[str, object]] = []
    exclusions: Counter[str] = Counter()
    with gzip.open(Path(path), 'rt', encoding='utf-8') as stream:
        for line_number, line in enumerate(stream, start=1):
            if limit is not None and len(workloads) >= limit:
                break
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                exclusions['malformed_json'] += 1
                continue
            if not isinstance(row, Mapping):
                exclusions['non_object_row'] += 1
                continue
            source_row_id = str(row.get('qa_id') or f'line-{line_number}').strip()
            question = str(row.get('question') or '').strip()
            answers = _unique_strings(
                (*_parse_sequence(row.get('answers')), *_parse_sequence(row.get('answers_additional')))
            )
            if not question or not answers:
                exclusions['missing_question_or_answer'] += 1
                continue
            evidence_id = str(row.get('evidence_id') or source_row_id)
            evidence_hash = hashlib.sha256(evidence_id.encode('utf-8')).hexdigest()
            example_id = f'streamingqa:{source_row_id}'
            chain_id = f'streamingqa:evidence:{evidence_hash}'
            fact_id = f'streamingqa:fact:{evidence_hash}'
            origin = str(row.get('written_or_generated') or 'unknown')
            workload = _workload(
                example_id=example_id,
                question=question,
                answers=answers,
                hops=1,
                chain_id=chain_id,
                constituents=(fact_id,),
                provenance={
                    'source_id': 'streamingqa_valid',
                    'source_row_id': source_row_id,
                    'adapter_version': 1,
                    'recent_or_past': str(row.get('recent_or_past') or ''),
                    'written_or_generated': origin,
                },
            )
            lineage = {
                'entity_id': f'streamingqa:evidence-entity:{evidence_hash}',
                'chain_id': chain_id,
                'template_id': f'streamingqa:origin:{origin}',
                'source_fact_id': fact_id,
            }
            evidence_ts = _number_or_none(row.get('evidence_ts'))
            question_ts = _number_or_none(row.get('question_ts'))
            evidence_date = (
                datetime.fromtimestamp(float(evidence_ts), tz=timezone.utc).date().isoformat()
                if evidence_ts is not None
                else None
            )
            question_date = (
                datetime.fromtimestamp(float(question_ts), tz=timezone.utc).date().isoformat()
                if question_ts is not None
                else None
            )
            seed = _condition_seed(
                example_id,
                r1_proxy=None,
                r1_source='not supplied by StreamingQA',
                r1_unit='unresolved',
                source_id='streamingqa_valid',
            )
            seed['R3'] = {
                'event_date_proxy': evidence_date,
                'question_date': question_date,
                'proxy_source': 'StreamingQA evidence_ts and question_ts',
                'value_kind': 'proxy',
                'recent_or_past': str(row.get('recent_or_past') or ''),
                'model_cutoff_date': None,
                'warning': 'Evidence publication time is not guaranteed to be the underlying fact event date.',
            }
            workloads.append(workload)
            examples.append(_example(workload, lineage))
            seeds.append(seed)
    return workloads, examples, seeds, exclusions


_MUSIQUE_MEMBERS = (
    ('train', 'data/musique_ans_v1.0_train.jsonl'),
    ('dev', 'data/musique_ans_v1.0_dev.jsonl'),
)
_MUSIQUE_TEST_MEMBER = 'data/musique_ans_v1.0_test.jsonl'
_MUSIQUE_GRAPH_TYPE = re.compile(r'^(?P<hops>[234])hop(?:[1-4])?$')


def _musique_graph(source_row_id: str) -> tuple[int, str]:
    graph_type, separator, _ = source_row_id.partition('__')
    match = _MUSIQUE_GRAPH_TYPE.fullmatch(graph_type)
    if not separator or match is None:
        raise ValueError('invalid MuSiQue composition identifier')
    return int(match.group('hops')), graph_type


def adapt_musique(path: str | Path, limit: int | None = None) -> tuple[list[WorkloadRecord], list[Example], list[dict[str, object]], Counter[str]]:
    '''Convert labeled MuSiQue-Ans rows with decomposition-backed R5 levels.'''

    workloads: list[WorkloadRecord] = []
    examples: list[Example] = []
    seeds: list[dict[str, object]] = []
    exclusions: Counter[str] = Counter()
    seen_ids: set[str] = set()
    with zipfile.ZipFile(Path(path)) as archive:
        available = set(archive.namelist())
        missing_members = [member for _, member in _MUSIQUE_MEMBERS if member not in available]
        if missing_members:
            raise ValueError(f'MuSiQue archive is missing required members: {missing_members}')
        stop = False
        for upstream_split, member in _MUSIQUE_MEMBERS:
            with archive.open(member) as stream:
                for line_number, raw_line in enumerate(stream, start=1):
                    if limit is not None and len(workloads) >= limit:
                        stop = True
                        break
                    try:
                        row = json.loads(raw_line)
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        exclusions['malformed_json'] += 1
                        continue
                    if not isinstance(row, Mapping):
                        exclusions['non_object_row'] += 1
                        continue
                    source_row_id = str(row.get('id') or '').strip()
                    if not source_row_id:
                        exclusions['missing_source_id'] += 1
                        continue
                    if source_row_id in seen_ids:
                        exclusions['duplicate_source_id'] += 1
                        continue
                    try:
                        hops, graph_type = _musique_graph(source_row_id)
                    except ValueError:
                        exclusions['invalid_composition_id'] += 1
                        continue
                    question = str(row.get('question') or '').strip()
                    answers = _unique_strings(
                        (row.get('answer', ''), *_parse_sequence(row.get('answer_aliases')))
                    )
                    decomposition = row.get('question_decomposition')
                    paragraphs = row.get('paragraphs')
                    if not question or not answers:
                        exclusions['missing_question_or_answer'] += 1
                        continue
                    if not isinstance(decomposition, list) or len(decomposition) != hops:
                        exclusions['decomposition_hop_mismatch'] += 1
                        continue
                    if not isinstance(paragraphs, list) or not all(
                        isinstance(value, Mapping) for value in paragraphs
                    ):
                        exclusions['invalid_paragraphs'] += 1
                        continue
                    paragraph_by_index = {value.get('idx'): value for value in paragraphs}
                    step_ids: list[str] = []
                    supporting_titles: list[str] = []
                    normalized_steps: list[dict[str, object]] = []
                    invalid_step = False
                    for position, step in enumerate(decomposition, start=1):
                        if not isinstance(step, Mapping):
                            invalid_step = True
                            break
                        upstream_step_id = str(step.get('id') or '').strip()
                        step_question = str(step.get('question') or '').strip()
                        step_answer = str(step.get('answer') or '').strip()
                        support_index = step.get('paragraph_support_idx')
                        paragraph = paragraph_by_index.get(support_index)
                        if (
                            not upstream_step_id
                            or not step_question
                            or not step_answer
                            or not isinstance(support_index, int)
                            or paragraph is None
                            or not bool(paragraph.get('is_supporting'))
                        ):
                            invalid_step = True
                            break
                        title = str(paragraph.get('title') or '').strip()
                        if not title:
                            invalid_step = True
                            break
                        constituent_id = f'musique:singlehop:{upstream_step_id}'
                        step_ids.append(constituent_id)
                        supporting_titles.append(f'musique:title:{title}')
                        normalized_steps.append(
                            {
                                'position': position,
                                'source_step_id': upstream_step_id,
                                'question': step_question,
                                'answer': step_answer,
                                'paragraph_support_idx': support_index,
                                'supporting_title': title,
                            }
                        )
                    if invalid_step:
                        exclusions['invalid_decomposition_step'] += 1
                        continue
                    if len(set(step_ids)) != hops:
                        exclusions['duplicate_decomposition_step'] += 1
                        continue
                    example_id = f'musique:{source_row_id}'
                    chain_id = f'musique:composition:{source_row_id}'
                    workload = _workload(
                        example_id=example_id,
                        question=question,
                        answers=answers,
                        hops=hops,
                        chain_id=chain_id,
                        constituents=step_ids,
                        provenance={
                            'source_id': 'musique',
                            'source_row_id': source_row_id,
                            'source_split': upstream_split,
                            'adapter_version': 1,
                            'graph_type': graph_type,
                            'hop_count_source': 'composition_id_and_decomposition_length',
                            'question_decomposition': normalized_steps,
                        },
                    )
                    lineage = {
                        'entity_id': tuple(supporting_titles),
                        'chain_id': chain_id,
                        'template_id': f'musique:graph:{graph_type}',
                        'source_fact_id': tuple(step_ids),
                    }
                    workloads.append(workload)
                    examples.append(_example(workload, lineage))
                    seeds.append(
                        _condition_seed(
                            example_id,
                            r1_proxy=None,
                            r1_source='not supplied by MuSiQue',
                            r1_unit='unresolved',
                            source_id='musique',
                        )
                    )
                    seen_ids.add(source_row_id)
            if stop:
                break
        if limit is None and _MUSIQUE_TEST_MEMBER in available:
            with archive.open(_MUSIQUE_TEST_MEMBER) as stream:
                exclusions['unlabeled_official_test'] = sum(1 for _ in stream)
    return workloads, examples, seeds, exclusions


ADAPTERS = {
    'popqa': adapt_popqa,
    'socrates_v1': adapt_socrates,
    'streamingqa': adapt_streamingqa,
    'musique_v1': adapt_musique,
}
PRIMARY_SPLIT_KEYS = ('chain_id', 'source_fact_id', 'question_hash')


def _atomic_csv(path: Path, rows: Sequence[Mapping[str, object]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _audit_rows(
    workloads: Sequence[WorkloadRecord],
    examples: Sequence[Example],
    size: int,
    *,
    stratify_r5: bool = False,
) -> list[dict[str, object]]:
    by_id = {example.example_id: example for example in examples}
    ordered = sorted(
        workloads,
        key=lambda row: hashlib.sha256(row.example_id.encode('utf-8')).hexdigest(),
    )
    selected = ordered[:size]
    if stratify_r5 and ordered:
        buckets: dict[str, list[WorkloadRecord]] = {}
        for row in ordered:
            buckets.setdefault(row.dimensions['R5'].level, []).append(row)
        levels = sorted(buckets)
        base, remainder = divmod(size, len(levels))
        selected = []
        for index, level in enumerate(levels):
            quota = base + int(index < remainder)
            selected.extend(buckets[level][:quota])
        if len(selected) < size:
            selected_ids = {row.example_id for row in selected}
            selected.extend(
                row for row in ordered
                if row.example_id not in selected_ids
            )
            selected = selected[:size]
    return [
        {
            'example_id': row.example_id,
            'split': by_id[row.example_id].split,
            'question': row.question,
            'accepted_answers': ' | '.join(row.accepted_answers),
            'r2': row.dimensions['R2'].level,
            'r4': row.dimensions['R4'].level,
            'r5': row.dimensions['R5'].level,
            'r6': row.dimensions['R6'].level,
            'source_row_id': row.provenance.get('source_row_id', ''),
            'review_status': 'pending_human_review',
        }
        for row in selected
    ]


def refine_source(
    source_id: str,
    *,
    raw_path: str | Path | None = None,
    registry_path: str | Path = REGISTRY_PATH,
    raw_root: str | Path = Path('data/raw'),
    processed_root: str | Path = Path('data/processed'),
    limit: int | None = None,
    seed: int = 20260811,
    audit_size: int = 30,
    split_profile: str = 'primary',
) -> Path:
    '''Convert one source, validate records, split by lineage, and document outputs.'''

    spec = source_spec(source_id, registry_path)
    if spec.text('license_status') != 'approved':
        raise PermissionError(f'{source_id} is not license-approved')
    adapter_name = spec.text('adapter')
    if adapter_name not in ADAPTERS:
        raise NotImplementedError(f'{source_id} adapter {adapter_name!r} is not implemented yet')
    source_path = Path(raw_path) if raw_path is not None else Path(raw_root) / source_id / spec.filename
    if not source_path.is_file():
        raise FileNotFoundError(f'raw source not found: {source_path}; run fetch first')
    fingerprints = file_fingerprints(source_path)
    expected = spec.text('expected_sha256').lower()
    if expected and fingerprints['sha256'] != expected:
        raise ValueError(f'{source_id} raw SHA-256 does not match the registry')
    expected_md5 = spec.text('expected_md5').lower()
    if expected_md5 and fingerprints['md5'] != expected_md5:
        raise ValueError(f'{source_id} raw MD5 does not match the registry')

    workloads, unsplit, seeds, exclusions = ADAPTERS[adapter_name](source_path, limit)
    if not workloads:
        raise ValueError(f'{source_id} adapter emitted no valid records')
    if split_profile not in {'primary', 'strict_all'}:
        raise ValueError('split_profile must be primary or strict_all')
    split_keys = PRIMARY_SPLIT_KEYS if split_profile == 'primary' else DEFAULT_DISJOINT_KEYS
    strata_keys = ('r5_synthesis_level',) if source_id == 'musique' else ()
    examples = assign_splits(
        unsplit,
        seed=seed,
        disjoint_keys=split_keys,
        strata_keys=strata_keys,
    )
    assert_no_split_leakage(examples, disjoint_keys=split_keys)
    all_lineage_findings = find_split_leakage(examples)
    for workload in workloads:
        WorkloadRecord.from_dict(workload.to_dict())
    for example in examples:
        Example.from_dict(example.to_dict())

    output = Path(processed_root) / source_id
    output.mkdir(parents=True, exist_ok=True)
    workload_path = output / 'workloads.jsonl'
    example_path = output / 'examples.jsonl'
    seed_path = output / 'condition_seeds.jsonl'
    audit_path = output / 'audit_sample.csv'
    card_path = output / 'DATA_CARD.md'
    write_jsonl(workload_path, (record.to_dict() for record in workloads))
    write_jsonl(example_path, (record.to_dict() for record in examples))
    write_jsonl(seed_path, seeds)
    audit = _audit_rows(
        workloads,
        examples,
        min(audit_size, len(workloads)),
        stratify_r5=source_id == 'musique',
    )
    _atomic_csv(audit_path, audit, tuple(audit[0]))

    split_counts = Counter(example.split for example in examples)
    if len(workloads) >= 30 and set(split_counts) != {'development', 'calibration', 'test'}:
        raise ValueError(
            f'{split_profile} split profile produced empty partitions: {dict(split_counts)}'
        )
    r5_counts = Counter(workload.dimensions['R5'].level for workload in workloads)
    r3_limitation = (
        'StreamingQA evidence and question publication dates are preserved as R3 proxies, but the '
        'underlying fact event date may differ and a model cutoff is still required.'
        if source_id == 'streamingqa_valid'
        else 'R3 remains unresolved until a dated fact and immutable model cutoff are joined.'
    )
    source_limitation = (
        'Only labeled MuSiQue-Ans train/dev records are included. The unlabeled official test '
        'split is counted as an exclusion, and MuSiQue-Full is omitted to avoid duplicate '
        'answerable questions. Hop labels are cross-checked against decomposition length, and '
        'shared constituent single-hop IDs are protected across CalibRead splits.'
        if source_id == 'musique'
        else ''
    )
    card = f'''# Data card: {spec.text('title')}

- Source ID: `{source_id}`
- Upstream: {spec.text('homepage')}
- License: {spec.text('license')} ({spec.text('license_url')})
- Redistribution permitted by registry: {bool(spec.values.get('redistribution', False))}
- Attribution: {spec.text('attribution')}
- Raw file: `{source_path}`
- Raw bytes: {fingerprints['bytes']}
- Raw SHA-256: `{fingerprints['sha256']}`
- Adapter: `{adapter_name}` version 1
- Created UTC: {datetime.now(timezone.utc).isoformat()}
- Development limit: {limit if limit is not None else 'none (full source)'}

## Output and validation

- Valid workload records: {len(workloads)}
- Development/calibration/test: {split_counts['development']} / {split_counts['calibration']} / {split_counts['test']}
- Primary split profile: `{split_profile}`; protected keys: {list(split_keys)}
- Split stratification keys: {list(strata_keys)}
- Entity/template overlap under strict-all audit: {dict((key, len(values)) for key, values in all_lineage_findings.items()) or {}}
- R5 levels: {dict(sorted(r5_counts.items()))}
- Exclusions: {dict(sorted(exclusions.items())) or {}}
- Strict WorkloadRecord validation: passed
- R1 and R3 routing to condition seeds: passed
- Primary chain/fact/question lineage completeness and leakage audit: passed
- Audit sample rows: {len(audit)}; human review remains pending
- Audit sample R5 stratification: {'balanced across available R5 levels' if source_id == 'musique' else 'not requested'}

## Intended use and limitations

This derivative is for evaluating pretrained-model Read reliability. It is not a
training corpus. R1 fields are source-specific proxies, not proof of model-training
exposure. {r3_limitation} R2, R4, and R6 use conservative adapter defaults and must not be treated as
independent evidence for those axes. This source primarily supports: {spec.text('role')}.
{source_limitation}
The primary split prevents chain, source-fact, and normalized-question leakage.
Entity and template overlaps are reported above and must be addressed with a
separate strict holdout before making entity- or template-generalization claims.
'''
    card_path.write_text(card, encoding='utf-8', newline='\n')

    output_files = (workload_path, example_path, seed_path, audit_path, card_path)
    manifest = {
        'manifest_version': 1,
        'source_id': source_id,
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'seed': seed,
        'split_profile': split_profile,
        'protected_split_keys': list(split_keys),
        'stratification_keys': list(strata_keys),
        'limit': limit,
        'raw': {'path': str(source_path), **fingerprints},
        'records': len(workloads),
        'split_counts': dict(sorted(split_counts.items())),
        'exclusions': dict(sorted(exclusions.items())),
        'checks': {
            'license_approved': True,
            'raw_hash_verified': bool(expected or expected_md5),
            'workload_schema': 'passed',
            'r1_r6_routing': 'passed',
            'r5_hop_decomposition': 'passed' if source_id == 'musique' else 'not_applicable',
            'primary_lineage_complete': 'passed',
            'primary_split_leakage': 'passed',
            'strict_all_overlap_counts': {key: len(values) for key, values in all_lineage_findings.items()},
            'human_audit': 'pending',
        },
        'outputs': {path.name: {'sha256': sha256_file(path), 'bytes': path.stat().st_size} for path in output_files},
    }
    (output / 'REFINEMENT_MANIFEST.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
        newline='\n',
    )
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Acquire and refine CalibRead research data')
    parser.add_argument('--registry', type=Path, default=REGISTRY_PATH)
    subparsers = parser.add_subparsers(dest='command', required=True)
    subparsers.add_parser('list', help='list registry sources')
    for command in ('fetch', 'refine', 'prepare'):
        child = subparsers.add_parser(command)
        child.add_argument('source_id')
        child.add_argument('--raw-root', type=Path, default=Path('data/raw'))
        if command != 'fetch':
            child.add_argument('--processed-root', type=Path, default=Path('data/processed'))
            child.add_argument('--raw-path', type=Path)
            child.add_argument('--limit', type=int)
            child.add_argument('--seed', type=int, default=20260811)
            child.add_argument('--audit-size', type=int, default=30)
            child.add_argument('--split-profile', choices=('primary', 'strict_all'), default='primary')
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == 'list':
        for source_id, spec in load_registry(args.registry).items():
            status = spec.text('license_status')
            transport = spec.text('transport')
            title = spec.text('title')
            print(f'{source_id}\t{status}\t{transport}\t{title}')
        return 0
    if args.command in {'fetch', 'prepare'}:
        fetched = fetch_source(args.source_id, registry_path=args.registry, raw_root=args.raw_root)
        print(f'fetched {fetched}')
    if args.command in {'refine', 'prepare'}:
        path = refine_source(
            args.source_id,
            raw_path=args.raw_path,
            registry_path=args.registry,
            raw_root=args.raw_root,
            processed_root=args.processed_root,
            limit=args.limit,
            seed=args.seed,
            audit_size=args.audit_size,
            split_profile=args.split_profile,
        )
        print(f'refined {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
