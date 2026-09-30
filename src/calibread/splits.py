"""Stable, leakage-aware split assignment."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from math import isfinite
from typing import Mapping, Sequence

from .leakage import (
    DEFAULT_DISJOINT_KEYS,
    LINEAGE_EXEMPTION_FIELD,
    validated_lineage_identifiers,
)
from .schema import Example

_SPLIT_NAMES = ("development", "calibration", "test")
_LEVEL_FIELDS = {
    "r1_frequency_level": "R1",
    "r2_precision_level": "R2",
    "r3_recency_level": "R3",
    "r4_ambiguity_level": "R4",
    "r5_synthesis_level": "R5",
    "r6_domain_level": "R6",
    "r7_policy_level": "R7",
}


def _validate_fractions(fractions: tuple[float, float, float]) -> None:
    if len(fractions) != 3:
        raise ValueError(
            "fractions must contain development, calibration, and test shares"
        )
    if any(value < 0.0 or not isfinite(value) for value in fractions):
        raise ValueError("split fractions must be finite and non-negative")
    if abs(sum(fractions) - 1.0) > 1e-12:
        raise ValueError("split fractions must sum to 1")


def _validate_fields(name: str, fields: Sequence[str]) -> tuple[str, ...]:
    if isinstance(fields, (str, bytes)):
        raise ValueError(f"{name} must be a sequence of field names")
    normalized = tuple(str(field).strip() for field in fields)
    if not normalized or any(not field for field in normalized):
        raise ValueError(f"{name} must contain nonempty field names")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} must not contain duplicates")
    return normalized


def _field_value(example: Example, field: str) -> object | None:
    if hasattr(example, field):
        return getattr(example, field)
    if field in example.metadata:
        return example.metadata[field]
    dimension = _LEVEL_FIELDS.get(field)
    if dimension is not None:
        values = example.dimension_values()
        if dimension in values:
            return values[dimension].level
    return None


def _scalar_token(value: object) -> str:
    if isinstance(value, bool):
        return f"bool:{str(value).lower()}"
    if isinstance(value, int):
        return f"int:{value}"
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("split identifiers must be finite")
        return f"float:{value!r}"
    rendered = str(value).strip()
    return f"{type(value).__name__}:{rendered}" if rendered else ""


def _value_tokens(value: object | None) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, Mapping):
        raise ValueError("split identifiers must be scalars or sequences of scalars")
    if isinstance(value, (list, tuple, set, frozenset)):
        tokens = {_scalar_token(item) for item in value if item is not None}
        return tuple(sorted(token for token in tokens if token))
    token = _scalar_token(value)
    return (token,) if token else ()


def _tokens_for_fields(
    example: Example,
    fields: Sequence[str],
    *,
    missing_token: bool,
) -> tuple[str, ...]:
    tokens: list[str] = []
    for field in fields:
        values = _value_tokens(_field_value(example, field))
        if values:
            tokens.extend(f"{field}={value}" for value in values)
        elif missing_token:
            tokens.append(f"{field}=<missing>")
    return tuple(tokens)


def deterministic_split(
    key: str,
    *,
    seed: int = 0,
    fractions: tuple[float, float, float] = (0.2, 0.3, 0.5),
) -> str:
    """Map a grouping key to a stable development/calibration/test split."""

    _validate_fractions(fractions)
    if not str(key):
        raise ValueError("key must not be empty")
    digest = sha256(f"{seed}:{key}".encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big") / 2**64
    if value < fractions[0]:
        return _SPLIT_NAMES[0]
    if value < fractions[0] + fractions[1]:
        return _SPLIT_NAMES[1]
    return _SPLIT_NAMES[2]


@dataclass(frozen=True)
class _Component:
    indices: tuple[int, ...]
    signature: str
    strata: Counter[str]


def _components(
    examples: Sequence[Example],
    disjoint_keys: Sequence[str],
    strata_keys: Sequence[str],
    *,
    strict_lineage: bool,
    exemption_field: str,
) -> list[_Component]:
    parents = list(range(len(examples)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parents[max(left_root, right_root)] = min(left_root, right_root)

    owner: dict[str, int] = {}
    row_tokens: list[tuple[str, ...]] = []
    for index, example in enumerate(examples):
        if strict_lineage:
            identifiers = validated_lineage_identifiers(
                example,
                disjoint_keys=disjoint_keys,
                exemption_field=exemption_field,
            )
            tokens = tuple(
                f"{key}=str:{identifier}"
                for key in disjoint_keys
                for identifier in identifiers.get(key, ())
            )
        else:
            tokens = _tokens_for_fields(
                example, disjoint_keys, missing_token=False
            )
        if not tokens:
            joined = ", ".join(disjoint_keys)
            raise KeyError(
                f"example {example.example_id!r} has none of the disjoint fields: {joined}"
            )
        row_tokens.append(tokens)
        for token in tokens:
            previous = owner.setdefault(token, index)
            union(index, previous)

    grouped: dict[int, list[int]] = {}
    for index in range(len(examples)):
        grouped.setdefault(find(index), []).append(index)

    result: list[_Component] = []
    for indices in grouped.values():
        lineage = sorted({token for index in indices for token in row_tokens[index]})
        strata: Counter[str] = Counter()
        for index in indices:
            strata.update(
                _tokens_for_fields(
                    examples[index], strata_keys, missing_token=True
                )
            )
        result.append(
            _Component(
                indices=tuple(indices),
                signature="|".join(lineage),
                strata=strata,
            )
        )
    return result


def _stratified_assignments(
    components: Sequence[_Component],
    *,
    seed: int,
    fractions: tuple[float, float, float],
) -> dict[int, str]:
    """Greedily balance atomic components across every requested marginal."""

    total_examples = sum(len(component.indices) for component in components)
    stratum_totals: Counter[str] = Counter()
    for component in components:
        stratum_totals.update(component.strata)

    current_sizes = {split: 0 for split in _SPLIT_NAMES}
    current_strata = {split: Counter() for split in _SPLIT_NAMES}
    assignments: dict[int, str] = {}
    ordered = sorted(
        components,
        key=lambda component: (
            -len(component.indices),
            sha256(f"{seed}:{component.signature}".encode("utf-8")).hexdigest(),
        ),
    )

    def score(component: _Component, candidate: str) -> float:
        value = 0.0
        for split, fraction in zip(_SPLIT_NAMES, fractions):
            size = current_sizes[split]
            if split == candidate:
                size += len(component.indices)
            target = total_examples * fraction
            value += (size - target) ** 2 / max(target, 1.0)
            for stratum, total in stratum_totals.items():
                count = current_strata[split][stratum]
                if split == candidate:
                    count += component.strata[stratum]
                marginal_target = total * fraction
                value += (count - marginal_target) ** 2 / max(marginal_target, 1.0)
        return value

    for component in ordered:
        ranked: list[tuple[float, str, str]] = []
        for split in _SPLIT_NAMES:
            tie_break = sha256(
                f"{seed}:{component.signature}:{split}".encode("utf-8")
            ).hexdigest()
            ranked.append((score(component, split), tie_break, split))
        selected = min(ranked)[2]
        current_sizes[selected] += len(component.indices)
        current_strata[selected].update(component.strata)
        for index in component.indices:
            assignments[index] = selected
    return assignments


def assign_splits(
    examples: Sequence[Example],
    *,
    seed: int = 0,
    fractions: tuple[float, float, float] = (0.2, 0.3, 0.5),
    key_field: str | None = None,
    disjoint_keys: Sequence[str] | None = None,
    strata_keys: Sequence[str] = (),
    lineage_exemption_field: str = LINEAGE_EXEMPTION_FIELD,
    legacy_single_key_mode: bool = False,
) -> list[Example]:
    """Return copies assigned by leakage components and optional marginal strata.

    Rows are joined transitively whenever they share any value under the same
    disjoint field. The resulting connected component is atomic. The primary
    path requires a value or validated exemption for every declared disjoint
    key. Historical single-key behavior requires legacy_single_key_mode=True.
    """

    _validate_fractions(fractions)
    if legacy_single_key_mode:
        if disjoint_keys is not None:
            raise ValueError(
                "legacy_single_key_mode accepts key_field, not disjoint_keys"
            )
        keys = _validate_fields(
            "disjoint_keys", (key_field or "example_id",)
        )
    else:
        if key_field is not None:
            raise ValueError(
                "key_field requires legacy_single_key_mode=True"
            )
        keys = _validate_fields(
            "disjoint_keys",
            disjoint_keys
            if disjoint_keys is not None
            else DEFAULT_DISJOINT_KEYS,
        )
    strata = (
        _validate_fields("strata_keys", strata_keys) if strata_keys else ()
    )
    overlap = set(keys) & set(strata)
    if overlap:
        raise ValueError("disjoint_keys and strata_keys must not overlap")
    if not examples:
        return []

    components = _components(
        examples,
        keys,
        strata,
        strict_lineage=not legacy_single_key_mode,
        exemption_field=lineage_exemption_field,
    )
    if strata:
        assignments = _stratified_assignments(
            components, seed=seed, fractions=fractions
        )
    else:
        assignments = {
            index: deterministic_split(
                component.signature, seed=seed, fractions=fractions
            )
            for component in components
            for index in component.indices
        }
    return [
        replace(example, split=assignments[index])
        for index, example in enumerate(examples)
    ]
