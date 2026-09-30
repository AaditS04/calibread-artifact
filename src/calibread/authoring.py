'''Auditable authoring, adjudication, and refinement for CalibRead R2/R4/R6 data.'''

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .data_pipeline import _condition_seed, _example, _hash_json, _unique_strings
from .dimensions import DimensionValues, dimension_value, r4_from_interpretation_count, r5_from_hop_count, r6_from_specificity
from .io import sha256_file, write_jsonl
from .leakage import assert_no_split_leakage, find_split_leakage
from .schema import Example, WorkloadRecord
from .splits import assign_splits


PROTOCOL_VERSION = 'r2-r4-r6-authoring-v1'
R2_LEVELS = ('coarse', 'medium', 'fine')
R4_LEVELS = ('unambiguous', 'two_way', 'three_plus')
R6_LEVELS = ('general', 'specialized', 'expert')
PRIMARY_SPLIT_KEYS = ('chain_id', 'source_fact_id', 'question_hash')
R6_RAW = {'general': 0.10, 'specialized': 0.50, 'expert': 0.90}


def _nonempty(value: object, field: str) -> str:
    rendered = str(value or '').strip()
    if not rendered:
        raise ValueError(f'{field} must not be empty')
    return rendered


def _strings(value: object, field: str, *, minimum: int = 1) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(f'{field} must be a list')
    result = _unique_strings(value)
    if len(result) < minimum:
        raise ValueError(f'{field} must contain at least {minimum} unique values')
    return result


def _ordered_strings(value: object, field: str, *, minimum: int = 1) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(f'{field} must be a list')
    result = tuple(str(item).strip() for item in value)
    if len(result) < minimum or any(not item for item in result):
        raise ValueError(f'{field} must contain at least {minimum} nonempty values')
    return result


def _interpretations(value: object) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError('interpretation_answers must be a nonempty object')
    result: dict[str, tuple[str, ...]] = {}
    for key, answers in value.items():
        name = _nonempty(key, 'interpretation name')
        result[name] = _strings(answers, f'interpretation_answers[{name}]')
    return result


def _labels(value: object, dimension: str, *, required: bool) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError('independent_labels must be an object')
    allowed = R2_LEVELS if dimension == 'R2' else R4_LEVELS if dimension == 'R4' else R6_LEVELS
    result: dict[str, str] = {}
    for annotator, label in value.items():
        annotator_id = _nonempty(annotator, 'annotator ID')
        normalized = str(label).strip()
        if normalized not in allowed:
            raise ValueError(f'{annotator_id} label must be one of {allowed}')
        result[annotator_id] = normalized
    if required and len(result) < 2:
        raise ValueError('accepted rows require at least two independent annotators')
    return result


