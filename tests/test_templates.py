"""Structural checks for typed example records in the artifact."""

from __future__ import annotations

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
            read_jsonl(ROOT / "data" / "EXAMPLE_GENERATION_RECORD.jsonl")[0]
        )
        decision = ReadResultRecord.from_dict(
            read_jsonl(ROOT / "data" / "EXAMPLE_READ_RESULT_RECORD.jsonl")[0]
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
