"""R4 ambiguity and semantic-idempotency metric tests."""

from __future__ import annotations

import unittest

from calibread.ambiguity import ambiguity_report


class AmbiguityReportTests(unittest.TestCase):
    def test_validity_and_pairwise_idempotency_are_separate(self) -> None:
        report = ambiguity_report(["a", "a", "b", "invalid"], {"a", "b"})
        self.assertEqual(report.response_count, 4)
        self.assertEqual(report.valid_response_rate, 0.75)
        self.assertEqual(report.unique_response_classes, 3)
        self.assertAlmostEqual(report.pairwise_idempotency, 1 / 6)

    def test_single_response_has_undefined_pairwise_rate(self) -> None:
        self.assertIsNone(ambiguity_report(["a"], {"a"}).pairwise_idempotency)

    def test_empty_inputs_fail(self) -> None:
        with self.assertRaises(ValueError):
            ambiguity_report([], {"a"})
        with self.assertRaises(ValueError):
            ambiguity_report(["a"], set())


if __name__ == "__main__":
    unittest.main()
