import json
from pathlib import Path
import tempfile
import unittest

from calibread.dimensions import (
    DimensionValues,
    dimension_value,
    r4_from_interpretation_count,
    r5_from_hop_count,
    r6_from_specificity,
)
from calibread.io import read_jsonl, write_jsonl
from calibread.leakage import normalized_question_hash
from calibread.r5_atoms import (
    build_musique_atomic_records,
    materialize_musique_atomic_probes,
    resolve_musique_placeholders,
)
from calibread.schema import Example, WorkloadRecord


def _dimensions(hops: int) -> DimensionValues:
    return DimensionValues(
        {
            "R2": dimension_value("R2", "medium", "medium"),
            "R4": r4_from_interpretation_count(1),
            "R5": r5_from_hop_count(hops),
            "R6": r6_from_specificity(
                0.10, general_max=0.33, specialized_max=0.66
            ),
        }
    )


def _composite(
    source_row_id: str,
    split: str,
    steps: list[dict[str, str]],
) -> tuple[WorkloadRecord, Example]:
    example_id = f"musique:{source_row_id}"
    chain_id = f"musique:composition:{source_row_id}"
    decomposition = [
        {
            "position": position,
            "source_step_id": step["id"],
            "question": step["question"],
            "answer": step["answer"],
            "paragraph_support_idx": position - 1,
            "supporting_title": step["title"],
        }
        for position, step in enumerate(steps, start=1)
    ]
    constituents = tuple(f"musique:singlehop:{step['id']}" for step in steps)
    dimensions = _dimensions(len(steps))
    final_answer = steps[-1]["answer"]
    workload = WorkloadRecord(
        example_id=example_id,
        question=f"Composite question for {source_row_id}?",
        accepted_answers=(final_answer,),
        track="open_ended_stress",
        dimensions=dimensions,
        r4_annotation_hash="1" * 64,
        r5_chain_spec_hash="2" * 64,
        interpretation_answers={"source_interpretation_1": (final_answer,)},
        chain_id=chain_id,
        constituent_example_ids=constituents,
        domain_name="general_knowledge",
        missing_reasons={
            "R1": "model_condition_record",
            "R3": "model_condition_record",
        },
        provenance={
            "source_id": "musique",
            "source_row_id": source_row_id,
            "source_split": "train",
            "graph_type": f"{len(steps)}hop",
            "question_decomposition": decomposition,
        },
    )
    composite_question = workload.question
    return workload, Example(
        example_id=example_id,
        question=composite_question,
        accepted_answers=workload.accepted_answers,
        split=split,
        metadata={
            "chain_id": chain_id,
            "source_fact_id": constituents,
            "question_hash": normalized_question_hash(composite_question),
        },
    )


def _write_inputs(
    directory: Path,
    records: list[tuple[WorkloadRecord, Example]],
) -> tuple[Path, Path]:
    workload_path = directory / "workloads.jsonl"
    example_path = directory / "examples.jsonl"
    write_jsonl(workload_path, (workload.to_dict() for workload, _ in records))
    write_jsonl(example_path, (example.to_dict() for _, example in records))
    return workload_path, example_path


def _shared_records(
    *, second_split: str = "development", answer: str = "1990", title: str = "Acme"
) -> list[tuple[WorkloadRecord, Example]]:
    shared = {
        "id": "20",
        "question": "When was #1 founded?",
        "answer": answer,
        "title": title,
    }
    return [
        _composite(
            "2hop__1_20",
            "development",
            [
                {
                    "id": "1",
                    "question": "Who owns The Paper?",
                    "answer": "Acme",
                    "title": "The Paper",
                },
                {
                    "id": "20",
                    "question": "When was #1 founded?",
                    "answer": "1990",
                    "title": "Acme",
                },
            ],
        ),
        _composite(
            "2hop__2_20",
            second_split,
            [
                {
                    "id": "2",
                    "question": "The Journal >> owned by",
                    "answer": "Acme",
                    "title": "The Journal",
                },
                shared,
            ],
        ),
    ]


