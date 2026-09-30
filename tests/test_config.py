"""Canonical all-dimensions study configuration validation tests."""

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from calibread.config import (
    REQUIRED_ESTIMANDS,
    load_study_config,
    validate_study_config,
)

ROOT = Path(__file__).resolve().parents[1]


class StudyConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pilot = load_study_config(ROOT / "configs" / "pilot.toml")
        cls.full = load_study_config(ROOT / "configs" / "full_study.toml")

    def test_workspace_configs_freeze_all_dimensions_and_lineage(self) -> None:
        self.assertEqual(
            self.full["scope"]["dimensions"], [f"R{i}" for i in range(1, 8)]
        )
        self.assertIn("source_fact_id", self.full["splits"]["disjoint_keys"])
        self.assertIn("r1_x_r5_cell", self.full["splits"]["strata_keys"])
        self.assertIn("r3_x_r6_cell", self.full["splits"]["strata_keys"])
        self.assertNotEqual(
            set(self.full["splits"]["disjoint_keys"]),
            set(self.full["splits"]["strata_keys"]),
        )

    def test_full_model_ids_and_explicit_breadth_levels_are_coherent(self) -> None:
        families = self.full["models"]["family_slots"]
        full_suite = self.full["models"]["full_suite_family_ids"]
        breadth = self.full["models"]["breadth_levels"]
        self.assertEqual(len(families), 10)
        self.assertEqual(len(set(families)), 10)
        self.assertEqual(len(full_suite), 3)
        self.assertLessEqual(set(full_suite), set(families))
        self.assertEqual(breadth["R1"], self.full["dimensions"]["R1"]["levels"])
        self.assertEqual(breadth["R2"], self.full["dimensions"]["R2"]["levels"])
        self.assertEqual(breadth["R3"], self.full["dimensions"]["R3"]["levels"])
        self.assertEqual(breadth["R4"], ["unambiguous", "three_plus"])
        self.assertEqual(breadth["R5"], ["one_hop", "four_plus_hop"])
        self.assertEqual(breadth["R6"], ["general", "expert"])

    def test_targets_match_twenty_thirty_fifty_and_budget(self) -> None:
        gates = self.full["sample_gates"]
        self.assertEqual(
            [
                gates["target_development_per_level"],
                gates["target_calibration_per_level"],
                gates["target_test_per_level"],
            ],
            [80, 120, 200],
        )
        self.assertEqual(
            [
                gates["target_development_per_interaction_cell"],
                gates["target_calibration_per_interaction_cell"],
                gates["target_test_per_interaction_cell"],
            ],
            [60, 90, 150],
        )
        self.assertEqual(
            self.full["budget"]["base_pair_budget_before_overcollection"], 56800
        )

    def test_missing_dimension_interaction_or_track_fails(self) -> None:
        for field in ("dimensions", "confirmatory_interactions", "tracks"):
            bad = copy.deepcopy(self.pilot)
            bad["scope"][field] = bad["scope"][field][:-1]
            with self.subTest(field=field), self.assertRaisesRegex(
                ValueError, "canonical P03 protocol"
            ):
                validate_study_config(bad)

    def test_dimension_name_fields_levels_and_anchor_are_canonical(self) -> None:
        mutations = [
            ("name", "frequency"),
            ("raw_fields", ["frequency_value"]),
            ("levels", ["tail", "middle", "head"]),
            ("anchor", "head"),
        ]
        for field, value in mutations:
            bad = copy.deepcopy(self.pilot)
            bad["dimensions"]["R1"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_study_config(bad)

    def test_proxy_mapping_rules_and_hashes_must_freeze_before_finalization(self) -> None:
        missing_method = copy.deepcopy(self.full)
        del missing_method["dimensions"]["R1"]["level_mapping_method"]
        with self.assertRaisesRegex(ValueError, "level_mapping_method"):
            validate_study_config(missing_method)

        malformed_hash = copy.deepcopy(self.full)
        malformed_hash["dimensions"]["R2"]["level_mapping_manifest_hash"] = "later"
        with self.assertRaisesRegex(ValueError, "sha256"):
            validate_study_config(malformed_hash)

        finalized_tbd = copy.deepcopy(self.full)
        finalized_tbd["study"]["finalized"] = True
        with self.assertRaisesRegex(ValueError, "cannot retain a TBD"):
            validate_study_config(finalized_tbd)

    def test_threshold_and_target_coverage_correspondence_fails_closed(self) -> None:
        bad_threshold = copy.deepcopy(self.pilot)
        bad_threshold["policy"]["r7_thresholds"] = [0.50, 0.90]
        with self.assertRaisesRegex(ValueError, "frozen P03"):
            validate_study_config(bad_threshold)

        bad_coverage = copy.deepcopy(self.pilot)
        bad_coverage["study"]["target_coverage"] = 0.95
        with self.assertRaisesRegex(ValueError, "one-to-one"):
            validate_study_config(bad_coverage)

    def test_split_lineage_and_strata_drift_fail(self) -> None:
        missing_source = copy.deepcopy(self.pilot)
        missing_source["splits"]["disjoint_keys"].remove("source_fact_id")
        with self.assertRaisesRegex(ValueError, "source-fact"):
            validate_study_config(missing_source)

        bad_strata = copy.deepcopy(self.pilot)
        bad_strata["splits"]["strata_keys"] = ["r1_frequency_level"]
        with self.assertRaisesRegex(ValueError, "canonical P03"):
            validate_study_config(bad_strata)

        overlap = copy.deepcopy(self.pilot)
        overlap["splits"]["strata_keys"][0] = "entity_id"
        with self.assertRaises(ValueError):
            validate_study_config(overlap)

    def test_strict_missing_lineage_policy_cannot_be_relaxed(self) -> None:
        expected = self.full["splits"]
        self.assertEqual(
            expected["missing_lineage_policy"],
            "require_value_or_explicit_exemption",
        )
        self.assertEqual(
            expected["lineage_exemption_field"], "lineage_exemptions"
        )
        self.assertEqual(
            expected["non_exemptable_disjoint_keys"], ["question_hash"]
        )
        self.assertFalse(expected["legacy_single_key_mode"])

        mutations = [
            ("missing_lineage_policy", "skip_missing"),
            ("lineage_exemption_field", "missing_reasons"),
            ("question_hash_method", "unspecified"),
            ("legacy_single_key_mode", True),
        ]
        for key, value in mutations:
            bad = copy.deepcopy(self.full)
            bad["splits"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_study_config(bad)

        bad_reasons = copy.deepcopy(self.full)
        bad_reasons["splits"]["allowed_lineage_exemption_reasons"].append(
            "unknown"
        )
        with self.assertRaisesRegex(ValueError, "canonical P03 protocol"):
            validate_study_config(bad_reasons)

    def test_exact_target_ratios_and_hard_floors_are_checked(self) -> None:
        bad_ratio = copy.deepcopy(self.full)
        bad_ratio["sample_gates"]["target_calibration_per_level"] = 100
        with self.assertRaisesRegex(ValueError, "exactly match"):
            validate_study_config(bad_ratio)

        bad_floor = copy.deepcopy(self.full)
        bad_floor["sample_gates"]["hard_floor_test_per_main_level"] = 201
        with self.assertRaisesRegex(ValueError, "must not exceed"):
            validate_study_config(bad_floor)

        nonpositive = copy.deepcopy(self.full)
        nonpositive["sample_gates"]["breadth_target_development_per_level"] = 0
        with self.assertRaisesRegex(ValueError, "positive integer"):
            validate_study_config(nonpositive)

    def test_full_family_uniqueness_subset_and_count_are_checked(self) -> None:
        duplicate = copy.deepcopy(self.full)
        duplicate["models"]["family_slots"][-1] = duplicate["models"]["family_slots"][0]
        with self.assertRaisesRegex(ValueError, "duplicates"):
            validate_study_config(duplicate)

        outsider = copy.deepcopy(self.full)
        outsider["models"]["full_suite_family_ids"][0] = "not_a_family"
        with self.assertRaisesRegex(ValueError, "subset"):
            validate_study_config(outsider)

        two_full = copy.deepcopy(self.full)
        two_full["models"]["full_suite_family_ids"] = two_full["models"][
            "full_suite_family_ids"
        ][:2]
        with self.assertRaisesRegex(ValueError, "exactly three"):
            validate_study_config(two_full)

    def test_breadth_levels_estimands_and_budget_are_checked(self) -> None:
        bad_breadth = copy.deepcopy(self.full)
        bad_breadth["models"]["breadth_levels"]["R3"] = ["pre_cutoff"]
        with self.assertRaisesRegex(ValueError, "canonical P03"):
            validate_study_config(bad_breadth)

        missing_estimand = copy.deepcopy(self.full)
        del missing_estimand["evaluation"]["primary_estimands"]["OP-R4"]
        with self.assertRaisesRegex(ValueError, "primary_estimands"):
            validate_study_config(missing_estimand)
        self.assertEqual(
            set(self.full["evaluation"]["primary_estimands"]), REQUIRED_ESTIMANDS
        )

        vague_estimand = copy.deepcopy(self.full)
        vague_estimand["evaluation"]["primary_estimands"]["OP-R1"] = (
            "docs/hypothesis_registry.md#op-r1"
        )
        with self.assertRaisesRegex(ValueError, "operational description"):
            validate_study_config(vague_estimand)

        bad_budget = copy.deepcopy(self.full)
        bad_budget["budget"]["additional_breadth_pairs"] -= 1
        with self.assertRaisesRegex(ValueError, "implied by models"):
            validate_study_config(bad_budget)


if __name__ == "__main__":
    unittest.main()
