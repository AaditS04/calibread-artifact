import tempfile
from pathlib import Path
import unittest

from calibread.data_sources import fetch_source, load_registry


class DataSourceRegistryTests(unittest.TestCase):
    def test_registry_loads_and_has_fail_closed_statuses(self) -> None:
        registry = load_registry()
        self.assertEqual(registry['socrates_v1'].text('license_status'), 'approved')
        self.assertEqual(registry['ambigqa'].text('license_status'), 'review_required')
        self.assertEqual(registry['popqa'].text('expected_sha256'), '9a5227f41bff0e4c331d4a774d946b12f95307892b58f860a9606ef356e6089b')
        self.assertEqual(registry['musique'].text('transport'), 'url')
        self.assertEqual(
            registry['musique'].text('expected_sha256'),
            '98f839bf2fd5319f5c688aed77901a6d5c30b3b9f9f691ab9a8ecafb045ee0cd',
        )

    def test_fetch_denies_unreviewed_source_before_network_or_disk(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(PermissionError):
                fetch_source('ambigqa', raw_root=Path(directory))


if __name__ == '__main__':
    unittest.main()
