"""Determinism and fail-closed lineage tests for split assignment."""

from __future__ import annotations

from collections import Counter
import unittest

from calibread.leakage import normalized_question_hash
from calibread.schema import Example
from calibread.splits import assign_splits, deterministic_split


def partial_example(example_id: str, entity_id: str, **metadata: object) -> Example:
    return Example(
        example_id=example_id,
        question=f"Question {example_id}?",
        accepted_answers=("answer",),
        metadata={"entity_id": entity_id, **metadata},
    )


def complete_example(
    example_id: str,
    entity_id: str,
    *,
    question: str | None = None,
    **metadata: object,
) -> Example:
    question = question or f"Question {example_id}?"
    lineage: dict[str, object] = {
        "entity_id": entity_id,
        "chain_id": f"chain-{example_id}",
        "template_id": f"template-{example_id}",
        "source_fact_id": f"fact-{example_id}",
        "question_hash": normalized_question_hash(question),
    }
    lineage.update(metadata)
    return Example(
        example_id=example_id,
        question=question,
        accepted_answers=("answer",),
        metadata=lineage,
    )


class DeterministicSplitTests(unittest.TestCase):
    def test_same_key_and_seed_always_have_same_split(self) -> None:
        first = deterministic_split("entity-Q1", seed=17)
        second = deterministic_split("entity-Q1", seed=17)
        self.assertEqual(first, second)
        self.assertIn(first, {"development", "calibration", "test"})

    def test_legacy_single_key_requires_explicit_mode(self) -> None:
        examples = [
            partial_example("q1", "e1"),
            partial_example("q2", "e1"),
            partial_example("q3", "e2"),
        ]
        with self.assertRaisesRegex(ValueError, "requires legacy_single_key_mode"):
            assign_splits(examples, seed=3, key_field="entity_id")
        forward = assign_splits(
            examples,
            seed=3,
            key_field="entity_id",
            legacy_single_key_mode=True,
        )
        reverse = assign_splits(
            list(reversed(examples)),
            seed=3,
            key_field="entity_id",
            legacy_single_key_mode=True,
        )
        self.assertEqual(
            {item.example_id: item.split for item in forward},
            {item.example_id: item.split for item in reverse},
        )
        self.assertTrue(all(item.split == "unassigned" for item in examples))

    def test_multiple_identifiers_form_transitive_connected_components(self) -> None:
        examples = [
            complete_example("q1", "e1", chain_id="c1", template_id="t1"),
            complete_example("q2", "e2", chain_id="c1", template_id="t2"),
            complete_example("q3", "e3", chain_id="c3", template_id="t2"),
            complete_example("q4", "e4", chain_id="c4", template_id="t4"),
        ]
        assigned = assign_splits(examples, seed=11)
        connected = {item.split for item in assigned[:3]}
        self.assertEqual(len(connected), 1)

    def test_sequence_lineage_values_are_connected(self) -> None:
        examples = [
            partial_example("q1", "e1", source_fact_id=["f1", "f2"]),
            partial_example("q2", "e2", source_fact_id=["f2", "f3"]),
        ]
        assigned = assign_splits(
            examples, disjoint_keys=("entity_id", "source_fact_id")
        )
        self.assertEqual(assigned[0].split, assigned[1].split)

    def test_question_hash_is_required_verified_and_disjoint(self) -> None:
        examples = [
            complete_example(
                "q1", "e1", question="  WHO   is München? "
            ),
            complete_example(
                "q2", "e2", question="who is münchen?"
            ),
        ]
        assigned = assign_splits(examples)
        self.assertEqual(assigned[0].split, assigned[1].split)

        wrong_hash = complete_example(
            "bad", "e3", question_hash="0" * 64
        )
        with self.assertRaisesRegex(ValueError, "does not match"):
            assign_splits([wrong_hash])

    def test_valid_per_key_exemption_allows_genuinely_absent_lineage(self) -> None:
        item = complete_example("q1", "e1")
        metadata = dict(item.metadata)
        del metadata["chain_id"]
        metadata["lineage_exemptions"] = {
            "chain_id": {
                "reason_code": "not_applicable_by_construction",
                "justification": "Atomic one-hop item has no evidence chain.",
            }
        }
        exempted = Example(
            item.example_id,
            item.question,
            item.accepted_answers,
            metadata=metadata,
        )
        assigned = assign_splits([exempted])
        self.assertIn(
            assigned[0].split, {"development", "calibration", "test"}
        )

    def test_unexplained_or_invalid_exemptions_fail_closed(self) -> None:
        incomplete = complete_example("q1", "e1")
        metadata = dict(incomplete.metadata)
        del metadata["chain_id"]
        missing = Example(
            incomplete.example_id,
            incomplete.question,
            incomplete.accepted_answers,
            metadata=metadata,
        )
        with self.assertRaisesRegex(ValueError, "without an explicit"):
            assign_splits([missing])

        metadata["lineage_exemptions"] = {
            "chain_id": {
                "reason_code": "unknown",
                "justification": "There is no chain for this item.",
            }
        }
        bad_reason = Example(
            "q2", incomplete.question, ("answer",), metadata=metadata
        )
        with self.assertRaisesRegex(ValueError, "reason_code"):
            assign_splits([bad_reason])

        present = complete_example(
            "q3",
            "e3",
            lineage_exemptions={
                "chain_id": {
                    "reason_code": "not_applicable_by_construction",
                    "justification": "Contradictory exemption should be rejected.",
                }
            },
        )
        with self.assertRaisesRegex(ValueError, "both value and exemption"):
            assign_splits([present])

        no_hash = complete_example("q4", "e4")
        metadata = dict(no_hash.metadata)
        del metadata["question_hash"]
        metadata["lineage_exemptions"] = {
            "question_hash": {
                "reason_code": "not_defined_by_source_schema",
                "justification": "Source did not provide a stored hash.",
            }
        }
        forbidden = Example(
            no_hash.example_id,
            no_hash.question,
            no_hash.accepted_answers,
            metadata=metadata,
        )
        with self.assertRaisesRegex(ValueError, "cannot be exempted"):
            assign_splits([forbidden])

    def test_marginal_strata_are_deterministic_and_balanced(self) -> None:
        examples = [
            partial_example(
                f"q{i}", f"e{i}", domain=("a" if i < 30 else "b")
            )
            for i in range(60)
        ]
        forward = assign_splits(
            examples,
            seed=23,
            disjoint_keys=("entity_id",),
            strata_keys=("domain",),
        )
        reverse = assign_splits(
            list(reversed(examples)),
            seed=23,
            disjoint_keys=("entity_id",),
            strata_keys=("domain",),
        )
        self.assertEqual(
            {item.example_id: item.split for item in forward},
            {item.example_id: item.split for item in reverse},
        )
        for domain in ("a", "b"):
            counts = Counter(
                item.split
                for item in forward
                if item.metadata["domain"] == domain
            )
            self.assertLessEqual(abs(counts["development"] - 6), 1)
            self.assertLessEqual(abs(counts["calibration"] - 9), 1)
            self.assertLessEqual(abs(counts["test"] - 15), 1)

    def test_precomputed_interaction_cells_can_be_balanced_directly(self) -> None:
        examples = [
            partial_example(
                f"q{i}",
                f"e{i}",
                r1_x_r5_cell=(
                    "tail|four_plus_hop" if i < 30 else "head|one_hop"
                ),
            )
            for i in range(60)
        ]
        assigned = assign_splits(
            examples,
            seed=31,
            disjoint_keys=("entity_id",),
            strata_keys=("r1_x_r5_cell",),
        )
        for cell in ("tail|four_plus_hop", "head|one_hop"):
            counts = Counter(
                item.split
                for item in assigned
                if item.metadata["r1_x_r5_cell"] == cell
            )
            self.assertEqual(
                [
                    counts["development"],
                    counts["calibration"],
                    counts["test"],
                ],
                [6, 9, 15],
            )

    def test_invalid_inputs_fail(self) -> None:
        with self.assertRaises(ValueError):
            deterministic_split("key", fractions=(0.5, 0.4, 0.2))
        with self.assertRaises(ValueError):
            deterministic_split("")
        with self.assertRaises(KeyError):
            assign_splits(
                [partial_example("q1", "e1")],
                key_field="relation_id",
                legacy_single_key_mode=True,
            )
        with self.assertRaisesRegex(ValueError, "accepts key_field"):
            assign_splits(
                [partial_example("q1", "e1")],
                disjoint_keys=("entity_id",),
                legacy_single_key_mode=True,
            )
        with self.assertRaisesRegex(ValueError, "must not overlap"):
            assign_splits(
                [partial_example("q1", "e1")],
                disjoint_keys=("entity_id",),
                strata_keys=("entity_id",),
            )


if __name__ == "__main__":
    unittest.main()
