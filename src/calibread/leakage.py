"""Fail-closed lineage validation and cross-split leakage checks."""

from __future__ import annotations

import hashlib
from math import isfinite
import unicodedata
from collections import defaultdict
from typing import Mapping, Sequence

from .schema import Example

DEFAULT_DISJOINT_KEYS = (
    "entity_id",
    "chain_id",
    "template_id",
    "source_fact_id",
    "question_hash",
)
LINEAGE_EXEMPTION_FIELD = "lineage_exemptions"
LINEAGE_EXEMPTION_REASONS = (
    "not_applicable_by_construction",
    "not_defined_by_source_schema",
)
NON_EXEMPTABLE_DISJOINT_KEYS = ("question_hash",)
QUESTION_HASH_METHOD = "sha256_nfkc_casefold_whitespace_v1"
_PLACEHOLDER_JUSTIFICATIONS = {
    "n/a",
    "na",
    "none",
    "not applicable",
    "tbd",
    "todo",
    "unknown",
}


def normalized_question_hash(question: str) -> str:
    """Hash a conservative Unicode/case/whitespace normalization of a question."""

    normalized = unicodedata.normalize("NFKC", question).casefold()
    normalized = " ".join(normalized.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _field_names(fields: Sequence[str], label: str) -> tuple[str, ...]:
    if isinstance(fields, (str, bytes)):
        raise ValueError(f"{label} must be a sequence of field names")
    normalized = tuple(str(field).strip() for field in fields)
    if not normalized or any(not field for field in normalized):
        raise ValueError(f"{label} must contain nonblank field names")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{label} must not contain duplicates")
    return normalized


def _raw_identifier(example: Example, key: str) -> object | None:
    if hasattr(example, key):
        return getattr(example, key)
    return example.metadata.get(key)


def _identifier(value: object, key: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError(
            f"lineage identifier {key!r} must be a string or finite number"
        )
    if isinstance(value, float) and not isfinite(value):
        raise ValueError(f"lineage identifier {key!r} must be finite")
    rendered = str(value).strip()
    if not rendered:
        raise ValueError(f"lineage identifier {key!r} must not be blank")
    return rendered


def _identifiers(value: object | None, key: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, Mapping):
        raise ValueError(
            f"lineage identifier {key!r} must be a scalar or sequence of scalars"
        )
    if isinstance(value, (list, tuple, set, frozenset)):
        if not value:
            raise ValueError(
                f"lineage identifier {key!r} sequence must not be empty"
            )
        identifiers = {_identifier(item, key) for item in value}
        return tuple(sorted(identifiers))
    return (_identifier(value, key),)


def _validated_exemptions(
    example: Example,
    keys: Sequence[str],
    *,
    exemption_field: str,
) -> dict[str, tuple[str, str]]:
    payload = example.metadata.get(exemption_field, {})
    if not isinstance(payload, Mapping):
        raise ValueError(
            f"example {example.example_id!r} metadata[{exemption_field!r}] "
            "must be a mapping"
        )
    exemptions: dict[str, tuple[str, str]] = {}
    for raw_key, raw_spec in payload.items():
        key = str(raw_key).strip()
        if key not in keys:
            raise ValueError(
                f"example {example.example_id!r} exempts undeclared lineage key {key!r}"
            )
        if key in NON_EXEMPTABLE_DISJOINT_KEYS:
            raise ValueError(
                f"lineage key {key!r} is required and cannot be exempted"
            )
        if not isinstance(raw_spec, Mapping) or set(raw_spec) != {
            "reason_code",
            "justification",
        }:
            raise ValueError(
                f"lineage exemption {key!r} must contain exactly reason_code "
                "and justification"
            )
        reason = raw_spec.get("reason_code")
        if reason not in LINEAGE_EXEMPTION_REASONS:
            allowed = ", ".join(LINEAGE_EXEMPTION_REASONS)
            raise ValueError(
                f"lineage exemption {key!r} reason_code must be one of: {allowed}"
            )
        justification = raw_spec.get("justification")
        if not isinstance(justification, str):
            raise ValueError(
                f"lineage exemption {key!r} justification must be a string"
            )
        justification = justification.strip()
        if (
            len(justification) < 8
            or justification.casefold() in _PLACEHOLDER_JUSTIFICATIONS
        ):
            raise ValueError(
                f"lineage exemption {key!r} requires a substantive justification"
            )
        exemptions[key] = (str(reason), justification)
    return exemptions


def validated_lineage_identifiers(
    example: Example,
    *,
    disjoint_keys: Sequence[str] = DEFAULT_DISJOINT_KEYS,
    exemption_field: str = LINEAGE_EXEMPTION_FIELD,
) -> dict[str, tuple[str, ...]]:
    """Require a value or audited exemption for every declared lineage key."""

    keys = _field_names(disjoint_keys, "disjoint_keys")
    if not isinstance(exemption_field, str) or not exemption_field.strip():
        raise ValueError("exemption_field must be a nonblank string")
    values = {
        key: _identifiers(_raw_identifier(example, key), key) for key in keys
    }
    exemptions = _validated_exemptions(
        example, keys, exemption_field=exemption_field
    )
    for key in keys:
        if values[key] and key in exemptions:
            raise ValueError(
                f"example {example.example_id!r} supplies both value and exemption "
                f"for lineage key {key!r}"
            )
        if not values[key] and key not in exemptions:
            raise ValueError(
                f"example {example.example_id!r} is missing lineage key {key!r} "
                "without an explicit validated exemption"
            )
    if "question_hash" in values:
        supplied = values["question_hash"]
        expected = normalized_question_hash(example.question)
        if len(supplied) != 1 or supplied[0] != expected:
            raise ValueError(
                f"example {example.example_id!r} question_hash does not match "
                f"{QUESTION_HASH_METHOD}"
            )
    return {key: identifiers for key, identifiers in values.items() if identifiers}


def _legacy_identifiers(example: Example, key: str) -> tuple[str, ...]:
    """Return old permissive metadata values for an explicitly legacy audit."""

    return _identifiers(example.metadata.get(key), key)


def find_split_leakage(
    examples: Sequence[Example],
    *,
    disjoint_keys: Sequence[str] | None = None,
    exemption_field: str = LINEAGE_EXEMPTION_FIELD,
    legacy_permissive_missing_keys: bool = False,
    metadata_keys: Sequence[str] | None = None,
) -> dict[str, list[str]]:
    """Return protected identifiers observed in more than one declared split.

    The primary path requires every declared key to carry a value or a validated
    per-key exemption. The old skip-missing behavior is available only when
    legacy_permissive_missing_keys is explicitly true.
    """

    if legacy_permissive_missing_keys:
        if disjoint_keys is not None:
            raise ValueError(
                "legacy mode accepts metadata_keys, not disjoint_keys"
            )
        keys = _field_names(
            metadata_keys
            if metadata_keys is not None
            else DEFAULT_DISJOINT_KEYS[:-1],
            "metadata_keys",
        )
        observations: dict[str, dict[str, set[str]]] = {
            "question_hash": defaultdict(set)
        }
        observations.update({key: defaultdict(set) for key in keys})
    else:
        if metadata_keys is not None:
            raise ValueError(
                "metadata_keys is available only with "
                "legacy_permissive_missing_keys=True"
            )
        keys = _field_names(
            disjoint_keys if disjoint_keys is not None else DEFAULT_DISJOINT_KEYS,
            "disjoint_keys",
        )
        observations = {key: defaultdict(set) for key in keys}

    seen_ids: set[str] = set()
    duplicate_ids: list[str] = []
    for example in examples:
        if example.example_id in seen_ids:
            duplicate_ids.append(example.example_id)
        seen_ids.add(example.example_id)
        if legacy_permissive_missing_keys:
            observations["question_hash"][
                normalized_question_hash(example.question)
            ].add(example.split)
            identifiers_by_key = {
                key: _legacy_identifiers(example, key) for key in keys
            }
        else:
            identifiers_by_key = validated_lineage_identifiers(
                example,
                disjoint_keys=keys,
                exemption_field=exemption_field,
            )
        for key, identifiers in identifiers_by_key.items():
            for identifier in identifiers:
                observations[key][identifier].add(example.split)

    findings: dict[str, list[str]] = {}
    if duplicate_ids:
        findings["example_id"] = sorted(set(duplicate_ids))
    for key, values in observations.items():
        leaked = sorted(
            value for value, splits in values.items() if len(splits) > 1
        )
        if leaked:
            findings[key] = leaked
    return findings


def assert_no_split_leakage(
    examples: Sequence[Example],
    *,
    disjoint_keys: Sequence[str] | None = None,
    exemption_field: str = LINEAGE_EXEMPTION_FIELD,
    legacy_permissive_missing_keys: bool = False,
    metadata_keys: Sequence[str] | None = None,
) -> None:
    """Raise when lineage is incomplete or any identifier spans splits."""

    findings = find_split_leakage(
        examples,
        disjoint_keys=disjoint_keys,
        exemption_field=exemption_field,
        legacy_permissive_missing_keys=legacy_permissive_missing_keys,
        metadata_keys=metadata_keys,
    )
    if findings:
        summary = ", ".join(
            f"{key}={len(values)}" for key, values in findings.items()
        )
        raise ValueError(f"split leakage detected: {summary}")


__all__ = [
    "DEFAULT_DISJOINT_KEYS",
    "LINEAGE_EXEMPTION_FIELD",
    "LINEAGE_EXEMPTION_REASONS",
    "NON_EXEMPTABLE_DISJOINT_KEYS",
    "QUESTION_HASH_METHOD",
    "assert_no_split_leakage",
    "find_split_leakage",
    "normalized_question_hash",
    "validated_lineage_identifiers",
]
