from collections import Counter, defaultdict
from pathlib import Path
import tempfile
import unittest

from calibread.authoring import load_authored
from calibread.candidates import build_candidates, write_candidates


class CandidateBuilderTests(unittest.TestCase):
    def test_candidate_pack_is_structurally_valid_and_balanced(self) -> None:
        rows = build_candidates()
        self.assertEqual(len(rows), 37)
        self.assertEqual(Counter(row['dimension'] for row in rows), {'R2': 12, 'R4': 16, 'R6': 9})
        levels: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            levels[str(row['dimension'])].add(str(row['adjudicated_level']))
            self.assertEqual(row['adjudication_status'], 'draft')
            self.assertFalse(row['contributor_consent'])
        self.assertEqual(levels['R2'], {'coarse', 'medium', 'fine'})
        self.assertEqual(levels['R4'], {'unambiguous', 'two_way', 'three_plus'})
        self.assertEqual(levels['R6'], {'general', 'specialized', 'expert'})

    def test_written_pack_round_trips_through_authoring_validator(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = write_candidates(Path(directory) / 'candidates.jsonl')
            rows, errors = load_authored(output)
            self.assertEqual(errors, [])
            self.assertEqual(len(rows), 37)
            self.assertTrue(output.with_name('CANDIDATE_CARD.md').is_file())


if __name__ == '__main__':
    unittest.main()
