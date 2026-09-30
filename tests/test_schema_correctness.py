"""Record validation and deterministic short-answer scoring tests."""

from __future__ import annotations

import json
import math
import unittest

from calibread.correctness import exact_match, normalize_answer, score_prediction
from calibread.dimensions import DimensionValues, r3_from_dates
from calibread.manifest import RunManifest
from calibread.schema import (
    Example,
    GenerationRecord,
    ModelConditionRecord,
    Prediction,
    ReadResultRecord,
    WorkloadRecord,
    condition_table_hash,
    decide_generation,
    validate_pipeline_linkage,
)


R4_HASH = "4" * 64
R5_HASH = "5" * 64
R1_BIN_HASH = "1" * 64
R3_BIN_HASH = "3" * 64


def make_workload(**overrides: object) -> WorkloadRecord:
    values: dict[str, object] = {
        "example_id": "q-ambiguous-chain",
        "question": "Which Mercury is meant and where was it formed?",
        "accepted_answers": ("planet", "element"),
        "track": "finite_label_certified",
        "dimensions": DimensionValues(
            {
                "R2": {"raw": "entity", "level": "coarse"},
                "R4": {"raw": 2, "level": "two_way"},
                "R5": {"raw": 2, "level": "two_hop"},
                "R6": {"raw": 0.5, "level": "specialized"},
            }
        ),
        "r4_annotation_hash": R4_HASH,
        "r5_chain_spec_hash": R5_HASH,
        "candidate_universe": ("planet", "element", "newspaper"),
        "interpretation_answers": {
            "planet-reading": ("planet",),
            "element-reading": ("element",),
        },
        "chain_id": "chain-7",
        "constituent_example_ids": ("q-source-1", "q-source-2"),
        "domain_name": "astronomy",
        "allowed_actions": ("answer", "set", "abstain"),
        "missing_reasons": {
            "R1": "model_condition_record",
            "R3": "model_condition_record",
        },
        "provenance": {
            "source_revision": "dataset-v2",
            "extraction": {"pages": [1, 2]},
        },
    }
    values.update(overrides)
    return WorkloadRecord(**values)  # type: ignore[arg-type]


def make_condition(**overrides: object) -> ModelConditionRecord:
    event_date = str(overrides.get("r3_event_date", "2025-01-01"))
    cutoff_date = str(overrides.get("r3_model_cutoff_date", "2025-07-01"))
    r3 = r3_from_dates(event_date, cutoff_date)
    values: dict[str, object] = {
        "example_id": "q-ambiguous-chain",
        "model_snapshot_id": "org/model@immutable-revision",
        "condition_version": "p03-condition-v1",
        "dimensions": DimensionValues(
            {
                "R1": {"raw": 128, "level": "middle"},
                "R3": {"raw": r3.raw, "level": r3.level},
            }
        ),
        "r1_frequency_source": "audited-corpus-counter-v1",
        "r1_corpus_snapshot_id": "corpus@immutable-revision",
        "r1_exposure_unit": "estimated occurrences",
        "r1_value_kind": "proxy",
        "r1_tail_max": 50,
        "r1_middle_max": 500,
        "r1_bin_rule_hash": R1_BIN_HASH,
        "r3_event_date": event_date,
        "r3_model_cutoff_date": cutoff_date,
        "r3_cutoff_source": "model-card-revision-1",
        "r3_cutoff_uncertainty": "day-level",
        "r3_value_kind": "exact",
        "r3_bin_rule_hash": R3_BIN_HASH,
        "metadata": {"audit": {"reviewers": ["a", "b"]}},
    }
    values.update(overrides)
    return ModelConditionRecord(**values)  # type: ignore[arg-type]


