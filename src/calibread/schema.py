"""Validated, serializable records shared by CalibRead stages."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from math import isfinite
from types import MappingProxyType
from typing import Callable, Iterable, Literal, Mapping, Sequence

from .dimensions import (
    DIMENSIONS_METADATA_KEY,
    DimensionValues,
    dimension_spec,
    r1_from_frequency,
    r3_from_dates,
)


EvaluationTrack = Literal["finite_label_certified", "open_ended_stress"]
ScoreKind = Literal["raw", "probability", "legacy_probability"]
CorrectnessScorer = Callable[[str, Sequence[str]], bool | int]
_TRACKS = {"finite_label_certified", "open_ended_stress"}
_SCORE_KINDS = {"raw", "probability", "legacy_probability"}
_READ_ACTIONS = {"answer", "set", "abstain"}
R3_MONTH_TOLERANCE = 1e-6


def _nonempty(value: object, name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    return normalized


def _sha256_hex(value: object, name: str) -> str:
    normalized = _nonempty(value, name).casefold()
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise ValueError(f"{name} must be a 64-character SHA-256 hex digest")
    return normalized


def _string_tuple(values: Sequence[object], name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} must be a sequence, not a string")
    normalized = tuple(str(value).strip() for value in values)
    if any(not value for value in normalized):
        raise ValueError(f"{name} must contain only nonempty strings")
    return normalized


def _sequence_field(value: object, name: str) -> tuple[object, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{name} must be a list or tuple")
    return tuple(value)


def _freeze_json(value: object, path: str) -> object:
    if isinstance(value, Mapping):
        normalized: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise ValueError(f"{path} keys must be nonempty strings")
            normalized[key] = _freeze_json(item, f"{path}.{key}")
        return MappingProxyType(normalized)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item, f"{path}[]") for item in value)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError(f"{path} must not contain non-finite floats")
        return value
    raise ValueError(f"{path} must contain only JSON-compatible values")


def _thaw_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _frozen_mapping(
    value: Mapping[str, object], name: str = "mapping"
) -> Mapping[str, object]:
    frozen = _freeze_json(value, name)
    if not isinstance(frozen, Mapping):
        raise ValueError(f"{name} must be a mapping")
    return frozen


@dataclass(frozen=True)
class Example:
    """One question with references and predeclared evaluation metadata."""

    example_id: str
    question: str
    accepted_answers: tuple[str, ...]
    group: str = "all"
    split: str = "unassigned"
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.accepted_answers, (str, bytes)):
            raise ValueError("accepted_answers must be a sequence of answer strings")
        answers = tuple(str(answer) for answer in self.accepted_answers)
        if not self.example_id.strip():
            raise ValueError("example_id must not be empty")
        if not self.question.strip():
            raise ValueError("question must not be empty")
        if not answers or any(not answer.strip() for answer in answers):
            raise ValueError("accepted_answers must contain nonempty strings")
        if not self.group:
            raise ValueError("group must not be empty")
        if not self.split:
            raise ValueError("split must not be empty")
        object.__setattr__(self, "accepted_answers", answers)
        object.__setattr__(self, "metadata", _frozen_mapping(self.metadata, "metadata"))

        if DIMENSIONS_METADATA_KEY in self.metadata:
            DimensionValues.from_metadata(self.metadata)

    def with_dimension_values(
        self, dimensions: DimensionValues, *, overwrite: bool = False
    ) -> "Example":
        """Return a copy carrying dimensions without changing the constructor."""

        return replace(
            self,
            metadata=dimensions.merge_metadata(self.metadata, overwrite=overwrite),
        )

    def dimension_values(self) -> DimensionValues:
        """Return validated R1--R7 readings stored in metadata."""

        return DimensionValues.from_metadata(self.metadata)

    def to_dict(self) -> dict[str, object]:
        return {
            "example_id": self.example_id,
            "question": self.question,
            "accepted_answers": list(self.accepted_answers),
            "group": self.group,
            "split": self.split,
            "metadata": _thaw_json(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "Example":
        answers = value.get("accepted_answers")
        if not isinstance(answers, (list, tuple)):
            raise ValueError("accepted_answers must be a list or tuple")
        metadata = value.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise ValueError("metadata must be a mapping")
        return cls(
            example_id=str(value.get("example_id", "")),
            question=str(value.get("question", "")),
            accepted_answers=tuple(str(answer) for answer in answers),
            group=str(value.get("group", "all")),
            split=str(value.get("split", "unassigned")),
            metadata=dict(metadata),
        )


@dataclass(frozen=True)
class Prediction:
    """Backward-compatible point prediction.

    New pipeline records should declare score_kind and use GenerationRecord. The
    legacy_probability default preserves old callers but must be explicitly opted into by the
    evaluator; it is not evidence that an uncalibrated score is a correctness probability.
    """

    example_id: str
    answer: str
    confidence: float
    score_kind: ScoreKind = "legacy_probability"
    score_source: str = "legacy_confidence"
    calibrator_id: str | None = "legacy_unspecified"

    def __post_init__(self) -> None:
        confidence = float(self.confidence)
        if not self.example_id.strip():
            raise ValueError("example_id must not be empty")
        if not isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be finite and lie in [0, 1]")
        if self.score_kind not in _SCORE_KINDS:
            raise ValueError("score_kind must be raw, probability, or legacy_probability")
        score_source = _nonempty(self.score_source, "score_source")
        calibrator_id = None if self.calibrator_id is None else str(self.calibrator_id).strip()
        if self.score_kind == "probability" and not calibrator_id:
            raise ValueError(
                "probability scores require a calibrator_id (use 'identity' if applicable)"
            )
        object.__setattr__(self, "answer", str(self.answer))
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "score_source", score_source)
        object.__setattr__(self, "calibrator_id", calibrator_id)

    def to_dict(self) -> dict[str, object]:
        return {
            "example_id": self.example_id,
            "answer": self.answer,
            "confidence": self.confidence,
            "score_kind": self.score_kind,
            "score_source": self.score_source,
            "calibrator_id": self.calibrator_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "Prediction":
        return cls(
            example_id=str(value.get("example_id", "")),
            answer=str(value.get("answer", "")),
            confidence=float(value.get("confidence", float("nan"))),
            score_kind=str(value.get("score_kind", "legacy_probability")),  # type: ignore[arg-type]
            score_source=str(value.get("score_source", "legacy_confidence")),
            calibrator_id=(
                None
                if value.get("calibrator_id", "legacy_unspecified") is None
                else str(value.get("calibrator_id", "legacy_unspecified"))
            ),
        )


@dataclass(frozen=True)
class WorkloadRecord:
    """One model-independent P03 query record.

    R1 and R3 live in ModelConditionRecord because they vary with the immutable model
    snapshot. R2, R4, R5, and R6 are query properties and are frozen here once.
    """

    example_id: str
    question: str
    accepted_answers: tuple[str, ...]
    track: EvaluationTrack
    dimensions: DimensionValues | Mapping[str, object]
    r4_annotation_hash: str
    r5_chain_spec_hash: str
    candidate_universe: tuple[str, ...] = ()
    interpretation_answers: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    chain_id: str | None = None
    constituent_example_ids: tuple[str, ...] = ()
    domain_name: str | None = None
    allowed_actions: tuple[str, ...] = ("answer", "set", "abstain")
    missing_reasons: Mapping[str, str] = field(default_factory=dict)
    provenance: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.interpretation_answers, Mapping):
            raise ValueError("interpretation_answers must be a mapping")
        if not isinstance(self.missing_reasons, Mapping):
            raise ValueError("missing_reasons must be a mapping")
        if not isinstance(self.provenance, Mapping):
            raise ValueError("provenance must be a mapping")
        object.__setattr__(self, "example_id", _nonempty(self.example_id, "example_id"))
        object.__setattr__(self, "question", _nonempty(self.question, "question"))
        answers = _string_tuple(self.accepted_answers, "accepted_answers")
        if not answers:
            raise ValueError("accepted_answers must not be empty")
        if len(set(answers)) != len(answers):
            raise ValueError("accepted_answers must be unique")
        if self.track not in _TRACKS:
            raise ValueError("track must be finite_label_certified or open_ended_stress")
        r4_annotation_hash = _sha256_hex(
            self.r4_annotation_hash, "r4_annotation_hash"
        )
        r5_chain_spec_hash = _sha256_hex(
            self.r5_chain_spec_hash, "r5_chain_spec_hash"
        )
        candidate_universe = _string_tuple(self.candidate_universe, "candidate_universe")
        if self.track == "finite_label_certified" and not candidate_universe:
            raise ValueError(
                "finite_label_certified workloads require a nonempty candidate_universe"
            )
        if len(set(candidate_universe)) != len(candidate_universe):
            raise ValueError("candidate_universe must be unique")
        constituents = _string_tuple(
            self.constituent_example_ids, "constituent_example_ids"
        )
        actions = _string_tuple(self.allowed_actions, "allowed_actions")
        if (
            not actions
            or len(set(actions)) != len(actions)
            or not set(actions) <= _READ_ACTIONS
        ):
            raise ValueError("allowed_actions must be unique answer/set/abstain values")
        if "abstain" not in actions:
            raise ValueError("allowed_actions must include abstain for fail-closed behavior")
        if isinstance(self.dimensions, DimensionValues):
            dimensions = self.dimensions
        elif isinstance(self.dimensions, Mapping):
            dimensions = DimensionValues.from_dict(self.dimensions)
        else:
            raise ValueError("dimensions must be DimensionValues or a mapping")
        if "R7" in dimensions:
            raise ValueError("R7 is a decision/result dimension, not a workload field")
        missing_reasons: dict[str, str] = {}
        for identifier, reason in self.missing_reasons.items():
            if not isinstance(reason, str):
                raise ValueError("missing reasons must be strings")
            code = dimension_spec(str(identifier)).code
            if code == "R7":
                raise ValueError("R7 cannot have a workload missing reason")
            if code in missing_reasons:
                raise ValueError(f"duplicate missing reason for {code}")
            missing_reasons[code] = _nonempty(reason, f"missing_reasons[{code}]")
        overlap = set(dimensions.entries).intersection(missing_reasons)
        if overlap:
            raise ValueError(
                "dimensions cannot also have missing reasons: "
                + ", ".join(sorted(overlap))
            )
        interpretations: dict[str, tuple[str, ...]] = {}
        for identifier, values in self.interpretation_answers.items():
            key = _nonempty(identifier, "interpretation identifier")
            mapped = _string_tuple(values, f"interpretation_answers[{key!r}]")
            if not mapped:
                raise ValueError("each interpretation must have at least one accepted answer")
            interpretations[key] = mapped
        chain_id = (
            None if self.chain_id is None else _nonempty(self.chain_id, "chain_id")
        )
        domain_name = (
            None
            if self.domain_name is None
            else _nonempty(self.domain_name, "domain_name")
        )
        if self.track == "finite_label_certified":
            candidate_set = set(candidate_universe)
            absent_answers = set(answers) - candidate_set
            if absent_answers:
                raise ValueError(
                    "finite-label candidate_universe must contain every accepted answer"
                )
            interpretation_union = {
                answer
                for interpretation in interpretations.values()
                for answer in interpretation
            }
            if interpretation_union - candidate_set:
                raise ValueError(
                    "finite-label candidate_universe must contain every interpretation answer"
                )
        if "R4" in dimensions:
            interpretation_count = int(dimensions["R4"].raw)
            if len(interpretations) != interpretation_count:
                raise ValueError(
                    "interpretation_answers count must equal audited R4 raw count"
                )
            interpretation_union = {
                answer
                for interpretation in interpretations.values()
                for answer in interpretation
            }
            if interpretation_union != set(answers):
                raise ValueError(
                    "interpretation answer union must equal accepted_answers"
                )
        if "R5" in dimensions:
            hop_count = int(dimensions["R5"].raw)
            if chain_id is None:
                raise ValueError("R5 requires chain_id")
            if len(set(constituents)) != len(constituents):
                raise ValueError("R5 constituent_example_ids must be unique")
            if self.example_id in constituents:
                raise ValueError(
                    "R5 constituent_example_ids must not contain the workload example_id"
                )
            if len(constituents) != hop_count:
                raise ValueError(
                    "constituent_example_ids count must equal audited R5 raw hop count"
                )
        if "R6" in dimensions and domain_name is None:
            raise ValueError("R6 requires domain_name")
        object.__setattr__(self, "accepted_answers", answers)
        object.__setattr__(self, "candidate_universe", candidate_universe)
        object.__setattr__(self, "constituent_example_ids", constituents)
        object.__setattr__(self, "allowed_actions", actions)
        object.__setattr__(self, "dimensions", dimensions)
        object.__setattr__(self, "r4_annotation_hash", r4_annotation_hash)
        object.__setattr__(self, "r5_chain_spec_hash", r5_chain_spec_hash)
        object.__setattr__(
            self, "missing_reasons", MappingProxyType(missing_reasons)
        )
        object.__setattr__(
            self, "interpretation_answers", MappingProxyType(interpretations)
        )
        object.__setattr__(self, "chain_id", chain_id)
        object.__setattr__(self, "domain_name", domain_name)
        object.__setattr__(
            self, "provenance", _frozen_mapping(self.provenance, "provenance")
        )
        self.validate_dimension_completeness()

    def validate_dimension_completeness(self) -> None:
        """Require model-independent axes here and route R1/R3 to condition records."""

        expected_dimensions = {"R2", "R4", "R5", "R6"}
        if set(self.dimensions.entries) != expected_dimensions:
            raise ValueError(
                "WorkloadRecord dimensions must contain exactly R2, R4, R5, and R6"
            )
        expected_reasons = {
            "R1": "model_condition_record",
            "R3": "model_condition_record",
        }
        if dict(self.missing_reasons) != expected_reasons:
            raise ValueError(
                "WorkloadRecord must route R1 and R3 to model_condition_record"
            )

    @property
    def ambiguity_annotation_complete(self) -> bool:
        """Return whether the frozen R4 annotation is internally complete."""

        interpretation_union = {
            answer
            for interpretation in self.interpretation_answers.values()
            for answer in interpretation
        }
        return (
            bool(self.r4_annotation_hash)
            and len(self.interpretation_answers) == int(self.dimensions["R4"].raw)
            and interpretation_union == set(self.accepted_answers)
        )

    def ambiguity_complete_for(self, candidates: Iterable[str]) -> bool:
        """Derive completeness from audited R4 plus the returned candidate coverage."""

        if isinstance(candidates, (str, bytes)):
            raise ValueError("candidates must be an iterable of candidate strings")
        normalized = tuple(str(candidate).strip() for candidate in candidates)
        if any(not candidate for candidate in normalized):
            raise ValueError("candidates must contain only nonempty strings")
        interpretation_union = {
            answer
            for interpretation in self.interpretation_answers.values()
            for answer in interpretation
        }
        return self.ambiguity_annotation_complete and interpretation_union <= set(
            normalized
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "example_id": self.example_id,
            "question": self.question,
            "accepted_answers": list(self.accepted_answers),
            "track": self.track,
            "r4_annotation_hash": self.r4_annotation_hash,
            "r5_chain_spec_hash": self.r5_chain_spec_hash,
            "candidate_universe": list(self.candidate_universe),
            "interpretation_answers": {
                key: list(values) for key, values in self.interpretation_answers.items()
            },
            "chain_id": self.chain_id,
            "constituent_example_ids": list(self.constituent_example_ids),
            "domain_name": self.domain_name,
            "allowed_actions": list(self.allowed_actions),
            "dimensions": self.dimensions.to_dict(),
            "missing_reasons": dict(self.missing_reasons),
            "provenance": _thaw_json(self.provenance),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "WorkloadRecord":
        interpretations = value.get("interpretation_answers", {})
        provenance = value.get("provenance", {})
        dimensions = value.get("dimensions", {})
        missing_reasons = value.get("missing_reasons", {})
        if not isinstance(interpretations, Mapping):
            raise ValueError("interpretation_answers must be a mapping")
        if not isinstance(provenance, Mapping):
            raise ValueError("provenance must be a mapping")
        if not isinstance(dimensions, Mapping):
            raise ValueError("dimensions must be a mapping")
        if not isinstance(missing_reasons, Mapping):
            raise ValueError("missing_reasons must be a mapping")
        return cls(
            example_id=str(value.get("example_id", "")),
            question=str(value.get("question", "")),
            accepted_answers=_sequence_field(
                value.get("accepted_answers", ()), "accepted_answers"
            ),
            track=str(value.get("track", "")),  # type: ignore[arg-type]
            r4_annotation_hash=str(value.get("r4_annotation_hash", "")),
            r5_chain_spec_hash=str(value.get("r5_chain_spec_hash", "")),
            candidate_universe=_sequence_field(
                value.get("candidate_universe", ()), "candidate_universe"
            ),
            interpretation_answers={
                str(key): _sequence_field(
                    items, f"interpretation_answers[{key!r}]"
                )
                for key, items in interpretations.items()
            },
            chain_id=(
                None if value.get("chain_id") is None else str(value["chain_id"])
            ),
            constituent_example_ids=_sequence_field(
                value.get("constituent_example_ids", ()),
                "constituent_example_ids",
            ),
            domain_name=(
                None
                if value.get("domain_name") is None
                else str(value["domain_name"])
            ),
            allowed_actions=_sequence_field(
                value.get("allowed_actions", ("answer", "set", "abstain")),
                "allowed_actions",
            ),
            dimensions=DimensionValues.from_dict(dimensions),
            missing_reasons={
                str(identifier): reason  # type: ignore[dict-item]
                for identifier, reason in missing_reasons.items()
            },
            provenance=provenance,
        )


@dataclass(frozen=True)
class ModelConditionRecord:
    """Model-specific R1/R3 condition for one model-independent workload.

    R3 signed months derived from ISO dates may differ by at most
    R3_MONTH_TOLERANCE because serialized decimal values are rounded.
    """

    example_id: str
    model_snapshot_id: str
    condition_version: str
    dimensions: DimensionValues | Mapping[str, object]
    r1_frequency_source: str
    r1_corpus_snapshot_id: str
    r1_exposure_unit: str
    r1_value_kind: Literal["exact", "proxy"]
    r1_tail_max: float
    r1_middle_max: float
    r1_bin_rule_hash: str
    r3_event_date: str
    r3_model_cutoff_date: str
    r3_cutoff_source: str
    r3_cutoff_uncertainty: str
    r3_value_kind: Literal["exact", "proxy"]
    r3_bin_rule_hash: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "example_id",
            "model_snapshot_id",
            "condition_version",
            "r1_frequency_source",
            "r1_corpus_snapshot_id",
            "r1_exposure_unit",
            "r3_event_date",
            "r3_model_cutoff_date",
            "r3_cutoff_source",
            "r3_cutoff_uncertainty",
        ):
            object.__setattr__(self, name, _nonempty(getattr(self, name), name))
        object.__setattr__(
            self,
            "r1_bin_rule_hash",
            _sha256_hex(self.r1_bin_rule_hash, "r1_bin_rule_hash"),
        )
        object.__setattr__(
            self,
            "r3_bin_rule_hash",
            _sha256_hex(self.r3_bin_rule_hash, "r3_bin_rule_hash"),
        )
        if self.r1_value_kind not in {"exact", "proxy"}:
            raise ValueError("r1_value_kind must be exact or proxy")
        if self.r3_value_kind not in {"exact", "proxy"}:
            raise ValueError("r3_value_kind must be exact or proxy")
        if isinstance(self.dimensions, DimensionValues):
            dimensions = self.dimensions
        elif isinstance(self.dimensions, Mapping):
            dimensions = DimensionValues.from_dict(self.dimensions)
        else:
            raise ValueError("dimensions must be DimensionValues or a mapping")
        if set(dimensions.entries) != {"R1", "R3"}:
            raise ValueError(
                "ModelConditionRecord dimensions must contain exactly R1 and R3"
            )
        r1_tail_max = float(self.r1_tail_max)
        r1_middle_max = float(self.r1_middle_max)
        if not isfinite(r1_tail_max) or not isfinite(r1_middle_max):
            raise ValueError("R1 cutpoints must be finite")
        derived_r1 = r1_from_frequency(
            float(dimensions["R1"].raw),
            tail_max=r1_tail_max,
            middle_max=r1_middle_max,
        )
        if derived_r1 != dimensions["R1"]:
            raise ValueError(
                "R1 raw value and level must match the frozen condition cutpoints"
            )
        derived_r3 = r3_from_dates(
            self.r3_event_date, self.r3_model_cutoff_date
        )
        recorded_r3 = dimensions["R3"]
        if (
            abs(float(recorded_r3.raw) - float(derived_r3.raw))
            > R3_MONTH_TOLERANCE
            or recorded_r3.level != derived_r3.level
        ):
            raise ValueError(
                "R3 raw signed months and level must match event/cutoff dates "
                f"within tolerance {R3_MONTH_TOLERANCE}"
            )
        if not isinstance(self.metadata, Mapping):
            raise ValueError("metadata must be a mapping")
        object.__setattr__(self, "dimensions", dimensions)
        object.__setattr__(self, "r1_tail_max", r1_tail_max)
        object.__setattr__(self, "r1_middle_max", r1_middle_max)
        object.__setattr__(
            self, "metadata", _frozen_mapping(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "example_id": self.example_id,
            "model_snapshot_id": self.model_snapshot_id,
            "condition_version": self.condition_version,
            "dimensions": self.dimensions.to_dict(),
            "r1_frequency_source": self.r1_frequency_source,
            "r1_corpus_snapshot_id": self.r1_corpus_snapshot_id,
            "r1_exposure_unit": self.r1_exposure_unit,
            "r1_value_kind": self.r1_value_kind,
            "r1_tail_max": self.r1_tail_max,
            "r1_middle_max": self.r1_middle_max,
            "r1_bin_rule_hash": self.r1_bin_rule_hash,
            "r3_event_date": self.r3_event_date,
            "r3_model_cutoff_date": self.r3_model_cutoff_date,
            "r3_cutoff_source": self.r3_cutoff_source,
            "r3_cutoff_uncertainty": self.r3_cutoff_uncertainty,
            "r3_value_kind": self.r3_value_kind,
            "r3_bin_rule_hash": self.r3_bin_rule_hash,
            "metadata": _thaw_json(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "ModelConditionRecord":
        dimensions = value.get("dimensions", {})
        metadata = value.get("metadata", {})
        if not isinstance(dimensions, Mapping):
            raise ValueError("dimensions must be a mapping")
        if not isinstance(metadata, Mapping):
            raise ValueError("metadata must be a mapping")
        return cls(
            example_id=str(value.get("example_id", "")),
            model_snapshot_id=str(value.get("model_snapshot_id", "")),
            condition_version=str(value.get("condition_version", "")),
            dimensions=DimensionValues.from_dict(dimensions),
            r1_frequency_source=str(value.get("r1_frequency_source", "")),
            r1_corpus_snapshot_id=str(value.get("r1_corpus_snapshot_id", "")),
            r1_exposure_unit=str(value.get("r1_exposure_unit", "")),
            r1_value_kind=str(value.get("r1_value_kind", "")),  # type: ignore[arg-type]
            r1_tail_max=float(value.get("r1_tail_max", float("nan"))),
            r1_middle_max=float(value.get("r1_middle_max", float("nan"))),
            r1_bin_rule_hash=str(value.get("r1_bin_rule_hash", "")),
            r3_event_date=str(value.get("r3_event_date", "")),
            r3_model_cutoff_date=str(value.get("r3_model_cutoff_date", "")),
            r3_cutoff_source=str(value.get("r3_cutoff_source", "")),
            r3_cutoff_uncertainty=str(
                value.get("r3_cutoff_uncertainty", "")
            ),
            r3_value_kind=str(value.get("r3_value_kind", "")),  # type: ignore[arg-type]
            r3_bin_rule_hash=str(value.get("r3_bin_rule_hash", "")),
            metadata=metadata,
        )

    def condition_hash(self) -> str:
        """Return the canonical SHA-256 identity used by generation records."""

        payload = json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


def condition_table_hash(records: Iterable[ModelConditionRecord]) -> str:
    """Hash a condition table independently of input row order."""

    materialized = tuple(records)
    if not materialized:
        raise ValueError("condition table must not be empty")
    keyed: dict[tuple[str, str, str], ModelConditionRecord] = {}
    for record in materialized:
        if not isinstance(record, ModelConditionRecord):
            raise ValueError("condition table must contain ModelConditionRecord values")
        key = (
            record.example_id,
            record.model_snapshot_id,
            record.condition_version,
        )
        if key in keyed:
            raise ValueError(f"duplicate model-condition key {key!r}")
        keyed[key] = record
    payload = json.dumps(
        [keyed[key].to_dict() for key in sorted(keyed)],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class GenerationRecord:
    """Raw generation plus an explicitly typed score and candidate list."""

    generation_id: str
    run_id: str
    example_id: str
    model_snapshot_id: str
    condition_hash: str
    track: EvaluationTrack
    raw_text: str
    candidates: tuple[str, ...]
    score: float
    score_kind: Literal["raw", "probability"]
    score_source: str
    calibrator_id: str | None = None
    normalization_contract: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("generation_id", "run_id", "example_id", "model_snapshot_id"):
            object.__setattr__(self, name, _nonempty(getattr(self, name), name))
        object.__setattr__(
            self,
            "condition_hash",
            _sha256_hex(self.condition_hash, "condition_hash"),
        )
        if self.track not in _TRACKS:
            raise ValueError("track must be finite_label_certified or open_ended_stress")
        score = float(self.score)
        if not isfinite(score):
            raise ValueError("score must be finite")
        if self.score_kind not in {"raw", "probability"}:
            raise ValueError("score_kind must be raw or probability")
        if self.score_kind == "probability" and not 0.0 <= score <= 1.0:
            raise ValueError("probability scores must lie in [0, 1]")
        source = _nonempty(self.score_source, "score_source")
        calibrator = (
            None if self.calibrator_id is None else str(self.calibrator_id).strip()
        )
        if self.score_kind == "probability" and not calibrator:
            raise ValueError(
                "probability scores require a calibrator_id (use 'identity' if applicable)"
            )
        normalization_contract = (
            None
            if self.normalization_contract is None
            else _nonempty(
                self.normalization_contract, "normalization_contract"
            )
        )
        object.__setattr__(self, "raw_text", str(self.raw_text))
        object.__setattr__(self, "candidates", _string_tuple(self.candidates, "candidates"))
        object.__setattr__(self, "score", score)
        object.__setattr__(self, "score_source", source)
        object.__setattr__(self, "calibrator_id", calibrator)
        object.__setattr__(
            self, "normalization_contract", normalization_contract
        )
        object.__setattr__(
            self, "metadata", _frozen_mapping(self.metadata, "metadata")
        )

    @property
    def is_probability(self) -> bool:
        return self.score_kind == "probability"

    def to_dict(self) -> dict[str, object]:
        return {
            "generation_id": self.generation_id,
            "run_id": self.run_id,
            "example_id": self.example_id,
            "model_snapshot_id": self.model_snapshot_id,
            "condition_hash": self.condition_hash,
            "track": self.track,
            "raw_text": self.raw_text,
            "candidates": list(self.candidates),
            "score": self.score,
            "score_kind": self.score_kind,
            "score_source": self.score_source,
            "calibrator_id": self.calibrator_id,
            "normalization_contract": self.normalization_contract,
            "metadata": _thaw_json(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "GenerationRecord":
        metadata = value.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise ValueError("metadata must be a mapping")
        return cls(
            generation_id=str(value.get("generation_id", "")),
            run_id=str(value.get("run_id", "")),
            example_id=str(value.get("example_id", "")),
            model_snapshot_id=str(value.get("model_snapshot_id", "")),
            condition_hash=str(value.get("condition_hash", "")),
            track=str(value.get("track", "")),  # type: ignore[arg-type]
            raw_text=str(value.get("raw_text", "")),
            candidates=_sequence_field(value.get("candidates", ()), "candidates"),
            score=float(value.get("score", float("nan"))),
            score_kind=str(value.get("score_kind", "")),  # type: ignore[arg-type]
            score_source=str(value.get("score_source", "")),
            calibrator_id=(
                None
                if value.get("calibrator_id") is None
                else str(value["calibrator_id"])
            ),
            normalization_contract=(
                None
                if value.get("normalization_contract") is None
                else str(value["normalization_contract"])
            ),
            metadata=metadata,
        )


@dataclass(frozen=True)
class ReadResultRecord:
    """One R7 outcome linked to a cached generation rather than to the static query."""

    run_id: str
    generation_id: str
    example_id: str
    model_snapshot_id: str
    condition_hash: str
    track: EvaluationTrack
    score: float
    score_kind: Literal["raw", "probability"]
    score_source: str
    calibrator_id: str | None
    threshold: float
    policy_level: str
    action: Literal["answer", "set", "abstain"]
    reason: str
    ambiguity_complete: bool
    correctness_rule: str
    candidates: tuple[str, ...] = ()
    answer: str | None = None
    allowed_actions: tuple[str, ...] = ("answer", "set", "abstain")
    correct: bool | None = None
    normalization_contract: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        generation = GenerationRecord(
            generation_id=self.generation_id,
            run_id=self.run_id,
            example_id=self.example_id,
            model_snapshot_id=self.model_snapshot_id,
            condition_hash=self.condition_hash,
            track=self.track,
            raw_text="",
            candidates=self.candidates,
            score=self.score,
            score_kind=self.score_kind,
            score_source=self.score_source,
            calibrator_id=self.calibrator_id,
            normalization_contract=self.normalization_contract,
        )
        from .dimensions import r7_from_threshold

        expected_level = r7_from_threshold(self.threshold).level
        if self.policy_level != expected_level:
            raise ValueError("policy_level must match the frozen R7 threshold")
        if self.score_kind == "raw":
            if generation.normalization_contract is None:
                raise ValueError(
                    "R7 decisions on raw scores require a normalization_contract"
                )
            if not 0.0 <= generation.score <= 1.0:
                raise ValueError(
                    "R7 decisions require a normalized score in [0, 1]"
                )
        if self.action not in _READ_ACTIONS:
            raise ValueError("action must be answer, set, or abstain")
        actions = _string_tuple(self.allowed_actions, "allowed_actions")
        if (
            "abstain" not in actions
            or len(set(actions)) != len(actions)
            or not set(actions) <= _READ_ACTIONS
        ):
            raise ValueError("allowed_actions must be unique, valid, and include abstain")
        if self.action not in actions:
            raise ValueError("action must be permitted by allowed_actions")
        answer = None if self.answer is None else str(self.answer)
        if not isinstance(self.ambiguity_complete, bool):
            raise ValueError("ambiguity_complete must be boolean")
        correctness_rule = _nonempty(self.correctness_rule, "correctness_rule")
        if self.action == "answer":
            if not answer or not self.ambiguity_complete:
                raise ValueError(
                    "answer actions require a nonempty answer and complete ambiguity handling"
                )
            if not generation.candidates or answer not in generation.candidates:
                raise ValueError(
                    "answer actions require the committed answer in candidates"
                )
        if self.action == "set" and not generation.candidates:
            raise ValueError("set actions require at least one candidate")
        if self.correct is not None and not isinstance(self.correct, bool):
            raise ValueError("correct must be boolean or None")
        object.__setattr__(self, "score", generation.score)
        object.__setattr__(
            self, "model_snapshot_id", generation.model_snapshot_id
        )
        object.__setattr__(self, "condition_hash", generation.condition_hash)
        object.__setattr__(self, "score_source", generation.score_source)
        object.__setattr__(self, "calibrator_id", generation.calibrator_id)
        object.__setattr__(
            self,
            "normalization_contract",
            generation.normalization_contract,
        )
        object.__setattr__(self, "threshold", float(self.threshold))
        object.__setattr__(self, "reason", _nonempty(self.reason, "reason"))
        object.__setattr__(self, "candidates", generation.candidates)
        object.__setattr__(self, "answer", answer)
        object.__setattr__(self, "correctness_rule", correctness_rule)
        object.__setattr__(self, "allowed_actions", actions)
        object.__setattr__(
            self, "metadata", _frozen_mapping(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "generation_id": self.generation_id,
            "example_id": self.example_id,
            "model_snapshot_id": self.model_snapshot_id,
            "condition_hash": self.condition_hash,
            "track": self.track,
            "score": self.score,
            "score_kind": self.score_kind,
            "score_source": self.score_source,
            "calibrator_id": self.calibrator_id,
            "threshold": self.threshold,
            "policy_level": self.policy_level,
            "action": self.action,
            "reason": self.reason,
            "correctness_rule": self.correctness_rule,
            "candidates": list(self.candidates),
            "answer": self.answer,
            "allowed_actions": list(self.allowed_actions),
            "ambiguity_complete": self.ambiguity_complete,
            "correct": self.correct,
            "normalization_contract": self.normalization_contract,
            "metadata": _thaw_json(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "ReadResultRecord":
        metadata = value.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise ValueError("metadata must be a mapping")
        if "ambiguity_complete" not in value:
            raise ValueError("ambiguity_complete must be explicitly recorded")
        return cls(
            run_id=str(value.get("run_id", "")),
            generation_id=str(value.get("generation_id", "")),
            example_id=str(value.get("example_id", "")),
            model_snapshot_id=str(value.get("model_snapshot_id", "")),
            condition_hash=str(value.get("condition_hash", "")),
            track=str(value.get("track", "")),  # type: ignore[arg-type]
            score=float(value.get("score", float("nan"))),
            score_kind=str(value.get("score_kind", "")),  # type: ignore[arg-type]
            score_source=str(value.get("score_source", "")),
            calibrator_id=(
                None
                if value.get("calibrator_id") is None
                else str(value["calibrator_id"])
            ),
            threshold=float(value.get("threshold", float("nan"))),
            policy_level=str(value.get("policy_level", "")),
            action=str(value.get("action", "")),  # type: ignore[arg-type]
            reason=str(value.get("reason", "")),
            ambiguity_complete=value["ambiguity_complete"],  # type: ignore[arg-type]
            correctness_rule=str(value.get("correctness_rule", "")),
            candidates=_sequence_field(value.get("candidates", ()), "candidates"),
            answer=None if value.get("answer") is None else str(value["answer"]),
            allowed_actions=_sequence_field(
                value.get("allowed_actions", ("answer", "set", "abstain")),
                "allowed_actions",
            ),
            correct=value.get("correct"),  # type: ignore[arg-type]
            normalization_contract=(
                None
                if value.get("normalization_contract") is None
                else str(value["normalization_contract"])
            ),
            metadata=metadata,
        )


def _scored_candidate_is_correct(
    candidate: str,
    accepted_answers: Sequence[str],
    correctness_scorer: CorrectnessScorer,
) -> bool:
    """Run an explicit scorer and reject non-binary results."""

    scored = correctness_scorer(candidate, accepted_answers)
    if isinstance(scored, bool):
        return scored
    if type(scored) is int and scored in (0, 1):
        return bool(scored)
    raise ValueError("correctness_scorer must return bool, 0, or 1")


def _recompute_action_correctness(
    workload: WorkloadRecord,
    action: Literal["answer", "set", "abstain"],
    answer: str | None,
    candidates: Sequence[str],
    correctness_scorer: CorrectnessScorer | None,
) -> bool | None:
    """Score a committed answer/set against the workload's frozen answers."""

    if action == "abstain":
        return None
    if correctness_scorer is None:
        raise ValueError(
            "answer/set correctness validation requires an explicit correctness_scorer"
        )
    if action == "answer":
        if answer is None:
            raise ValueError("answer action lacks a committed answer")
        return _scored_candidate_is_correct(
            answer, workload.accepted_answers, correctness_scorer
        )
    if action == "set":
        return any(
            _scored_candidate_is_correct(
                candidate, workload.accepted_answers, correctness_scorer
            )
            for candidate in candidates
        )
    raise ValueError("unknown read action")


