"""Materialize deterministic MuSiQue atomic probes for R5 composition tests.

The processed MuSiQue workload stores each decomposition inside its composite
record.  This module turns those decomposition steps into first-class one-hop
``Example`` and ``WorkloadRecord`` objects while retaining a lossless link back
to every parent composition.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Mapping, Sequence
import unicodedata

from .dimensions import (
    DimensionValues,
    dimension_value,
    r4_from_interpretation_count,
    r5_from_hop_count,
    r6_from_specificity,
)
from .io import read_jsonl, sha256_file, write_jsonl
from .leakage import assert_no_split_leakage, normalized_question_hash
from .schema import Example, WorkloadRecord


MATERIALIZER_VERSION = 1
_VALID_SPLITS = ("development", "calibration", "test")
_PRIMARY_ATOMIC_LINEAGE_KEYS = ("chain_id", "source_fact_id", "question_hash")
_HASH_REFERENCE_RE = re.compile(r"(?<!\w)#(?P<index>[0-9]+)\b")


def _canonical_text(value: object, label: str) -> str:
    text = unicodedata.normalize("NFKC", str(value)).strip()
    text = " ".join(text.split())
    if not text:
        raise ValueError(f"{label} must not be blank")
    return text


def _identity_text(value: object, label: str) -> str:
    return _canonical_text(value, label).casefold()


def _hash_json(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def resolve_musique_placeholders(
    question: str,
    prior_gold_answers: Sequence[str],
    *,
    hop_count: int,
) -> str:
    """Resolve MuSiQue ``#N`` references using earlier gold step answers.

    References within the current chain's hop range are structural references
    and must point strictly backward.  Larger numbers are retained because
    MuSiQue contains literal titles such as ``#9 Dream``.
    """

    if isinstance(hop_count, bool) or not isinstance(hop_count, int) or hop_count < 1:
        raise ValueError("hop_count must be a positive integer")
    answers = tuple(
        _canonical_text(answer, f"prior_gold_answers[{index}]")
        for index, answer in enumerate(prior_gold_answers)
    )
    raw_question = _canonical_text(question, "question")

    def replace(match: re.Match[str]) -> str:
        reference = int(match.group("index"))
        if reference > hop_count:
            return match.group(0)
        if reference < 1:
            raise ValueError("MuSiQue placeholder indices are one-based")
        if reference > len(answers):
            raise ValueError(
                f"unresolved or forward MuSiQue placeholder #{reference}; "
                f"only {len(answers)} prior gold answers are available"
            )
        return answers[reference - 1]

    resolved = _HASH_REFERENCE_RE.sub(replace, raw_question)
    unresolved = [
        int(match.group("index"))
        for match in _HASH_REFERENCE_RE.finditer(resolved)
        if int(match.group("index")) <= hop_count
    ]
    if unresolved:
        rendered = ", ".join(f"#{index}" for index in unresolved)
        raise ValueError(f"unresolved MuSiQue placeholders remain: {rendered}")
    return _canonical_text(resolved, "resolved question")


@dataclass
class _AtomicAccumulator:
    source_step_id: str
    split: str
    answer_identity: str
    title_identity: str
    answer_counts: Counter[str] = field(default_factory=Counter)
    title_counts: Counter[str] = field(default_factory=Counter)
    question_counts: Counter[str] = field(default_factory=Counter)
    raw_question_counts: Counter[str] = field(default_factory=Counter)
    parent_links: dict[tuple[str, str, int], dict[str, object]] = field(
        default_factory=dict
    )

    def add(
        self,
        *,
        split: str,
        answer: str,
        title: str,
        question: str,
        raw_question: str,
        parent_link: Mapping[str, object],
    ) -> None:
        if split != self.split:
            raise ValueError(
                f"MuSiQue source step {self.source_step_id!r} crosses CalibRead "
                f"splits: {self.split!r} and {split!r}"
            )
        if _identity_text(answer, "step answer") != self.answer_identity:
            raise ValueError(
                f"conflicting answers for MuSiQue source step {self.source_step_id!r}"
            )
        if _identity_text(title, "supporting title") != self.title_identity:
            raise ValueError(
                f"conflicting supporting titles for MuSiQue source step "
                f"{self.source_step_id!r}"
            )
        self.answer_counts[answer] += 1
        self.title_counts[title] += 1
        self.question_counts[question] += 1
        self.raw_question_counts[raw_question] += 1
        key = (
            str(parent_link["chain_id"]),
            str(parent_link["composite_example_id"]),
            int(parent_link["position"]),
        )
        if key in self.parent_links and self.parent_links[key] != dict(parent_link):
            raise ValueError(
                f"conflicting parent link for MuSiQue source step {self.source_step_id!r}"
            )
        self.parent_links[key] = dict(parent_link)


@dataclass(frozen=True)
class AtomicBuild:
    """Validated in-memory result of atomic-probe construction."""

    workloads: tuple[WorkloadRecord, ...]
    examples: tuple[Example, ...]
    composite_workloads: tuple[WorkloadRecord, ...]
    composite_examples: tuple[Example, ...]
    input_composite_count: int
    excluded_composite_count: int
    input_decomposition_occurrences: int
    decomposition_occurrences: int
    question_variant_count: int
    cross_split_question_hash_count: int
    excluded_question_hash_count: int
    exclusion_rounds: int


def _preferred(counts: Counter[str]) -> str:
    if not counts:
        raise ValueError("cannot choose a canonical value from an empty collection")
    return min(
        counts,
        key=lambda value: (-counts[value], len(value), value.casefold(), value),
    )


def _sorted_variants(counts: Counter[str]) -> list[dict[str, object]]:
    return [
        {"value": value, "occurrences": counts[value]}
        for value in sorted(counts, key=lambda item: (item.casefold(), item))
    ]


def _atomic_dimensions() -> DimensionValues:
    return DimensionValues(
        {
            "R2": dimension_value("R2", "medium", "medium"),
            "R4": r4_from_interpretation_count(1),
            "R5": r5_from_hop_count(1),
            "R6": r6_from_specificity(
                0.10, general_max=0.33, specialized_max=0.66
            ),
        }
    )


def _load_composites(
    workload_path: str | Path, example_path: str | Path
) -> tuple[list[WorkloadRecord], dict[str, Example]]:
    workloads = [WorkloadRecord.from_dict(row) for row in read_jsonl(workload_path)]
    examples_list = [Example.from_dict(row) for row in read_jsonl(example_path)]
    workload_ids = [record.example_id for record in workloads]
    example_ids = [record.example_id for record in examples_list]
    if len(workload_ids) != len(set(workload_ids)):
        raise ValueError("duplicate composite workload example_id")
    if len(example_ids) != len(set(example_ids)):
        raise ValueError("duplicate composite Example example_id")
    if set(workload_ids) != set(example_ids):
        missing_examples = sorted(set(workload_ids) - set(example_ids))
        missing_workloads = sorted(set(example_ids) - set(workload_ids))
        raise ValueError(
            "MuSiQue workload/Example IDs differ: "
            f"missing_examples={missing_examples[:3]}, "
            f"missing_workloads={missing_workloads[:3]}"
        )
    return workloads, {record.example_id: record for record in examples_list}


def _accumulate_atoms(
    composites: Sequence[WorkloadRecord],
    composite_examples: Mapping[str, Example],
) -> tuple[dict[str, _AtomicAccumulator], int]:
    atoms: dict[str, _AtomicAccumulator] = {}
    decomposition_occurrences = 0

    for composite in sorted(composites, key=lambda record: record.example_id):
        parent_example = composite_examples[composite.example_id]
        if parent_example.split not in _VALID_SPLITS:
            raise ValueError(
                f"composite {composite.example_id!r} has unsupported split "
                f"{parent_example.split!r}"
            )
        if composite.provenance.get("source_id") != "musique":
            raise ValueError(
                f"composite {composite.example_id!r} is not a MuSiQue workload"
            )
        if "R5" not in composite.dimensions:
            raise ValueError(f"composite {composite.example_id!r} lacks R5")
        hop_count = int(composite.dimensions["R5"].raw)
        decomposition = composite.provenance.get("question_decomposition")
        if not isinstance(decomposition, (list, tuple)) or len(decomposition) != hop_count:
            raise ValueError(
                f"composite {composite.example_id!r} has an invalid decomposition"
            )
        if len(composite.constituent_example_ids) != hop_count:
            raise ValueError(
                f"composite {composite.example_id!r} has inconsistent constituents"
            )
        source_row_id = _canonical_text(
            composite.provenance.get("source_row_id", ""), "source_row_id"
        )
        source_split = _canonical_text(
            composite.provenance.get("source_split", ""), "source_split"
        )
        graph_type = _canonical_text(
            composite.provenance.get("graph_type", ""), "graph_type"
        )
        if not composite.chain_id:
            raise ValueError(f"composite {composite.example_id!r} lacks chain_id")

        prior_answers: list[str] = []
        seen_step_ids: set[str] = set()
        for expected_position, raw_step in enumerate(decomposition, start=1):
            if not isinstance(raw_step, Mapping):
                raise ValueError(
                    f"composite {composite.example_id!r} contains a non-object step"
                )
            position = raw_step.get("position")
            if isinstance(position, bool) or position != expected_position:
                raise ValueError(
                    f"composite {composite.example_id!r} has non-sequential step positions"
                )
            source_step_id = _canonical_text(
                raw_step.get("source_step_id", ""), "source_step_id"
            )
            if source_step_id in seen_step_ids:
                raise ValueError(
                    f"composite {composite.example_id!r} repeats source step "
                    f"{source_step_id!r}"
                )
            seen_step_ids.add(source_step_id)
            atomic_example_id = f"musique:singlehop:{source_step_id}"
            if composite.constituent_example_ids[expected_position - 1] != atomic_example_id:
                raise ValueError(
                    f"composite {composite.example_id!r} constituent at position "
                    f"{expected_position} does not match source_step_id"
                )
            raw_question = _canonical_text(raw_step.get("question", ""), "step question")
            answer = _canonical_text(raw_step.get("answer", ""), "step answer")
            title = _canonical_text(
                raw_step.get("supporting_title", ""), "supporting title"
            )
            question = resolve_musique_placeholders(
                raw_question, prior_answers, hop_count=hop_count
            )
            parent_link = {
                "chain_id": composite.chain_id,
                "composite_example_id": composite.example_id,
                "position": expected_position,
                "source_row_id": source_row_id,
                "source_split": source_split,
                "graph_type": graph_type,
            }
            accumulator = atoms.get(source_step_id)
            if accumulator is None:
                accumulator = _AtomicAccumulator(
                    source_step_id=source_step_id,
                    split=parent_example.split,
                    answer_identity=_identity_text(answer, "step answer"),
                    title_identity=_identity_text(title, "supporting title"),
                )
                atoms[source_step_id] = accumulator
            accumulator.add(
                split=parent_example.split,
                answer=answer,
                title=title,
                question=question,
                raw_question=raw_question,
                parent_link=parent_link,
            )
            prior_answers.append(answer)
            decomposition_occurrences += 1

    return atoms, decomposition_occurrences


def _records_from_atoms(
    atoms: Mapping[str, _AtomicAccumulator],
) -> tuple[tuple[WorkloadRecord, ...], tuple[Example, ...], int]:
    workloads: list[WorkloadRecord] = []
    examples: list[Example] = []
    dimensions = _atomic_dimensions()
    question_variant_count = 0
    for source_step_id in sorted(atoms, key=lambda value: (value.casefold(), value)):
        atom = atoms[source_step_id]
        example_id = f"musique:singlehop:{source_step_id}"
        atomic_chain_id = f"musique:atomic:{source_step_id}"
        stable_fact_id = f"musique:fact:{source_step_id}"
        question = _preferred(atom.question_counts)
        accepted_answers = tuple(
            sorted(atom.answer_counts, key=lambda value: (value.casefold(), value))
        )
        title = _preferred(atom.title_counts)
        parent_links = [
            atom.parent_links[key]
            for key in sorted(
                atom.parent_links,
                key=lambda value: (value[0].casefold(), value[1].casefold(), value[2]),
            )
        ]
        question_variants = _sorted_variants(atom.question_counts)
        raw_question_variants = _sorted_variants(atom.raw_question_counts)
        question_variant_count += len(question_variants)
        fact_identity_hash = _hash_json(
            {
                "source_step_id": source_step_id,
                "answer_identity": atom.answer_identity,
                "supporting_title_identity": atom.title_identity,
            }
        )
        provenance = {
            "source_id": "musique_atomic",
            "upstream_source_id": "musique",
            "materializer_version": MATERIALIZER_VERSION,
            "r5_atomic_probe": True,
            "source_step_id": source_step_id,
            "stable_fact_id": stable_fact_id,
            "fact_identity_hash": fact_identity_hash,
            "supporting_title": title,
            "parent_chain_links": parent_links,
            "question_variants": question_variants,
            "raw_question_variants": raw_question_variants,
        }
        interpretations = {"source_interpretation_1": accepted_answers}
        chain_spec = {
            "chain_id": atomic_chain_id,
            "constituents": [stable_fact_id],
            "hops": 1,
        }
        workload = WorkloadRecord(
            example_id=example_id,
            question=question,
            accepted_answers=accepted_answers,
            track="open_ended_stress",
            dimensions=dimensions,
            r4_annotation_hash=_hash_json(interpretations),
            r5_chain_spec_hash=_hash_json(chain_spec),
            interpretation_answers=interpretations,
            chain_id=atomic_chain_id,
            constituent_example_ids=(stable_fact_id,),
            domain_name="general_knowledge",
            missing_reasons={
                "R1": "model_condition_record",
                "R3": "model_condition_record",
            },
            provenance=provenance,
        )
        metadata = {
            "dataset": "musique_atomic",
            "source_id": "musique_atomic",
            "r5_atomic_probe": True,
            "source_step_id": source_step_id,
            "parent_chain_links": parent_links,
            "question_hash": normalized_question_hash(question),
            "track": workload.track,
            "domain_name": workload.domain_name,
            "entity_id": f"musique:title:{title}",
            "chain_id": atomic_chain_id,
            "template_id": f"musique:atomic-source-step:{source_step_id}",
            "source_fact_id": stable_fact_id,
            "source_provenance": provenance,
        }
        example = Example(
            example_id=example_id,
            question=question,
            accepted_answers=accepted_answers,
            group=dimensions.crossed_group(("R2", "R4", "R5", "R6")),
            split=atom.split,
            metadata=dimensions.merge_metadata(metadata),
        )
        WorkloadRecord.from_dict(workload.to_dict())
        Example.from_dict(example.to_dict())
        workloads.append(workload)
        examples.append(example)

    return tuple(workloads), tuple(examples), question_variant_count


def _cross_split_question_hashes(
    atoms: Mapping[str, _AtomicAccumulator],
) -> set[str]:
    splits_by_hash: dict[str, set[str]] = {}
    for atom in atoms.values():
        question_hash = normalized_question_hash(_preferred(atom.question_counts))
        splits_by_hash.setdefault(question_hash, set()).add(atom.split)
    return {
        question_hash
        for question_hash, splits in splits_by_hash.items()
        if len(splits) > 1
    }


def _parents_for_question_hashes(
    atoms: Mapping[str, _AtomicAccumulator], question_hashes: set[str]
) -> set[str]:
    parent_ids: set[str] = set()
    for atom in atoms.values():
        question_hash = normalized_question_hash(_preferred(atom.question_counts))
        if question_hash in question_hashes:
            parent_ids.update(
                str(link["composite_example_id"])
                for link in atom.parent_links.values()
            )
    return parent_ids


def build_musique_atomic_records(
    workload_path: str | Path,
    example_path: str | Path,
) -> AtomicBuild:
    """Build the strict, question-disjoint MuSiQue composition panel.

    Filtering is iterative because removing a parent chain can change the
    deterministic canonical wording selected for a reused source step.  Every
    round removes all chains touching a currently cross-split atomic question;
    no chain or atom is reassigned to a different split.
    """

    all_composites, all_composite_examples = _load_composites(
        workload_path, example_path
    )
    composite_by_id = {record.example_id: record for record in all_composites}
    retained_ids = set(composite_by_id)
    atoms, input_decomposition_occurrences = _accumulate_atoms(
        all_composites, all_composite_examples
    )
    excluded_question_hashes: set[str] = set()
    excluded_ids: set[str] = set()
    exclusion_rounds = 0

    while True:
        cross_split_hashes = _cross_split_question_hashes(atoms)
        if not cross_split_hashes:
            break
        newly_excluded = (
            _parents_for_question_hashes(atoms, cross_split_hashes) & retained_ids
        )
        if not newly_excluded:
            raise ValueError(
                "cross-split atomic question hashes could not be traced to parents"
            )
        excluded_question_hashes.update(cross_split_hashes)
        excluded_ids.update(newly_excluded)
        retained_ids.difference_update(newly_excluded)
        exclusion_rounds += 1
        if not retained_ids:
            raise ValueError(
                "strict question-hash filtering removed every MuSiQue composite"
            )
        retained = [
            composite_by_id[example_id]
            for example_id in sorted(retained_ids)
        ]
        atoms, _ = _accumulate_atoms(retained, all_composite_examples)

    retained_composites = tuple(
        composite_by_id[example_id] for example_id in sorted(retained_ids)
    )
    retained_composite_examples = tuple(
        all_composite_examples[example_id] for example_id in sorted(retained_ids)
    )
    atoms, decomposition_occurrences = _accumulate_atoms(
        retained_composites, all_composite_examples
    )
    workloads, examples, question_variant_count = _records_from_atoms(atoms)
    if not workloads:
        raise ValueError("MuSiQue inputs produced no strict atomic probes")
    assert_no_split_leakage(
        examples, disjoint_keys=_PRIMARY_ATOMIC_LINEAGE_KEYS
    )
    assert_no_split_leakage(
        retained_composite_examples,
        disjoint_keys=_PRIMARY_ATOMIC_LINEAGE_KEYS,
    )
    final_cross_split_hashes = _cross_split_question_hashes(atoms)
    if final_cross_split_hashes:
        raise ValueError("strict atomic panel still contains question-hash leakage")
    parent_ids = {
        str(link["composite_example_id"])
        for atom in atoms.values()
        for link in atom.parent_links.values()
    }
    if parent_ids != retained_ids:
        raise ValueError(
            "strict atomic parent links do not exactly cover retained composites"
        )
    return AtomicBuild(
        workloads=workloads,
        examples=examples,
        composite_workloads=retained_composites,
        composite_examples=retained_composite_examples,
        input_composite_count=len(all_composites),
        excluded_composite_count=len(excluded_ids),
        input_decomposition_occurrences=input_decomposition_occurrences,
        decomposition_occurrences=decomposition_occurrences,
        question_variant_count=question_variant_count,
        cross_split_question_hash_count=0,
        excluded_question_hash_count=len(excluded_question_hashes),
        exclusion_rounds=exclusion_rounds,
    )


def _audit_records(examples: Sequence[Example], audit_size: int) -> list[dict[str, object]]:
    if isinstance(audit_size, bool) or not isinstance(audit_size, int) or audit_size < 0:
        raise ValueError("audit_size must be a nonnegative integer")
    buckets: dict[str, list[Example]] = {
        split: sorted(
            (example for example in examples if example.split == split),
            key=lambda item: (
                hashlib.sha256(item.example_id.encode("utf-8")).hexdigest(),
                item.example_id,
            ),
        )
        for split in _VALID_SPLITS
    }
    selected: list[Example] = []
    offsets = {split: 0 for split in _VALID_SPLITS}
    while len(selected) < min(audit_size, len(examples)):
        progressed = False
        for split in _VALID_SPLITS:
            offset = offsets[split]
            if offset < len(buckets[split]) and len(selected) < audit_size:
                selected.append(buckets[split][offset])
                offsets[split] += 1
                progressed = True
        if not progressed:
            break
    rows: list[dict[str, object]] = []
    for example in selected:
        links = example.metadata["parent_chain_links"]
        provenance = example.metadata["source_provenance"]
        rows.append(
            {
                "example_id": example.example_id,
                "split": example.split,
                "source_step_id": example.metadata["source_step_id"],
                "question": example.question,
                "accepted_answers": json.dumps(
                    list(example.accepted_answers), ensure_ascii=False
                ),
                "supporting_title": provenance["supporting_title"],
                "parent_chain_count": len(links),
                "parent_chain_links": json.dumps(
                    [dict(link) for link in links],
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "review_status": "pending",
                "review_notes": "",
            }
        )
    return rows


_AUDIT_FIELDS = (
    "example_id",
    "split",
    "source_step_id",
    "question",
    "accepted_answers",
    "supporting_title",
    "parent_chain_count",
    "parent_chain_links",
    "review_status",
    "review_notes",
)


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=_AUDIT_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(value)
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def materialize_musique_atomic_probes(
    *,
    input_dir: str | Path = Path("data/processed/musique"),
    output_dir: str | Path = Path("data/processed/musique_atomic"),
    audit_size: int = 60,
) -> Path:
    """Write atomic records, deterministic audit sample, and hash manifest."""

    source_dir = Path(input_dir)
    destination = Path(output_dir)
    workload_input = source_dir / "workloads.jsonl"
    example_input = source_dir / "examples.jsonl"
    build = build_musique_atomic_records(workload_input, example_input)
    destination.mkdir(parents=True, exist_ok=True)
    workload_output = destination / "workloads.jsonl"
    example_output = destination / "examples.jsonl"
    composite_workload_output = destination / "composite_workloads.jsonl"
    composite_example_output = destination / "composite_examples.jsonl"
    audit_output = destination / "audit_sample.csv"
    card_output = destination / "DATA_CARD.md"
    write_jsonl(workload_output, (record.to_dict() for record in build.workloads))
    write_jsonl(example_output, (record.to_dict() for record in build.examples))
    write_jsonl(
        composite_workload_output,
        (record.to_dict() for record in build.composite_workloads),
    )
    write_jsonl(
        composite_example_output,
        (record.to_dict() for record in build.composite_examples),
    )
    audit_rows = _audit_records(build.examples, audit_size)
    _write_csv(audit_output, audit_rows)

    split_counts = Counter(example.split for example in build.examples)
    composite_split_counts = Counter(
        example.split for example in build.composite_examples
    )
    parent_link_count = sum(
        len(example.metadata["parent_chain_links"]) for example in build.examples
    )
    card = f"""# Data card: MuSiQue atomic probes

