"""Freeze a PopQA popularity-proxy panel for the R1 sealed test.

R1 levels are assigned with development-only tertile cutpoints of the upstream
``s_pop`` score. Calibration and test rows receive those frozen thresholds.
They do not move the cutpoints. The score is subject popularity, not a count
of documents in the evaluated model's pretraining corpus.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path
from statistics import quantiles

from .dimensions import DimensionValues, r1_from_frequency
from .io import read_jsonl, sha256_file, write_jsonl
from .schema import Example, WorkloadRecord


PANEL_VERSION = 1
MAPPING_METHOD = "development_tertiles_inclusive_v1"
PROXY_SOURCE = "PopQA subject popularity field s_pop"
LEVELS = ("tail", "middle", "head")


def development_tertile_cutpoints(values: list[float]) -> tuple[float, float]:
    """Return ``(tail_max, middle_max)`` from development proxy values only."""

    if len(values) < 3:
        raise ValueError("R1 tertiles require at least three development proxy values")
    if any(value < 0 for value in values):
        raise ValueError("R1 proxy values must be >= 0")
    tail_max, middle_max = quantiles(values, n=3, method="inclusive")
    if not tail_max < middle_max:
        raise ValueError(
            "development tertiles collapsed "
            f"(tail_max={tail_max}, middle_max={middle_max}); ties prevent three levels"
        )
    return float(tail_max), float(middle_max)


def materialize_popqa_r1_panel(
    *,
    examples_path: str | Path,
    workloads_path: str | Path,
    seeds_path: str | Path,
    output_dir: str | Path,
) -> dict[str, object]:
    """Write the frozen R1 panel and return the bin manifest payload."""

    examples_path = Path(examples_path)
    workloads_path = Path(workloads_path)
    seeds_path = Path(seeds_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    examples = [Example.from_dict(row) for row in read_jsonl(examples_path)]
    workloads = {
        row["example_id"]: WorkloadRecord.from_dict(row)
        for row in read_jsonl(workloads_path)
        if isinstance(row.get("example_id"), str)
    }
    seeds = {
        str(row["example_id"]): row
        for row in read_jsonl(seeds_path)
    }
    if len({example.example_id for example in examples}) != len(examples):
        raise ValueError("PopQA examples contain duplicate example IDs")

    development_values: list[float] = []
    exclusions: Counter[str] = Counter()
    proxies: dict[str, float] = {}
    for example in examples:
        seed = seeds.get(example.example_id)
        if seed is None:
            exclusions["missing_seed"] += 1
            continue
        raw_proxy = seed.get("R1", {})
        proxy = raw_proxy.get("proxy_value") if isinstance(raw_proxy, dict) else None
        if isinstance(proxy, bool) or not isinstance(proxy, (int, float)):
            exclusions["missing_proxy"] += 1
            continue
        value = float(proxy)
        if value < 0:
            exclusions["negative_proxy"] += 1
            continue
        proxies[example.example_id] = value
        if example.split == "development":
            development_values.append(value)

    tail_max, middle_max = development_tertile_cutpoints(development_values)
    labeled: list[Example] = []
    kept_workloads: list[dict[str, object]] = []
    counts: Counter[tuple[str, str]] = Counter()
    for example in examples:
        if example.example_id not in proxies:
            continue
        workload = workloads.get(example.example_id)
        if workload is None:
            raise ValueError(f"{example.example_id} has no workload")
        reading = r1_from_frequency(
            proxies[example.example_id],
            tail_max=tail_max,
            middle_max=middle_max,
        )
        if example.split not in {"development", "calibration", "test"}:
            raise ValueError(f"{example.example_id} has unassigned split {example.split!r}")
        entries = example.dimension_values().to_dict()
        entries["R1"] = {"raw": reading.raw, "level": reading.level}
        dimensions = DimensionValues.from_dict(entries)
        assignment = {
            "proxy_source": PROXY_SOURCE,
            "proxy_unit": "upstream popularity score",
            "mapping_method": MAPPING_METHOD,
            "tail_max": tail_max,
            "middle_max": middle_max,
            "claim_limit": (
                "s_pop is a popularity proxy. It is not a document count in the "
                "evaluated model's pretraining corpus."
            ),
        }
        metadata = dict(example.metadata)
        metadata["r1_assignment"] = assignment
        labeled_example = replace(example, metadata=metadata)
        labeled_example = labeled_example.with_dimension_values(dimensions, overwrite=True)
        labeled_example = replace(
            labeled_example,
            group=dimensions.crossed_group(("R1", "R2", "R4", "R5", "R6")),
        )
        labeled.append(labeled_example)
        kept_workloads.append(workload.to_dict())
        counts[(example.split, reading.level)] += 1

    for split in ("development", "calibration", "test"):
        missing = [level for level in LEVELS if counts[(split, level)] == 0]
        if missing:
            raise ValueError(f"{split} is missing R1 levels {missing}")

    manifest = {
        "panel_version": PANEL_VERSION,
        "mapping_method": MAPPING_METHOD,
        "proxy_source": PROXY_SOURCE,
        "proxy_unit": "upstream popularity score",
        "cutpoint_split": "development",
        "tail_max": tail_max,
        "middle_max": middle_max,
        "rule": "tail if value <= tail_max; middle if value <= middle_max; otherwise head",
        "source_examples_sha256": sha256_file(examples_path),
        "source_workloads_sha256": sha256_file(workloads_path),
        "source_seeds_sha256": sha256_file(seeds_path),
        "records": len(labeled),
        "exclusions": dict(exclusions),
        "counts": {
            f"{split}:{level}": counts[(split, level)]
            for split in ("development", "calibration", "test")
            for level in LEVELS
        },
        "claim_limit": (
            "Confirmatory R1 levels on this panel are PopQA subject-popularity "
            "tertiles frozen on the development split. They do not measure "
            "training-corpus frequency for Qwen or Mixtral."
        ),
    }
    write_jsonl(output_dir / "examples.jsonl", (example.to_dict() for example in labeled))
    write_jsonl(output_dir / "workloads.jsonl", kept_workloads)
    manifest_path = output_dir / "BIN_MANIFEST.json"
    _write_manifest(manifest_path, manifest)
    (output_dir / "DATA_CARD.md").write_text(_data_card(manifest), encoding="utf-8")
    return manifest


def _write_manifest(path: Path, manifest: dict[str, object]) -> None:
    existing = path
    if existing.is_file():
        previous = json.loads(existing.read_text(encoding="utf-8"))
        if (
            previous.get("tail_max") != manifest["tail_max"]
            or previous.get("middle_max") != manifest["middle_max"]
            or previous.get("source_seeds_sha256") != manifest["source_seeds_sha256"]
        ):
            raise ValueError(
                "refusing to replace a frozen R1 bin manifest with different cutpoints"
            )
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _data_card(manifest: dict[str, object]) -> str:
    counts = manifest["counts"]
    assert isinstance(counts, dict)
    lines = [
        "# Data card: PopQA R1 popularity-proxy panel",
        "",
        f"- Mapping: `{manifest['mapping_method']}`",
        f"- Cutpoints frozen on: `{manifest['cutpoint_split']}`",
        f"- `tail_max`: {manifest['tail_max']}",
        f"- `middle_max`: {manifest['middle_max']}",
        f"- Rule: {manifest['rule']}",
        f"- Records: {manifest['records']}",
        f"- Exclusions: {json.dumps(manifest['exclusions'], sort_keys=True)}",
        "",
        "## Counts",
        "",
    ]
    for key, value in counts.items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Claim limit",
            "",
            str(manifest["claim_limit"]),
            "",
            "Human audit of the upstream PopQA refinement remains pending. This panel is",
            "eligible for an engineering sealed run. It is not publication-final gold.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples", type=Path, default=Path("data/processed/popqa/examples.jsonl"))
    parser.add_argument("--workloads", type=Path, default=Path("data/processed/popqa/workloads.jsonl"))
    parser.add_argument("--seeds", type=Path, default=Path("data/processed/popqa/condition_seeds.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/popqa_r1"))
    args = parser.parse_args(argv)
    manifest = materialize_popqa_r1_panel(
        examples_path=args.examples,
        workloads_path=args.workloads,
        seeds_path=args.seeds,
        output_dir=args.output_dir,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