def make_generation(
    condition: ModelConditionRecord | None = None, **overrides: object
) -> GenerationRecord:
    condition = condition or make_condition()
    values: dict[str, object] = {
        "generation_id": "g1",
        "run_id": "run1",
        "example_id": condition.example_id,
        "model_snapshot_id": condition.model_snapshot_id,
        "condition_hash": condition.condition_hash(),
        "track": "finite_label_certified",
        "raw_text": "planet",
        "candidates": ("planet",),
        "score": 0.93,
        "score_kind": "probability",
        "score_source": "temperature_scaled_sequence_score",
        "calibrator_id": "temp-v1",
        "metadata": {"model_revision": "rev-1"},
    }
    values.update(overrides)
    return GenerationRecord(**values)  # type: ignore[arg-type]


def make_result(
    generation: GenerationRecord | None = None, **overrides: object
) -> ReadResultRecord:
    generation = generation or make_generation()
    values: dict[str, object] = {
        "run_id": generation.run_id,
        "generation_id": generation.generation_id,
        "example_id": generation.example_id,
        "model_snapshot_id": generation.model_snapshot_id,
        "condition_hash": generation.condition_hash,
        "track": generation.track,
        "score": generation.score,
        "score_kind": generation.score_kind,
        "score_source": generation.score_source,
        "calibrator_id": generation.calibrator_id,
        "threshold": 0.9,
        "policy_level": "tau_0_90",
        "action": "answer",
        "reason": "threshold_accepted",
        "ambiguity_complete": True,
        "correctness_rule": "normalized-alias-v1",
        "candidates": generation.candidates,
        "answer": generation.candidates[0],
        "correct": True,
        "normalization_contract": generation.normalization_contract,
    }
    values.update(overrides)
    return ReadResultRecord(**values)  # type: ignore[arg-type]


def make_linked_manifest(
    condition: ModelConditionRecord,
    conditions: tuple[ModelConditionRecord, ...],
) -> RunManifest:
    return RunManifest(
        run_id="run1",
        model_id="org/model",
        model_revision="immutable-revision",
        model_snapshot_id=condition.model_snapshot_id,
        condition_table_hash=condition_table_hash(conditions),
        dataset_id="dataset/name",
        dataset_revision="v1",
        prompt_template="Q: {question}\nA:",
        correctness_rule="normalized-alias-v1",
        calibration_ids_hash="a" * 64,
        test_ids_hash="b" * 64,
        code_revision="deadbeef",
        seed=7,
        decoding={"temperature": 0.0},
        hardware={"device": "cpu"},
        evaluation_track="finite_label_certified",
    )