- Source ID: `musique_atomic`
- Upstream processed source: `musique`
- Materializer: `calibread.r5_atoms` version {MATERIALIZER_VERSION}
- Input composite records: {build.input_composite_count}
- Strict retained composite records: {len(build.composite_examples)}
- Excluded composite records: {build.excluded_composite_count}
- Cross-split atomic question hashes triggering exclusion: {build.excluded_question_hash_count}
- Strict-filter rounds: {build.exclusion_rounds}
- Atomic records: {len(build.examples)}
- Input decomposition occurrences: {build.input_decomposition_occurrences}
- Decomposition occurrences: {build.decomposition_occurrences}
- Deduplicated occurrences: {build.decomposition_occurrences - len(build.examples)}
- Development/calibration/test: {split_counts['development']} / {split_counts['calibration']} / {split_counts['test']}
- Audit sample rows: {len(audit_rows)}; human review remains pending
- Final cross-split resolved-question hashes: {build.cross_split_question_hash_count}

## Construction

Each MuSiQue decomposition step is emitted as a one-hop R5 probe. Structural
`#N` references are replaced with earlier gold step answers. Stable upstream
step IDs deduplicate facts, while every parent chain ID, composite example ID,
position, source row ID, and upstream split remains in `parent_chain_links`.

Before output, the materializer iteratively removes every composite chain that
contains an atomic question hash seen in more than one CalibRead split. It then
rebuilds the atoms and parent links only from retained chains and asserts strict
question-hash, source-fact, and chain separation. It also fails closed on
cross-split source-fact reuse, conflicting answers or supporting titles,
malformed chain positions, mismatched constituent IDs, and unresolved or
forward structural placeholders. Literal titles whose number is outside the
current chain, such as `#9 Dream`, are preserved.

