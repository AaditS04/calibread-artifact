"""Finite-sample and group-safety tests for conformal prediction."""

from __future__ import annotations

import math
import unittest

from calibread.conformal import (
    apply_group_prediction_sets,
    conformal_quantile,
    empirical_coverage,
    finite_label_prediction_set,
    group_conformal_quantiles,
    true_label_nonconformity,
)


class SplitConformalTests(unittest.TestCase):
    def test_quantile_uses_finite_sample_ceiling_rank(self) -> None:
        scores = [0.4, 0.1, 0.3, 0.2]
        # ceil((4 + 1) * (1 - .5)) = 3, hence the third order statistic.
        self.assertEqual(conformal_quantile(scores, alpha=0.5), 0.3)

    def test_unattainable_rank_returns_infinity_and_full_set(self) -> None:
        threshold = conformal_quantile([0.1, 0.2], alpha=0.1)
        self.assertTrue(math.isinf(threshold))
        self.assertEqual(finite_label_prediction_set([0.2, 0.3, 0.5], threshold), {0, 1, 2})

    def test_invalid_alpha_scores_and_thresholds_fail(self) -> None:
        invalid_calls = (
            lambda: conformal_quantile([], 0.1),
            lambda: conformal_quantile([0.1], 0.0),
            lambda: conformal_quantile([math.nan], 0.1),
            lambda: finite_label_prediction_set([0.4, 0.6], -0.1),
            lambda: finite_label_prediction_set([0.4, 0.6], 1.01),
        )
        for call in invalid_calls:
            with self.subTest(call=call), self.assertRaises(ValueError):
                call()

    def test_probability_rows_require_one_cardinality(self) -> None:
        with self.assertRaises(ValueError):
            true_label_nonconformity([[0.4, 0.6], [0.2, 0.3, 0.5]], [1, 2])

    def test_coverage_uses_membership(self) -> None:
        self.assertAlmostEqual(empirical_coverage([{0, 1}, {1}, {2}], [0, 0, 2]), 2.0 / 3.0)


class GroupConformalTests(unittest.TestCase):
    def test_group_keys_do_not_collide_after_stringification(self) -> None:
        thresholds = group_conformal_quantiles([0.1, 0.2], [1, "1"], alpha=0.5)
        self.assertEqual(len(thresholds), 2)
        self.assertIn(1, thresholds)
        self.assertIn("1", thresholds)

    def test_too_small_group_fails_before_claiming_group_coverage(self) -> None:
        with self.assertRaisesRegex(ValueError, "minimum"):
            group_conformal_quantiles([0.1, 0.2, 0.3], ["head", "head", "tail"], 0.2, min_group_size=2)

    def test_unseen_group_fails_closed(self) -> None:
        with self.assertRaises(KeyError):
            apply_group_prediction_sets([[0.25, 0.75]], ["unseen"], {"seen": 0.5})

    def test_group_threshold_is_applied_to_matching_row(self) -> None:
        result = apply_group_prediction_sets(
            [[0.8, 0.2], [0.3, 0.7]],
            ["head", "tail"],
            {"head": 0.25, "tail": 0.75},
        )
        self.assertEqual(result, [frozenset({0}), frozenset({0, 1})])


if __name__ == "__main__":
    unittest.main()
