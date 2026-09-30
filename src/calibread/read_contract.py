"""Executable answer/set/abstain semantics for the P03 R7 policy axis."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Hashable, Iterable, Literal, Sequence

from .dimensions import r7_from_threshold

ReadAction = Literal["answer", "set", "abstain"]


@dataclass(frozen=True)
class ReadDecision:
    action: ReadAction
    answer: Hashable | None
    candidates: tuple[Hashable, ...]
    reason: str
    confidence: float | None = None
    threshold: float | None = None
    policy_level: str | None = None
    score_kind: str | None = None
    score_source: str | None = None
    calibrator_id: str | None = None
    normalization_contract: str | None = None
    allowed_actions: tuple[ReadAction, ...] = ("answer", "set", "abstain")
    ambiguity_complete: bool = False


def _validated_actions(actions: Sequence[ReadAction]) -> tuple[ReadAction, ...]:
    normalized = tuple(actions)
    if (
        not normalized
        or len(set(normalized)) != len(normalized)
        or not set(normalized) <= {"answer", "set", "abstain"}
    ):
        raise ValueError("allowed_actions must be unique answer/set/abstain values")
    if "abstain" not in normalized:
        raise ValueError("allowed_actions must include abstain for fail-closed behavior")
    return normalized


def _r7_level(threshold: float) -> str | None:
    try:
        return r7_from_threshold(threshold).level
    except ValueError:
        return None


def read_policy(
    answer: Hashable | None,
    score: float,
    threshold: float,
    *,
    candidates: Iterable[Hashable] = (),
    supported: bool = True,
    allowed_actions: Sequence[ReadAction] = ("answer", "set", "abstain"),
    ambiguity_complete: bool = False,
    score_kind: Literal["raw", "probability", "legacy_probability"] = "raw",
    score_source: str = "unspecified",
    calibrator_id: str | None = None,
    normalization_contract: str | None = None,
) -> ReadDecision:
    """Apply one fail-closed answer/set/abstain policy to a cached scored output.

    An ambiguity-incomplete singleton is never committed. Frozen R7 thresholds receive their
    canonical policy label; denser diagnostic thresholds have no canonical label.
    """

    score = float(score)
    threshold = float(threshold)
    if not isfinite(score) or not 0.0 <= score <= 1.0:
        raise ValueError("score must be finite and lie in [0, 1]")
    if not isfinite(threshold) or not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be finite and lie in [0, 1]")
    if score_kind not in {"raw", "probability", "legacy_probability"}:
        raise ValueError("score_kind must be raw, probability, or legacy_probability")
    if not isinstance(supported, bool):
        raise ValueError("supported must be boolean")
    if not isinstance(ambiguity_complete, bool):
        raise ValueError("ambiguity_complete must be boolean")
    source = str(score_source).strip()
    if not source:
        raise ValueError("score_source must not be empty")
    calibrator = None if calibrator_id is None else str(calibrator_id).strip()
    if score_kind == "probability" and not calibrator:
        raise ValueError(
            "probability scores require a calibrator_id (use 'identity' if applicable)"
        )
    normalizer = (
        None
        if normalization_contract is None
        else str(normalization_contract).strip()
    )
    if normalization_contract is not None and not normalizer:
        raise ValueError("normalization_contract must not be blank")
    if score_kind == "raw" and not normalizer:
        raise ValueError(
            "R7 thresholding of raw scores requires a normalization_contract"
        )
    actions = _validated_actions(allowed_actions)
    try:
        unique = tuple(dict.fromkeys(candidates))
    except TypeError as error:
        raise ValueError("candidates must contain only hashable values") from error
    if answer is not None:
        try:
            hash(answer)
        except TypeError as error:
            raise ValueError("answer must be hashable") from error
        if unique and answer not in unique:
            raise ValueError("answer must belong to candidates when candidates are supplied")
        if not unique:
            unique = (answer,)
    level = _r7_level(threshold)

    def decision(
        action: ReadAction,
        reason: str,
        *,
        committed_answer: Hashable | None = None,
        returned_candidates: tuple[Hashable, ...] = (),
    ) -> ReadDecision:
        return ReadDecision(
            action=action,
            answer=committed_answer,
            candidates=returned_candidates,
            reason=reason,
            confidence=score,
            threshold=threshold,
            policy_level=level,
            score_kind=score_kind,
            score_source=source,
            calibrator_id=calibrator,
            normalization_contract=normalizer,
            allowed_actions=actions,
            ambiguity_complete=bool(ambiguity_complete),
        )

    if not supported:
        return decision("abstain", "unsupported_calibration_group")
    if score < threshold:
        return decision("abstain", "below_threshold")
    if not unique:
        return decision("abstain", "empty_candidate_set")
    if len(unique) > 1:
        if "set" in actions:
            return decision(
                "set",
                (
                    "ambiguity_incomplete_candidate_set"
                    if not ambiguity_complete
                    else "non_singleton_prediction_set"
                ),
                returned_candidates=unique,
            )
        return decision("abstain", "non_singleton_set_not_allowed")
    if not ambiguity_complete:
        return decision("abstain", "ambiguity_incomplete_singleton")
    if "answer" in actions:
        return decision(
            "answer",
            "threshold_accepted",
            committed_answer=unique[0],
            returned_candidates=unique,
        )
    if "set" in actions:
        return decision(
            "set", "singleton_answer_not_allowed", returned_candidates=unique
        )
    return decision("abstain", "no_permitted_commit_action")


def selective_read(
    answer: Hashable,
    confidence: float,
    threshold: float,
    *,
    supported: bool = True,
) -> ReadDecision:
    """Apply the legacy singleton wrapper without claiming audited R4 coverage.

    This compatibility helper cannot inspect a WorkloadRecord, so it always
    fails closed on a singleton. Use decide_generation for an audited commit.
    """
    return read_policy(
        answer,
        confidence,
        threshold,
        candidates=(answer,),
        supported=supported,
        allowed_actions=("answer", "abstain"),
        ambiguity_complete=False,
        score_kind="legacy_probability",
        score_source="legacy_confidence",
        calibrator_id="legacy_unspecified",
    )


def prediction_set_read(
    candidates: Iterable[Hashable],
    *,
    supported: bool = True,
    allowed_actions: Sequence[ReadAction] = ("answer", "set", "abstain"),
) -> ReadDecision:
    """Map a prediction set without claiming unaudited R4 completeness."""
    unique = tuple(dict.fromkeys(candidates))
    return read_policy(
        unique[0] if len(unique) == 1 else None,
        1.0,
        0.0,
        candidates=unique,
        supported=supported,
        allowed_actions=allowed_actions,
        ambiguity_complete=False,
        score_kind="raw",
        score_source="conformal_prediction_set",
        normalization_contract="binary_set_membership-v1",
    )
