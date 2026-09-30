"""Boundary and reproducibility tests for uncertainty summaries."""

from __future__ import annotations

import unittest

from calibread.statistics import (
    bootstrap_mean_interval,
    clopper_pearson_interval,
    clustered_paired_bootstrap_difference,
    holm_adjusted_pvalues,
    wilson_interval,
)


class ClopperPearsonIntervalTests(unittest.TestCase):
    def test_known_exact_equal_tailed_intervals(self) -> None:
        zero = clopper_pearson_interval(0, 10)
        middle = clopper_pearson_interval(5, 10)
        all_success = clopper_pearson_interval(10, 10)
        self.assertEqual(zero[0], 0.0)
        self.assertAlmostEqual(zero[1], 0.3084971078, places=8)
        self.assertAlmostEqual(middle[0], 0.1870860284, places=8)
        self.assertAlmostEqual(middle[1], 0.8129139716, places=8)
        self.assertAlmostEqual(all_success[0], 0.6915028922, places=8)
        self.assertEqual(all_success[1], 1.0)

    def test_invalid_inputs_fail_closed(self) -> None:
        for call in (
            lambda: clopper_pearson_interval(True, 10),
            lambda: clopper_pearson_interval(0, 0),
            lambda: clopper_pearson_interval(-1, 10),
            lambda: clopper_pearson_interval(11, 10),
            lambda: clopper_pearson_interval(5, 10, confidence=1.0),
        ):
            with self.subTest(call=call), self.assertRaises(ValueError):
                call()


class WilsonIntervalTests(unittest.TestCase):
    def test_boundary_counts_stay_inside_probability_range(self) -> None:
        zero = wilson_interval(0, 10)
        all_success = wilson_interval(10, 10)
        self.assertEqual(zero[0], 0.0)
        self.assertEqual(all_success[1], 1.0)
        for lower, upper in (zero, all_success, wilson_interval(5, 10)):
            self.assertGreaterEqual(lower, 0.0)
            self.assertLessEqual(upper, 1.0)
            self.assertLessEqual(lower, upper)

    def test_observed_proportion_lies_in_interval(self) -> None:
        lower, upper = wilson_interval(37, 100)
        self.assertLessEqual(lower, 0.37)
        self.assertGreaterEqual(upper, 0.37)

    def test_invalid_counts_and_confidence_fail(self) -> None:
        for call in (
            lambda: wilson_interval(0, 0),
            lambda: wilson_interval(-1, 10),
            lambda: wilson_interval(11, 10),
            lambda: wilson_interval(5, 10, confidence=1.0),
        ):
            with self.subTest(call=call), self.assertRaises(ValueError):
                call()


class BootstrapIntervalTests(unittest.TestCase):
    def test_seed_makes_interval_deterministic(self) -> None:
        first = bootstrap_mean_interval([0.0, 1.0, 2.0, 3.0], n_resamples=200, seed=9)
        second = bootstrap_mean_interval([0.0, 1.0, 2.0, 3.0], n_resamples=200, seed=9)
        self.assertEqual(first, second)

    def test_constant_sample_has_degenerate_interval(self) -> None:
        self.assertEqual(
            bootstrap_mean_interval([2.5, 2.5, 2.5], n_resamples=20, seed=3),
            (2.5, 2.5),
        )

    def test_invalid_bootstrap_arguments_fail(self) -> None:
        for call in (
            lambda: bootstrap_mean_interval([]),
            lambda: bootstrap_mean_interval([1.0], n_resamples=1),
            lambda: bootstrap_mean_interval([1.0], confidence=0.0),
        ):
            with self.subTest(call=call), self.assertRaises(ValueError):
                call()


class MultipleComparisonTests(unittest.TestCase):
    def test_holm_adjustment_preserves_original_order(self) -> None:
        self.assertEqual(holm_adjusted_pvalues([]), [])
        adjusted = holm_adjusted_pvalues([0.01, 0.04, 0.03])
        self.assertEqual(adjusted, [0.03, 0.06, 0.06])

    def test_holm_rejects_invalid_values(self) -> None:
        for values in ([-0.01], [1.01], [float('nan')]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                holm_adjusted_pvalues(values)


class ClusteredPairedBootstrapTests(unittest.TestCase):
    def test_constant_paired_difference_is_degenerate(self) -> None:
        result = clustered_paired_bootstrap_difference(
            [2.0, 3.0, 4.0, 5.0],
            [1.0, 2.0, 3.0, 4.0],
            ['family-a', 'family-a', 'family-b', 'family-b'],
            n_resamples=100,
            seed=13,
        )
        self.assertEqual(result, (1.0, 1.0, 1.0))

    def test_seed_is_deterministic_and_alignment_is_validated(self) -> None:
        arguments = (
            [1.0, 0.0, 4.0, 2.0],
            [0.0, 1.0, 1.0, 1.0],
            ['a', 'a', 'b', 'c'],
        )
        first = clustered_paired_bootstrap_difference(
            *arguments, n_resamples=100, seed=9
        )
        second = clustered_paired_bootstrap_difference(
            *arguments, n_resamples=100, seed=9
        )
        self.assertEqual(first, second)
        with self.assertRaises(ValueError):
            clustered_paired_bootstrap_difference(
                [1.0], [1.0, 2.0], ['a'], n_resamples=10
            )


if __name__ == "__main__":
    unittest.main()
