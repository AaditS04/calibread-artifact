"""Validation, derivation, metadata, and grouping tests for P03 R1--R7."""

from __future__ import annotations

import math
import unittest

from calibread.dimensions import (
    DIMENSION_REGISTRY,
    DIMENSIONS_METADATA_KEY,
    DimensionSpec,
    DimensionValues,
    crossed_group_label,
    dimension_spec,
    r1_from_frequency,
    r3_from_dates,
    r3_from_relative_months,
    r4_from_interpretation_count,
    r5_from_hop_count,
    r6_from_specificity,
    r7_from_threshold,
)
from calibread.schema import Example


def all_values() -> DimensionValues:
    return DimensionValues(
        {
            "R1": {"raw": 8, "level": "tail"},
            "R2": {"raw": "day", "level": "fine"},
            "R3": {"raw": 12, "level": "post_4_12_months"},
            "R4": {"raw": 2, "level": "two_way"},
            "R5": {"raw": 5, "level": "four_plus_hop"},
            "R6": {"raw": 0.9, "level": "expert"},
            "R7": {"raw": 0.9, "level": "tau_0_90"},
        }
    )


class DimensionRegistryTests(unittest.TestCase):
    def test_registry_exactly_matches_professor_p03_axes(self) -> None:
        self.assertEqual(tuple(DIMENSION_REGISTRY), tuple(f"R{i}" for i in range(1, 8)))
        self.assertEqual(
            [spec.name for spec in DIMENSION_REGISTRY.values()],
            [
                "Knowledge Frequency",
                "Precision Requirement",
                "Knowledge Recency",
                "Query Ambiguity",
                "Synthesis Depth",
                "Domain Specificity",
                "Confidence Threshold",
            ],
        )
        self.assertTrue(DIMENSION_REGISTRY["R7"].is_policy)
        self.assertTrue(all(not spec.is_policy for spec in list(DIMENSION_REGISTRY.values())[:6]))
        self.assertEqual(
            {code: spec.levels for code, spec in DIMENSION_REGISTRY.items()},
            {
                "R1": ("head", "middle", "tail"),
                "R2": ("coarse", "medium", "fine"),
                "R3": ("pre_cutoff", "post_0_3_months", "post_4_12_months", "post_13_plus_months"),
                "R4": ("unambiguous", "two_way", "three_plus"),
                "R5": ("one_hop", "two_hop", "three_hop", "four_plus_hop"),
                "R6": ("general", "specialized", "expert"),
                "R7": ("tau_0_50", "tau_0_70", "tau_0_90", "tau_0_95", "tau_0_99"),
            },
        )

    def test_codes_and_slugs_resolve_but_unknown_axes_fail(self) -> None:
        self.assertIs(dimension_spec("r1"), dimension_spec("knowledge_frequency"))
        with self.assertRaises(ValueError):
            dimension_spec("R8")

    def test_r1_and_r6_raw_measurement_contracts_are_unambiguous(self) -> None:
        r1 = dimension_spec('R1')
        r6 = dimension_spec('R6')
        self.assertIn('source-declared exposure count', r1.unit)
        self.assertIn('provenance', r1.unit)
        self.assertEqual(r6.raw_kinds, ('number',))
        self.assertIn('[0,1]', r6.unit)
        with self.assertRaises(ValueError):
            DimensionValues(
                {'R6': {'raw': 'medicine', 'level': 'specialized'}}
            )

    def test_spec_definitions_validate_themselves(self) -> None:
        with self.assertRaises(ValueError):
            DimensionSpec("D1", "bad", "Bad", "core", "query", ("number",), ("x",), "u")
        with self.assertRaises(ValueError):
            DimensionSpec("R1", "bad", "Bad", "core", "hidden", ("number",), ("x",), "u")


class DimensionValuesTests(unittest.TestCase):
    def test_all_dimensions_round_trip_with_raw_values_and_levels(self) -> None:
        values = all_values()
        self.assertEqual(len(values), 7)
        self.assertEqual(DimensionValues.from_dict(values.to_dict()).to_dict(), values.to_dict())
        self.assertEqual(values["synthesis_depth"].raw, 5)
        self.assertEqual(values["R2"].raw, "day")

    def test_each_dimension_rejects_invalid_raw_measurement(self) -> None:
        cases = {
            "R1": (-1, "tail"),
            "R2": (" ", "fine"),
            "R3": (math.inf, "post_13_plus_months"),
            "R4": (1.5, "two_way"),
            "R5": (0, "one_hop"),
            "R6": (1.01, "expert"),
            "R7": (-0.01, "tau_0_50"),
        }
        for code, (raw, level) in cases.items():
            with self.subTest(code=code), self.assertRaises(ValueError):
                DimensionValues({code: {"raw": raw, "level": level}})

    def test_each_dimension_rejects_an_unregistered_level(self) -> None:
        valid_raw = {"R1": 1, "R2": 1, "R3": 1, "R4": 1, "R5": 1, "R6": 0.5, "R7": 0.5}
        for code, raw in valid_raw.items():
            with self.subTest(code=code), self.assertRaises(ValueError):
                DimensionValues({code: {"raw": raw, "level": "invented"}})

    def test_r7_threshold_and_level_must_correspond(self) -> None:
        with self.assertRaisesRegex(ValueError, "one-to-one"):
            DimensionValues({"R7": {"raw": 0.50, "level": "tau_0_99"}})

    def test_r3_r4_r5_raw_values_must_match_deterministic_levels(self) -> None:
        mismatches = {
            "R3": {"raw": 3.1, "level": "post_0_3_months"},
            "R4": {"raw": 1, "level": "two_way"},
            "R5": {"raw": 4, "level": "three_hop"},
        }
        for code, supplied in mismatches.items():
            with self.subTest(code=code), self.assertRaisesRegex(
                ValueError, "deterministic mapping"
            ):
                DimensionValues({code: supplied})

    def test_crossed_groups_are_ordered_and_fail_on_missing_or_duplicate_axes(self) -> None:
        values = all_values()
        self.assertEqual(values.crossed_group(("R1", "R5", "R6")), "R1=tail|R5=four_plus_hop|R6=expert")
        self.assertEqual(crossed_group_label(values, ("R5", "R1"), use_levels=False), "R5=5|R1=8.0")
        for axes in ((), ("R1", "R1")):
            with self.subTest(axes=axes), self.assertRaises(ValueError):
                values.crossed_group(axes)
        with self.assertRaises(ValueError):
            DimensionValues({"R1": {"raw": 1, "level": "tail"}}).crossed_group(("R1", "R5"))


