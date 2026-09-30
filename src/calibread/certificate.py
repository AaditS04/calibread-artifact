"""Versioned, machine-readable certificates for one CalibRead Read decision.

The certificate is deliberately a derived artifact. Real certificates must be built from a
finalized :class:`RunManifest` and records that pass the shared pipeline-linkage validator; the
flat schema then makes every identity and claim boundary visible to downstream consumers.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from math import isfinite
from types import MappingProxyType
from typing import Iterable, Literal, Mapping

from .manifest import RunManifest
from .schema import (
    CorrectnessScorer,
    EvaluationTrack,
    GenerationRecord,
    ModelConditionRecord,
    ReadResultRecord,
    WorkloadRecord,
    validate_pipeline_linkage,
)


READ_CERTIFICATE_SCHEMA_VERSION = 1

CertificateCoverageScope = Literal["marginal", "group_marginal"]
CertificateGuaranteeStatus = Literal[
    "finite_label_marginal_under_recorded_assumptions",
    "finite_label_group_marginal_under_recorded_assumptions",
    "none_open_ended_generated_candidates",
    "none_unsupported_calibration",
    "none_assumptions_not_satisfied",
    "none_not_claimed",
]

REQUIRED_CERTIFICATE_ASSUMPTIONS = (
    "calibration_test_exchangeable",
    "calibration_only_fitting",
    "scoring_rule_fixed",
    "true_label_in_fixed_candidate_universe",
    "coverage_procedure_valid_for_r7_policy",
)

_CORE_EVIDENCE_KEYS = (
    "workload_record",
    "model_condition_record",
    "generation_record",
    "read_result_record",
)
_TRACKS = {"finite_label_certified", "open_ended_stress"}
_ACTIONS = {"answer", "set", "abstain"}
_SCORE_KINDS = {"raw", "probability"}
_CALIBRATION_SCOPES = {"global", "group"}
_COVERAGE_SCOPES = {"marginal", "group_marginal"}

_GUARANTEE_STATEMENTS: dict[CertificateGuaranteeStatus, str] = {
    "finite_label_marginal_under_recorded_assumptions": (
        "Finite-label marginal coverage is eligible only under every recorded assumption; "
        "this certificate records, but does not prove, those assumptions."
    ),
    "finite_label_group_marginal_under_recorded_assumptions": (
        "Finite-label group-marginal coverage is eligible only for the recorded group and "
        "under every recorded assumption; this certificate records, but does not prove, "
        "those assumptions."
    ),
    "none_open_ended_generated_candidates": (
        "No coverage guarantee: open-ended generated candidates may omit the true answer; "
        "target_alpha is diagnostic only and candidate-oracle recall must be reported."
    ),
    "none_unsupported_calibration": (
        "No coverage guarantee: the recorded calibration scope is unsupported and the Read "
        "must abstain."
    ),
    "none_assumptions_not_satisfied": (
        "No coverage guarantee: at least one required recorded assumption is not satisfied."
    ),
    "none_not_claimed": (
        "No coverage guarantee is claimed for this finite-label Read certificate."
    ),
}


def _required_string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    return normalized


def _optional_string(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _required_string(value, name)


def _sha256_hex(value: object, name: str) -> str:
    normalized = _required_string(value, name).casefold()
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise ValueError(f"{name} must be a 64-character SHA-256 hex digest")
    return normalized


def _finite_float(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    normalized = float(value)
    if not isfinite(normalized):
        raise ValueError(f"{name} must be finite")
    return normalized


def _string_tuple(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{name} must be a list or tuple")
    return tuple(_required_string(item, f"{name}[]") for item in value)


def _canonical_hash(value: Mapping[str, object]) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _guarantee_status(
    track: EvaluationTrack,
    calibration_supported: bool,
    assumptions: Mapping[str, bool],
    coverage_scope: CertificateCoverageScope | None,
) -> CertificateGuaranteeStatus:
    if track == "open_ended_stress":
        return "none_open_ended_generated_candidates"
    if not calibration_supported:
        return "none_unsupported_calibration"
    if not all(assumptions.values()):
        return "none_assumptions_not_satisfied"
    if coverage_scope is None:
        return "none_not_claimed"
    if coverage_scope == "marginal":
        return "finite_label_marginal_under_recorded_assumptions"
    return "finite_label_group_marginal_under_recorded_assumptions"


@dataclass(frozen=True)
class ReadCertificate:
    """One immutable, fail-closed certificate for one versioned Read outcome.

    ``guarantee_status`` and ``guarantee_statement`` are derived, not caller-controlled. A
    finite-label coverage scope is accepted only when the calibration scope is supported and all
    v1 assumptions are explicitly true. The open-ended track can never acquire a coverage claim.
    """

    schema_version: int
    request_id: str
    workload_id: str
    run_id: str
    generation_id: str
    model_snapshot_id: str
    condition_hash: str
    condition_table_hash: str
    evaluation_track: EvaluationTrack
    calibration_method: str
    calibration_object_hash: str
    calibration_ids_hash: str
    calibration_scope: Literal["global", "group"]
    calibration_group: str | None
    calibration_support_n: int
    calibration_supported: bool
    unsupported_reason: str | None
    assumption_status: Mapping[str, bool]
    target_alpha: float
    r7_threshold: float
    policy_level: str
    allowed_actions: tuple[str, ...]
    selected_action: Literal["answer", "set", "abstain"]
    action_reason: str
    answer: str | None
    candidates: tuple[str, ...]
    ambiguity_complete: bool
    correctness_rule: str
    correct: bool | None
    score: float
    score_kind: Literal["raw", "probability"]
    score_source: str
    calibrator_id: str | None
    normalization_contract: str | None
    coverage_scope: CertificateCoverageScope | None
    evidence_hashes: Mapping[str, str]
    manifest_hash: str
    research_evidence: bool
    research_evidence_reason: str
    guarantee_status: CertificateGuaranteeStatus = field(init=False)
    guarantee_statement: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version != READ_CERTIFICATE_SCHEMA_VERSION
        ):
            raise ValueError(
                f"schema_version must equal {READ_CERTIFICATE_SCHEMA_VERSION}"
            )
        for name in (
            "request_id",
            "workload_id",
            "run_id",
            "generation_id",
            "model_snapshot_id",
            "calibration_method",
            "policy_level",
            "action_reason",
            "correctness_rule",
            "score_source",
            "research_evidence_reason",
        ):
            object.__setattr__(
                self, name, _required_string(getattr(self, name), name)
            )
        for name in (
            "condition_hash",
            "condition_table_hash",
            "calibration_object_hash",
            "calibration_ids_hash",
            "manifest_hash",
        ):
            object.__setattr__(self, name, _sha256_hex(getattr(self, name), name))

        evaluation_track = _required_string(
            self.evaluation_track, "evaluation_track"
        )
        if evaluation_track not in _TRACKS:
            raise ValueError(
                "evaluation_track must be finite_label_certified or open_ended_stress"
            )
        calibration_scope = _required_string(
            self.calibration_scope, "calibration_scope"
        )
        if calibration_scope not in _CALIBRATION_SCOPES:
            raise ValueError("calibration_scope must be global or group")
        calibration_group = _optional_string(
            self.calibration_group, "calibration_group"
        )
        if calibration_scope == "global" and calibration_group is not None:
            raise ValueError("global calibration must not name a calibration_group")
        if calibration_scope == "group" and calibration_group is None:
            raise ValueError("group calibration requires calibration_group")
        if (
            isinstance(self.calibration_support_n, bool)
            or not isinstance(self.calibration_support_n, int)
            or self.calibration_support_n < 0
        ):
            raise ValueError("calibration_support_n must be a nonnegative integer")
        if not isinstance(self.calibration_supported, bool):
            raise ValueError("calibration_supported must be boolean")
        unsupported_reason = _optional_string(
            self.unsupported_reason, "unsupported_reason"
        )
        if self.calibration_supported:
            if self.calibration_support_n == 0:
                raise ValueError("supported calibration requires positive support")
            if unsupported_reason is not None:
                raise ValueError(
                    "supported calibration must not carry an unsupported_reason"
                )
        elif unsupported_reason is None:
            raise ValueError("unsupported calibration requires unsupported_reason")

        if not isinstance(self.assumption_status, Mapping):
            raise ValueError("assumption_status must be a mapping")
        if any(not isinstance(name, str) for name in self.assumption_status):
            raise ValueError("assumption_status keys must be strings")
        assumption_keys = set(self.assumption_status)
        expected_assumptions = set(REQUIRED_CERTIFICATE_ASSUMPTIONS)
        if assumption_keys != expected_assumptions:
            missing = sorted(expected_assumptions - assumption_keys)
            unexpected = sorted(assumption_keys - expected_assumptions)
            raise ValueError(
                "assumption_status must contain exactly the v1 assumptions; "
                f"missing={missing}, unexpected={unexpected}"
            )
        assumptions: dict[str, bool] = {}
        for name in REQUIRED_CERTIFICATE_ASSUMPTIONS:
            status = self.assumption_status[name]
            if not isinstance(status, bool):
                raise ValueError(f"assumption_status[{name!r}] must be boolean")
            assumptions[name] = status
        if (
            evaluation_track == "open_ended_stress"
            and assumptions["true_label_in_fixed_candidate_universe"]
        ):
            raise ValueError(
                "open-ended track must record "
                "true_label_in_fixed_candidate_universe=False"
            )

        target_alpha = _finite_float(self.target_alpha, "target_alpha")
        if not 0.0 < target_alpha < 1.0:
            raise ValueError("target_alpha must lie strictly between 0 and 1")
        r7_threshold = _finite_float(self.r7_threshold, "r7_threshold")
        if not 0.0 <= r7_threshold <= 1.0:
            raise ValueError("r7_threshold must lie in [0, 1]")
        allowed_actions = _string_tuple(self.allowed_actions, "allowed_actions")
        if (
            not allowed_actions
            or len(set(allowed_actions)) != len(allowed_actions)
            or not set(allowed_actions) <= _ACTIONS
            or "abstain" not in allowed_actions
        ):
            raise ValueError(
                "allowed_actions must be unique answer/set/abstain values and include abstain"
            )
        selected_action = _required_string(self.selected_action, "selected_action")
        if selected_action not in _ACTIONS:
            raise ValueError("selected_action must be answer, set, or abstain")
        if selected_action not in allowed_actions:
            raise ValueError("selected_action must be permitted by allowed_actions")
        answer = _optional_string(self.answer, "answer")
        candidates = _string_tuple(self.candidates, "candidates")
        if len(set(candidates)) != len(candidates):
            raise ValueError("candidates must be unique")
        if not isinstance(self.ambiguity_complete, bool):
            raise ValueError("ambiguity_complete must be boolean")
        if self.correct is not None and not isinstance(self.correct, bool):
            raise ValueError("correct must be boolean or None")
        if selected_action == "abstain":
            if answer is not None or self.correct is not None:
                raise ValueError("abstain requires answer=None and correct=None")
        else:
            if not isinstance(self.correct, bool):
                raise ValueError("answer/set actions require explicit boolean correctness")
            if selected_action == "answer" and answer is None:
                raise ValueError("answer action requires a committed answer")
            if selected_action == "set" and answer is not None:
                raise ValueError("set action must not carry a singleton answer")

        score = _finite_float(self.score, "score")
        score_kind = _required_string(self.score_kind, "score_kind")
        if score_kind not in _SCORE_KINDS:
            raise ValueError("score_kind must be raw or probability")
        calibrator_id = _optional_string(self.calibrator_id, "calibrator_id")
        normalization_contract = _optional_string(
            self.normalization_contract, "normalization_contract"
        )
        coverage_scope = _optional_string(self.coverage_scope, "coverage_scope")
        if coverage_scope is not None and coverage_scope not in _COVERAGE_SCOPES:
            raise ValueError("coverage_scope must be marginal, group_marginal, or None")
        if evaluation_track == "open_ended_stress" and coverage_scope is not None:
            raise ValueError(
                "open-ended generated-candidate Reads cannot claim coverage_scope"
            )
        if coverage_scope is not None:
            if not self.calibration_supported:
                raise ValueError("unsupported calibration cannot claim coverage_scope")
            if not all(assumptions.values()):
                raise ValueError(
                    "coverage_scope requires every recorded assumption to be true"
                )
            if coverage_scope == "marginal" and calibration_scope != "global":
                raise ValueError("marginal coverage requires global calibration_scope")
            if (
                coverage_scope == "group_marginal"
                and calibration_scope != "group"
            ):
                raise ValueError(
                    "group_marginal coverage requires group calibration_scope"
                )

        if not self.calibration_supported:
            if not (
                selected_action == "abstain"
                and self.action_reason == "unsupported_calibration_group"
            ):
                raise ValueError(
                    "unsupported calibration must fail closed with "
                    "abstain/unsupported_calibration_group"
                )
        elif self.action_reason == "unsupported_calibration_group":
            raise ValueError(
                "supported calibration cannot use unsupported_calibration_group"
            )

        # Reuse ReadResultRecord validation for R7 labels, action shape, score semantics, and
        # normalization/calibrator requirements instead of maintaining a second policy schema.
        validated_result = ReadResultRecord(
            run_id=self.run_id,
            generation_id=self.generation_id,
            example_id=self.workload_id,
            model_snapshot_id=self.model_snapshot_id,
            condition_hash=self.condition_hash,
            track=evaluation_track,  # type: ignore[arg-type]
            score=score,
            score_kind=score_kind,  # type: ignore[arg-type]
            score_source=self.score_source,
            calibrator_id=calibrator_id,
            threshold=r7_threshold,
            policy_level=self.policy_level,
            action=selected_action,  # type: ignore[arg-type]
            reason=self.action_reason,
            ambiguity_complete=self.ambiguity_complete,
            correctness_rule=self.correctness_rule,
            candidates=candidates,
            answer=answer,
            allowed_actions=allowed_actions,
            correct=self.correct,
            normalization_contract=normalization_contract,
        )

        if not isinstance(self.evidence_hashes, Mapping):
            raise ValueError("evidence_hashes must be a mapping")
        evidence: dict[str, str] = {}
        for raw_name, raw_hash in self.evidence_hashes.items():
            name = _required_string(raw_name, "evidence_hashes key")
            if name in evidence:
                raise ValueError(f"duplicate evidence hash name {name!r}")
            evidence[name] = _sha256_hex(
                raw_hash, f"evidence_hashes[{name!r}]"
            )
        missing_evidence = sorted(set(_CORE_EVIDENCE_KEYS) - set(evidence))
        if missing_evidence:
            raise ValueError(
                "evidence_hashes lacks core records: " + ", ".join(missing_evidence)
            )
        if not isinstance(self.research_evidence, bool):
            raise ValueError("research_evidence must be boolean")

        guarantee_status = _guarantee_status(
            evaluation_track,  # type: ignore[arg-type]
            self.calibration_supported,
            assumptions,
            coverage_scope,
        )
        object.__setattr__(self, "calibration_group", calibration_group)
        object.__setattr__(self, "evaluation_track", evaluation_track)
        object.__setattr__(self, "calibration_scope", calibration_scope)
        object.__setattr__(self, "unsupported_reason", unsupported_reason)
        object.__setattr__(
            self, "assumption_status", MappingProxyType(assumptions)
        )
        object.__setattr__(self, "target_alpha", target_alpha)
        object.__setattr__(self, "r7_threshold", validated_result.threshold)
        object.__setattr__(self, "allowed_actions", allowed_actions)
        object.__setattr__(self, "answer", answer)
        object.__setattr__(self, "candidates", validated_result.candidates)
        object.__setattr__(self, "score", validated_result.score)
        object.__setattr__(self, "selected_action", selected_action)
        object.__setattr__(self, "score_kind", score_kind)
        object.__setattr__(self, "calibrator_id", validated_result.calibrator_id)
        object.__setattr__(
            self,
            "normalization_contract",
            validated_result.normalization_contract,
        )
        object.__setattr__(
            self, "evidence_hashes", MappingProxyType(dict(sorted(evidence.items())))
        )
        object.__setattr__(self, "coverage_scope", coverage_scope)
        object.__setattr__(self, "guarantee_status", guarantee_status)
        object.__setattr__(
            self, "guarantee_statement", _GUARANTEE_STATEMENTS[guarantee_status]
        )

    def to_dict(self) -> dict[str, object]:
        """Return the strict v1 JSON object, including derived guarantee language."""

        return {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "workload_id": self.workload_id,
            "run_id": self.run_id,
            "generation_id": self.generation_id,
            "model_snapshot_id": self.model_snapshot_id,
            "condition_hash": self.condition_hash,
            "condition_table_hash": self.condition_table_hash,
            "evaluation_track": self.evaluation_track,
            "calibration_method": self.calibration_method,
            "calibration_object_hash": self.calibration_object_hash,
            "calibration_ids_hash": self.calibration_ids_hash,
            "calibration_scope": self.calibration_scope,
            "calibration_group": self.calibration_group,
            "calibration_support_n": self.calibration_support_n,
            "calibration_supported": self.calibration_supported,
            "unsupported_reason": self.unsupported_reason,
            "assumption_status": dict(self.assumption_status),
            "target_alpha": self.target_alpha,
            "r7_threshold": self.r7_threshold,
            "policy_level": self.policy_level,
            "allowed_actions": list(self.allowed_actions),
            "selected_action": self.selected_action,
            "action_reason": self.action_reason,
            "answer": self.answer,
            "candidates": list(self.candidates),
            "ambiguity_complete": self.ambiguity_complete,
            "correctness_rule": self.correctness_rule,
            "correct": self.correct,
            "score": self.score,
            "score_kind": self.score_kind,
            "score_source": self.score_source,
            "calibrator_id": self.calibrator_id,
            "normalization_contract": self.normalization_contract,
            "coverage_scope": self.coverage_scope,
            "guarantee_status": self.guarantee_status,
            "guarantee_statement": self.guarantee_statement,
            "evidence_hashes": dict(self.evidence_hashes),
            "manifest_hash": self.manifest_hash,
            "research_evidence": self.research_evidence,
            "research_evidence_reason": self.research_evidence_reason,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "ReadCertificate":
        """Load exactly the v1 schema and reject omitted, unknown, or altered fields."""

        if not isinstance(value, Mapping):
            raise ValueError("ReadCertificate payload must be a mapping")
        expected = set(_SERIALIZED_FIELDS)
        observed = set(value)
        if observed != expected:
            missing = sorted(expected - observed)
            unexpected = sorted(observed - expected)
            raise ValueError(
                "ReadCertificate v1 fields do not match schema; "
                f"missing={missing}, unexpected={unexpected}"
            )
        assumptions = value["assumption_status"]
        evidence = value["evidence_hashes"]
        if not isinstance(assumptions, Mapping):
            raise ValueError("assumption_status must be a mapping")
        if not isinstance(evidence, Mapping):
            raise ValueError("evidence_hashes must be a mapping")
        certificate = cls(
            schema_version=value["schema_version"],  # type: ignore[arg-type]
            request_id=value["request_id"],  # type: ignore[arg-type]
            workload_id=value["workload_id"],  # type: ignore[arg-type]
            run_id=value["run_id"],  # type: ignore[arg-type]
            generation_id=value["generation_id"],  # type: ignore[arg-type]
            model_snapshot_id=value["model_snapshot_id"],  # type: ignore[arg-type]
            condition_hash=value["condition_hash"],  # type: ignore[arg-type]
            condition_table_hash=value["condition_table_hash"],  # type: ignore[arg-type]
            evaluation_track=value["evaluation_track"],  # type: ignore[arg-type]
            calibration_method=value["calibration_method"],  # type: ignore[arg-type]
            calibration_object_hash=value["calibration_object_hash"],  # type: ignore[arg-type]
            calibration_ids_hash=value["calibration_ids_hash"],  # type: ignore[arg-type]
            calibration_scope=value["calibration_scope"],  # type: ignore[arg-type]
            calibration_group=value["calibration_group"],  # type: ignore[arg-type]
            calibration_support_n=value["calibration_support_n"],  # type: ignore[arg-type]
            calibration_supported=value["calibration_supported"],  # type: ignore[arg-type]
            unsupported_reason=value["unsupported_reason"],  # type: ignore[arg-type]
            assumption_status=assumptions,  # type: ignore[arg-type]
            target_alpha=value["target_alpha"],  # type: ignore[arg-type]
            r7_threshold=value["r7_threshold"],  # type: ignore[arg-type]
            policy_level=value["policy_level"],  # type: ignore[arg-type]
            allowed_actions=_string_tuple(value["allowed_actions"], "allowed_actions"),
            selected_action=value["selected_action"],  # type: ignore[arg-type]
            action_reason=value["action_reason"],  # type: ignore[arg-type]
            answer=value["answer"],  # type: ignore[arg-type]
            candidates=_string_tuple(value["candidates"], "candidates"),
            ambiguity_complete=value["ambiguity_complete"],  # type: ignore[arg-type]
            correctness_rule=value["correctness_rule"],  # type: ignore[arg-type]
            correct=value["correct"],  # type: ignore[arg-type]
            score=value["score"],  # type: ignore[arg-type]
            score_kind=value["score_kind"],  # type: ignore[arg-type]
            score_source=value["score_source"],  # type: ignore[arg-type]
            calibrator_id=value["calibrator_id"],  # type: ignore[arg-type]
            normalization_contract=value["normalization_contract"],  # type: ignore[arg-type]
            coverage_scope=value["coverage_scope"],  # type: ignore[arg-type]
            evidence_hashes=evidence,  # type: ignore[arg-type]
            manifest_hash=value["manifest_hash"],  # type: ignore[arg-type]
            research_evidence=value["research_evidence"],  # type: ignore[arg-type]
            research_evidence_reason=value["research_evidence_reason"],  # type: ignore[arg-type]
        )
        if value["guarantee_status"] != certificate.guarantee_status:
            raise ValueError("serialized guarantee_status does not match derived status")
        if value["guarantee_statement"] != certificate.guarantee_statement:
            raise ValueError(
                "serialized guarantee_statement does not match derived statement"
            )
        return certificate

    def content_hash(self) -> str:
        """Return the canonical SHA-256 identity of the complete certificate."""

        return _canonical_hash(self.to_dict())

    def validate_against(
        self,
        workload: WorkloadRecord,
        condition: ModelConditionRecord,
        generation: GenerationRecord,
        result: ReadResultRecord,
        manifest: RunManifest,
        condition_table: Iterable[ModelConditionRecord],
        *,
        correctness_scorer: CorrectnessScorer,
    ) -> None:
        """Rebuild from source records and reject any certificate/linkage mismatch."""

        validate_read_certificate(
            self,
            workload,
            condition,
            generation,
            result,
            manifest,
            condition_table,
            correctness_scorer=correctness_scorer,
        )


_SERIALIZED_FIELDS = tuple(ReadCertificate.__dataclass_fields__)


def build_read_certificate(
    *,
    request_id: str,
    workload: WorkloadRecord,
    condition: ModelConditionRecord,
    generation: GenerationRecord,
    result: ReadResultRecord,
    manifest: RunManifest,
    condition_table: Iterable[ModelConditionRecord],
    correctness_scorer: CorrectnessScorer,
    calibration_scope: Literal["global", "group"],
    calibration_group: str | None,
    calibration_support_n: int,
    calibration_supported: bool,
    unsupported_reason: str | None,
    assumption_status: Mapping[str, bool],
    target_alpha: float,
    coverage_scope: CertificateCoverageScope | None,
    research_evidence: bool,
    research_evidence_reason: str,
    additional_evidence_hashes: Mapping[str, str] | None = None,
) -> ReadCertificate:
    """Build a certificate only after all source records and the manifest agree."""

    if not isinstance(manifest, RunManifest):
        raise ValueError("manifest must be a RunManifest")
    if not manifest.is_finalized:
        raise ValueError("Read certificates require a finalized RunManifest")
    manifest.validate_finalized()
    conditions = tuple(condition_table)
    validate_pipeline_linkage(
        workload,
        condition,
        generation,
        manifest,
        conditions,
        decision=result,
        correctness_scorer=correctness_scorer,
    )
    if result.threshold not in manifest.policy_grid:
        raise ValueError("read result threshold is absent from manifest policy_grid")

    evidence: dict[str, str] = {
        "workload_record": _canonical_hash(workload.to_dict()),
        "model_condition_record": _canonical_hash(condition.to_dict()),
        "generation_record": _canonical_hash(generation.to_dict()),
        "read_result_record": _canonical_hash(result.to_dict()),
    }
    if additional_evidence_hashes is not None:
        if not isinstance(additional_evidence_hashes, Mapping):
            raise ValueError("additional_evidence_hashes must be a mapping")
        overlap = set(evidence).intersection(additional_evidence_hashes)
        if overlap:
            raise ValueError(
                "additional evidence cannot replace core hashes: "
                + ", ".join(sorted(overlap))
            )
        evidence.update(additional_evidence_hashes)

    return ReadCertificate(
        schema_version=READ_CERTIFICATE_SCHEMA_VERSION,
        request_id=request_id,
        workload_id=workload.example_id,
        run_id=generation.run_id,
        generation_id=generation.generation_id,
        model_snapshot_id=generation.model_snapshot_id,
        condition_hash=generation.condition_hash,
        condition_table_hash=manifest.condition_table_hash,
        evaluation_track=workload.track,
        calibration_method=manifest.calibration_method,
        calibration_object_hash=manifest.calibration_object_hash,
        calibration_ids_hash=manifest.calibration_ids_hash,
        calibration_scope=calibration_scope,
        calibration_group=calibration_group,
        calibration_support_n=calibration_support_n,
        calibration_supported=calibration_supported,
        unsupported_reason=unsupported_reason,
        assumption_status=assumption_status,
        target_alpha=target_alpha,
        r7_threshold=result.threshold,
        policy_level=result.policy_level,
        allowed_actions=result.allowed_actions,
        selected_action=result.action,
        action_reason=result.reason,
        answer=result.answer,
        candidates=result.candidates,
        ambiguity_complete=result.ambiguity_complete,
        correctness_rule=result.correctness_rule,
        correct=result.correct,
        score=result.score,
        score_kind=result.score_kind,
        score_source=result.score_source,
        calibrator_id=result.calibrator_id,
        normalization_contract=result.normalization_contract,
        coverage_scope=coverage_scope,
        evidence_hashes=evidence,
        manifest_hash=manifest.content_hash(),
        research_evidence=research_evidence,
        research_evidence_reason=research_evidence_reason,
    )


def validate_read_certificate(
    certificate: ReadCertificate,
    workload: WorkloadRecord,
    condition: ModelConditionRecord,
    generation: GenerationRecord,
    result: ReadResultRecord,
    manifest: RunManifest,
    condition_table: Iterable[ModelConditionRecord],
    *,
    correctness_scorer: CorrectnessScorer,
) -> None:
    """Reject a certificate whose fields or hashes differ from its source records."""

    if not isinstance(certificate, ReadCertificate):
        raise ValueError("certificate must be a ReadCertificate")
    additional = {
        name: digest
        for name, digest in certificate.evidence_hashes.items()
        if name not in _CORE_EVIDENCE_KEYS
    }
    rebuilt = build_read_certificate(
        request_id=certificate.request_id,
        workload=workload,
        condition=condition,
        generation=generation,
        result=result,
        manifest=manifest,
        condition_table=tuple(condition_table),
        correctness_scorer=correctness_scorer,
        calibration_scope=certificate.calibration_scope,
        calibration_group=certificate.calibration_group,
        calibration_support_n=certificate.calibration_support_n,
        calibration_supported=certificate.calibration_supported,
        unsupported_reason=certificate.unsupported_reason,
        assumption_status=certificate.assumption_status,
        target_alpha=certificate.target_alpha,
        coverage_scope=certificate.coverage_scope,
        research_evidence=certificate.research_evidence,
        research_evidence_reason=certificate.research_evidence_reason,
        additional_evidence_hashes=additional,
    )
    rebuilt_payload = rebuilt.to_dict()
    certificate_payload = certificate.to_dict()
    if rebuilt_payload != certificate_payload:
        mismatched = [
            name
            for name in _SERIALIZED_FIELDS
            if rebuilt_payload[name] != certificate_payload[name]
        ]
        raise ValueError(
            "ReadCertificate does not match linked source records: "
            + ", ".join(mismatched)
        )


__all__ = [
    "CertificateCoverageScope",
    "CertificateGuaranteeStatus",
    "READ_CERTIFICATE_SCHEMA_VERSION",
    "REQUIRED_CERTIFICATE_ASSUMPTIONS",
    "ReadCertificate",
    "build_read_certificate",
    "validate_read_certificate",
]
