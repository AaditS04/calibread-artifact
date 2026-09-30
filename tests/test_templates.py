"""Structural checks for committed research artifact templates."""

from __future__ import annotations

import csv
import unittest
from functools import partial
from pathlib import Path

from calibread.io import read_jsonl
from calibread.manifest import RunManifest
from calibread.schema import (
    GenerationRecord,
    ModelConditionRecord,
    ReadResultRecord,
    WorkloadRecord,
    condition_table_hash,
    validate_pipeline_linkage,
)
from calibread.typed_correctness import date_match


ROOT = Path(__file__).resolve().parents[1]
MONTH_DATE_MATCH = partial(date_match, granularity="month")


class CsvTemplateTests(unittest.TestCase):
    def test_result_templates_have_unique_headers_and_aligned_rows(self) -> None:
        for relative in (
            "data/SOURCE_LICENSE_TEMPLATE.csv",
            "results/RUN_LEDGER_TEMPLATE.csv",
            "results/CLAIM_EVIDENCE_TEMPLATE.csv",
            "results/MODEL_PROBE_TEMPLATE.csv",
            "results/POWER_PRECISION_TEMPLATE.csv",
        ):
            with self.subTest(template=relative):
                with (ROOT / relative).open(encoding="utf-8", newline="") as stream:
                    rows = list(csv.reader(stream))
                self.assertTrue(rows)
                header = rows[0]
                self.assertTrue(all(value.strip() for value in header))
                self.assertEqual(len(header), len(set(header)))
                for row_number, row in enumerate(rows[1:], start=2):
                    self.assertEqual(
                        len(row),
                        len(header),
                        f"{relative}:{row_number} does not match its header",
                    )

    def test_claim_evidence_template_has_frozen_unique_claims(self) -> None:
        with (ROOT / "results" / "CLAIM_EVIDENCE_TEMPLATE.csv").open(
            encoding="utf-8", newline=""
        ) as stream:
            rows = list(csv.DictReader(stream))

        expected_claim_ids = {
            "P03-H1",
            "P03-H2",
            "P03-H3",
            "P03-H4",
            "P03-H5",
            "OP-R1",
            "OP-R2",
            "OP-R3",
            "OP-R4",
            "OP-R5",
            "OP-R6",
            "OP-R7",
            "OP-I15",
            "OP-I36",
            "OP-I47",
            "OP-CPR",
            "OP-CONTRACT",
        }
        claim_ids = [row["claim_id"] for row in rows]
        self.assertEqual(len(claim_ids), len(set(claim_ids)))
        self.assertEqual(set(claim_ids), expected_claim_ids)
        self.assertNotIn("P03_H1", claim_ids)

        crosswalk_ids = {f"P03-H{index}" for index in range(1, 6)}
        for row in rows:
            with self.subTest(claim_id=row["claim_id"]):
                expected_status = (
                    "registered_original_crosswalk"
                    if row["claim_id"] in crosswalk_ids
                    else "confirmatory"
                )
                self.assertEqual(row["confirmatory_status"], expected_status)
                for field in (
                    "professor_hypothesis",
                    "dimension_or_interaction",
                    "contrast",
                    "primary_metric",
                    "model_tier",
                    "multiplicity_family",
                    "allowed_claim",
                    "limitations",
                ):
                    self.assertTrue(row[field].strip())
                    self.assertNotEqual(row[field], "TBD")
                for field in (
                    "model_id",
                    "calibration_n",
                    "test_n",
                    "cluster_n",
                    "effect_estimate",
                    "ci_95_low",
                    "ci_95_high",
                    "p_value",
                    "adjusted_p_value",
                    "artifact_path",
                    "figure_or_table",
                    "reviewer",
                ):
                    self.assertEqual(row[field], "TBD")
                self.assertEqual(row["assumptions_passed"], "false")
                self.assertEqual(row["stop_rule_triggered"], "false")


class PipelineExampleTests(unittest.TestCase):
    def test_typed_pipeline_examples_round_trip_and_link(self) -> None:
        workload = WorkloadRecord.from_dict(
            read_jsonl(ROOT / "data" / "EXAMPLE_WORKLOAD_RECORD.jsonl")[0]
        )
        condition = ModelConditionRecord.from_dict(
            read_jsonl(
                ROOT / "data" / "EXAMPLE_MODEL_CONDITION_RECORD.jsonl"
            )[0]
        )
        generation = GenerationRecord.from_dict(
            read_jsonl(ROOT / "results" / "EXAMPLE_GENERATION_RECORD.jsonl")[0]
        )
        decision = ReadResultRecord.from_dict(
            read_jsonl(ROOT / "results" / "EXAMPLE_READ_RESULT_RECORD.jsonl")[0]
        )

        self.assertEqual(workload.example_id, generation.example_id)
        self.assertEqual(workload.example_id, condition.example_id)
        self.assertEqual(condition.condition_hash(), generation.condition_hash)
        self.assertEqual(condition.model_snapshot_id, generation.model_snapshot_id)
        self.assertEqual(generation.example_id, decision.example_id)
        self.assertEqual(generation.generation_id, decision.generation_id)
        self.assertEqual(generation.run_id, decision.run_id)
        self.assertEqual(set(workload.dimensions.entries), {"R2", "R4", "R5", "R6"})
        self.assertEqual(set(condition.dimensions.entries), {"R1", "R3"})
        self.assertEqual(decision.policy_level, "tau_0_70")
        conditions = (condition,)
        manifest = RunManifest(
            run_id=generation.run_id,
            model_id="illustrative/model",
            model_revision="immutable-revision",
            model_snapshot_id=condition.model_snapshot_id,
            condition_table_hash=condition_table_hash(conditions),
            dataset_id="illustrative/dataset",
            dataset_revision="immutable-revision",
            prompt_template="Q: {question}\nA:",
            correctness_rule="iso-date-month-v1",
            calibration_ids_hash="a" * 64,
            test_ids_hash="b" * 64,
            code_revision="deadbeef",
            seed=7,
            evaluation_track=workload.track,
        )
        validate_pipeline_linkage(
            workload,
            condition,
            generation,
            manifest,
            conditions,
            decision=decision,
            correctness_scorer=MONTH_DATE_MATCH,
        )
        self.assertEqual(
            WorkloadRecord.from_dict(workload.to_dict()).to_dict(),
            workload.to_dict(),
        )
        self.assertEqual(
            ModelConditionRecord.from_dict(condition.to_dict()).to_dict(),
            condition.to_dict(),
        )
        self.assertEqual(
            GenerationRecord.from_dict(generation.to_dict()).to_dict(),
            generation.to_dict(),
        )
        self.assertEqual(
            ReadResultRecord.from_dict(decision.to_dict()).to_dict(),
            decision.to_dict(),
        )


if __name__ == "__main__":
    unittest.main()
