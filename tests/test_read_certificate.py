"""Strict construction and claim-boundary tests for ReadCertificate v1."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from calibread.certificate import (
    REQUIRED_CERTIFICATE_ASSUMPTIONS,
    ReadCertificate,
    build_read_certificate,
)
from calibread.correctness import exact_match
from calibread.dimensions import DimensionValues, r3_from_dates
from calibread.io import read_jsonl
from calibread.manifest import RunManifest
from calibread.schema import (
    GenerationRecord,
    ModelConditionRecord,
    WorkloadRecord,
    condition_table_hash,
    decide_generation,
)


def assumption_status(**overrides: bool) -> dict[str, bool]:
    values = {name: True for name in REQUIRED_CERTIFICATE_ASSUMPTIONS}
    values.update(overrides)
    return values


def make_records(
    *,
    track: str = "finite_label_certified",
    supported: bool = True,
) -> tuple[
    WorkloadRecord,
    ModelConditionRecord,
    GenerationRecord,
    object,
    RunManifest,
]:
    workload = WorkloadRecord(
        example_id="q-certificate",
        question="Which Mercury interpretation is intended?",
        accepted_answers=("planet", "element"),
        track=track,  # type: ignore[arg-type]
        dimensions=DimensionValues(
            {
                "R2": {"raw": "entity", "level": "coarse"},
                "R4": {"raw": 2, "level": "two_way"},
                "R5": {"raw": 2, "level": "two_hop"},
                "R6": {"raw": 0.5, "level": "specialized"},
            }
        ),
        r4_annotation_hash="4" * 64,
        r5_chain_spec_hash="5" * 64,
        candidate_universe=(
            ("planet", "element", "newspaper")
            if track == "finite_label_certified"
            else ()
        ),
        interpretation_answers={
            "planet-reading": ("planet",),
            "element-reading": ("element",),
        },
        chain_id="chain-7",
        constituent_example_ids=("q-source-1", "q-source-2"),
        domain_name="astronomy",
        allowed_actions=("answer", "set", "abstain"),
        missing_reasons={
            "R1": "model_condition_record",
            "R3": "model_condition_record",
        },
        provenance={"source_revision": "dataset-v2"},
    )
    r3 = r3_from_dates("2025-01-01", "2025-07-01")
    condition = ModelConditionRecord(
        example_id=workload.example_id,
        model_snapshot_id="org/model@immutable-revision",
        condition_version="p03-condition-v1",
        dimensions=DimensionValues(
            {
                "R1": {"raw": 128, "level": "middle"},
                "R3": {"raw": r3.raw, "level": r3.level},
            }
        ),
        r1_frequency_source="audited-corpus-counter-v1",
        r1_corpus_snapshot_id="corpus@immutable-revision",
        r1_exposure_unit="estimated occurrences",
        r1_value_kind="proxy",
        r1_tail_max=50,
        r1_middle_max=500,
        r1_bin_rule_hash="1" * 64,
        r3_event_date="2025-01-01",
        r3_model_cutoff_date="2025-07-01",
        r3_cutoff_source="model-card-revision-1",
        r3_cutoff_uncertainty="day-level",
        r3_value_kind="exact",
        r3_bin_rule_hash="3" * 64,
    )
    generation = GenerationRecord(
        generation_id="generation-1",
        run_id="run-1",
        example_id=workload.example_id,
        model_snapshot_id=condition.model_snapshot_id,
        condition_hash=condition.condition_hash(),
        track=track,  # type: ignore[arg-type]
        raw_text="planet | element",
        candidates=("planet", "element"),
        score=0.93,
        score_kind="probability",
        score_source="temperature_scaled_sequence_score",
        calibrator_id="temp-v1",
    )
    result = decide_generation(
        workload,
        generation,
        0.9,
        correctness_rule="normalized-alias-v1",
        correctness_scorer=exact_match,
        supported=supported,
    )
    table = (condition,)
    manifest = RunManifest(
        run_id=generation.run_id,
        model_id="org/model",
        model_revision="immutable-revision",
        dataset_id="dataset/name",
        dataset_revision="v1",
        prompt_template="Q: {question}\\nA:",
        correctness_rule="normalized-alias-v1",
        calibration_ids_hash="a" * 64,
        test_ids_hash="b" * 64,
        code_revision="deadbeef",
        model_snapshot_id=condition.model_snapshot_id,
        condition_table_hash=condition_table_hash(table),
        seed=7,
        decoding={"temperature": 0.0},
        hardware={"device": "cpu"},
        protocol_version="p03-v1",
        dimension_schema_hash="c" * 64,
        dimension_bin_hash="d" * 64,
        tokenizer_revision="tokenizer-rev-1",
        dataset_license="CC-BY-4.0",
        dataset_source_url="https://example.test/dataset",
        evaluation_track=track,
        model_cutoff="2025-07-01",
        model_cutoff_source="model-card-revision-1",
        model_cutoff_uncertainty="day-level",
        candidate_constructor="catalog-closure-v1",
        scoring_rule="typed-exact-match-v1",
        calibration_method="split-conformal-v1",
        calibration_object_hash="e" * 64,
        split_manifest_hash="f" * 64,
        package_lock_hash="1" * 64,
        model_parameter_count=7_000_000_000,
        model_capacity_measure="released-parameter-count",
        dimension_settings={
            f"R{index}": {"enabled": True} for index in range(1, 8)
        },
        policy_grid=(0.5, 0.7, 0.9, 0.95, 0.99),
        runtime={"python": "3.13.5"},
        artifact_hashes={"generations": "2" * 64},
    ).finalized_copy()
    return workload, condition, generation, result, manifest


def make_certificate(
    *,
    track: str = "finite_label_certified",
    supported: bool = True,
    assumptions: dict[str, bool] | None = None,
    coverage_scope: str | None = "marginal",
) -> tuple[ReadCertificate, tuple[object, ...]]:
    workload, condition, generation, result, manifest = make_records(
        track=track, supported=supported
    )
    if assumptions is None:
        assumptions = assumption_status(
            true_label_in_fixed_candidate_universe=(
                track == "finite_label_certified"
            )
        )
    certificate = build_read_certificate(
        request_id="request-2026-001",
        workload=workload,
        condition=condition,
        generation=generation,
        result=result,  # type: ignore[arg-type]
        manifest=manifest,
        condition_table=(condition,),
        correctness_scorer=exact_match,
        calibration_scope="global",
        calibration_group=None,
        calibration_support_n=120 if supported else 0,
        calibration_supported=supported,
        unsupported_reason=None if supported else "group below frozen support floor",
        assumption_status=assumptions,
        target_alpha=0.10,
        coverage_scope=coverage_scope,  # type: ignore[arg-type]
        research_evidence=False,
        research_evidence_reason="synthetic unit-test fixture",
        additional_evidence_hashes={"r4_human_audit": "9" * 64},
    )
    return certificate, (workload, condition, generation, result, manifest)


class ReadCertificateTests(unittest.TestCase):
    def test_builder_round_trip_hash_and_record_revalidation(self) -> None:
        certificate, records = make_certificate()
        restored = ReadCertificate.from_dict(certificate.to_dict())
        self.assertEqual(restored, certificate)
        self.assertRegex(certificate.content_hash(), r"^[0-9a-f]{64}$")
        self.assertEqual(restored.content_hash(), certificate.content_hash())
        self.assertEqual(
            certificate.guarantee_status,
            "finite_label_marginal_under_recorded_assumptions",
        )
        self.assertIn("records, but does not prove", certificate.guarantee_statement)
        workload, condition, generation, result, manifest = records
        certificate.validate_against(
            workload,  # type: ignore[arg-type]
            condition,  # type: ignore[arg-type]
            generation,  # type: ignore[arg-type]
            result,  # type: ignore[arg-type]
            manifest,  # type: ignore[arg-type]
            (condition,),  # type: ignore[arg-type]
            correctness_scorer=exact_match,
        )
        with self.assertRaises(TypeError):
            certificate.assumption_status["scoring_rule_fixed"] = False  # type: ignore[index]

    def test_strict_schema_and_derived_guarantee_reject_tampering(self) -> None:
        certificate, _ = make_certificate()
        payload = certificate.to_dict()
        missing = dict(payload)
        missing.pop("manifest_hash")
        with self.assertRaisesRegex(ValueError, "fields do not match"):
            ReadCertificate.from_dict(missing)
        extra = {**payload, "unknown": "value"}
        with self.assertRaisesRegex(ValueError, "fields do not match"):
            ReadCertificate.from_dict(extra)
        dishonest = {
            **payload,
            "guarantee_status": "none_not_claimed",
        }
        with self.assertRaisesRegex(ValueError, "guarantee_status"):
            ReadCertificate.from_dict(dishonest)

    def test_source_hash_tampering_is_detected_on_revalidation(self) -> None:
        certificate, records = make_certificate()
        payload = certificate.to_dict()
        payload["evidence_hashes"] = {
            **payload["evidence_hashes"],  # type: ignore[dict-item]
            "generation_record": "f" * 64,
        }
        tampered = ReadCertificate.from_dict(payload)
        workload, condition, generation, result, manifest = records
        with self.assertRaisesRegex(ValueError, "source records"):
            tampered.validate_against(
                workload,  # type: ignore[arg-type]
                condition,  # type: ignore[arg-type]
                generation,  # type: ignore[arg-type]
                result,  # type: ignore[arg-type]
                manifest,  # type: ignore[arg-type]
                (condition,),  # type: ignore[arg-type]
                correctness_scorer=exact_match,
            )

    def test_open_ended_track_cannot_claim_coverage(self) -> None:
        with self.assertRaisesRegex(ValueError, "open-ended"):
            make_certificate(track="open_ended_stress", coverage_scope="marginal")
        certificate, _ = make_certificate(
            track="open_ended_stress", coverage_scope=None
        )
        self.assertEqual(
            certificate.guarantee_status,
            "none_open_ended_generated_candidates",
        )
        self.assertIn("may omit the true answer", certificate.guarantee_statement)
        self.assertIn("diagnostic only", certificate.guarantee_statement)

    def test_unsupported_calibration_must_abstain_and_cannot_claim(self) -> None:
        certificate, _ = make_certificate(supported=False, coverage_scope=None)
        self.assertEqual(certificate.selected_action, "abstain")
        self.assertIsNone(certificate.correct)
        self.assertEqual(
            certificate.guarantee_status, "none_unsupported_calibration"
        )
        with self.assertRaisesRegex(ValueError, "unsupported calibration"):
            make_certificate(supported=False, coverage_scope="marginal")

    def test_failed_assumption_requires_explicit_no_claim(self) -> None:
        failed = assumption_status(calibration_test_exchangeable=False)
        with self.assertRaisesRegex(ValueError, "every recorded assumption"):
            make_certificate(assumptions=failed, coverage_scope="marginal")
        certificate, _ = make_certificate(
            assumptions=failed, coverage_scope=None
        )
        self.assertEqual(
            certificate.guarantee_status, "none_assumptions_not_satisfied"
        )

    def test_builder_requires_finalized_manifest(self) -> None:
        workload, condition, generation, result, manifest = make_records()
        unfinalized = RunManifest.from_dict(
            {**manifest.to_dict(), "is_finalized": False}
        )
        with self.assertRaisesRegex(ValueError, "finalized"):
            build_read_certificate(
                request_id="request-2026-001",
                workload=workload,
                condition=condition,
                generation=generation,
                result=result,  # type: ignore[arg-type]
                manifest=unfinalized,
                condition_table=(condition,),
                correctness_scorer=exact_match,
                calibration_scope="global",
                calibration_group=None,
                calibration_support_n=120,
                calibration_supported=True,
                unsupported_reason=None,
                assumption_status=assumption_status(),
                target_alpha=0.10,
                coverage_scope="marginal",
                research_evidence=False,
                research_evidence_reason="synthetic unit-test fixture",
            )

    def test_documented_jsonl_example_is_valid_and_not_evidence(self) -> None:
        path = Path("results/EXAMPLE_READ_CERTIFICATE.jsonl")
        rows = read_jsonl(path)
        self.assertEqual(len(rows), 1)
        certificate = ReadCertificate.from_dict(rows[0])
        self.assertFalse(certificate.research_evidence)
        self.assertEqual(certificate.schema_version, 1)
        json.dumps(certificate.to_dict())


if __name__ == "__main__":
    unittest.main()
