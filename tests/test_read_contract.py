"""R7 answer/set/abstain contract tests."""

from __future__ import annotations

import unittest

from calibread.read_contract import prediction_set_read, read_policy, selective_read


class SelectiveReadTests(unittest.TestCase):
    def test_legacy_singleton_wrapper_fails_closed_without_r4_provenance(self) -> None:
        accepted = selective_read("Paris", 0.9, 0.9)
        rejected = selective_read("Paris", 0.89, 0.9)
        self.assertEqual(accepted.action, "abstain")
        self.assertEqual(accepted.reason, "ambiguity_incomplete_singleton")
        self.assertFalse(accepted.ambiguity_complete)
        self.assertEqual(rejected.action, "abstain")

    def test_unsupported_group_fails_closed(self) -> None:
        decision = selective_read("Paris", 0.99, 0.9, supported=False)
        self.assertEqual(decision.action, "abstain")
        self.assertEqual(decision.reason, "unsupported_calibration_group")

    def test_invalid_policy_values_fail(self) -> None:
        with self.assertRaises(ValueError):
            selective_read("Paris", 1.1, 0.9)
        with self.assertRaises(ValueError):
            selective_read("Paris", 0.9, -0.1)


class PredictionSetReadTests(unittest.TestCase):
    def test_empty_singleton_and_multiple_sets_map_to_three_actions(self) -> None:
        self.assertEqual(prediction_set_read([]).action, "abstain")
        singleton = prediction_set_read([2])
        self.assertEqual(singleton.action, "abstain")
        self.assertFalse(singleton.ambiguity_complete)
        multiple = prediction_set_read([2, 1, 2])
        self.assertEqual(multiple.action, "set")
        self.assertEqual(multiple.candidates, (2, 1))

    def test_unsupported_prediction_set_is_not_returned(self) -> None:
        decision = prediction_set_read([1, 2], supported=False)
        self.assertEqual(decision.action, "abstain")
        self.assertEqual(decision.candidates, ())

    def test_ambiguity_incomplete_singleton_never_commits(self) -> None:
        decision = read_policy(
            "Mercury",
            0.99,
            0.9,
            candidates=("Mercury",),
            ambiguity_complete=False,
            score_kind="probability",
            score_source="temperature_scaled",
            calibrator_id="temp-v1",
        )
        self.assertEqual(decision.action, "abstain")
        self.assertEqual(decision.reason, "ambiguity_incomplete_singleton")
        self.assertEqual(decision.policy_level, "tau_0_90")

    def test_allowed_actions_and_candidate_depth_control_decision(self) -> None:
        multiple = read_policy(
            None,
            0.95,
            0.9,
            candidates=("planet", "element"),
            allowed_actions=("set", "abstain"),
            score_kind="raw",
            score_source="normalized_sequence_score",
            normalization_contract="minmax-on-calibration-v1",
        )
        self.assertEqual(multiple.action, "set")
        self.assertEqual(multiple.candidates, ("planet", "element"))
        singleton_set = read_policy(
            "planet",
            0.95,
            0.9,
            candidates=("planet",),
            allowed_actions=("set", "abstain"),
            score_kind="raw",
            score_source="normalized_sequence_score",
            normalization_contract="minmax-on-calibration-v1",
        )
        self.assertEqual(singleton_set.action, "abstain")
        self.assertEqual(singleton_set.reason, "ambiguity_incomplete_singleton")

    def test_declared_probability_and_fail_closed_action_validation(self) -> None:
        with self.assertRaisesRegex(ValueError, "calibrator_id"):
            read_policy(
                "Paris",
                0.9,
                0.9,
                score_kind="probability",
                score_source="temperature_scaled",
            )
        with self.assertRaisesRegex(ValueError, "include abstain"):
            read_policy(
                "Paris",
                0.9,
                0.9,
                allowed_actions=("answer",),
                score_kind="raw",
                score_source="normalized_sequence_score",
                normalization_contract="minmax-on-calibration-v1",
            )
        with self.assertRaisesRegex(ValueError, "ambiguity_complete"):
            read_policy(
                "Paris",
                0.9,
                0.9,
                ambiguity_complete="false",  # type: ignore[arg-type]
                score_kind="raw",
                score_source="normalized_sequence_score",
                normalization_contract="minmax-on-calibration-v1",
            )
        with self.assertRaisesRegex(ValueError, "normalization_contract"):
            read_policy(
                "Paris",
                0.9,
                0.9,
                score_kind="raw",
                score_source="unnormalized_log_probability",
            )


if __name__ == "__main__":
    unittest.main()
