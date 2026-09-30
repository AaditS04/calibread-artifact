"""Scientific invariants for dependency-free reliability metrics."""

from __future__ import annotations

import unittest

from calibread.metrics import (
    area_under_risk_coverage_curve,
    brier_score,
    candidate_oracle_recall,
    expected_calibration_error,
    group_reliability_report,
    paired_aurc_comparison,
    prediction_set_efficiency,
    reliability_bins,
    risk_coverage_curve,
    selective_report,
)


class MetricValidationTests(unittest.TestCase):
    def test_brier_score_and_boundaries(self) -> None:
        self.assertAlmostEqual(brier_score([0.0, 0.5, 1.0], [0, 1, 1]), 1.0 / 12.0)
        bins = reliability_bins([0.0, 0.499, 0.5, 1.0], [0, 1, 1, 1], n_bins=2)
        self.assertEqual([item.count for item in bins], [2, 2])
        self.assertEqual((bins[0].lower, bins[0].upper), (0.0, 0.5))
        self.assertEqual((bins[1].lower, bins[1].upper), (0.5, 1.0))

    def test_metric_inputs_are_strictly_validated(self) -> None:
        invalid_calls = (
            lambda: brier_score([], []),
            lambda: brier_score([0.5], [1, 0]),
            lambda: brier_score([-0.01], [0]),
            lambda: brier_score([1.01], [1]),
            lambda: reliability_bins([0.5], [1], n_bins=0),
            lambda: selective_report([0.5], [1], threshold=1.01),
        )
        for call in invalid_calls:
            with self.subTest(call=call), self.assertRaises(ValueError):
                call()

    def test_ece_uses_sample_weighted_nonempty_bins(self) -> None:
        # First bin: |0.2 - 0|; second bin: |0.8 - 1|.
        self.assertAlmostEqual(expected_calibration_error([0.2, 0.8], [0, 1], n_bins=2), 0.2)

    def test_selective_report_handles_abstain_all(self) -> None:
        report = selective_report([0.1, 0.2], [1, 0], threshold=0.9)
        self.assertEqual(report.accepted, 0)
        self.assertEqual(report.coverage, 0.0)
        self.assertIsNone(report.risk)
        self.assertIsNone(report.accuracy)


class RiskCoverageTests(unittest.TestCase):
    def test_equal_confidence_examples_enter_as_one_tie_block(self) -> None:
        curve = risk_coverage_curve([0.9, 0.9, 0.5], [1, 0, 0])
        self.assertEqual(len(curve), 2)
        self.assertEqual(curve[0].accepted, 2)
        self.assertAlmostEqual(curve[0].coverage, 2.0 / 3.0)
        self.assertAlmostEqual(curve[0].risk, 0.5)
        self.assertEqual(curve[-1].accepted, 3)
        self.assertAlmostEqual(curve[-1].coverage, 1.0)

    def test_aurc_is_right_continuous_step_integral(self) -> None:
        curve = risk_coverage_curve([0.9, 0.9, 0.5], [1, 0, 0])
        self.assertAlmostEqual(area_under_risk_coverage_curve(curve), 5.0 / 9.0)

    def test_groups_preserve_hashable_identity(self) -> None:
        report = group_reliability_report([0.8, 0.2], [1, 0], [1, "1"], n_bins=2)
        self.assertEqual(len(report), 2)




class PredictionSetMetricTests(unittest.TestCase):
    def test_efficiency_reports_size_singletons_and_empty_sets(self) -> None:
        report = prediction_set_efficiency([{0}, {0, 1}, set()])
        self.assertAlmostEqual(report['mean_size'], 1.0)
        self.assertAlmostEqual(report['median_size'], 1.0)
        self.assertAlmostEqual(report['p90_size'], 2.0)
        self.assertAlmostEqual(report['singleton_rate'], 1.0 / 3.0)
        self.assertAlmostEqual(report['empty_rate'], 1.0 / 3.0)

    def test_candidate_oracle_recall_is_separate_from_coverage(self) -> None:
        recall = candidate_oracle_recall([{1, 2}, {3}, {4}], [2, 1, 4])
        self.assertAlmostEqual(recall, 2.0 / 3.0)

    def test_prediction_set_inputs_must_be_nonempty_and_aligned(self) -> None:
        with self.assertRaises(ValueError):
            prediction_set_efficiency([])
        with self.assertRaises(ValueError):
            candidate_oracle_recall([{0}], [0, 1])


class PairedPolicyComparisonTests(unittest.TestCase):
    def test_identical_fixed_grid_policies_have_zero_difference(self) -> None:
        result = paired_aurc_comparison(
            [0.9, 0.7, 0.3, 0.1],
            [0.9, 0.7, 0.3, 0.1],
            [1, 1, 0, 0],
            clusters=['a', 'a', 'b', 'b'],
            n_resamples=100,
            seed=4,
        )
        self.assertEqual(result.difference, 0.0)
        self.assertEqual(result.interval_lower, 0.0)
        self.assertEqual(result.interval_upper, 0.0)

    def test_better_error_ranking_has_lower_aurc_and_is_deterministic(self) -> None:
        arguments = (
            [0.9, 0.8, 0.2, 0.1],
            [0.2, 0.1, 0.9, 0.8],
            [1, 1, 0, 0],
        )
        first = paired_aurc_comparison(
            *arguments,
            clusters=['a', 'a', 'b', 'b'],
            n_resamples=100,
            seed=5,
        )
        second = paired_aurc_comparison(
            *arguments,
            clusters=['a', 'a', 'b', 'b'],
            n_resamples=100,
            seed=5,
        )
        self.assertEqual(first, second)
        self.assertLess(first.method_a_aurc, first.method_b_aurc)
        self.assertLess(first.difference, 0.0)

    def test_paired_policy_inputs_must_align(self) -> None:
        with self.assertRaises(ValueError):
            paired_aurc_comparison([0.9], [0.8, 0.7], [1])
        with self.assertRaises(ValueError):
            paired_aurc_comparison(
                [0.9], [0.8], [1], clusters=['a', 'b']
            )


if __name__ == "__main__":
    unittest.main()