class SchemaTests(unittest.TestCase):
    def test_example_json_shape_round_trip(self) -> None:
        example = Example(
            example_id="q-1",
            question="Which city?",
            accepted_answers=("München", "Munich"),
            group="tail-hop2",
            split="test",
            metadata={"entity_id": "Q1726", "hop_count": 2},
        )
        payload = example.to_dict()
        self.assertEqual(payload["accepted_answers"], ["München", "Munich"])
        self.assertEqual(Example.from_dict(payload), example)

    def test_prediction_round_trip_and_confidence_validation(self) -> None:
        prediction = Prediction("q-1", "Munich", 0.75)
        self.assertEqual(Prediction.from_dict(prediction.to_dict()), prediction)
        for confidence in (-0.01, 1.01, math.nan):
            with self.subTest(confidence=confidence), self.assertRaises(ValueError):
                Prediction("q-1", "answer", confidence)
        declared = Prediction(
            "q-1",
            "Munich",
            0.75,
            score_kind="probability",
            score_source="temperature_scaled",
            calibrator_id="temp-v1",
        )
        self.assertEqual(Prediction.from_dict(declared.to_dict()), declared)
        with self.assertRaisesRegex(ValueError, "calibrator_id"):
            Prediction(
                "q-1",
                "Munich",
                0.75,
                score_kind="probability",
                score_source="temperature_scaled",
                calibrator_id=None,
            )

    def test_required_example_fields_are_rejected_when_blank(self) -> None:
        with self.assertRaises(ValueError):
            Example("", "question", ("answer",))
        with self.assertRaises(ValueError):
            Example("q", " ", ("answer",))
        with self.assertRaises(ValueError):
            Example("q", "question", ())

    def test_answer_collection_cannot_be_a_bare_string(self) -> None:
        with self.assertRaises(ValueError):
            Example("q", "Capital?", "Paris")  # type: ignore[arg-type]

    def test_model_independent_workload_round_trip_and_immutability(self) -> None:
        provenance = {
            "source_revision": "dataset-v2",
            "extraction": {"pages": [1, 2]},
        }
        record = make_workload(provenance=provenance)
        self.assertEqual(set(record.dimensions.entries), {"R2", "R4", "R5", "R6"})
        self.assertEqual(
            dict(record.missing_reasons),
            {"R1": "model_condition_record", "R3": "model_condition_record"},
        )
        self.assertEqual(WorkloadRecord.from_dict(record.to_dict()), record)
        provenance["extraction"]["pages"].append(99)  # type: ignore[index,union-attr]
        self.assertEqual(
            record.to_dict()["provenance"],
            {
                "source_revision": "dataset-v2",
                "extraction": {"pages": [1, 2]},
            },
        )
        with self.assertRaises(TypeError):
            record.provenance["extraction"]["new"] = True  # type: ignore[index,union-attr]
        json.dumps(record.to_dict())

    def test_workload_candidates_cover_all_audited_answers(self) -> None:
        with self.assertRaisesRegex(ValueError, "every accepted answer"):
            make_workload(candidate_universe=("planet", "newspaper"))
        payload = make_workload().to_dict()
        payload["candidate_universe"] = "planet"
        with self.assertRaisesRegex(ValueError, "list or tuple"):
            WorkloadRecord.from_dict(payload)

    def test_workload_r4_interpretation_invariants(self) -> None:
        with self.assertRaisesRegex(ValueError, "count must equal"):
            make_workload(
                interpretation_answers={"planet-reading": ("planet", "element")}
            )
        with self.assertRaisesRegex(ValueError, "union must equal"):
            make_workload(
                interpretation_answers={
                    "planet-reading": ("planet",),
                    "second-reading": ("planet",),
                }
            )

    def test_workload_r5_chain_and_r6_domain_invariants(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires chain_id"):
            make_workload(chain_id=None)
        with self.assertRaisesRegex(ValueError, "must be unique"):
            make_workload(
                constituent_example_ids=("q-source-1", "q-source-1")
            )
        with self.assertRaisesRegex(ValueError, "must not contain"):
            make_workload(
                constituent_example_ids=(
                    "q-ambiguous-chain",
                    "q-source-2",
                )
            )
        with self.assertRaisesRegex(ValueError, "count must equal"):
            make_workload(constituent_example_ids=("q-source-1",))
        with self.assertRaisesRegex(ValueError, "requires domain_name"):
            make_workload(domain_name=None)

    def test_workload_dimension_routing_and_audit_hashes_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly R2"):
            make_workload(
                dimensions=DimensionValues(
                    {
                        "R2": {"raw": "entity", "level": "coarse"},
                        "R4": {"raw": 2, "level": "two_way"},
                        "R5": {"raw": 2, "level": "two_hop"},
                    }
                )
            )
        with self.assertRaisesRegex(ValueError, "route R1 and R3"):
            make_workload(missing_reasons={"R1": "unknown", "R3": "unknown"})
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            make_workload(r4_annotation_hash="not-a-hash")

    def test_model_condition_round_trip_hashes_and_table_are_canonical(self) -> None:
        condition = make_condition()
        restored = ModelConditionRecord.from_dict(condition.to_dict())
        self.assertEqual(restored, condition)
        self.assertEqual(restored.condition_hash(), condition.condition_hash())
        self.assertRegex(condition.condition_hash(), r"^[0-9a-f]{64}$")
        second = make_condition(example_id="q-second")
        self.assertEqual(
            condition_table_hash((condition, second)),
            condition_table_hash((second, condition)),
        )
        with self.assertRaisesRegex(ValueError, "duplicate"):
            condition_table_hash((condition, condition))

    def test_model_condition_r1_r3_and_exact_proxy_claims_fail_closed(self) -> None:
        condition = make_condition()
        mismatched_r1 = DimensionValues(
            {
                "R1": {"raw": 128, "level": "tail"},
                "R3": condition.dimensions["R3"],
            }
        )
        with self.assertRaisesRegex(ValueError, "frozen condition cutpoints"):
            make_condition(dimensions=mismatched_r1)
        mismatched_r3 = DimensionValues(
            {
                "R1": condition.dimensions["R1"],
                "R3": {
                    "raw": float(condition.dimensions["R3"].raw) + 0.1,
                    "level": condition.dimensions["R3"].level,
                },
            }
        )
        with self.assertRaisesRegex(ValueError, "within tolerance"):
            make_condition(dimensions=mismatched_r3)
        with self.assertRaisesRegex(ValueError, "exact or proxy"):
            make_condition(r1_value_kind="estimated")
        with self.assertRaisesRegex(ValueError, "exactly R1 and R3"):
            make_condition(dimensions=DimensionValues({"R1": condition.dimensions["R1"]}))

    def test_generation_and_r7_result_round_trip_with_condition_link(self) -> None:
        condition = make_condition()
        generation = make_generation(condition)
        self.assertTrue(generation.is_probability)
        self.assertEqual(GenerationRecord.from_dict(generation.to_dict()), generation)
        raw_generation = make_generation(
            condition,
            generation_id="g-raw",
            track="open_ended_stress",
            score=-12.5,
            score_kind="raw",
            score_source="sequence_log_probability",
            calibrator_id=None,
        )
        self.assertFalse(raw_generation.is_probability)
        self.assertEqual(
            GenerationRecord.from_dict(raw_generation.to_dict()), raw_generation
        )
        result = make_result(generation)
        self.assertEqual(ReadResultRecord.from_dict(result.to_dict()), result)
        with self.assertRaisesRegex(ValueError, "ambiguity"):
            make_result(generation, ambiguity_complete=False)
        with self.assertRaisesRegex(ValueError, "frozen R7"):
            make_result(generation, policy_level="tau_0_95")
        raw_policy_generation = make_generation(
            condition,
            score=0.8,
            score_kind="raw",
            score_source="minmax_sequence_score",
            calibrator_id=None,
            normalization_contract="calibration-minmax-v1",
        )
        self.assertEqual(
            make_result(raw_policy_generation).normalization_contract,
            "calibration-minmax-v1",
        )

    def test_typed_decision_derives_ambiguity_from_all_interpretations(self) -> None:
        workload = make_workload()
        condition = make_condition()
        singleton_generation = make_generation(condition)
        singleton = decide_generation(
            workload,
            singleton_generation,
            0.9,
            correctness_rule="normalized-alias-v1",
            correctness_scorer=exact_match,
        )
        self.assertEqual(singleton.action, "abstain")
        self.assertFalse(singleton.ambiguity_complete)
        self.assertIsNone(singleton.correct)

        complete_generation = make_generation(
            condition,
            raw_text="planet | element",
            candidates=("planet", "element"),
        )
        complete = decide_generation(
            workload,
            complete_generation,
            0.9,
            correctness_rule="normalized-alias-v1",
            correctness_scorer=exact_match,
        )
        self.assertEqual(complete.action, "set")
        self.assertTrue(complete.ambiguity_complete)
        self.assertTrue(complete.correct)

    def test_shared_canonical_answer_can_make_ambiguous_singleton_complete(self) -> None:
        workload = make_workload(
            accepted_answers=("planet",),
            candidate_universe=("planet", "newspaper"),
            interpretation_answers={
                "astronomy-reading": ("planet",),
                "mythology-reading": ("planet",),
            },
        )
        decision = decide_generation(
            workload,
            make_generation(),
            0.9,
            correctness_rule="normalized-alias-v1",
            correctness_scorer=exact_match,
        )
        self.assertEqual(decision.action, "answer")
        self.assertTrue(decision.ambiguity_complete)
        self.assertTrue(decision.correct)

    def test_pipeline_linkage_validator_covers_manifest_and_decision(self) -> None:
        workload = make_workload()
        condition = make_condition()
        generation = make_generation(
            condition,
            raw_text="planet | element",
            candidates=("planet", "element"),
        )
        decision = decide_generation(
            workload,
            generation,
            0.9,
            correctness_rule="normalized-alias-v1",
            correctness_scorer=exact_match,
        )
        conditions = (condition,)
        manifest = make_linked_manifest(condition, conditions)
        validate_pipeline_linkage(
            workload,
            condition,
            generation,
            manifest,
            conditions,
            decision=decision,
            correctness_scorer=exact_match,
        )
        with self.assertRaisesRegex(ValueError, "explicit correctness_scorer"):
            validate_pipeline_linkage(
                workload,
                condition,
                generation,
                manifest,
                conditions,
                decision=decision,
            )
        wrong_generation = GenerationRecord.from_dict(
            {**generation.to_dict(), "condition_hash": "f" * 64}
        )
        with self.assertRaisesRegex(ValueError, "condition_hash"):
            validate_pipeline_linkage(
                workload,
                condition,
                wrong_generation,
                manifest,
                conditions,
            )

        out_of_universe = make_generation(
            condition,
            candidates=("planet", "moon"),
        )
        with self.assertRaisesRegex(ValueError, "candidate_universe"):
            validate_pipeline_linkage(
                workload,
                condition,
                out_of_universe,
                manifest,
                conditions,
            )

        dishonest_correctness = ReadResultRecord.from_dict(
            {**decision.to_dict(), "correct": False}
        )
        with self.assertRaisesRegex(ValueError, "recomputed"):
            validate_pipeline_linkage(
                workload,
                condition,
                generation,
                manifest,
                conditions,
                decision=dishonest_correctness,
                correctness_scorer=exact_match,
            )

        dishonest_ambiguity = ReadResultRecord.from_dict(
            {**decision.to_dict(), "ambiguity_complete": False}
        )
        with self.assertRaisesRegex(ValueError, "audited workload"):
            validate_pipeline_linkage(
                workload,
                condition,
                generation,
                manifest,
                conditions,
                decision=dishonest_ambiguity,
                correctness_scorer=exact_match,
            )

        restricted_actions = ReadResultRecord.from_dict(
            {
                **decision.to_dict(),
                "allowed_actions": ["set", "abstain"],
            }
        )
        with self.assertRaisesRegex(ValueError, "allowed_actions"):
            validate_pipeline_linkage(
                workload,
                condition,
                generation,
                manifest,
                conditions,
                decision=restricted_actions,
                correctness_scorer=exact_match,
            )

        changed_score = ReadResultRecord.from_dict(
            {**decision.to_dict(), "score": 0.92}
        )
        with self.assertRaisesRegex(ValueError, "preserve generation"):
            validate_pipeline_linkage(
                workload,
                condition,
                generation,
                manifest,
                conditions,
                decision=changed_score,
                correctness_scorer=exact_match,
            )


class CorrectnessTests(unittest.TestCase):
    def test_normalization_handles_unicode_articles_and_punctuation(self) -> None:
        self.assertEqual(normalize_answer("  The MÜNCHEN! "), "münchen")

    def test_exact_match_accepts_any_declared_alias(self) -> None:
        self.assertTrue(exact_match("the USA.", ["United States", "USA"]))
        self.assertFalse(exact_match("Canada", ["United States", "USA"]))

    def test_scoring_requires_aligned_ids(self) -> None:
        example = Example("q-1", "Country?", ("United States", "USA"))
        self.assertEqual(
            score_prediction(Prediction("q-1", "the USA", 0.8), example), 1
        )
        with self.assertRaises(ValueError):
            score_prediction(Prediction("q-2", "USA", 0.8), example)


if __name__ == "__main__":
    unittest.main()