class R5AtomicMaterializationTests(unittest.TestCase):
    def test_resolves_structural_references_but_preserves_literal_hash_title(self) -> None:
        self.assertEqual(
            resolve_musique_placeholders(
                "When was #1 founded?", ("Acme Institute",), hop_count=2
            ),
            "When was Acme Institute founded?",
        )
        self.assertEqual(
            resolve_musique_placeholders("#9 Dream >> performer", (), hop_count=2),
            "#9 Dream >> performer",
        )
        with self.assertRaisesRegex(ValueError, "unresolved or forward"):
            resolve_musique_placeholders("Who succeeded #2?", (), hop_count=2)

    def test_deduplicates_atoms_and_preserves_every_parent_link(self) -> None:
        records = _shared_records()
        records[1][0].provenance  # exercise immutable input before serialization
        # A harmless wording variant for the same source fact must not fork its ID.
        second_workload, second_example = records[1]
        second_dict = second_workload.to_dict()
        second_dict["provenance"]["question_decomposition"][1]["question"] = (
            "When was the #1 founded?"
        )
        records[1] = (WorkloadRecord.from_dict(second_dict), second_example)
        with tempfile.TemporaryDirectory() as directory:
            paths = _write_inputs(Path(directory), records)
            build = build_musique_atomic_records(*paths)

        self.assertEqual(build.decomposition_occurrences, 4)
        self.assertEqual(len(build.examples), 3)
        atom = next(
            item for item in build.examples if item.example_id == "musique:singlehop:20"
        )
        workload = next(
            item
            for item in build.workloads
            if item.example_id == "musique:singlehop:20"
        )
        self.assertEqual(atom.question, "When was Acme founded?")
        self.assertEqual(atom.split, "development")
        self.assertEqual(atom.dimension_values()["R5"].level, "one_hop")
        self.assertIs(atom.metadata["r5_atomic_probe"], True)
        self.assertEqual(atom.metadata["source_step_id"], "20")
        self.assertEqual(len(atom.metadata["parent_chain_links"]), 2)
        self.assertEqual(
            {link["position"] for link in atom.metadata["parent_chain_links"]}, {2}
        )
        self.assertEqual(workload.dimensions["R5"].raw, 1)
        self.assertEqual(workload.provenance["source_id"], "musique_atomic")
        self.assertEqual(workload.constituent_example_ids, ("musique:fact:20",))

    def test_outputs_manifest_card_and_audit_are_byte_deterministic(self) -> None:
        record = _composite(
            "2hop__1_2",
            "calibration",
            [
                {
                    "id": "1",
                    "question": "Who owns Example?",
                    "answer": "Owner",
                    "title": "Example",
                },
                {
                    "id": "2",
                    "question": "Where is #1 based?",
                    "answer": "Delhi",
                    "title": "Owner",
                },
            ],
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            _write_inputs(source, [record])
            first = materialize_musique_atomic_probes(
                input_dir=source, output_dir=root / "first", audit_size=2
            )
            second = materialize_musique_atomic_probes(
                input_dir=source, output_dir=root / "second", audit_size=2
            )
            for filename in (
                "workloads.jsonl",
                "examples.jsonl",
                "composite_workloads.jsonl",
                "composite_examples.jsonl",
                "audit_sample.csv",
                "ATOMIC_MANIFEST.json",
                "DATA_CARD.md",
            ):
                self.assertEqual(
                    (first / filename).read_bytes(), (second / filename).read_bytes()
                )
            manifest = json.loads(
                (first / "ATOMIC_MANIFEST.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["atomic_records"], 2)
            self.assertEqual(manifest["composite_records"], 1)
            self.assertEqual(manifest["excluded_composite_records"], 0)
            self.assertEqual(manifest["checks"]["placeholder_resolution"], "passed")
            self.assertEqual(len(read_jsonl(first / "examples.jsonl")), 2)

    def test_strict_panel_excludes_every_chain_touching_cross_split_question(self) -> None:
        duplicate_dev = _composite(
            "2hop__1_2",
            "development",
            [
                {
                    "id": "1",
                    "question": "Which duplicate fact?",
                    "answer": "Alpha",
                    "title": "Alpha",
                },
                {
                    "id": "2",
                    "question": "What follows #1?",
                    "answer": "A2",
                    "title": "A2",
                },
            ],
        )
        duplicate_test = _composite(
            "2hop__3_4",
            "test",
            [
                {
                    "id": "3",
                    "question": "  which DUPLICATE fact? ",
                    "answer": "Beta",
                    "title": "Beta",
                },
                {
                    "id": "4",
                    "question": "What follows #1?",
                    "answer": "B2",
                    "title": "B2",
                },
            ],
        )
        retained = _composite(
            "2hop__5_6",
            "calibration",
            [
                {
                    "id": "5",
                    "question": "A unique first fact?",
                    "answer": "Gamma",
                    "title": "Gamma",
                },
                {
                    "id": "6",
                    "question": "Where is #1?",
                    "answer": "Delhi",
                    "title": "Delhi",
                },
            ],
        )
        with tempfile.TemporaryDirectory() as directory:
            paths = _write_inputs(
                Path(directory), [duplicate_dev, duplicate_test, retained]
            )
            build = build_musique_atomic_records(*paths)

        self.assertEqual(build.input_composite_count, 3)
        self.assertEqual(build.excluded_composite_count, 2)
        self.assertEqual(build.excluded_question_hash_count, 1)
        self.assertEqual(build.exclusion_rounds, 1)
        self.assertEqual(
            [record.example_id for record in build.composite_examples],
            ["musique:2hop__5_6"],
        )
        self.assertEqual(
            {record.example_id for record in build.examples},
            {"musique:singlehop:5", "musique:singlehop:6"},
        )
        self.assertEqual(build.cross_split_question_hash_count, 0)
        self.assertEqual(build.decomposition_occurrences, 2)
        self.assertEqual(build.input_decomposition_occurrences, 6)

    def test_rejects_cross_split_fact_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = _write_inputs(
                Path(directory), _shared_records(second_split="test")
            )
            with self.assertRaisesRegex(ValueError, "crosses CalibRead splits"):
                build_musique_atomic_records(*paths)

    def test_rejects_conflicting_answer_or_title(self) -> None:
        for field, value, message in (
            ("answer", "1991", "conflicting answers"),
            ("title", "Different title", "conflicting supporting titles"),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                kwargs = {field: value}
                paths = _write_inputs(Path(directory), _shared_records(**kwargs))
                with self.assertRaisesRegex(ValueError, message):
                    build_musique_atomic_records(*paths)

    def test_rejects_forward_placeholder_in_composite(self) -> None:
        record = _composite(
            "2hop__1_2",
            "development",
            [
                {
                    "id": "1",
                    "question": "Who succeeded #2?",
                    "answer": "First",
                    "title": "First",
                },
                {
                    "id": "2",
                    "question": "Second question?",
                    "answer": "Second",
                    "title": "Second",
                },
            ],
        )
        with tempfile.TemporaryDirectory() as directory:
            paths = _write_inputs(Path(directory), [record])
            with self.assertRaisesRegex(ValueError, "unresolved or forward"):
                build_musique_atomic_records(*paths)


if __name__ == "__main__":
    unittest.main()
