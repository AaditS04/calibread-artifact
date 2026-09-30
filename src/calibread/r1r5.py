"""Freeze SOCRATES R1 x R5 labels and score them on a sealed R5 cache.

R1 cutpoints come from development one-hop WIMBD Dolma co-occurrence counts.
A two-hop chain inherits the minimum of its two atom counts, then those same
cutpoints. The composed triple co-occurrence is not used: on this extract it is
zero for every chain, so it cannot separate head from tail.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
import json
from pathlib import Path
import random

from .io import read_jsonl, sha256_file, write_jsonl
from .r1_panel import development_tertile_cutpoints
from .schema import Example


PANEL_VERSION = 1
MAPPING_METHOD = "socrates_development_atom_tertiles_min_chain_v1"
PROXY_SOURCE = "SOCRATES WIMBD Dolma-1.7 atom co-occurrence"
LEVELS = ("tail", "middle", "head")
TEST_CELL_FLOOR = 75


def _kind(example_id: str) -> str:
    return example_id.rsplit(":", 1)[-1]


def _uid(example_id: str) -> str:
    parts = example_id.split(":")
    if len(parts) != 3 or parts[0] != "socrates" or parts[2] not in {"r1", "r2", "composed"}:
        raise ValueError(f"unexpected SOCRATES example id {example_id}")
    return parts[1]


def _level(value: float, tail_max: float, middle_max: float) -> str:
    if value <= tail_max:
        return "tail"
    if value <= middle_max:
        return "middle"
    return "head"


def materialize_socrates_r1r5_panel(
    *,
    examples_path: str | Path,
    seeds_path: str | Path,
    output_dir: str | Path,
) -> dict[str, object]:
    """Write development-frozen R1 labels for SOCRATES atoms and chains."""

    examples_path = Path(examples_path)
    seeds_path = Path(seeds_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    examples = [Example.from_dict(row) for row in read_jsonl(examples_path)]
    seeds = {str(row["example_id"]): row for row in read_jsonl(seeds_path)}
    by_id = {example.example_id: example for example in examples}
    if len(by_id) != len(examples):
        raise ValueError("SOCRATES examples contain duplicate ids")

    atom_proxy: dict[str, float] = {}
    development_atoms: list[float] = []
    for example in examples:
        kind = _kind(example.example_id)
        if kind not in {"r1", "r2"}:
            continue
        seed = seeds.get(example.example_id)
        if seed is None:
            raise ValueError(f"missing seed for {example.example_id}")
        raw = seed.get("R1", {})
        proxy = raw.get("proxy_value") if isinstance(raw, dict) else None
        if isinstance(proxy, bool) or not isinstance(proxy, (int, float)):
            raise ValueError(f"{example.example_id} has no numeric atom proxy")
        value = float(proxy)
        atom_proxy[example.example_id] = value
        if example.split == "development":
            development_atoms.append(value)
    tail_max, middle_max = development_tertile_cutpoints(development_atoms)

    assignments: list[dict[str, object]] = []
    counts: Counter[tuple[str, str, str]] = Counter()
    for example in examples:
        kind = _kind(example.example_id)
        uid = _uid(example.example_id)
        atom_ids = (f"socrates:{uid}:r1", f"socrates:{uid}:r2")
        if kind == "composed":
            for atom_id in atom_ids:
                atom = by_id.get(atom_id)
                if atom is None:
                    raise ValueError(f"{example.example_id} is missing {atom_id}")
                if atom.split != example.split:
                    raise ValueError(f"{example.example_id} crosses splits at {atom_id}")
            proxy_value = min(atom_proxy[atom_id] for atom_id in atom_ids)
            proxy_definition = "min_constituent_dolma17"
            hop = "two_hop"
            constituents = list(atom_ids)
        else:
            proxy_value = atom_proxy[example.example_id]
            proxy_definition = "dolma17_atom"
            hop = "one_hop"
            constituents = []
        level = _level(proxy_value, tail_max, middle_max)
        assignments.append(
            {
                "example_id": example.example_id,
                "split": example.split,
                "r5_level": hop,
                "r1_level": level,
                "proxy_value": proxy_value,
                "proxy_definition": proxy_definition,
                "constituent_example_ids": constituents,
            }
        )
        counts[(example.split, hop, level)] += 1

    unsupported = [
        f"{split}:{hop}:{level}"
        for split in ("development", "calibration", "test")
        for hop in ("one_hop", "two_hop")
        for level in LEVELS
        if counts[(split, hop, level)] < TEST_CELL_FLOOR
    ]
    manifest = {
        "panel_version": PANEL_VERSION,
        "mapping_method": MAPPING_METHOD,
        "proxy_source": PROXY_SOURCE,
        "cutpoint_split": "development",
        "cutpoint_rows": "one-hop atoms only",
        "chain_rule": "two-hop proxy is the minimum of its two atom Dolma-1.7 counts",
        "unused_composed_proxy": (
            "wimbd.dolma(e1,e2,e3) is zero for every SOCRATES chain in this extract "
            "and is not a cutpoint source"
        ),
        "tail_max": tail_max,
        "middle_max": middle_max,
        "test_cell_floor": TEST_CELL_FLOOR,
        "source_examples_sha256": sha256_file(examples_path),
        "source_seeds_sha256": sha256_file(seeds_path),
        "records": len(assignments),
        "counts": {
            f"{split}:{hop}:{level}": counts[(split, hop, level)]
            for split in ("development", "calibration", "test")
            for hop in ("one_hop", "two_hop")
            for level in LEVELS
        },
        "unsupported_cells": unsupported,
        "interaction_contrast": (
            "head x two_hop is below the test-cell floor, so the confirmatory "
            "interaction contrasts tail against not_tail (middle and head pooled) "
            "within each hop. The three-level table is still reported."
        ),
        "claim_limit": (
            "R1 is a Dolma-1.7 co-occurrence proxy from SOCRATES, not a document "
            "count in the Qwen or Mixtral training corpus. MuSiQue has no R1 proxy "
            "and is excluded."
        ),
    }
    write_jsonl(output_dir / "assignments.jsonl", assignments)
    manifest_path = output_dir / "BIN_MANIFEST.json"
    if manifest_path.is_file():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        if previous.get("tail_max") != tail_max or previous.get("middle_max") != middle_max:
            raise ValueError("refusing to replace frozen SOCRATES R1 x R5 cutpoints")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _accuracy(flags: list[int]) -> float | None:
    if not flags:
        return None
    return sum(flags) / len(flags)


def _difference(left: list[int], right: list[int], seed: int) -> dict[str, object]:
    if not left or not right:
        return {"estimate": None, "interval_95": None, "n_left": len(left), "n_right": len(right)}
    observed = _accuracy(left) - _accuracy(right)
    generator = random.Random(seed)
    replicates: list[float] = []
    for _ in range(2000):
        left_draw = [left[generator.randrange(len(left))] for _ in left]
        right_draw = [right[generator.randrange(len(right))] for _ in right]
        replicates.append((_accuracy(left_draw) or 0.0) - (_accuracy(right_draw) or 0.0))
    return {
        "estimate": observed,
        "interval_95": [_percentile(replicates, 0.025), _percentile(replicates, 0.975)],
        "bootstrap_samples": 2000,
        "n_left": len(left),
        "n_right": len(right),
    }


def score_r1r5(
    scored_path: str | Path,
    assignments_path: str | Path,
    *,
    dataset_id: str = "socrates_v1",
    seed: int = 7,
) -> dict[str, object]:
    """Cross a sealed scored file with the frozen SOCRATES R1 x R5 assignments."""

    assignments = {
        str(row["example_id"]): row for row in read_jsonl(assignments_path)
    }
    with Path(scored_path).open(newline="", encoding="utf-8") as stream:
        scored = [
            row for row in csv.DictReader(stream) if row.get("dataset_id") == dataset_id
        ]
    if not scored:
        raise ValueError(f"{scored_path} has no {dataset_id} rows")
    grouped: dict[tuple[str, str], list[int]] = defaultdict(list)
    by_id: dict[str, dict[str, str]] = {}
    for row in scored:
        assignment = assignments.get(row["example_id"])
        if assignment is None:
            raise ValueError(f"{row['example_id']} has no R1 x R5 assignment")
        if assignment["split"] != row["split"]:
            raise ValueError(f"{row['example_id']} split does not match its assignment")
        key = (str(assignment["r5_level"]), str(assignment["r1_level"]))
        grouped[key].append(int(row["correct"]))
        by_id[row["example_id"]] = row

    cells = {}
    for hop in ("one_hop", "two_hop"):
        for level in LEVELS:
            flags = grouped[(hop, level)]
            cells[f"{hop}:{level}"] = {
                "n": len(flags),
                "correct": sum(flags),
                "accuracy": _accuracy(flags),
                "supported": len(flags) >= TEST_CELL_FLOOR,
            }

    def _pool(hop: str, levels: tuple[str, ...]) -> list[int]:
        flags: list[int] = []
        for level in levels:
            flags.extend(grouped[(hop, level)])
        return flags

    one_gap = _difference(grouped[("one_hop", "tail")], _pool("one_hop", ("middle", "head")), seed)
    two_gap = _difference(grouped[("two_hop", "tail")], _pool("two_hop", ("middle", "head")), seed + 1)
    interaction_replicates: list[float] = []
    generator = random.Random(seed + 2)
    groups = {
        "one_tail": grouped[("one_hop", "tail")],
        "one_rest": _pool("one_hop", ("middle", "head")),
        "two_tail": grouped[("two_hop", "tail")],
        "two_rest": _pool("two_hop", ("middle", "head")),
    }
    for _ in range(2000):
        drawn = {
            name: [values[generator.randrange(len(values))] for _ in values]
            for name, values in groups.items()
        }
        one = (_accuracy(drawn["one_tail"]) or 0.0) - (_accuracy(drawn["one_rest"]) or 0.0)
        two = (_accuracy(drawn["two_tail"]) or 0.0) - (_accuracy(drawn["two_rest"]) or 0.0)
        interaction_replicates.append(two - one)
    observed_interaction = (two_gap["estimate"] or 0.0) - (one_gap["estimate"] or 0.0)

    synthesis: dict[str, dict[str, object]] = {}
    for level in LEVELS:
        chains = [
            row for row in assignments.values()
            if row["r5_level"] == "two_hop" and row["r1_level"] == level and row["split"] == scored[0]["split"]
        ]
        both_correct = 0
        synthesis_failures = 0
        composed_correct = 0
        for chain in chains:
            composed = by_id.get(str(chain["example_id"]))
            atoms = [by_id.get(str(atom_id)) for atom_id in chain["constituent_example_ids"]]
            if composed is None or any(atom is None for atom in atoms):
                continue
            composed_correct += int(composed["correct"])
            if all(int(atom["correct"]) == 1 for atom in atoms):
                both_correct += 1
                if int(composed["correct"]) == 0:
                    synthesis_failures += 1
        synthesis[level] = {
            "n_chains": len(chains),
            "supported": len(chains) >= TEST_CELL_FLOOR,
            "composed_accuracy": composed_correct / len(chains) if chains else None,
            "both_atoms_correct": both_correct,
            "synthesis_loss": (
                synthesis_failures / both_correct if both_correct else None
            ),
        }

    return {
        "scored_results_sha256": sha256_file(scored_path),
        "dataset_id": dataset_id,
        "split": scored[0]["split"],
        "n": len(scored),
        "cells": cells,
        "tail_minus_not_tail": {"one_hop": one_gap, "two_hop": two_gap},
        "interaction": {
            "contrast": "two_hop_tail_gap_minus_one_hop_tail_gap",
            "definition": "gap is tail accuracy minus pooled middle+head accuracy",
            "estimate": observed_interaction,
            "interval_95": [
                _percentile(interaction_replicates, 0.025),
                _percentile(interaction_replicates, 0.975),
            ],
            "bootstrap_samples": 2000,
        },
        "synthesis_by_r1": synthesis,
        "claim_limit": (
            "Head x two-hop is below the 75-example floor and is not a confirmatory "
            "cell. The interaction uses tail versus pooled middle and head."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples", type=Path, default=Path("data/processed/socrates_v1/examples.jsonl"))
    parser.add_argument("--seeds", type=Path, default=Path("data/processed/socrates_v1/condition_seeds.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/socrates_r1r5"))
    parser.add_argument("--scored", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    manifest = materialize_socrates_r1r5_panel(
        examples_path=args.examples,
        seeds_path=args.seeds,
        output_dir=args.output_dir,
    )
    if args.scored is None:
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0
    report = score_r1r5(args.scored, args.output_dir / "assignments.jsonl")
    report["bin_manifest"] = {
        "tail_max": manifest["tail_max"],
        "middle_max": manifest["middle_max"],
        "mapping_method": manifest["mapping_method"],
    }
    target = args.report or (args.output_dir / "r1r5_report.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