def validate_authored_row(row: Mapping[str, object]) -> dict[str, object]:
    '''Validate one row and return a normalized JSON-compatible representation.'''

    dimension = _nonempty(row.get('dimension'), 'dimension')
    if dimension not in {'R2', 'R4', 'R6'}:
        raise ValueError('dimension must be R2, R4, or R6')
    status = _nonempty(row.get('adjudication_status'), 'adjudication_status')
    if status not in {'draft', 'accepted', 'rejected'}:
        raise ValueError('adjudication_status must be draft, accepted, or rejected')
    accepted = status == 'accepted'
    example_id = _nonempty(row.get('example_id'), 'example_id')
    family_id = _nonempty(row.get('family_id'), 'family_id')
    question = _nonempty(row.get('question'), 'question')
    answers = _strings(row.get('accepted_answers'), 'accepted_answers')
    interpretations = _interpretations(row.get('interpretation_answers'))
    if {answer for values in interpretations.values() for answer in values} != set(answers):
        raise ValueError('interpretation answer union must equal accepted_answers')

    level = _nonempty(row.get('adjudicated_level'), 'adjudicated_level')
    allowed = R2_LEVELS if dimension == 'R2' else R4_LEVELS if dimension == 'R4' else R6_LEVELS
    if level not in allowed:
        raise ValueError(f'adjudicated_level must be one of {allowed}')
    if dimension == 'R4':
        expected = 'unambiguous' if len(interpretations) == 1 else 'two_way' if len(interpretations) == 2 else 'three_plus'
        if level != expected:
            raise ValueError('R4 adjudicated_level must match interpretation count')
    elif len(interpretations) != 1:
        raise ValueError('R2 and R6 records must hold R4 at one audited interpretation')

    labels = _labels(row.get('independent_labels', {}), dimension, required=accepted)
    adjudicator_id = str(row.get('adjudicator_id') or '').strip()
    if accepted:
        if not adjudicator_id:
            raise ValueError('accepted rows require adjudicator_id')
        if adjudicator_id in labels:
            raise ValueError('adjudicator must be independent of annotators')
        if row.get('contributor_consent') is not True:
            raise ValueError('accepted rows require contributor_consent=true')

    source_urls = _ordered_strings(row.get('source_urls'), 'source_urls')
    source_licenses = _ordered_strings(row.get('source_licenses'), 'source_licenses')
    if len(source_urls) != len(source_licenses):
        raise ValueError('source_urls and source_licenses must align one-to-one')
    if any(not url.startswith(('https://', 'http://')) for url in source_urls):
        raise ValueError('source_urls must use http or https')
    rationale = _nonempty(row.get('expertise_rationale'), 'expertise_rationale')
    prerequisite = _nonempty(row.get('expertise_prerequisite'), 'expertise_prerequisite')
    if accepted and (len(rationale) < 20 or len(prerequisite) < 8):
        raise ValueError('accepted rows require substantive expertise rationale and prerequisite')

    domain_name = _nonempty(row.get('domain_name'), 'domain_name')
    if dimension == 'R6' and level != 'general' and domain_name.casefold() in {
        'general',
        'general_knowledge',
        'general knowledge',
    }:
        raise ValueError('specialized and expert R6 rows require a named specialist domain')
    answer_type = _nonempty(row.get('precision_answer_type', 'categorical'), 'precision_answer_type')
    granularity = _nonempty(row.get('required_granularity', 'exact accepted answer'), 'required_granularity')
    tolerance_value = row.get('numeric_tolerance')
    if tolerance_value is None:
        tolerance: float | None = None
    elif isinstance(tolerance_value, bool) or not isinstance(tolerance_value, (int, float)):
        raise ValueError('numeric_tolerance must be null or a nonnegative number')
    else:
        tolerance = float(tolerance_value)
        if tolerance < 0:
            raise ValueError('numeric_tolerance must be nonnegative')
    if dimension == 'R2' and answer_type == 'numeric' and tolerance is None:
        raise ValueError('numeric R2 rows require numeric_tolerance')
    normalized: dict[str, object] = {
        'protocol_version': PROTOCOL_VERSION,
        'example_id': example_id,
        'family_id': family_id,
        'dimension': dimension,
        'question': question,
        'accepted_answers': list(answers),
        'interpretation_answers': {key: list(values) for key, values in interpretations.items()},
        'adjudicated_level': level,
        'adjudication_status': status,
        'independent_labels': labels,
        'adjudicator_id': adjudicator_id,
        'author_id': _nonempty(row.get('author_id'), 'author_id'),
        'contributor_consent': row.get('contributor_consent') is True,
        'domain_name': domain_name,
        'expertise_prerequisite': prerequisite,
        'expertise_rationale': rationale,
        'precision_answer_type': answer_type,
        'required_granularity': granularity,
        'numeric_tolerance': tolerance,
        'entity_id': list(_strings(row.get('entity_id'), 'entity_id')),
        'template_id': _nonempty(row.get('template_id'), 'template_id'),
        'source_fact_id': list(_strings(row.get('source_fact_id'), 'source_fact_id')),
        'source_urls': list(source_urls),
        'source_licenses': list(source_licenses),
    }
    return normalized