class DimensionDerivationTests(unittest.TestCase):
    def test_protocol_supplied_r1_and_r6_cut_points(self) -> None:
        self.assertEqual(r1_from_frequency(5, tail_max=10, middle_max=100).level, "tail")
        self.assertEqual(r1_from_frequency(50, tail_max=10, middle_max=100).level, "middle")
        self.assertEqual(r1_from_frequency(101, tail_max=10, middle_max=100).level, "head")
        self.assertEqual(r6_from_specificity(0.5, general_max=0.2, specialized_max=0.7).level, "specialized")
        with self.assertRaises(ValueError):
            r1_from_frequency(5, tail_max=100, middle_max=10)
        with self.assertRaises(ValueError):
            r6_from_specificity(0.5, general_max=0.8, specialized_max=0.7)

    def test_recency_from_months_and_dates(self) -> None:
        self.assertEqual(r3_from_relative_months(-1).level, "pre_cutoff")
        self.assertEqual(r3_from_dates("2026-02-01", "2026-01-01").level, "post_0_3_months")
        self.assertEqual(r3_from_dates("2026-07-01", "2026-01-01").level, "post_4_12_months")
        self.assertEqual(r3_from_dates("2027-02-01", "2026-01-01").level, "post_13_plus_months")
        with self.assertRaises(ValueError):
            r3_from_dates("not-a-date", "2026-01-01")

    def test_recency_band_boundaries_are_gap_free(self) -> None:
        expected = (
            (0.0, 'pre_cutoff'),
            (1e-9, 'post_0_3_months'),
            (3.0, 'post_0_3_months'),
            (3.0001, 'post_4_12_months'),
            (12.0, 'post_4_12_months'),
            (12.0001, 'post_13_plus_months'),
        )
        for months, level in expected:
            with self.subTest(months=months):
                self.assertEqual(r3_from_relative_months(months).level, level)

    def test_ambiguity_depth_and_policy_threshold_derivations(self) -> None:
        self.assertEqual(r4_from_interpretation_count(1).level, "unambiguous")
        self.assertEqual(r4_from_interpretation_count(3).level, "three_plus")
        self.assertEqual(r5_from_hop_count(2).level, "two_hop")
        self.assertEqual(r5_from_hop_count(3).level, "three_hop")
        self.assertEqual(r5_from_hop_count(5).level, "four_plus_hop")
        self.assertEqual(r7_from_threshold(0.95).level, "tau_0_95")
        with self.assertRaises(ValueError):
            r7_from_threshold(0.8)


class ExampleDimensionMetadataTests(unittest.TestCase):
    def test_legacy_example_constructor_and_round_trip_remain_unchanged(self) -> None:
        example = Example("legacy", "Question?", ("answer",), metadata={"hop_count": 2})
        self.assertEqual(len(example.dimension_values()), 0)
        self.assertEqual(Example.from_dict(example.to_dict()), example)

    def test_dimensions_merge_into_metadata_and_serialize(self) -> None:
        original = Example("q1", "Question?", ("answer",), metadata={"source": "audited"})
        enriched = original.with_dimension_values(all_values())
        self.assertNotIn(DIMENSIONS_METADATA_KEY, original.metadata)
        self.assertEqual(enriched.metadata["source"], "audited")
        restored = Example.from_dict(enriched.to_dict())
        self.assertEqual(restored.dimension_values().to_dict(), all_values().to_dict())
        with self.assertRaises(ValueError):
            enriched.with_dimension_values(all_values())

    def test_malformed_canonical_dimension_metadata_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            Example("q", "Question?", ("answer",), metadata={DIMENSIONS_METADATA_KEY: []})
        with self.assertRaises(ValueError):
            Example(
                "q",
                "Question?",
                ("answer",),
                metadata={DIMENSIONS_METADATA_KEY: {"R7": {"raw": 2, "level": "tau_0_90"}}},
            )


if __name__ == "__main__":
    unittest.main()
