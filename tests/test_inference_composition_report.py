'''Tests for joining cached R5 atomic and composite inference outputs.'''

from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from calibread.dimensions import DimensionValues
from calibread.inference.composition_report import build_composition_report
from calibread.inference.config import InferenceConfig, load_inference_config
from calibread.inference.runner import run_inference
from calibread.inference.scoring import score_run
from calibread.io import sha256_file
from calibread.schema import Example, WorkloadRecord


class InferenceCompositionReportTests(unittest.TestCase):
    def _fixture(self, root: Path, *, omit_atom: bool = False) -> Path:
        example_path = root / 'examples.jsonl'
        workload_path = root / 'workloads.jsonl'
        output = root / 'results'
        output.mkdir()
        dimensions_one = DimensionValues(
            {
                'R2': {'raw': 'medium', 'level': 'medium'},
                'R4': {'raw': 1, 'level': 'unambiguous'},
                'R5': {'raw': 1, 'level': 'one_hop'},
                'R6': {'raw': 0.1, 'level': 'general'},
            }
        )
        dimensions_two = DimensionValues(
            {
                'R2': {'raw': 'medium', 'level': 'medium'},
                'R4': {'raw': 1, 'level': 'unambiguous'},
                'R5': {'raw': 2, 'level': 'two_hop'},
                'R6': {'raw': 0.1, 'level': 'general'},
            }
        )
        specs = (
            ('a1', 'MOCK_ANSWER=A?', ('A',), dimensions_one, ('fact:a1',)),
            ('a2', 'MOCK_ANSWER=B?', ('B',), dimensions_one, ('fact:a2',)),
            ('c1', 'MOCK_ANSWER=wrong?', ('B',), dimensions_two, ('a1', 'a2')),
        )
        examples = []
        workloads = []
        for identifier, question, answers, dimensions, constituents in specs:
            example = Example(
                example_id=identifier,
                question=question,
                accepted_answers=answers,
                group='R5',
                split='development',
                metadata={
                    'calibread_dimensions': dimensions.to_dict(),
                    'chain_id': 'chain:1',
                    'entity_id': [identifier],
                    'source_fact_id': list(constituents),
                    'template_id': 'template:1',
                    'question_hash': identifier * 16,
                },
            )
            workload = WorkloadRecord(
                example_id=identifier,
                question=question,
                accepted_answers=answers,
                track='open_ended_stress',
                dimensions=dimensions,
                r4_annotation_hash='a' * 64,
                r5_chain_spec_hash=('b' if identifier != 'c1' else 'c') * 64,
                interpretation_answers={'i1': answers},
                chain_id='chain:1',
                constituent_example_ids=constituents,
                domain_name='general',
                missing_reasons={'R1': 'model_condition_record', 'R3': 'model_condition_record'},
            )
            examples.append(example)
            workloads.append(workload)
        example_path.write_text(
            ''.join(json.dumps(value.to_dict()) + '\n' for value in examples),
            encoding='utf-8',
        )
        workload_path.write_text(
            ''.join(json.dumps(value.to_dict()) + '\n' for value in workloads),
            encoding='utf-8',
        )
        config_path = root / 'run.toml'
        config_path.write_text(
            f'''[run]\nrun_id='composition-test'\nsplit='development'\nseed=7\noutput_dir='{output.as_posix()}'\nresume=true\n\n[provider]\nkind='mock'\n\n[model]\nrequested_model='mock-model-v1'\ndata_collection='deny'\n\n[prompt]\ntemplate_id='p1'\nsystem='Answer.'\nuser_template='Question: {{question}}'\n\n[budget]\nmax_cost_usd=0\nmax_requests=3\n\n[[datasets]]\ndataset_id='fixture'\nexamples='{example_path.as_posix()}'\nworkloads='{workload_path.as_posix()}'\n''',
            encoding='utf-8',
        )
        config = load_inference_config(config_path)
        summary = run_inference(config)
        if summary['remaining_after_invocation'] != 0:
            raise AssertionError('composition fixture inference did not complete')
        scored_path = score_run(config)
        if omit_atom:
            with scored_path.open('r', encoding='utf-8', newline='') as stream:
                rows = list(csv.DictReader(stream))
            rows = [row for row in rows if row['example_id'] != 'a2']
            with scored_path.open('w', encoding='utf-8', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=rows[0])
                writer.writeheader()
                writer.writerows(rows)
        return config_path

    @staticmethod
    def _write_calibrated(
        config: InferenceConfig,
        *,
        score_kind: str = 'probability',
        include_object_hash: bool = True,
    ) -> Path:
        output = config.run.output_dir
        with (output / 'scored_results.csv').open(
            'r', encoding='utf-8', newline=''
        ) as stream:
            scored = list(csv.DictReader(stream))
        confidence_by_id = {'a1': 0.9, 'a2': 0.8, 'c1': 0.4}
        rows = []
        for row in scored:
            value = {
                'run_id': row['run_id'],
                'split': row['split'],
                'example_id': row['example_id'],
                'calibrated_confidence': confidence_by_id[row['example_id']],
                'calibrated_score_kind': score_kind,
                'calibrated_score_source': 'weighted_isotonic_pava(mock_score)',
                'calibrator_id': 'fixture-calibrator',
                'condition_table_hash': 'e' * 64,
                'calibration_supported': 1,
            }
            if include_object_hash:
                value['calibrator_object_sha256'] = 'f' * 64
            rows.append(value)
        target = output / 'calibrated_results.csv'
        with target.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=rows[0])
            writer.writeheader()
            writer.writerows(rows)
        manifest = {
            'schema_version': 1,
            'run_id': config.run.run_id,
            'split': config.run.split,
            'input_rows': len(rows),
            'supported_rows': len(rows),
            'calibrator_id': 'fixture-calibrator',
            'calibrator_object_sha256': 'f' * 64,
            'condition_table_hash': 'e' * 64,
            'calibrated_results_sha256': sha256_file(target),
        }
        (output / 'CALIBRATED_RESULTS_MANIFEST.json').write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + '\n',
            encoding='utf-8',
        )
        return target

    def test_builds_synthesis_loss_and_audit_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = load_inference_config(self._fixture(root))
            target = build_composition_report(config, bootstrap_samples=20)
            report = json.loads(target.read_text(encoding='utf-8'))
            group = report['by_dataset_and_r5']['fixture:two_hop']
            self.assertEqual(group['chain_accuracy'], 0.0)
            self.assertEqual(group['all_atoms_correct_rate'], 1.0)
            self.assertEqual(group['synthesis_loss'], 1.0)
            self.assertTrue((config.run.output_dir / 'r5_chain_results.csv').is_file())

    def test_missing_atom_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = load_inference_config(self._fixture(root, omit_atom=True))
            with self.assertRaisesRegex(ValueError, 'complete generation cache'):
                build_composition_report(config, bootstrap_samples=5)

    def test_calibrated_composition_requires_frozen_probability_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = load_inference_config(self._fixture(root))
            calibrated = self._write_calibrated(config)
            target = build_composition_report(
                config, calibrated_path=calibrated, bootstrap_samples=20
            )
            report = json.loads(target.read_text(encoding='utf-8'))
            group = report['by_dataset_and_r5']['fixture:two_hop']
            self.assertAlmostEqual(group['mean_product_prediction'], 0.72)
            self.assertAlmostEqual(group['product_calibration_gap'], 0.72)
            self.assertEqual(
                report['calibration_identity']['calibrator_id'],
                'fixture-calibrator',
            )
            self.assertEqual(
                report['calibrated_results_sha256'], sha256_file(calibrated)
            )

            self._write_calibrated(config, score_kind='raw')
            with self.assertRaisesRegex(ValueError, 'not a probability'):
                build_composition_report(
                    config, calibrated_path=calibrated, bootstrap_samples=5
                )

            self._write_calibrated(config, include_object_hash=False)
            with self.assertRaisesRegex(ValueError, 'object hash'):
                build_composition_report(
                    config, calibrated_path=calibrated, bootstrap_samples=5
                )

            self._write_calibrated(config)
            with calibrated.open('a', encoding='utf-8') as stream:
                stream.write('\n')
            with self.assertRaisesRegex(ValueError, 'frozen manifest'):
                build_composition_report(
                    config, calibrated_path=calibrated, bootstrap_samples=5
                )

    def test_scored_correctness_tampering_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = load_inference_config(self._fixture(root))
            scored_path = config.run.output_dir / 'scored_results.csv'
            with scored_path.open('r', encoding='utf-8', newline='') as stream:
                rows = list(csv.DictReader(stream))
            for row in rows:
                if row['example_id'] == 'c1':
                    row['correct'] = '1'
            with scored_path.open('w', encoding='utf-8', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=rows[0])
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, 'generation and gold data'):
                build_composition_report(config, bootstrap_samples=5)


if __name__ == '__main__':
    unittest.main()
