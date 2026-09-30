'''Offline end-to-end tests for the API inference package.'''

from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from calibread.dimensions import DimensionValues
from calibread.inference.cli import main as inference_cli
from calibread.inference.config import load_inference_config
from calibread.inference.report import report_run
from calibread.inference.runner import plan_run, run_inference
from calibread.inference.scoring import score_run
from calibread.io import read_jsonl
from calibread.schema import Example, GenerationRecord


class InferencePipelineTests(unittest.TestCase):
    def test_mock_run_resume_score_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            examples_path = root / 'examples.jsonl'
            workloads_path = root / 'workloads.jsonl'
            output_path = root / 'results'
            example = Example(
                example_id='fixture-q1',
                question='MOCK_ANSWER=Paris?',
                accepted_answers=('Paris',),
                split='development',
                metadata={'chain_id': 'fixture-chain'},
            ).with_dimension_values(
                DimensionValues({'R5': {'raw': 2, 'level': 'two_hop'}})
            )
            examples_path.write_text(
                json.dumps(example.to_dict(), sort_keys=True) + '\n',
                encoding='utf-8',
            )
            workloads_path.write_text('{\'fixture\': true}\n', encoding='utf-8')
            config_path = root / 'mock.toml'
            config_path.write_text(
                f'''[run]
run_id = 'mock-r5'
split = 'development'
seed = 7
limit_per_level = 1
output_dir = '{output_path.as_posix()}'
resume = true

[provider]
kind = 'mock'

[model]
requested_model = 'mock/fixed'
temperature = 0.0
max_tokens = 8
require_logprobs = true
top_logprobs = 1
allow_fallbacks = false
require_parameters = true
data_collection = 'deny'

[prompt]
template_id = 'mock-r5-v1'
system = 'Answer briefly.'
user_template = 'Question: {{question}}'

[budget]
max_cost_usd = 0.0
max_requests = 1
prompt_usd_per_million = 0.0
completion_usd_per_million = 0.0

[[datasets]]
dataset_id = 'fixture'
examples = '{examples_path.as_posix()}'
workloads = '{workloads_path.as_posix()}'
''',
                encoding='utf-8',
            )

            config = load_inference_config(config_path)
            self.assertEqual(plan_run(config)['requests'], 1)
            first = run_inference(config)
            self.assertEqual(first['succeeded_this_invocation'], 1)
            manifest = json.loads(
                (output_path / 'RUN_MANIFEST.json').read_text(encoding='utf-8')
            )
            self.assertEqual(manifest['manifest_version'], 2)
            self.assertEqual(manifest['closed_book']['dataset_fields_sent'], ['question'])
            self.assertEqual(manifest['closed_book']['tools'], [])
            self.assertEqual(
                manifest['provider_fingerprint']['model_snapshot_id'],
                'mock/fixed',
            )
            second = run_inference(config)
            self.assertEqual(second['attempted_this_invocation'], 0)

            generations = list(read_jsonl(output_path / 'generations.jsonl'))
            self.assertEqual(len(generations), 1)
            record = GenerationRecord.from_dict(generations[0])
            self.assertEqual(record.raw_text, 'Paris')

            scored = score_run(config)
            with scored.open(encoding='utf-8', newline='') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]['correct'], '1')
            report = report_run(config)
            result = json.loads(report.read_text(encoding='utf-8'))
            self.assertEqual(result['overall']['accuracy'], 1.0)

            rows[0]['correct'] = '0'
            with scored.open('w', encoding='utf-8', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, 'incorrect correct'):
                report_run(config)

            config_path.write_text(
                config_path.read_text(encoding='utf-8').replace(
                    'max_tokens = 8', 'max_tokens = 9'
                ),
                encoding='utf-8',
            )
            changed = load_inference_config(config_path)
            with self.assertRaisesRegex(ValueError, 'RUN_MANIFEST'):
                run_inference(changed)

    def test_committed_openrouter_pilot_plans_but_cannot_run_unfrozen(self) -> None:
        config = load_inference_config(
            Path('configs/inference/r5_openrouter_pilot.toml')
        )
        plan = plan_run(config)
        self.assertEqual(plan['requests'], 500)
        with self.assertRaisesRegex(ValueError, 'concrete non-moving model'):
            config.validate_for_execution()
        with self.assertRaisesRegex(ValueError, 'concrete non-moving model'):
            inference_cli(
                ['validate-config', 'configs/inference/r5_openrouter_pilot.toml']
            )


if __name__ == '__main__':
    unittest.main()
