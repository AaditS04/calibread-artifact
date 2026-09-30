"""R1 popularity-bin report over a completed scored run."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import random

from ..schema import Example
from ..io import read_jsonl
from .config import InferenceConfig
from .scoring import verify_scored_results


_LEVELS = ("tail", "middle", "head")


def _summary(rows: list[dict[str, str]]) -> dict[str, object]:
    count = len(rows)
    correct = sum(int(row["correct"]) for row in rows)
    return {
        "n": count,
        "correct": correct,
        "accuracy": (correct / count) if count else None,
    }


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        raise ValueError("bootstrap sample is empty")
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _tail_minus_head(rows_by_level: dict[str, list[dict[str, str]]], seed: int) -> dict[str, object]:
    tail = [int(row["correct"]) for row in rows_by_level["tail"]]
    head = [int(row["correct"]) for row in rows_by_level["head"]]
    if not tail or not head:
        raise ValueError("tail-minus-head contrast requires both tail and head rows")
    observed = (sum(tail) / len(tail)) - (sum(head) / len(head))
    generator = random.Random(seed)
    replicates: list[float] = []
    for _ in range(2000):
        tail_draw = [tail[generator.randrange(len(tail))] for _ in tail]
        head_draw = [head[generator.randrange(len(head))] for _ in head]
        replicates.append((sum(tail_draw) / len(tail_draw)) - (sum(head_draw) / len(head_draw)))
    return {
        "contrast": "tail_accuracy_minus_head_accuracy",
        "estimate": observed,
        "interval_95": [_percentile(replicates, 0.025), _percentile(replicates, 0.975)],
        "bootstrap_samples": 2000,
        "bootstrap": "independent resample within each R1 level",
    }


def build_r1_report(config: InferenceConfig) -> Path:
    """Write ``r1_report.json`` for the configured split."""

    verify_scored_results(config)
    levels: dict[str, str] = {}
    for dataset in config.datasets:
        for value in read_jsonl(dataset.examples):
            example = Example.from_dict(value)
            dimensions = example.dimension_values()
            if "R1" not in dimensions:
                raise ValueError(f"{example.example_id} has no frozen R1 level")
            levels[example.example_id] = dimensions["R1"].level
    source = config.run.output_dir / "scored_results.csv"
    with source.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    grouped: dict[str, list[dict[str, str]]] = {level: [] for level in _LEVELS}
    for row in rows:
        level = levels.get(row["example_id"])
        if level not in grouped:
            raise ValueError(f"{row['example_id']} is missing a frozen R1 level")
        grouped[level].append(row)
    report = {
        "run_id": config.run.run_id,
        "parent_experiment_id": config.run.parent_experiment_id,
        "split": config.run.split,
        "axis": "R1",
        "measure": "PopQA s_pop popularity proxy",
        "overall": _summary(rows),
        "by_r1_level": {level: _summary(grouped[level]) for level in _LEVELS},
        "tail_minus_head": _tail_minus_head(grouped, config.run.seed),
        "claim_limit": (
            "Levels are development-frozen tertiles of PopQA subject popularity. "
            "This is not a training-frequency threshold for the evaluated model."
        ),
    }
    target = config.run.output_dir / "r1_report.json"
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target
