'''Offline tests for frozen calibration and R7 inference artifacts.'''

from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from calibread.dimensions import DimensionValues
from calibread.evaluate import evaluate_rows
from calibread.inference.calibration import (
    calibrate_run,
    fit_calibrator,
    fit_weighted_isotonic,
    load_calibrator,
    predict_isotonic,
    r5_level_balanced_weights,
)
from calibread.inference.calibration_report import calibration_report
from calibread.inference.config import InferenceConfig, load_inference_config
from calibread.inference.decisions import decide_r7
from calibread.inference.runner import run_inference
from calibread.inference.scoring import score_run
from calibread.io import read_jsonl, sha256_file, write_jsonl
from calibread.schema import Example


class InferenceCalibrationTests(unittest.TestCase):
    def test_weighted_pava_is_deterministic_and_monotone(self) -> None:
        expected = fit_weighted_isotonic(
            [-3.0, -2.0, -1.0, 0.0], [0, 1, 0, 1]
        )
        reordered = fit_weighted_isotonic(
            [0.0, -1.0, -3.0, -2.0], [1, 0, 0, 1]
        )
        self.assertEqual(expected, reordered)
        self.assertEqual(
            [block['prediction'] for block in expected], [0.0, 0.5, 1.0]
        )
        predictions = [
            predict_isotonic(expected, value)
            for value in (-10.0, -3.0, -2.0, -1.0, -0.5, 0.0, 10.0)
        ]
        self.assertEqual(predictions, sorted(predictions))
        self.assertEqual(predictions[0], 0.0)
        self.assertEqual(predictions[-1], 1.0)

    def test_level_balancing_changes_an_imbalanced_fit(self) -> None:
        levels = ['one_hop'] * 5 + ['two_hop']
        labels = [0, 0, 0, 0, 0, 1]
        scores = [-1.0] * len(labels)
        weights, summary = r5_level_balanced_weights(levels)
        unweighted = fit_weighted_isotonic(scores, labels)
        balanced = fit_weighted_isotonic(scores, labels, weights)
        self.assertAlmostEqual(float(unweighted[0]['prediction']), 1 / 6)
        self.assertAlmostEqual(float(balanced[0]['prediction']), 0.5)
        self.assertAlmostEqual(sum(weights), len(labels))
        self.assertEqual(
            summary['observed_level_counts'], {'one_hop': 5, 'two_hop': 1}
        )
        self.assertEqual(summary['scheme'], 'inverse_r5_level_frequency')

    def test_fit_apply_decide_report_and_split_guards(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            examples_path = root / 'examples.jsonl'
            workloads_path = root / 'workloads.jsonl'
            examples: list[dict[str, object]] = []
            labels = [0, 1, 0, 1]
            for split in ('calibration', 'test'):
                for index, correct in enumerate(labels):
                    emitted = f'answer-{index}'
                    accepted = emitted if correct else f'gold-{index}'
                    example = Example(
                        example_id=f'{split}-{index}',
                        question=f'MOCK_ANSWER={emitted}?',
                        accepted_answers=(accepted,),
                        split=split,
                        metadata={'chain_id': f'{split}-chain-{index}'},
                    ).with_dimension_values(
                        DimensionValues({'R5': {'raw': 1, 'level': 'one_hop'}})
                    )
                    examples.append(example.to_dict())
            write_jsonl(examples_path, examples)
            workloads_path.write_text('{}\n', encoding='utf-8')

            calibration_config = self._config(
                root,
                examples_path,
                workloads_path,
                split='calibration',
                run_id='fixture-calibration',
                output=root / 'calibration-run',
            )
            test_config = self._config(
                root,
                examples_path,
                workloads_path,
                split='test',
                run_id='fixture-test',
                output=root / 'test-run',
            )
            scores = {
                f'calibration-{index}': value
                for index, value in enumerate((-3.0, -2.0, -1.0, 0.0))
            }
            scores.update(
                {
                    f'test-{index}': value
                    for index, value in enumerate((-3.0, -2.0, -1.0, 0.0))
                }
            )
            self._run_and_rescore(calibration_config, scores)
            self._run_and_rescore(test_config, scores)

            frozen = root / 'frozen' / 'CALIBRATOR.json'
            result = fit_calibrator(calibration_config, frozen)
            self.assertEqual(result, frozen)
            first_bytes = frozen.read_bytes()
            self.assertEqual(fit_calibrator(calibration_config, frozen), frozen)
            self.assertEqual(frozen.read_bytes(), first_bytes)
            bundle = load_calibrator(frozen)
            self.assertTrue(bundle.calibrator_id.startswith('r5-isotonic-'))
            self.assertEqual(bundle.payload['calibration_split'], 'calibration')
            self.assertEqual(bundle.payload['support_count'], 4)
            self.assertEqual(
                bundle.payload['weighting']['scheme'],
                'inverse_r5_level_frequency',
            )
            self.assertTrue((frozen.parent / 'CALIBRATION_MANIFEST.json').is_file())
            self.assertTrue((frozen.parent / 'calibration_metrics.json').is_file())

            calibrated = calibrate_run(test_config, frozen)
            with calibrated.open(encoding='utf-8', newline='') as stream:
                calibrated_rows = list(csv.DictReader(stream))
            self.assertEqual(len(calibrated_rows), 4)
            self.assertEqual(
                {row['calibrator_id'] for row in calibrated_rows},
                {bundle.calibrator_id},
            )
            self.assertEqual(
                {row['calibration_supported'] for row in calibrated_rows}, {'1'}
            )
            self.assertEqual(
                sorted(float(row['calibrated_confidence']) for row in calibrated_rows),
                [0.0, 0.5, 0.5, 1.0],
            )
            evaluation_path = test_config.run.output_dir / 'calibrated_evaluation.csv'
            with evaluation_path.open(encoding='utf-8', newline='') as stream:
                evaluation_rows = list(csv.DictReader(stream))
            self.assertEqual(len(evaluation_rows), 4)
            self.assertEqual({row['score_kind'] for row in evaluation_rows}, {'probability'})
            self.assertEqual(
                {row['calibration_object_hash'] for row in evaluation_rows},
                {bundle.sha256},
            )
            condition_manifest_path = (
                test_config.run.output_dir / 'CONDITION_IDENTITY_MANIFEST.json'
            )
            condition_manifest = json.loads(
                condition_manifest_path.read_text(encoding='utf-8')
            )
            original_condition_manifest = condition_manifest_path.read_bytes()
            self.assertEqual(calibrate_run(test_config, frozen), calibrated)
            self.assertEqual(
                condition_manifest_path.read_bytes(), original_condition_manifest
            )
            self.assertEqual(
                len(condition_manifest['entries']), len(evaluation_rows)
            )
            self.assertEqual(
                {row['condition_table_hash'] for row in evaluation_rows},
                {sha256_file(condition_manifest_path)},
            )
            evaluator_report = evaluate_rows(
                evaluation_rows, group_column='R5', n_bins=2
            )
            self.assertEqual(evaluator_report['count'], len(evaluation_rows))
            self.assertEqual(
                evaluator_report['report_identity']['calibrator_id'],
                bundle.calibrator_id,
            )
            self.assertTrue(
                (test_config.run.output_dir / 'CALIBRATED_RESULTS_MANIFEST.json').is_file()
            )

            decisions = decide_r7(test_config, frozen)
            with decisions.open(encoding='utf-8', newline='') as stream:
                decision_rows = list(csv.DictReader(stream))
            self.assertEqual(len(decision_rows), 20)
            self.assertEqual(
                {row['threshold'] for row in decision_rows},
                {'0.50', '0.70', '0.90', '0.95', '0.99'},
            )
            at_half = [row for row in decision_rows if row['threshold'] == '0.50']
            self.assertEqual(sum(row['action'] == 'answer' for row in at_half), 3)
            self.assertEqual(
                {row['score_source'] for row in decision_rows},
                {'weighted_isotonic_pava(mock_mean_generated_token_log_probability)'},
            )
            self.assertEqual(
                {row['raw_score_source'] for row in decision_rows},
                {'mock_mean_generated_token_log_probability'},
            )
            self.assertEqual(
                {row['condition_table_hash'] for row in decision_rows},
                {sha256_file(condition_manifest_path)},
            )
            self.assertEqual(
                {row['model_snapshot_id'] for row in decision_rows},
                {'mock/frozen'},
            )

            report_path = calibration_report(test_config, frozen)
            report = json.loads(report_path.read_text(encoding='utf-8'))
            self.assertEqual(report['evaluation_role'], 'held_out_test_evaluation')
            self.assertEqual(report['overall']['n'], 4)
            for name in (
                'brier', 'log_loss', 'ece_10', 'ace_10',
                'raw_score_correctness_auroc', 'risk_coverage_aurc',
            ):
                self.assertIn(name, report['overall'])

            with self.assertRaisesRegex(ValueError, 'only for run.split=calibration'):
                fit_calibrator(test_config, root / 'invalid' / 'CALIBRATOR.json')

            condition_manifest_path.write_bytes(
                original_condition_manifest + b'\n'
            )
            with self.assertRaisesRegex(FileExistsError, 'frozen artifact'):
                calibrate_run(test_config, frozen)
            condition_manifest_path.write_bytes(original_condition_manifest)

            scored_path = test_config.run.output_dir / 'scored_results.csv'
            original_scored = scored_path.read_bytes()
            with scored_path.open('r', encoding='utf-8', newline='') as stream:
                tampered_rows = list(csv.DictReader(stream))
            tampered_rows[0]['generation_id'] = 'tampered-generation-id'
            with scored_path.open('w', encoding='utf-8', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=tampered_rows[0])
                writer.writeheader()
                writer.writerows(tampered_rows)
            with self.assertRaisesRegex(ValueError, 'generation identity mismatch'):
                calibrate_run(test_config, frozen)
            scored_path.write_bytes(original_scored)

            with scored_path.open('r', encoding='utf-8', newline='') as stream:
                tampered_rows = list(csv.DictReader(stream))
            tampered_rows[0]['score'] = ''
            with scored_path.open('w', encoding='utf-8', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=tampered_rows[0])
                writer.writeheader()
                writer.writerows(tampered_rows)
            with self.assertRaisesRegex(ValueError, 'missing raw score'):
                calibrate_run(test_config, frozen)
            scored_path.write_bytes(original_scored)

            run_manifest_path = test_config.run.output_dir / 'RUN_MANIFEST.json'
            original_manifest = run_manifest_path.read_bytes()
            tampered_manifest = json.loads(original_manifest)
            tampered_manifest['provider_fingerprint']['model_snapshot_id'] = (
                'different-snapshot'
            )
            run_manifest_path.write_text(
                json.dumps(tampered_manifest, indent=2, sort_keys=True) + '\n',
                encoding='utf-8',
            )
            with self.assertRaisesRegex(ValueError, 'provider fingerprint'):
                calibrate_run(test_config, frozen)
            run_manifest_path.write_bytes(original_manifest)

            tampered_dir = root / 'tampered-calibrator'
            tampered_dir.mkdir()
            tampered_payload = json.loads(frozen.read_text(encoding='utf-8'))
            tampered_payload['training_score_range']['minimum'] = -999.0
            (tampered_dir / 'CALIBRATOR.json').write_text(
                json.dumps(tampered_payload, indent=2, sort_keys=True) + '\n',
                encoding='utf-8',
            )
            (tampered_dir / 'CALIBRATION_MANIFEST.json').write_bytes(
                (frozen.parent / 'CALIBRATION_MANIFEST.json').read_bytes()
            )
            with self.assertRaisesRegex(ValueError, 'identity hash'):
                load_calibrator(tampered_dir)

    @staticmethod
    def _config(
        root: Path,
        examples: Path,
        workloads: Path,
        *,
        split: str,
        run_id: str,
        output: Path,
    ) -> InferenceConfig:
        path = root / f'{run_id}.toml'
        path.write_text(
            f'''[run]
run_id = '{run_id}'
split = '{split}'
seed = 11
limit_per_level = 4
output_dir = '{output.as_posix()}'
resume = true

[provider]
kind = 'mock'

[model]
requested_model = 'mock/frozen'
temperature = 0.0
max_tokens = 8
require_logprobs = true
top_logprobs = 1
allow_fallbacks = false
require_parameters = true
data_collection = 'deny'

[prompt]
template_id = 'forced-answer-r5-v1'
system = 'Always provide a shortest factual answer.'
user_template = 'Question: {{question}}'

[budget]
max_cost_usd = 0.0
max_requests = 4
prompt_usd_per_million = 0.0
completion_usd_per_million = 0.0

[[datasets]]
dataset_id = 'fixture'
examples = '{examples.as_posix()}'
workloads = '{workloads.as_posix()}'
''',
            encoding='utf-8',
        )
        return load_inference_config(path)

    @staticmethod
    def _run_and_rescore(
        config: InferenceConfig, scores: dict[str, float]
    ) -> None:
        summary = run_inference(config)
        if summary['remaining_after_invocation'] != 0:
            raise AssertionError('fixture inference did not complete')
        generations_path = config.run.output_dir / 'generations.jsonl'
        generations = read_jsonl(generations_path)
        for row in generations:
            row['score'] = scores[str(row['example_id'])]
        write_jsonl(generations_path, generations)
        score_run(config)


if __name__ == '__main__':
    unittest.main()