def decide_generation(
    workload: WorkloadRecord,
    generation: GenerationRecord,
    threshold: float,
    *,
    correctness_rule: str,
    correctness_scorer: CorrectnessScorer,
    supported: bool = True,
    metadata: Mapping[str, object] | None = None,
) -> ReadResultRecord:
    """Create an R7 decision with R4 completeness derived from audited provenance."""

    if workload.example_id != generation.example_id:
        raise ValueError("workload and generation example_id do not match")
    if workload.track != generation.track:
        raise ValueError("workload and generation track do not match")
    if workload.track == "finite_label_certified" and not set(
        generation.candidates
    ) <= set(workload.candidate_universe):
        raise ValueError(
            "finite-label generation candidates must be in workload candidate_universe"
        )

    from .read_contract import read_policy

    unique_candidates = tuple(dict.fromkeys(generation.candidates))
    ambiguity_complete = workload.ambiguity_complete_for(generation.candidates)
    policy = read_policy(
        unique_candidates[0] if len(unique_candidates) == 1 else None,
        generation.score,
        threshold,
        candidates=generation.candidates,
        supported=supported,
        allowed_actions=workload.allowed_actions,  # type: ignore[arg-type]
        ambiguity_complete=ambiguity_complete,
        score_kind=generation.score_kind,
        score_source=generation.score_source,
        calibrator_id=generation.calibrator_id,
        normalization_contract=generation.normalization_contract,
    )
    if policy.policy_level is None:
        raise ValueError("threshold must be one of the frozen R7 policy levels")
    answer = None if policy.answer is None else str(policy.answer)
    correct = _recompute_action_correctness(
        workload,
        policy.action,
        answer,
        generation.candidates,
        correctness_scorer,
    )
    return ReadResultRecord(
        run_id=generation.run_id,
        generation_id=generation.generation_id,
        example_id=generation.example_id,
        model_snapshot_id=generation.model_snapshot_id,
        condition_hash=generation.condition_hash,
        track=generation.track,
        score=generation.score,
        score_kind=generation.score_kind,
        score_source=generation.score_source,
        calibrator_id=generation.calibrator_id,
        threshold=float(threshold),
        policy_level=policy.policy_level,
        action=policy.action,
        reason=policy.reason,
        ambiguity_complete=ambiguity_complete,
        correctness_rule=correctness_rule,
        candidates=generation.candidates,
        answer=answer,
        allowed_actions=workload.allowed_actions,
        correct=correct,
        normalization_contract=generation.normalization_contract,
        metadata={} if metadata is None else metadata,
    )


