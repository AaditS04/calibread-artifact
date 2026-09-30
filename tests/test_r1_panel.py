import csv
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from calibread.data_pipeline import adapt_popqa
from calibread.io import read_jsonl, write_jsonl
from calibread.r1_panel import development_tertile_cutpoints, materialize_popqa_r1_panel
from calibread.schema import Example


def _write_popqa(path: Path, rows: list[dict[str, str]]) -> None:
    fields = [
        "id", "subj", "prop", "obj", "subj_id", "prop_id", "obj_id",
        "s_pop", "question", "possible_answers",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def _pop_row(index: int, popularity: str) -> dict[str, str]:
    return {
        "id": str(index),
        "subj": f"Subject {index}",
        "prop": "occupation",
        "obj": f"answer-{index}",
        "subj_id": f"Q{index}",
        "prop_id": "P106",
        "obj_id": f"O{index}",
        "s_pop": popularity,
        "question": f"What is fact {index}?",
        "possible_answers": f"['answer-{index}']",
    }


class R1PanelTests(unittest.TestCase):
    def test_cutpoints_use_inclusive_tertiles(self) -> None:
        self.assertEqual(
            development_tertile_cutpoints([1, 2, 3, 4, 5, 6]),
            (2.6666666666666665, 4.333333333333333),
        )

    def test_panel_freezes_development_tertiles_and_labels_every_split(self) -> None:
        rows = [
            _pop_row(index, popularity)
            for index, popularity in enumerate(("1", "50", "100", "1", "50", "100", "1", "50", "100"), start=1)
        ]
        splits = (
            ["development"] * 3 + ["calibration"] * 3 + ["test"] * 3
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_popqa(root / "popqa.tsv", rows)
            workloads, examples, seeds, exclusions = adapt_popqa(root / "popqa.tsv")
            self.assertEqual(exclusions, {})
            labeled = [
                replace(example, split=split)
                for example, split in zip(examples, splits, strict=True)
            ]
            write_jsonl(root / "examples.jsonl", (example.to_dict() for example in labeled))
            write_jsonl(root / "workloads.jsonl", (workload.to_dict() for workload in workloads))
            write_jsonl(root / "seeds.jsonl", seeds)
            manifest = materialize_popqa_r1_panel(
                examples_path=root / "examples.jsonl",
                workloads_path=root / "workloads.jsonl",
                seeds_path=root / "seeds.jsonl",
                output_dir=root / "panel",
            )
            self.assertEqual(manifest["cutpoint_split"], "development")
            self.assertEqual(manifest["tail_max"], 33.666666666666664)
            self.assertEqual(manifest["middle_max"], 66.66666666666667)
            self.assertEqual(manifest["counts"]["test:head"], 1)
            self.assertEqual(manifest["counts"]["test:tail"], 1)
            self.assertEqual(manifest["counts"]["development:middle"], 1)
            written = [
                Example.from_dict(row) for row in read_jsonl(root / "panel" / "examples.jsonl")
            ]
            self.assertEqual(
                [example.dimension_values()["R1"].level for example in written],
                ["tail", "middle", "head"] * 3,
            )
            self.assertNotIn("R1", json.loads((root / "panel" / "workloads.jsonl").read_text(encoding="utf-8").splitlines()[0])["dimensions"])

    def test_refuses_to_replace_frozen_cutpoints(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            panel = root / "panel"
            panel.mkdir()
            (panel / "BIN_MANIFEST.json").write_text(
                json.dumps({"tail_max": 1.0, "middle_max": 9.0, "source_seeds_sha256": "old"}) + "\n",
                encoding="utf-8",
            )
            rows = [
                _pop_row(index, popularity)
                for index, popularity in enumerate(("1", "50", "100", "1", "50", "100", "1", "50", "100"), start=1)
            ]
            _write_popqa(root / "popqa.tsv", rows)
            workloads, examples, seeds, _ = adapt_popqa(root / "popqa.tsv")
            labeled = [
                replace(example, split=split)
                for example, split in zip(
                    examples,
                    ["development"] * 3 + ["calibration"] * 3 + ["test"] * 3,
                    strict=True,
                )
            ]
            write_jsonl(root / "examples.jsonl", (example.to_dict() for example in labeled))
            write_jsonl(root / "workloads.jsonl", (workload.to_dict() for workload in workloads))
            write_jsonl(root / "seeds.jsonl", seeds)
            with self.assertRaisesRegex(ValueError, "refusing to replace"):
                materialize_popqa_r1_panel(
                    examples_path=root / "examples.jsonl",
                    workloads_path=root / "workloads.jsonl",
                    seeds_path=root / "seeds.jsonl",
                    output_dir=panel,
                )


if __name__ == "__main__":
    unittest.main()
