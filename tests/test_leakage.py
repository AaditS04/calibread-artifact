"""Fail-closed tests for lineage completeness and split contamination."""

from __future__ import annotations

import unittest

from calibread.leakage import (
    DEFAULT_DISJOINT_KEYS,
    assert_no_split_leakage,
    find_split_leakage,
    normalized_question_hash,
    validated_lineage_identifiers,
)
from calibread.schema import Example


def item(
    identifier: str,
    question: str,
    split: str,
    **metadata: object,
) -> Example:
    lineage: dict[str, object] = {
        "entity_id": f"entity-{identifier}",
        "chain_id": f"chain-{identifier}",
        "template_id": f"template-{identifier}",
        "source_fact_id": f"fact-{identifier}",
        "question_hash": normalized_question_hash(question),
    }
    lineage.update(metadata)
    return Example(
        identifier,
        question,
        ("answer",),
        split=split,
        metadata=lineage,
    )


class LeakageTests(unittest.TestCase):
    def test_question_hash_normalizes_unicode_case_and_whitespace(self) -> None:
        self.assertEqual(
            normalized_question_hash("  WHO   is München? "),
            normalized_question_hash("who is münchen?"),
        )

    def test_question_variant_across_splits_is_leakage(self) -> None:
        examples = [
            item("q1", "Who   is Ada?", "calibration"),
            item("q2", "  who is ada? ", "test"),
        ]
        findings = find_split_leakage(examples)
        self.assertIn("question_hash", findings)
        with self.assertRaisesRegex(ValueError, "split leakage"):
            assert_no_split_leakage(examples)

    def test_entity_and_chain_overlap_across_splits_are_leakage(self) -> None:
        examples = [
            item(
                "q1",
                "First question?",
                "calibration",
                entity_id="E1",
                chain_id="C1",
            ),
            item(
                "q2",
                "Second question?",
                "test",
                entity_id="E1",
                chain_id="C1",
            ),
        ]
        findings = find_split_leakage(examples)
        self.assertEqual(findings["entity_id"], ["E1"])
        self.assertEqual(findings["chain_id"], ["C1"])

    def test_source_fact_and_multivalue_identifiers_are_protected(self) -> None:
        examples = [
            item(
                "q1",
                "First question?",
                "development",
                source_fact_id="F1",
                constituent_ids=["A", "B"],
            ),
            item(
                "q2",
                "Second question?",
                "test",
                source_fact_id="F1",
                constituent_ids=["B", "C"],
            ),
        ]
        findings = find_split_leakage(
            examples,
            disjoint_keys=("source_fact_id", "constituent_ids"),
        )
        self.assertEqual(findings["source_fact_id"], ["F1"])
        self.assertEqual(findings["constituent_ids"], ["B"])

    def test_every_declared_key_requires_value_or_valid_exemption(self) -> None:
        baseline = item("q1", "Question?", "test")
        for key in DEFAULT_DISJOINT_KEYS:
            metadata = dict(baseline.metadata)
            del metadata[key]
            incomplete = Example(
                baseline.example_id,
                baseline.question,
                baseline.accepted_answers,
                split=baseline.split,
                metadata=metadata,
            )
            with self.subTest(key=key), self.assertRaisesRegex(
                ValueError, f"missing lineage key {key!r}"
            ):
                find_split_leakage([incomplete])

    def test_blank_empty_and_nonscalar_lineage_values_fail(self) -> None:
        for value in ("", "   ", [], [" "], {"nested": "not-an-id"}, True):
            bad = item(
                "q1",
                "Question?",
                "test",
                entity_id=value,
            )
            with self.subTest(value=value), self.assertRaises(ValueError):
                find_split_leakage(
                    [bad],
                    disjoint_keys=("entity_id",),
                )

    def test_valid_exemption_is_per_key_audited_and_not_a_join_token(self) -> None:
        baseline = item("q1", "Question one?", "test")
        metadata = dict(baseline.metadata)
        del metadata["chain_id"]
        metadata["lineage_exemptions"] = {
            "chain_id": {
                "reason_code": "not_applicable_by_construction",
                "justification": "Atomic record was constructed without an evidence chain.",
            }
        }
        exempted = Example(
            baseline.example_id,
            baseline.question,
            baseline.accepted_answers,
            split=baseline.split,
            metadata=metadata,
        )
        identifiers = validated_lineage_identifiers(exempted)
        self.assertNotIn("chain_id", identifiers)
        self.assertEqual(find_split_leakage([exempted]), {})

    def test_malformed_redundant_and_nonexemptable_exemptions_fail(self) -> None:
        baseline = item("q1", "Question?", "test")

        redundant = item(
            "q2",
            "Another question?",
            "test",
            lineage_exemptions={
                "chain_id": {
                    "reason_code": "not_applicable_by_construction",
                    "justification": "This conflicts with the supplied chain identifier.",
                }
            },
        )
        with self.assertRaisesRegex(ValueError, "both value and exemption"):
            find_split_leakage([redundant])

        metadata = dict(baseline.metadata)
        del metadata["chain_id"]
        metadata["lineage_exemptions"] = {
            "chain_id": {
                "reason_code": "not_applicable_by_construction",
                "justification": "n/a",
            }
        }
        placeholder = Example(
            baseline.example_id,
            baseline.question,
            baseline.accepted_answers,
            split=baseline.split,
            metadata=metadata,
        )
        with self.assertRaisesRegex(ValueError, "substantive"):
            find_split_leakage([placeholder])

        metadata = dict(baseline.metadata)
        del metadata["question_hash"]
        metadata["lineage_exemptions"] = {
            "question_hash": {
                "reason_code": "not_defined_by_source_schema",
                "justification": "The source omitted a precomputed question hash.",
            }
        }
        forbidden = Example(
            baseline.example_id,
            baseline.question,
            baseline.accepted_answers,
            split=baseline.split,
            metadata=metadata,
        )
        with self.assertRaisesRegex(ValueError, "cannot be exempted"):
            find_split_leakage([forbidden])

    def test_supplied_question_hash_must_match_canonical_normalization(self) -> None:
        bad = item(
            "q1",
            "Question?",
            "test",
            question_hash="f" * 64,
        )
        with self.assertRaisesRegex(ValueError, "does not match"):
            find_split_leakage([bad])

    def test_duplicate_ids_fail_even_within_one_split(self) -> None:
        findings = find_split_leakage(
            [
                item("same", "Question one?", "test"),
                item("same", "Question two?", "test"),
            ]
        )
        self.assertEqual(findings["example_id"], ["same"])

    def test_same_split_reuse_is_allowed(self) -> None:
        examples = [
            item("q1", "Repeated?", "test", entity_id="E1"),
            item("q2", " repeated? ", "test", entity_id="E1"),
        ]
        self.assertEqual(find_split_leakage(examples), {})
        self.assertIsNone(assert_no_split_leakage(examples))

    def test_old_skip_missing_behavior_requires_explicit_legacy_mode(self) -> None:
        sparse = [
            Example(
                "q1",
                "Question one?",
                ("answer",),
                split="development",
                metadata={"entity_id": "E1"},
            ),
            Example(
                "q2",
                "Question two?",
                ("answer",),
                split="test",
                metadata={"entity_id": "E2"},
            ),
        ]
        with self.assertRaisesRegex(ValueError, "missing lineage key"):
            find_split_leakage(sparse)
        self.assertEqual(
            find_split_leakage(
                sparse,
                legacy_permissive_missing_keys=True,
            ),
            {},
        )
        with self.assertRaisesRegex(ValueError, "available only"):
            find_split_leakage(sparse, metadata_keys=("entity_id",))


if __name__ == "__main__":
    unittest.main()
