"""Round-trip and provenance tests for cached experiment artifacts."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from calibread.io import read_jsonl, sha256_file, write_jsonl
from calibread.manifest import RunManifest


def make_manifest(**overrides: object) -> RunManifest:
    values: dict[str, object] = {
        "run_id": "pilot-001",
        "model_id": "org/model",
        "model_revision": "immutable-revision",
        "dataset_id": "dataset/name",
        "dataset_revision": "v1",
        "prompt_template": "Q: {question}\nA:",
        "correctness_rule": "normalized-alias-v1",
        "calibration_ids_hash": "a" * 64,
        "test_ids_hash": "b" * 64,
        "code_revision": "deadbeef",
        "model_snapshot_id": "org/model@immutable-revision",
        "condition_table_hash": "9" * 64,
        "seed": 7,
        "decoding": {"temperature": 0.0},
        "hardware": {"device": "cpu"},
    }
    values.update(overrides)
    return RunManifest(**values)  # type: ignore[arg-type]


def make_final_manifest(**overrides: object) -> RunManifest:
    values: dict[str, object] = {
        "protocol_version": "p03-v1",
        "dimension_schema_hash": "c" * 64,
        "dimension_bin_hash": "d" * 64,
        "tokenizer_revision": "tokenizer-rev-1",
        "dataset_license": "CC-BY-4.0",
        "dataset_source_url": "https://example.test/dataset",
        "evaluation_track": "finite_label_certified",
        "model_cutoff": "2025-01",
        "model_cutoff_source": "model-card-revision-1",
        "model_cutoff_uncertainty": "month-level",
        "candidate_constructor": "catalog-closure-v1",
        "scoring_rule": "typed-exact-match-v1",
        "calibration_method": "temperature-scaling-v1",
        "calibration_object_hash": "e" * 64,
        "split_manifest_hash": "f" * 64,
        "package_lock_hash": "1" * 64,
        "model_parameter_count": 7_000_000_000,
        "model_capacity_measure": "released-parameter-count",
        "dimension_settings": {
            f"R{index}": {"enabled": True} for index in range(1, 8)
        },
        "policy_grid": (0.5, 0.7, 0.9, 0.95, 0.99),
        "runtime": {"python": "3.13.5"},
        "artifact_hashes": {"generations": "2" * 64},
    }
    values.update(overrides)
    return make_manifest(**values)


class JsonLinesTests(unittest.TestCase):
    def test_unicode_round_trip_and_file_hash(self) -> None:
        rows = [{"id": "q1", "answer": "München"}, {"id": "q2", "correct": True}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "records.jsonl"
            write_jsonl(path, rows)
            self.assertEqual(read_jsonl(path), rows)
            expected = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(sha256_file(path), expected)

    def test_invalid_row_does_not_replace_existing_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.jsonl"
            write_jsonl(path, [{"status": "original"}])
            with self.assertRaises(TypeError):
                write_jsonl(path, [{"status": "new"}, ["not", "an", "object"]])  # type: ignore[list-item]
            self.assertEqual(read_jsonl(path), [{"status": "original"}])

    def test_reader_rejects_blank_and_non_object_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.jsonl"
            path.write_text('{"id": 1}\n\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "blank"):
                read_jsonl(path)
            path.write_text('[1, 2]\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not an object"):
                read_jsonl(path)


class ManifestTests(unittest.TestCase):
    def test_round_trip_and_hash_are_deterministic(self) -> None:
        manifest = make_manifest()
        restored = RunManifest.from_dict(manifest.to_dict())
        self.assertEqual(restored, manifest)
        self.assertEqual(restored.content_hash(), manifest.content_hash())
        self.assertRegex(manifest.content_hash(), r"^[0-9a-f]{64}$")

    def test_hash_changes_when_research_provenance_changes(self) -> None:
        baseline = make_manifest()
        changed = make_manifest(model_revision="different-revision")
        self.assertNotEqual(baseline.content_hash(), changed.content_hash())
        changed_dimensions = make_manifest(dimension_bin_hash="frozen-r1-r7-bins")
        self.assertNotEqual(baseline.content_hash(), changed_dimensions.content_hash())
        changed_conditions = make_manifest(condition_table_hash="8" * 64)
        self.assertNotEqual(baseline.content_hash(), changed_conditions.content_hash())

    def test_blank_required_field_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            make_manifest(model_revision="   ")

    def test_nested_provenance_is_deep_frozen_and_canonicalized(self) -> None:
        decoding = {"sampling": {"stops": ["END"], "temperature": 0.0}}
        manifest = make_manifest(decoding=decoding)
        decoding["sampling"]["stops"].append("MUTATED")  # type: ignore[index,union-attr]
        self.assertEqual(
            manifest.to_dict()["decoding"],
            {"sampling": {"stops": ["END"], "temperature": 0.0}},
        )
        with self.assertRaises(TypeError):
            manifest.decoding["new"] = True  # type: ignore[index]
        with self.assertRaises(TypeError):
            manifest.decoding["sampling"]["new"] = True  # type: ignore[index,union-attr]

    def test_finalization_requires_complete_nonplaceholder_provenance(self) -> None:
        with self.assertRaisesRegex(ValueError, "placeholder"):
            make_manifest().finalized_copy()
        finalized = make_final_manifest().finalized_copy()
        self.assertTrue(finalized.is_finalized)
        self.assertEqual(finalized.model_parameter_count, 7_000_000_000)
        self.assertEqual(finalized.model_cutoff_source, "model-card-revision-1")
        self.assertEqual(
            RunManifest.from_dict(finalized.to_dict()).content_hash(),
            finalized.content_hash(),
        )

    def test_finalization_rejects_noncanonical_r7_and_nested_placeholders(self) -> None:
        with self.assertRaisesRegex(ValueError, "frozen values"):
            make_final_manifest(policy_grid=(0.8,)).finalized_copy()
        with self.assertRaisesRegex(ValueError, "nested placeholders"):
            make_final_manifest(runtime={"python": "unknown"}).finalized_copy()
        with self.assertRaisesRegex(ValueError, "increasing order"):
            make_manifest(policy_grid=(0.9, 0.7))


if __name__ == "__main__":
    unittest.main()
