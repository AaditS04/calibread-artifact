import csv
import gzip
import json
import tempfile
from pathlib import Path
import unittest
import zipfile

from calibread.data_pipeline import adapt_musique, adapt_popqa, adapt_socrates, adapt_streamingqa
from calibread.leakage import assert_no_split_leakage
from calibread.schema import Example, WorkloadRecord
from calibread.splits import assign_splits


class DataPipelineTests(unittest.TestCase):
    def test_popqa_adapter_emits_strict_records_and_condition_seed(self) -> None:
        fields = ['id', 'subj', 'prop', 'obj', 'subj_id', 'prop_id', 'obj_id', 's_pop', 'question', 'possible_answers']
        row = {
            'id': '7',
            'subj': 'Ada Lovelace',
            'prop': 'occupation',
            'obj': 'mathematician',
            'subj_id': 'Q7259',
            'prop_id': 'P106',
            'obj_id': 'Q170790',
            's_pop': '1234',
            'question': 'What was Ada Lovelace known as professionally?',
            'possible_answers': '[\'mathematician\', \'computer programmer\']',
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'popqa.tsv'
            with path.open('w', encoding='utf-8', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=fields, delimiter='\t')
                writer.writeheader()
                writer.writerow(row)
            workloads, examples, seeds, exclusions = adapt_popqa(path)
        self.assertEqual(len(workloads), 1)
        self.assertEqual(exclusions, {})
        WorkloadRecord.from_dict(workloads[0].to_dict())
        Example.from_dict(examples[0].to_dict())
        self.assertEqual(workloads[0].dimensions['R5'].level, 'one_hop')
        self.assertEqual(seeds[0]['status'], 'requires_model_snapshot_enrichment')

    def test_socrates_adapter_keeps_atomic_and_composed_rows_together(self) -> None:
        fields = [
            'uid', 'e1.wikidata_qid', 'e2.wikidata_qid', 'e3.wikidata_qid',
            'e2.value', 'e3.value', 'e2.minimal_aliases', 'e3.minimal_aliases',
            'r1.value', 'r2.value', 'r1.template_id', 'r2.template_id', 'mu.template_id',
            'r1(e1).prompt', 'r2(e2).prompt', 'r2(r1(e1)).prompt',
            'wimbd.dolma17(e1,e2)', 'wimbd.dolma17(e2,e3)', 'wimbd.dolma(e1,e2,e3)',
        ]
        row = {
            'uid': 'chain-1',
            'e1.wikidata_qid': 'Q1',
            'e2.wikidata_qid': 'Q2',
            'e3.wikidata_qid': 'Q3',
            'e2.value': 'Bridge entity',
            'e3.value': 'Final answer',
            'e2.minimal_aliases': '[\'Bridge entity\']',
            'e3.minimal_aliases': '[\'Final answer\']',
            'r1.value': 'Bridge entity',
            'r2.value': 'Final answer',
            'r1.template_id': 't1',
            'r2.template_id': 't2',
            'mu.template_id': 'tm',
            'r1(e1).prompt': 'What connects the first entity?',
            'r2(e2).prompt': 'What follows the bridge entity?',
            'r2(r1(e1)).prompt': 'What follows the thing connected to the first entity?',
            'wimbd.dolma17(e1,e2)': '10',
            'wimbd.dolma17(e2,e3)': '4',
            'wimbd.dolma(e1,e2,e3)': '2',
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'socrates.csv'
            with path.open('w', encoding='utf-8', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerow(row)
            workloads, examples, seeds, exclusions = adapt_socrates(path)
        self.assertEqual(len(workloads), 3)
        self.assertEqual(len(seeds), 3)
        self.assertEqual(exclusions, {})
        self.assertEqual([row.dimensions['R5'].raw for row in workloads], [1, 1, 2])
        split = assign_splits(examples, seed=5)
        self.assertEqual(len({example.split for example in split}), 1)
        assert_no_split_leakage(split)

    def test_streamingqa_adapter_preserves_dates_as_proxies(self) -> None:
        row = {
            'qa_id': 'valid-1',
            'question': 'Who won the example event?',
            'answers': ['Ada'],
            'answers_additional': ['Ada Example'],
            'evidence_id': 'evidence-1',
            'evidence_ts': 1577836800,
            'question_ts': 1577923200,
            'recent_or_past': 'recent',
            'written_or_generated': 'written',
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'streaming.jsonl.gz'
            with gzip.open(path, 'wt', encoding='utf-8') as stream:
                stream.write(json.dumps(row) + '\n')
            workloads, examples, seeds, exclusions = adapt_streamingqa(path)
        self.assertEqual(len(workloads), 1)
        self.assertEqual(len(examples), 1)
        self.assertEqual(exclusions, {})
        self.assertEqual(seeds[0]['R3']['event_date_proxy'], '2020-01-01')
        self.assertEqual(seeds[0]['R3']['question_date'], '2020-01-02')
        self.assertEqual(seeds[0]['R3']['value_kind'], 'proxy')

    def test_musique_adapter_maps_hops_and_protects_shared_constituents(self) -> None:
        def row(source_id: str, hops: int, step_ids: list[int]) -> dict[str, object]:
            steps = [
                {
                    'id': step_id,
                    'question': f'Step {position} question',
                    'answer': f'Step {position} answer',
                    'paragraph_support_idx': position,
                }
                for position, step_id in enumerate(step_ids)
            ]
            return {
                'id': source_id,
                'question': f'Composed {hops} hop question?',
                'answer': f'Final {hops}',
                'answer_aliases': [f'Alias {hops}'],
                'question_decomposition': steps,
                'paragraphs': [
                    {
                        'idx': position,
                        'title': f'Title {step_id}',
                        'paragraph_text': 'Supporting text.',
                        'is_supporting': True,
                    }
                    for position, step_id in enumerate(step_ids)
                ],
            }

        three_hop = row('3hop1__10_20_30', 3, [10, 20, 30])
        four_hop = row('4hop2__10_40_50_60', 4, [10, 40, 50, 60])
        malformed = row('4hop1__70_80_90_100', 4, [70, 80, 90])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'musique.zip'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr(
                    'data/musique_ans_v1.0_train.jsonl',
                    '\n'.join(json.dumps(value) for value in (three_hop, malformed)) + '\n',
                )
                archive.writestr(
                    'data/musique_ans_v1.0_dev.jsonl',
                    json.dumps(four_hop) + '\n',
                )
                archive.writestr(
                    'data/musique_ans_v1.0_test.jsonl',
                    json.dumps({'id': '2hop__unlabeled', 'question': 'Hidden?'}) + '\n',
                )
            workloads, examples, seeds, exclusions = adapt_musique(path)
        self.assertEqual(len(workloads), 2)
        self.assertEqual(len(seeds), 2)
        self.assertEqual(
            [value.dimensions['R5'].level for value in workloads],
            ['three_hop', 'four_plus_hop'],
        )
        self.assertEqual(exclusions['decomposition_hop_mismatch'], 1)
        self.assertEqual(exclusions['unlabeled_official_test'], 1)
        self.assertEqual(
            workloads[0].provenance['hop_count_source'],
            'composition_id_and_decomposition_length',
        )
        split = assign_splits(examples, seed=5)
        self.assertEqual(len({example.split for example in split}), 1)
        assert_no_split_leakage(split)


if __name__ == '__main__':
    unittest.main()
