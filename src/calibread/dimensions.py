"""Canonical definitions and validated values for the seven CalibRead axes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite
from types import MappingProxyType
from typing import Iterable, Mapping


Scalar = int | float | str
DIMENSIONS_METADATA_KEY = "calibread_dimensions"


@dataclass(frozen=True)
class DimensionSpec:
    """Schema for one controlled dimension from the P03 proposal."""

    code: str
    slug: str
    name: str
    dimension_type: str
    role: str
    raw_kinds: tuple[str, ...]
    levels: tuple[str, ...]
    unit: str
    minimum: float | None = None
    maximum: float | None = None
    integer: bool = False

    def __post_init__(self) -> None:
        if self.code not in {f"R{index}" for index in range(1, 8)}:
            raise ValueError("dimension code must be one of R1 through R7")
        if not self.slug.strip() or not self.name.strip() or not self.unit.strip():
            raise ValueError(f"{self.code} names and unit must not be empty")
        if self.role not in {"query", "policy"}:
            raise ValueError(f"{self.code} role must be query or policy")
        if not self.raw_kinds or not set(self.raw_kinds) <= {"number", "category"}:
            raise ValueError(f"{self.code} has invalid raw kinds")
        if len(set(self.levels)) != len(self.levels) or any(not level for level in self.levels):
            raise ValueError(f"{self.code} levels must be unique and nonempty")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError(f"{self.code} minimum must not exceed maximum")
        if self.integer and "number" not in self.raw_kinds:
            raise ValueError(f"{self.code} integer values require numeric raw kind")

    @property
    def is_policy(self) -> bool:
        """Return whether this axis is chosen at decision time."""

        return self.role == "policy"

    def validate_raw(self, value: object) -> Scalar:
        """Return a normalized raw value or reject an invalid measurement."""

        if isinstance(value, bool):
            raise ValueError(f"{self.code} raw value must not be boolean")
        if isinstance(value, (int, float)) and "number" in self.raw_kinds:
            numeric = float(value)
            if not isfinite(numeric):
                raise ValueError(f"{self.code} raw value must be finite")
            if self.integer and not numeric.is_integer():
                raise ValueError(f"{self.code} raw value must be an integer")
            if self.minimum is not None and numeric < self.minimum:
                raise ValueError(f"{self.code} raw value must be >= {self.minimum}")
            if self.maximum is not None and numeric > self.maximum:
                raise ValueError(f"{self.code} raw value must be <= {self.maximum}")
            return int(numeric) if self.integer else numeric
        if isinstance(value, str) and "category" in self.raw_kinds:
            normalized = value.strip()
            if not normalized:
                raise ValueError(f"{self.code} categorical raw value must not be empty")
            return normalized
        kinds = " or ".join(self.raw_kinds)
        raise ValueError(f"{self.code} raw value must be {kinds}")

    def validate_level(self, value: object) -> str:
        """Return a normalized registered level."""

        normalized = str(value).strip().casefold().replace("-", "_").replace(" ", "_")
        if normalized not in self.levels:
            allowed = ", ".join(self.levels)
            raise ValueError(f"{self.code} level must be one of: {allowed}")
        return normalized


R7_THRESHOLD_LEVELS: Mapping[float, str] = MappingProxyType(
    {
        0.50: "tau_0_50",
        0.70: "tau_0_70",
        0.90: "tau_0_90",
        0.95: "tau_0_95",
        0.99: "tau_0_99",
    }
)


_SPECS = (
    DimensionSpec('R1', 'knowledge_frequency', 'Knowledge Frequency', 'core', 'query', ('number',), ('head', 'middle', 'tail'), 'source-declared exposure count; unit stored in provenance', minimum=0.0),
    DimensionSpec("R2", "precision_requirement", "Precision Requirement", "core", "query", ("number", "category"), ("coarse", "medium", "fine"), "task-declared precision", minimum=0.0),
    DimensionSpec("R3", "knowledge_recency", "Knowledge Recency", "sequential", "query", ("number",), ("pre_cutoff", "post_0_3_months", "post_4_12_months", "post_13_plus_months"), "months relative to model cutoff"),
    DimensionSpec("R4", "query_ambiguity", "Query Ambiguity", "linguistic", "query", ("number",), ("unambiguous", "two_way", "three_plus"), "valid interpretations", minimum=1.0, integer=True),
    DimensionSpec("R5", "synthesis_depth", "Synthesis Depth", "structural", "query", ("number",), ("one_hop", "two_hop", "three_hop", "four_plus_hop"), "facts/hops combined", minimum=1.0, integer=True),
    DimensionSpec('R6', 'domain_specificity', 'Domain Specificity', 'structural', 'query', ('number',), ('general', 'specialized', 'expert'), 'normalized specificity score [0,1]; taxonomy stored in provenance', minimum=0.0, maximum=1.0),
    DimensionSpec("R7", "confidence_threshold", "Confidence Threshold", "core", "policy", ("number",), tuple(R7_THRESHOLD_LEVELS.values()), "probability threshold tau", minimum=0.0, maximum=1.0),
)

DIMENSION_REGISTRY: Mapping[str, DimensionSpec] = MappingProxyType(
    {spec.code: spec for spec in _SPECS}
)
_ALIASES = MappingProxyType(
    {alias.casefold(): spec.code for spec in _SPECS for alias in (spec.code, spec.slug)}
)


def dimension_spec(identifier: str) -> DimensionSpec:
    """Resolve a dimension by its R-code or canonical slug."""

    try:
        return DIMENSION_REGISTRY[_ALIASES[str(identifier).strip().casefold()]]
    except KeyError as error:
        raise ValueError(f"unknown CalibRead dimension {identifier!r}") from error


def _validated_pair(
    spec: DimensionSpec, raw: object, level: object
) -> tuple[Scalar, str]:
    normalized_raw = spec.validate_raw(raw)
    normalized_level = spec.validate_level(level)
    deterministic_level: str | None = None
    if spec.code == "R3":
        months = float(normalized_raw)
        deterministic_level = (
            "pre_cutoff"
            if months <= 0.0
            else (
                "post_0_3_months"
                if months <= 3.0
                else (
                    "post_4_12_months"
                    if months <= 12.0
                    else "post_13_plus_months"
                )
            )
        )
    elif spec.code == "R4":
        count = int(normalized_raw)
        deterministic_level = (
            "unambiguous" if count == 1 else "two_way" if count == 2 else "three_plus"
        )
    elif spec.code == "R5":
        count = int(normalized_raw)
        deterministic_level = (
            "one_hop"
            if count == 1
            else (
                "two_hop"
                if count == 2
                else "three_hop" if count == 3 else "four_plus_hop"
            )
        )
    if deterministic_level is not None and normalized_level != deterministic_level:
        raise ValueError(
            f"{spec.code} raw value and level must use the deterministic mapping"
        )
    if spec.code == "R7":
        matching = [
            expected
            for threshold, expected in R7_THRESHOLD_LEVELS.items()
            if abs(float(normalized_raw) - threshold) <= 1e-12
        ]
        if matching != [normalized_level]:
            raise ValueError("R7 raw threshold and level must use the frozen one-to-one mapping")
    return normalized_raw, normalized_level


@dataclass(frozen=True)
class DimensionValue:
    """One raw measurement paired with its controlled experimental level."""

    raw: Scalar
    level: str


@dataclass(frozen=True)
class DimensionValues:
    """Validated, JSON-serializable readings for any subset of R1--R7."""

    entries: Mapping[str, DimensionValue | Mapping[str, object]]

    def __post_init__(self) -> None:
        normalized: dict[str, DimensionValue] = {}
        for identifier, supplied in self.entries.items():
            spec = dimension_spec(identifier)
            if spec.code in normalized:
                raise ValueError(f"duplicate dimension {spec.code}")
            if isinstance(supplied, DimensionValue):
                raw, level = supplied.raw, supplied.level
            elif isinstance(supplied, Mapping):
                if set(supplied) != {"raw", "level"}:
                    raise ValueError(f"{spec.code} value must contain exactly raw and level")
                raw, level = supplied["raw"], supplied["level"]
            else:
                raise ValueError(f"{spec.code} value must be a DimensionValue or mapping")
            normalized_raw, normalized_level = _validated_pair(spec, raw, level)
            normalized[spec.code] = DimensionValue(
                raw=normalized_raw, level=normalized_level
            )
        object.__setattr__(self, "entries", MappingProxyType(normalized))

    def __len__(self) -> int:
        return len(self.entries)

    def __contains__(self, identifier: object) -> bool:
        try:
            return dimension_spec(str(identifier)).code in self.entries
        except ValueError:
            return False

    def __getitem__(self, identifier: str) -> DimensionValue:
        return self.entries[dimension_spec(identifier).code]  # type: ignore[return-value]

    def to_dict(self) -> dict[str, dict[str, Scalar | str]]:
        """Return a stable JSON-compatible representation ordered by R-code."""

        return {
            code: {"raw": self.entries[code].raw, "level": self.entries[code].level}  # type: ignore[union-attr]
            for code in DIMENSION_REGISTRY
            if code in self.entries
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "DimensionValues":
        """Validate a representation produced by :meth:`to_dict`."""

        return cls(value)  # type: ignore[arg-type]

    @classmethod
    def from_metadata(cls, metadata: Mapping[str, object]) -> "DimensionValues":
        """Read canonical dimensions from example metadata; absent means empty."""

        payload = metadata.get(DIMENSIONS_METADATA_KEY, {})
        if not isinstance(payload, Mapping):
            raise ValueError(f"metadata[{DIMENSIONS_METADATA_KEY!r}] must be a mapping")
        return cls.from_dict(payload)

    def merge_metadata(
        self, metadata: Mapping[str, object] | None = None, *, overwrite: bool = False
    ) -> dict[str, object]:
        """Copy metadata and add this validated dimension payload."""

        merged = dict(metadata or {})
        if DIMENSIONS_METADATA_KEY in merged and not overwrite:
            raise ValueError("metadata already contains CalibRead dimensions")
        merged[DIMENSIONS_METADATA_KEY] = self.to_dict()
        return merged

    def crossed_group(
        self, dimensions: Iterable[str], *, use_levels: bool = True
    ) -> str:
        """Build a label such as ``R1=tail|R5=four_plus_hop``."""

        parts: list[str] = []
        seen: set[str] = set()
        for identifier in dimensions:
            spec = dimension_spec(identifier)
            if spec.code in seen:
                raise ValueError(f"duplicate crossed dimension {spec.code}")
            seen.add(spec.code)
            if spec.code not in self.entries:
                raise ValueError(f"missing dimension {spec.code} for crossed group")
            reading = self.entries[spec.code]
            value = reading.level if use_levels else reading.raw  # type: ignore[union-attr]
            parts.append(f"{spec.code}={value}")
        if not parts:
            raise ValueError("crossed group requires at least one dimension")
        return "|".join(parts)


def dimension_value(identifier: str, raw: object, level: object) -> DimensionValue:
    """Construct one validated reading without building a collection."""

    spec = dimension_spec(identifier)
    normalized_raw, normalized_level = _validated_pair(spec, raw, level)
    return DimensionValue(normalized_raw, normalized_level)


def r3_from_relative_months(months: float) -> DimensionValue:
    '''Classify signed months with continuous, gap-free boundaries.

    Bins are m <= 0, 0 < m <= 3, 3 < m <= 12, and m > 12. The
    registered 4--12 and 13+ names are calendar shorthand.
    '''

    raw = dimension_spec("R3").validate_raw(months)
    level = "pre_cutoff" if float(raw) <= 0.0 else (
        "post_0_3_months" if float(raw) <= 3.0 else (
            "post_4_12_months" if float(raw) <= 12.0 else "post_13_plus_months"
        )
    )
    return dimension_value("R3", raw, level)


def _as_date(value: date | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as error:
        raise ValueError(f"date must use ISO YYYY-MM-DD form, got {value!r}") from error


def r3_from_dates(
    event_date: date | str,
    cutoff_date: date | str,
) -> DimensionValue:
    """Derive R3 using signed days divided by the mean Gregorian month."""

    months = (_as_date(event_date) - _as_date(cutoff_date)).days / (365.2425 / 12.0)
    return r3_from_relative_months(months)


def r1_from_frequency(
    frequency: float, *, tail_max: float, middle_max: float
) -> DimensionValue:
    """Classify R1 using cut points frozen by the experiment protocol."""

    raw = dimension_spec("R1").validate_raw(frequency)
    tail = dimension_spec("R1").validate_raw(tail_max)
    middle = dimension_spec("R1").validate_raw(middle_max)
    if not float(tail) < float(middle):
        raise ValueError("R1 requires tail_max < middle_max")
    level = "tail" if float(raw) <= float(tail) else (
        "middle" if float(raw) <= float(middle) else "head"
    )
    return dimension_value("R1", raw, level)


def r4_from_interpretation_count(count: int) -> DimensionValue:
    """Derive R4 from the audited number of valid interpretations."""

    raw = dimension_spec("R4").validate_raw(count)
    level = "unambiguous" if raw == 1 else "two_way" if raw == 2 else "three_plus"
    return dimension_value("R4", raw, level)


def r5_from_hop_count(count: int) -> DimensionValue:
    """Derive R5 from the audited number of facts or reasoning hops."""

    raw = dimension_spec("R5").validate_raw(count)
    level = "one_hop" if raw == 1 else (
        "two_hop" if raw == 2 else "three_hop" if raw == 3 else "four_plus_hop"
    )
    return dimension_value("R5", raw, level)


def r7_from_threshold(threshold: float) -> DimensionValue:
    """Construct the exact level paired with a frozen R7 policy threshold."""

    raw = dimension_spec("R7").validate_raw(threshold)
    for registered, level in R7_THRESHOLD_LEVELS.items():
        if abs(float(raw) - registered) <= 1e-12:
            return dimension_value("R7", registered, level)
    allowed = ", ".join(f"{value:.2f}" for value in R7_THRESHOLD_LEVELS)
    raise ValueError(f"R7 threshold must be one of the frozen values: {allowed}")


def r6_from_specificity(
    specificity: float, *, general_max: float, specialized_max: float
) -> DimensionValue:
    """Classify numeric R6 using protocol-supplied normalized cut points."""

    spec = dimension_spec("R6")
    raw = spec.validate_raw(specificity)
    general = spec.validate_raw(general_max)
    specialized = spec.validate_raw(specialized_max)
    if not isinstance(raw, float) or not isinstance(general, float) or not isinstance(specialized, float):
        raise ValueError("numeric R6 classification requires numeric values")
    if not general < specialized:
        raise ValueError("R6 requires general_max < specialized_max")
    level = "general" if raw <= general else (
        "specialized" if raw <= specialized else "expert"
    )
    return dimension_value("R6", raw, level)


def crossed_group_label(
    values: DimensionValues, dimensions: Iterable[str], *, use_levels: bool = True
) -> str:
    """Functional wrapper around :meth:`DimensionValues.crossed_group`."""

    return values.crossed_group(dimensions, use_levels=use_levels)


__all__ = [
    "DIMENSION_REGISTRY",
    "DIMENSIONS_METADATA_KEY",
    "DimensionSpec",
    "DimensionValue",
    "DimensionValues",
    "R7_THRESHOLD_LEVELS",
    "crossed_group_label",
    "dimension_value",
    "dimension_spec",
    "r1_from_frequency",
    "r3_from_dates",
    "r3_from_relative_months",
    "r4_from_interpretation_count",
    "r5_from_hop_count",
    "r6_from_specificity",
    "r7_from_threshold",
]