def load_authored(path: str | Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    '''Return normalized valid rows and structured validation errors.'''

    valid: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    seen: set[str] = set()
    with Path(path).open('r', encoding='utf-8') as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                errors.append({'line': line_number, 'error': 'blank lines are not allowed'})
                continue
            try:
                value = json.loads(line)
                if not isinstance(value, Mapping):
                    raise ValueError('row must be a JSON object')
                row = validate_authored_row(value)
                example_id = str(row['example_id'])
                if example_id in seen:
                    raise ValueError(f'duplicate example_id {example_id!r}')
                seen.add(example_id)
                valid.append(row)
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                errors.append({'line': line_number, 'error': str(error)})
    return valid, errors


def _agreement(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    reviewed = 0
    unanimous = 0
    pair_matches = 0
    pairs = 0
    for row in rows:
        labels = list(dict(row.get('independent_labels', {})).values())
        if len(labels) < 2:
            continue
        reviewed += 1
        unanimous += int(len(set(labels)) == 1)
        for left in range(len(labels)):
            for right in range(left + 1, len(labels)):
                pairs += 1
                pair_matches += int(labels[left] == labels[right])
    return {
        'reviewed_records': reviewed,
        'unanimous_records': unanimous,
        'unanimous_rate': unanimous / reviewed if reviewed else None,
        'annotator_pair_comparisons': pairs,
        'pairwise_agreement': pair_matches / pairs if pairs else None,
    }


def authoring_report(rows: Sequence[Mapping[str, object]], errors: Sequence[Mapping[str, object]]) -> dict[str, object]:
    accepted = [row for row in rows if row['adjudication_status'] == 'accepted']
    r4 = [row for row in accepted if row['dimension'] == 'R4']
    r6 = [row for row in accepted if row['dimension'] == 'R6']
    r2 = [row for row in accepted if row['dimension'] == 'R2']
    r2_levels = Counter(str(row['adjudicated_level']) for row in r2)
    r2_families: dict[str, set[str]] = defaultdict(set)
    for row in r2:
        r2_families[str(row['family_id'])].add(str(row['adjudicated_level']))
    incomplete_r2_families = sorted(
        family for family, levels in r2_families.items() if set(R2_LEVELS) - levels
    )
    r4_levels = Counter(str(row['adjudicated_level']) for row in r4)
    r6_levels = Counter(str(row['adjudicated_level']) for row in r6)
    r4_families: dict[str, set[str]] = defaultdict(set)
    for row in r4:
        r4_families[str(row['family_id'])].add(str(row['adjudicated_level']))
    unmatched = sorted(
        family for family, levels in r4_families.items()
        if 'unambiguous' not in levels or not (levels & {'two_way', 'three_plus'})
    )
    domains: dict[str, set[str]] = defaultdict(set)
    for row in r6:
        domains[str(row['domain_name'])].add(str(row['adjudicated_level']))
    incomplete_domains = sorted(domain for domain, levels in domains.items() if set(R6_LEVELS) - levels)
    gates = {
        'no_validation_errors': not errors,
        'has_accepted_rows': bool(accepted),
        'r2_all_levels': set(r2_levels) == set(R2_LEVELS),
        'r2_all_families_matched': bool(r2_families) and not incomplete_r2_families,
        'r4_all_levels': set(r4_levels) == set(R4_LEVELS),
        'r4_all_families_matched': bool(r4_families) and not unmatched,
        'r6_all_levels': set(r6_levels) == set(R6_LEVELS),
        'r6_every_domain_complete': bool(domains) and not incomplete_domains,
        'human_audit_approved': False,
    }
    return {
        'protocol_version': PROTOCOL_VERSION,
        'valid_rows': len(rows),
        'validation_errors': list(errors),
        'status_counts': dict(Counter(str(row['adjudication_status']) for row in rows)),
        'accepted_rows': len(accepted),
        'r2_level_counts': dict(r2_levels),
        'incomplete_r2_families': incomplete_r2_families,
        'r4_level_counts': dict(r4_levels),
        'r6_level_counts': dict(r6_levels),
        'unmatched_r4_families': unmatched,
        'incomplete_r6_domains': incomplete_domains,
        'agreement': _agreement(accepted),
        'promotion_gates': gates,
        'promotion_ready': all(gates.values()),
    }


def _to_workload(row: Mapping[str, object]) -> WorkloadRecord:
    interpretations = {
        str(key): tuple(str(answer) for answer in values)
        for key, values in dict(row['interpretation_answers']).items()
    }
    dimension = str(row['dimension'])
    r4_count = len(interpretations) if dimension == 'R4' else 1
    r6_level = str(row['adjudicated_level']) if dimension == 'R6' else 'general'
    r2_level = str(row['adjudicated_level']) if dimension == 'R2' else 'medium'
    specificity = R6_RAW[r6_level]
    dimensions = DimensionValues(
        {
            'R2': dimension_value('R2', r2_level, r2_level),
            'R4': r4_from_interpretation_count(r4_count),
            'R5': r5_from_hop_count(1),
            'R6': r6_from_specificity(specificity, general_max=0.33, specialized_max=0.66),
        }
    )
    chain_id = f'authored:family:{row["family_id"]}'
    factset = f'authored:factset:{_hash_json(row["source_fact_id"])}'
    provenance = {
        'source_id': 'calibread_authored_r4_r6',
        'protocol_version': PROTOCOL_VERSION,
        'annotation_hash': _hash_json(row),
        'author_id': row['author_id'],
        'annotator_ids': sorted(dict(row['independent_labels'])),
        'adjudicator_id': row['adjudicator_id'],
        'source_urls': row['source_urls'],
        'source_licenses': row['source_licenses'],
        'focal_dimension': dimension,
        'expertise_prerequisite': row['expertise_prerequisite'],
        'expertise_rationale': row['expertise_rationale'],
        'precision_answer_type': row['precision_answer_type'],
        'required_granularity': row['required_granularity'],
        'numeric_tolerance': row['numeric_tolerance'],
    }
    return WorkloadRecord(
        example_id=str(row['example_id']),
        question=str(row['question']),
        accepted_answers=tuple(str(value) for value in row['accepted_answers']),
        track='open_ended_stress',
        dimensions=dimensions,
        r4_annotation_hash=_hash_json(interpretations),
        r5_chain_spec_hash=_hash_json({'chain_id': chain_id, 'constituents': [factset], 'hops': 1}),
        interpretation_answers=interpretations,
        chain_id=chain_id,
        constituent_example_ids=(factset,),
        domain_name=str(row['domain_name']),
        missing_reasons={'R1': 'model_condition_record', 'R3': 'model_condition_record'},
        provenance=provenance,
    )


def refine_authored(
    input_path: str | Path,
    *,
    output_root: str | Path = Path('data/processed/calibread_authored_r4_r6'),
    seed: int = 20260811,
    audit_size: int = 30,
) -> Path:
    rows, errors = load_authored(input_path)
    report = authoring_report(rows, errors)
    accepted = [row for row in rows if row['adjudication_status'] == 'accepted']
    if errors:
        raise ValueError(f'authoring file has {len(errors)} validation errors')
    if not accepted:
        raise ValueError('authoring file has no accepted records')
    workloads = [_to_workload(row) for row in accepted]
    examples: list[Example] = []
    for row, workload in zip(accepted, workloads, strict=True):
        examples.append(
            _example(
                workload,
                {
                    'entity_id': row['entity_id'],
                    'chain_id': workload.chain_id,
                    'template_id': row['template_id'],
                    'source_fact_id': row['source_fact_id'],
                    'focal_dimension': row['dimension'],
                    'authoring_family_id': row['family_id'],
                },
            )
        )
    examples = assign_splits(examples, seed=seed, disjoint_keys=PRIMARY_SPLIT_KEYS)
    assert_no_split_leakage(examples, disjoint_keys=PRIMARY_SPLIT_KEYS)
    strict_findings = find_split_leakage(examples)

    output = Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    workload_path = output / 'workloads.jsonl'
    example_path = output / 'examples.jsonl'
    accepted_path = output / 'accepted_annotations.jsonl'
    seed_path = output / 'condition_seeds.jsonl'
    audit_path = output / 'audit_sample.jsonl'
    report_path = output / 'VALIDATION_REPORT.json'
    card_path = output / 'DATA_CARD.md'
    write_jsonl(workload_path, (record.to_dict() for record in workloads))
    write_jsonl(example_path, (record.to_dict() for record in examples))
    write_jsonl(accepted_path, accepted)
    write_jsonl(
        seed_path,
        (
            _condition_seed(
                record.example_id,
                r1_proxy=None,
                r1_source='not measured during human authoring',
                r1_unit='unresolved',
                source_id='calibread_authored_r4_r6',
            )
            for record in workloads
        ),
    )
    by_id = {example.example_id: example for example in examples}
    selected = sorted(accepted, key=lambda row: hashlib.sha256(str(row['example_id']).encode()).hexdigest())[:audit_size]
    write_jsonl(
        audit_path,
        (
            {
                **row,
                'split': by_id[str(row['example_id'])].split,
                'audit_status': 'pending_human_review',
                'audit_notes': '',
            }
            for row in selected
        ),
    )
    report = {**report, 'strict_all_overlap_counts': {key: len(values) for key, values in strict_findings.items()}}
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    card = f'''# Data card: CalibRead Authored R2/R4/R6 Benchmark

- Protocol: `{PROTOCOL_VERSION}`
- Input: `{input_path}`
- Input SHA-256: `{sha256_file(input_path)}`
- Accepted records: {len(accepted)}
- R2 levels: {report['r2_level_counts']}
- R4 levels: {report['r4_level_counts']}
- R6 levels: {report['r6_level_counts']}
- Pairwise annotation agreement: {report['agreement']['pairwise_agreement']}
- Primary protected split keys: {list(PRIMARY_SPLIT_KEYS)}
- Strict entity/template overlap counts: {report['strict_all_overlap_counts']}
- Promotion ready: {report['promotion_ready']}
- Human audit: pending
- Redistribution: prohibited until registry review and contributor-release approval

## Interpretation

Only independently annotated and adjudicated `accepted` rows are present. R4 varies
audited interpretation count. R6 uses frozen specificity anchors of 0.10, 0.50, and
0.90. Non-focal R2 and R5 values are controls; R1 and R3 remain model-condition
fields. See `VALIDATION_REPORT.json` for incomplete families, domains, and gates.
'''
    card_path.write_text(card, encoding='utf-8', newline='\n')
    artifacts = (workload_path, example_path, accepted_path, seed_path, audit_path, report_path, card_path)
    manifest = {
        'manifest_version': 1,
        'protocol_version': PROTOCOL_VERSION,
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'input': {'path': str(input_path), 'sha256': sha256_file(input_path)},
        'records': len(accepted),
        'seed': seed,
        'promotion_ready': report['promotion_ready'],
        'outputs': {path.name: {'bytes': path.stat().st_size, 'sha256': sha256_file(path)} for path in artifacts},
    }
    (output / 'REFINEMENT_MANIFEST.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Validate and refine authored R2/R4/R6 annotations')
    commands = parser.add_subparsers(dest='command', required=True)
    validate = commands.add_parser('validate')
    validate.add_argument('input', type=Path)
    validate.add_argument('--report', type=Path)
    refine = commands.add_parser('refine')
    refine.add_argument('input', type=Path)
    refine.add_argument('--output', type=Path, default=Path('data/processed/calibread_authored_r4_r6'))
    refine.add_argument('--seed', type=int, default=20260811)
    refine.add_argument('--audit-size', type=int, default=30)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == 'validate':
        rows, errors = load_authored(args.input)
        report = authoring_report(rows, errors)
        rendered = json.dumps(report, indent=2, sort_keys=True) + '\n'
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(rendered, encoding='utf-8')
        print(rendered, end='')
        return 1 if errors else 0
    output = refine_authored(args.input, output_root=args.output, seed=args.seed, audit_size=args.audit_size)
    print(f'refined {output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())


__all__ = [
    'PROTOCOL_VERSION',
    'authoring_report',
    'load_authored',
    'refine_authored',
    'validate_authored_row',
]