## Intended use and limitations

These records are evaluation probes, not training data. Placeholder replacement
uses gold prior answers only to create independently answerable atomic questions;
models receive only the resulting standalone question. Decomposition questions
retain MuSiQue's original terse wording, and the audit sample requires human
review before publication claims are made.
"""
    _write_text(card_output, card)
    output_files = (
        workload_output,
        example_output,
        composite_workload_output,
        composite_example_output,
        audit_output,
        card_output,
    )
    manifest = {
        "manifest_version": 1,
        "materializer": "calibread.r5_atoms",
        "materializer_version": MATERIALIZER_VERSION,
        "source_id": "musique_atomic",
        "inputs": {
            "workloads.jsonl": {
                "sha256": sha256_file(workload_input),
                "bytes": workload_input.stat().st_size,
            },
            "examples.jsonl": {
                "sha256": sha256_file(example_input),
                "bytes": example_input.stat().st_size,
            },
        },
        "input_composite_records": build.input_composite_count,
        "composite_records": len(build.composite_examples),
        "excluded_composite_records": build.excluded_composite_count,
        "input_decomposition_occurrences": build.input_decomposition_occurrences,
        "decomposition_occurrences": build.decomposition_occurrences,
        "atomic_records": len(build.examples),
        "deduplicated_occurrences": (
            build.decomposition_occurrences - len(build.examples)
        ),
        "question_variant_count": build.question_variant_count,
        "cross_split_question_hash_count": build.cross_split_question_hash_count,
        "excluded_question_hash_count": build.excluded_question_hash_count,
        "exclusion_rounds": build.exclusion_rounds,
        "exclusions": {
            "cross_split_atomic_question_hash_chains": (
                build.excluded_composite_count
            ),
            "cross_split_atomic_question_hashes": (
                build.excluded_question_hash_count
            ),
        },
        "parent_chain_links": parent_link_count,
        "split_counts": dict(sorted(split_counts.items())),
        "composite_split_counts": dict(sorted(composite_split_counts.items())),
        "audit_rows": len(audit_rows),
        "checks": {
            "schema_validation": "passed",
            "placeholder_resolution": "passed",
            "stable_fact_deduplication": "passed",
            "cross_split_atomic_facts": "passed",
            "cross_split_resolved_question_hashes": "passed",
            "strict_question_hash_filter": "passed",
            "filtered_composite_schema": "passed",
            "conflicting_answers": "none",
            "conflicting_supporting_titles": "none",
            "parent_chain_link_completeness": "passed",
            "human_audit": "pending",
        },
        "outputs": {
            path.name: {"sha256": sha256_file(path), "bytes": path.stat().st_size}
            for path in output_files
        },
    }
    _write_json(destination / "ATOMIC_MANIFEST.json", manifest)
    return destination


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize canonical MuSiQue atomic probes for R5"
    )
    parser.add_argument(
        "--input-dir", type=Path, default=Path("data/processed/musique")
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/processed/musique_atomic")
    )
    parser.add_argument("--audit-size", type=int, default=60)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = materialize_musique_atomic_probes(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        audit_size=args.audit_size,
    )
    print(f"materialized MuSiQue atomic probes at {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "AtomicBuild",
    "MATERIALIZER_VERSION",
    "build_musique_atomic_records",
    "materialize_musique_atomic_probes",
    "resolve_musique_placeholders",
]
