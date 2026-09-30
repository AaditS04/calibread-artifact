import json
from pathlib import Path
import tempfile
import unittest

from calibread.authoring import authoring_report, load_authored, refine_authored, validate_authored_row
from calibread.io import read_jsonl
from calibread.schema import WorkloadRecord


def row(
    example_id: str,
    *,
    dimension: str = 'R4',
    level: str = 'unambiguous',
    family_id: str = 'family-1',
    domain: str = 'general_knowledge',
) -> dict[str, object]:
    interpretations = {'reading_1': ['answer']}
    if dimension == 'R4' and level == 'two_way':
        interpretations = {'reading_1': ['answer'], 'reading_2': ['alternative']}
    if dimension == 'R4' and level == 'three_plus':
        interpretations = {
            'reading_1': ['answer'],
            'reading_2': ['alternative'],
            'reading_3': ['third'],
        }
    answers = [value for values in interpretations.values() for value in values]
    return {
        'example_id': example_id,
        'family_id': family_id,
        'dimension': dimension,
        'question': f'Original authored question {example_id}?',
        'accepted_answers': answers,
        'interpretation_answers': interpretations,
        'adjudicated_level': level,
        'adjudication_status': 'accepted',
        'independent_labels': {'annotator-a': level, 'annotator-b': level},
        'adjudicator_id': 'adjudicator-c',
        'author_id': 'author-d',
        'contributor_consent': True,
        'domain_name': domain,
        'expertise_prerequisite': 'Relevant background knowledge',
        'expertise_rationale': 'This is a substantive explanation of the required background.',
        'entity_id': [f'entity:{example_id}'],
        'template_id': f'template:{dimension}:{level}',
        'source_fact_id': [f'fact:{example_id}'],
        'source_urls': ['https://example.org/fact'],
        'source_licenses': ['CC-BY-4.0'],
    }


class AuthoringTests(unittest.TestCase):
    def test_accepted_row_requires_independent_adjudication_and_consent(self) -> None:
        value = row('valid')
        normalized = validate_authored_row(value)
        self.assertEqual(normalized['protocol_version'], 'r2-r4-r6-authoring-v1')
        value['adjudicator_id'] = 'annotator-a'
        with self.assertRaisesRegex(ValueError, 'independent'):
            validate_authored_row(value)
        value = row('no-consent')
        value['contributor_consent'] = False
        with self.assertRaisesRegex(ValueError, 'consent'):
            validate_authored_row(value)

    def test_r4_interpretations_and_r6_controls_are_strict(self) -> None:
        value = row('bad-r4', level='two_way')
        value['adjudicated_level'] = 'unambiguous'
        with self.assertRaisesRegex(ValueError, 'interpretation count'):
            validate_authored_row(value)
        value = row('bad-r6', dimension='R6', level='expert', domain='medicine')
        value['interpretation_answers'] = {'one': ['answer'], 'two': ['alternative']}
        value['accepted_answers'] = ['answer', 'alternative']
        with self.assertRaisesRegex(ValueError, 'one audited interpretation'):
            validate_authored_row(value)

    def test_r2_numeric_rows_require_tolerance_and_preserve_level(self) -> None:
        value = row('r2-fine', dimension='R2', level='fine')
        value['precision_answer_type'] = 'numeric'
        value['required_granularity'] = 'exact integer'
        value['numeric_tolerance'] = 0.0
        normalized = validate_authored_row(value)
        self.assertEqual(normalized['adjudicated_level'], 'fine')
        self.assertEqual(normalized['numeric_tolerance'], 0.0)
        value['numeric_tolerance'] = None
        with self.assertRaisesRegex(ValueError, 'require numeric_tolerance'):
            validate_authored_row(value)

    def test_report_exposes_coverage_gaps_and_agreement(self) -> None:
        rows = [validate_authored_row(row('control')), validate_authored_row(row('ambiguous', level='two_way'))]
        report = authoring_report(rows, [])
        self.assertEqual(report['agreement']['pairwise_agreement'], 1.0)
        self.assertFalse(report['promotion_ready'])
        self.assertFalse(report['promotion_gates']['r4_all_levels'])

    def test_refinement_emits_strict_workloads_and_keeps_family_together(self) -> None:
        records = [row('control', family_id='matched'), row('ambiguous', level='two_way', family_id='matched')]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'annotations.jsonl'
            source.write_text('\n'.join(json.dumps(value) for value in records) + '\n', encoding='utf-8')
            valid, errors = load_authored(source)
            self.assertEqual(len(valid), 2)
            self.assertEqual(errors, [])
            output = refine_authored(source, output_root=root / 'processed', audit_size=2)
            workloads = [WorkloadRecord.from_dict(value) for value in read_jsonl(output / 'workloads.jsonl')]
            examples = read_jsonl(output / 'examples.jsonl')
            self.assertEqual([workload.dimensions['R4'].raw for workload in workloads], [1, 2])
            self.assertEqual(len({example['split'] for example in examples}), 1)
            self.assertTrue((output / 'VALIDATION_REPORT.json').is_file())
            self.assertTrue((output / 'audit_sample.jsonl').is_file())


if __name__ == '__main__':
    unittest.main()