def validate_pipeline_linkage(
    workload: WorkloadRecord,
    condition: ModelConditionRecord,
    generation: GenerationRecord,
    manifest: object,
    condition_table: Iterable[ModelConditionRecord],
    *,
    decision: ReadResultRecord | None = None,
    correctness_scorer: CorrectnessScorer | None = None,
) -> None:
    """Fail closed unless workload, condition, generation, decision, and run agree."""

    records = tuple(condition_table)
    expected_condition_hash = condition.condition_hash()
    if workload.example_id != condition.example_id:
        raise ValueError("workload and model condition example_id do not match")
    if generation.example_id != condition.example_id:
        raise ValueError("generation and model condition example_id do not match")
    if generation.track != workload.track:
        raise ValueError("generation and workload track do not match")
    if workload.track == "finite_label_certified" and not set(
        generation.candidates
    ) <= set(workload.candidate_universe):
        raise ValueError(
            "finite-label generation candidates must be in workload candidate_universe"
        )
    if generation.model_snapshot_id != condition.model_snapshot_id:
        raise ValueError("generation and model condition snapshot do not match")
    if generation.condition_hash != expected_condition_hash:
        raise ValueError("generation condition_hash does not match condition record")
    if not any(
        item.condition_hash() == expected_condition_hash for item in records
    ):
        raise ValueError("linked model condition is absent from condition table")

    required_manifest_fields = (
        "run_id",
        "model_snapshot_id",
        "condition_table_hash",
        "evaluation_track",
        "correctness_rule",
    )
    if any(not hasattr(manifest, field) for field in required_manifest_fields):
        raise ValueError("manifest lacks model-condition linkage fields")
    if generation.run_id != getattr(manifest, "run_id"):
        raise ValueError("generation run_id does not match manifest")
    if condition.model_snapshot_id != getattr(manifest, "model_snapshot_id"):
        raise ValueError("condition model_snapshot_id does not match manifest")
    if condition_table_hash(records) != getattr(manifest, "condition_table_hash"):
        raise ValueError("condition table hash does not match manifest")
    if workload.track != getattr(manifest, "evaluation_track"):
        raise ValueError("workload track does not match manifest evaluation_track")

    if decision is not None:
        linked_fields = (
            "run_id",
            "generation_id",
            "example_id",
            "model_snapshot_id",
            "condition_hash",
            "track",
        )
        mismatched = [
            field
            for field in linked_fields
            if getattr(decision, field) != getattr(generation, field)
        ]
        if mismatched:
            raise ValueError(
                "read result does not match generation fields: "
                + ", ".join(mismatched)
            )
        generation_fields = (
            "score",
            "score_kind",
            "score_source",
            "calibrator_id",
            "normalization_contract",
            "candidates",
        )
        mismatched_generation_fields = [
            field
            for field in generation_fields
            if getattr(decision, field) != getattr(generation, field)
        ]
        if mismatched_generation_fields:
            raise ValueError(
                "read result does not preserve generation fields: "
                + ", ".join(mismatched_generation_fields)
            )
        if workload.track == "finite_label_certified" and not set(
            decision.candidates
        ) <= set(workload.candidate_universe):
            raise ValueError(
                "finite-label result candidates must be in workload candidate_universe"
            )
        if decision.allowed_actions != workload.allowed_actions:
            raise ValueError("read result allowed_actions do not match workload")
        expected_ambiguity_complete = workload.ambiguity_complete_for(
            generation.candidates
        )
        if decision.ambiguity_complete != expected_ambiguity_complete:
            raise ValueError(
                "read result ambiguity_complete does not match audited workload coverage"
            )
        if decision.correctness_rule != getattr(manifest, "correctness_rule"):
            raise ValueError("read result correctness_rule does not match manifest")
        expected_correct = _recompute_action_correctness(
            workload,
            decision.action,
            decision.answer,
            decision.candidates,
            correctness_scorer,
        )
        if decision.correct != expected_correct:
            raise ValueError(
                "read result correct does not match recomputed workload correctness"
            )
