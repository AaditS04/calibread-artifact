"""Tests for separating atomic failures from synthesis failures."""

from __future__ import annotations

import unittest

from calibread.composition import composition_report


class CompositionReportTests(unittest.TestCase):
    def test_synthesis_loss(self) -> None:
        report = composition_report([[1, 1], [1, 1], [1, 0]], [1, 0, 0])
        self.assertAlmostEqual(report.chain_accuracy, 1.0 / 3.0)
        self.assertAlmostEqual(report.all_atoms_correct_rate, 2.0 / 3.0)
        self.assertAlmostEqual(report.chain_accuracy_given_all_atoms, 0.5)
        self.assertAlmostEqual(report.synthesis_loss, 0.5)

    def test_product_gap_and_union_bound(self) -> None:
        report = composition_report(
            [[1, 1], [1, 1]], [1, 0], [[0.9, 0.8], [0.5, 0.5]]
        )
        self.assertAlmostEqual(report.mean_product_prediction, 0.485)
        self.assertAlmostEqual(report.product_calibration_gap, -0.015)
        self.assertAlmostEqual(report.mean_union_bound, 0.35)

    def test_undefined_synthesis_loss(self) -> None:
        report = composition_report([[1, 0], [0, 1]], [0, 1])
        self.assertIsNone(report.chain_accuracy_given_all_atoms)
        self.assertIsNone(report.synthesis_loss)

    def test_shapes_and_probabilities_are_validated(self) -> None:
        calls = (
            lambda: composition_report([], []),
            lambda: composition_report([[1]], [1, 0]),
            lambda: composition_report([[]], [1]),
            lambda: composition_report([[1, 0]], [1], [[0.8]]),
            lambda: composition_report([[1, 0]], [1], [[0.8, 1.2]]),
        )
        for call in calls:
            with self.subTest(call=call), self.assertRaises(ValueError):
                call()


if __name__ == '__main__':
    unittest.main()
