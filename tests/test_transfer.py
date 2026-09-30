"""R6 domain-calibration transfer diagnostic tests."""

from __future__ import annotations

import unittest

from calibread.transfer import calibration_transfer_comparison, domain_transfer_report


class DomainTransferTests(unittest.TestCase):
    def test_target_degradation_is_reported_as_signed_gap(self) -> None:
        report = domain_transfer_report(
            [0.9, 0.8, 0.2, 0.1],
            [1, 1, 0, 0],
            [0.9, 0.8, 0.8, 0.7],
            [1, 0, 0, 0],
            n_bins=2,
        )
        self.assertGreater(report.ece_increase, 0.0)
        self.assertGreater(report.brier_increase, 0.0)
        self.assertLess(report.target_accuracy, report.source_accuracy)

    def test_empty_or_misaligned_domains_fail(self) -> None:
        with self.assertRaises(ValueError):
            domain_transfer_report([], [], [0.5], [1])
        with self.assertRaises(ValueError):
            domain_transfer_report([0.5], [1], [0.5, 0.4], [1])

    def test_transfer_comparison_is_relative_to_a_panel_matched_baseline(self) -> None:
        report = calibration_transfer_comparison(
            [0.6, 0.6, 0.4, 0.4],
            [0.9, 0.8, 0.2, 0.1],
            [1, 1, 0, 0],
            [0.7, 0.6, 0.4, 0.3],
            [0.7, 0.6, 0.4, 0.3],
            [1, 0, 1, 0],
            n_bins=2,
        )
        self.assertGreater(report.within_brier_improvement, 0.0)
        self.assertAlmostEqual(report.cross_brier_improvement, 0.0)
        self.assertGreater(report.brier_transfer_advantage, 0.0)

    def test_transfer_comparison_requires_paired_methods_within_each_panel(self) -> None:
        with self.assertRaises(ValueError):
            calibration_transfer_comparison(
                [0.5], [0.5, 0.6], [1], [0.5], [0.5], [1]
            )


if __name__ == "__main__":
    unittest.main()
