import json
from pathlib import Path
import tempfile
import unittest

from calibread.condition_audit import audit_readiness


class ConditionAuditTests(unittest.TestCase):
    def test_placeholders_and_incomplete_seeds_block_freeze(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'pilot.toml'
            config.write_text(
                """[models]\nfamily_slots=['model_tbd']\nfull_suite_family_ids=['model_tbd']\n[dimensions.R1]\nlevel_mapping_manifest_hash='tbd_before_inference'\n""",
                encoding='utf-8',
            )
            source = root / 'processed' / 'source'
            source.mkdir(parents=True)
            (source / 'condition_seeds.jsonl').write_text(
                json.dumps({'R1': {'proxy_value': 3}, 'R3': {'event_date': None}}) + '\n',
                encoding='utf-8',
            )
            report = audit_readiness(config, root / 'processed')
        self.assertFalse(report['freeze_ready'])
        self.assertEqual(report['complete_seed_count'], 0)
        self.assertEqual(len(report['blockers']), 3)

    def test_exact_model_mapping_and_complete_seed_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'pilot.toml'
            config.write_text(
                """[models]\nfamily_slots=['model@revision']\nfull_suite_family_ids=['model@revision']\n[dimensions.R1]\nlevel_mapping_manifest_hash='abc123'\n""",
                encoding='utf-8',
            )
            source = root / 'processed' / 'source'
            source.mkdir(parents=True)
            (source / 'condition_seeds.jsonl').write_text(
                json.dumps({'R1': {'proxy_value': 3}, 'R3': {'event_date_proxy': '2020-01-01'}}) + '\n',
                encoding='utf-8',
            )
            report = audit_readiness(config, root / 'processed')
        self.assertTrue(report['freeze_ready'])
        self.assertEqual(report['complete_seed_count'], 1)


if __name__ == '__main__':
    unittest.main()
