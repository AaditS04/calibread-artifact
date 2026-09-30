"""Immutable provenance records for reproducible CalibRead runs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, fields, replace
from math import isfinite
from types import MappingProxyType
from typing import Mapping


_PLACEHOLDERS = {
    "development",
    "unspecified",
    "tbd",
    "unknown",
    "replace",
    "replace_me",
}
_TRACKS = {"finite_label_certified", "open_ended_stress"}


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


def _placeholder(value: object) -> bool:
    return str(value).strip().casefold() in _PLACEHOLDERS


def _sha256_hex(value: object, name: str) -> str:
    normalized = str(value).strip().casefold()
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise ValueError(f"{name} must be a 64-character SHA-256 hex digest")
    return normalized


def _placeholder_paths(value: object, path: str) -> list[str]:
    if isinstance(value, Mapping):
        result: list[str] = []
        for key, item in value.items():
            result.extend(_placeholder_paths(item, f"{path}.{key}"))
        return result
    if isinstance(value, tuple):
        result = []
        for index, item in enumerate(value):
            result.extend(_placeholder_paths(item, f"{path}[{index}]"))
        return result
    return [path] if isinstance(value, str) and _placeholder(value) else []


@dataclass(frozen=True)
class RunManifest:
    """Minimum information required to audit a cached model run."""

    run_id: str
    model_id: str
    model_revision: str
    dataset_id: str
    dataset_revision: str
    prompt_template: str
    correctness_rule: str
    calibration_ids_hash: str
    test_ids_hash: str
    code_revision: str
    model_snapshot_id: str
    condition_table_hash: str
    seed: int
    decoding: Mapping[str, object] = field(default_factory=dict)
    hardware: Mapping[str, object] = field(default_factory=dict)
    protocol_version: str = "development"
    dimension_schema_hash: str = "development"
    dimension_bin_hash: str = "development"
    tokenizer_revision: str = "development"
    dataset_license: str = "development"
    dataset_source_url: str = "development"
    evaluation_track: str = "development"
    model_cutoff: str = "development"
    model_cutoff_source: str = "development"
    model_cutoff_uncertainty: str = "development"
    candidate_constructor: str = "development"
    scoring_rule: str = "development"
    calibration_method: str = "development"
    calibration_object_hash: str = "development"
    split_manifest_hash: str = "development"
    package_lock_hash: str = "development"
    model_parameter_count: int | None = None
    model_capacity_measure: str = "development"
    dimension_settings: Mapping[str, object] = field(default_factory=dict)
    policy_grid: tuple[float, ...] = ()
    runtime: Mapping[str, object] = field(default_factory=dict)
    artifact_hashes: Mapping[str, object] = field(default_factory=dict)
    is_finalized: bool = False
    schema_version: int = 3

    def __post_init__(self) -> None:
        required = (
            self.run_id,
            self.model_id,
            self.model_revision,
            self.dataset_id,
            self.dataset_revision,
            self.prompt_template,
            self.correctness_rule,
            self.calibration_ids_hash,
            self.test_ids_hash,
            self.code_revision,
            self.model_snapshot_id,
            self.protocol_version,
            self.dimension_schema_hash,
            self.dimension_bin_hash,
        )
        if any(not str(value).strip() for value in required):
            raise ValueError("manifest string fields must not be blank")
        object.__setattr__(
            self,
            "condition_table_hash",
            _sha256_hex(self.condition_table_hash, "condition_table_hash"),
        )
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version < 1
        ):
            raise ValueError("schema_version must be positive")
        if not isinstance(self.is_finalized, bool):
            raise ValueError("is_finalized must be boolean")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("seed must be an integer")
        if self.model_parameter_count is not None and (
            isinstance(self.model_parameter_count, bool)
            or not isinstance(self.model_parameter_count, int)
            or self.model_parameter_count <= 0
        ):
            raise ValueError("model_parameter_count must be a positive integer or None")
        if any(isinstance(value, bool) for value in self.policy_grid):
            raise ValueError("policy_grid values must be numeric thresholds, not booleans")
        policy_grid = tuple(float(value) for value in self.policy_grid)
        if any(not isfinite(value) or not 0.0 <= value <= 1.0 for value in policy_grid):
            raise ValueError("policy_grid values must be finite and lie in [0, 1]")
        if len(set(policy_grid)) != len(policy_grid):
            raise ValueError("policy_grid values must be unique")
        if policy_grid != tuple(sorted(policy_grid)):
            raise ValueError("policy_grid values must be in increasing order")
        object.__setattr__(self, "policy_grid", policy_grid)
        for name in ("decoding", "hardware", "dimension_settings", "runtime", "artifact_hashes"):
            value = getattr(self, name)
            if not isinstance(value, Mapping):
                raise ValueError(f"{name} must be a mapping")
            object.__setattr__(self, name, _freeze_json(value, name))
        if self.is_finalized:
            self.validate_finalized()

    def to_dict(self) -> dict[str, object]:
        return {
            item.name: _thaw_json(getattr(self, item.name))
            for item in fields(self)
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "RunManifest":
        return cls(**dict(value))  # type: ignore[arg-type]

    def validate_finalized(self) -> None:
        """Reject placeholders or missing provenance before a real run is certified immutable."""

        final_strings = {
            "run_id": self.run_id,
            "model_id": self.model_id,
            "model_revision": self.model_revision,
            "dataset_id": self.dataset_id,
            "dataset_revision": self.dataset_revision,
            "prompt_template": self.prompt_template,
            "correctness_rule": self.correctness_rule,
            "calibration_ids_hash": self.calibration_ids_hash,
            "test_ids_hash": self.test_ids_hash,
            "code_revision": self.code_revision,
            "model_snapshot_id": self.model_snapshot_id,
            "condition_table_hash": self.condition_table_hash,
            "protocol_version": self.protocol_version,
            "dimension_schema_hash": self.dimension_schema_hash,
            "dimension_bin_hash": self.dimension_bin_hash,
            "tokenizer_revision": self.tokenizer_revision,
            "dataset_license": self.dataset_license,
            "dataset_source_url": self.dataset_source_url,
            "model_cutoff": self.model_cutoff,
            "model_cutoff_source": self.model_cutoff_source,
            "model_cutoff_uncertainty": self.model_cutoff_uncertainty,
            "candidate_constructor": self.candidate_constructor,
            "scoring_rule": self.scoring_rule,
            "calibration_method": self.calibration_method,
            "calibration_object_hash": self.calibration_object_hash,
            "split_manifest_hash": self.split_manifest_hash,
            "package_lock_hash": self.package_lock_hash,
            "model_capacity_measure": self.model_capacity_measure,
        }
        invalid = [
            name
            for name, value in final_strings.items()
            if not str(value).strip() or _placeholder(value)
        ]
        if invalid:
            raise ValueError(
                "finalized manifest contains placeholder fields: " + ", ".join(invalid)
            )
        if self.evaluation_track not in _TRACKS:
            raise ValueError("finalized manifest requires a declared evaluation_track")
        if self.model_parameter_count is None:
            raise ValueError("finalized manifest requires model_parameter_count")
        if set(self.dimension_settings) != {f"R{index}" for index in range(1, 8)}:
            raise ValueError("finalized manifest requires settings for exactly R1 through R7")
        if not self.policy_grid:
            raise ValueError("finalized manifest requires a nonempty R7 policy_grid")
        from .dimensions import r7_from_threshold

        for threshold in self.policy_grid:
            r7_from_threshold(threshold)
        for name in ("decoding", "hardware", "runtime", "artifact_hashes"):
            if not getattr(self, name):
                raise ValueError(f"finalized manifest requires nonempty {name}")
        nested_placeholders: list[str] = []
        for name in (
            "decoding",
            "hardware",
            "dimension_settings",
            "runtime",
            "artifact_hashes",
        ):
            nested_placeholders.extend(_placeholder_paths(getattr(self, name), name))
        if nested_placeholders:
            raise ValueError(
                "finalized manifest contains nested placeholders: "
                + ", ".join(nested_placeholders)
            )

    def finalized_copy(self) -> "RunManifest":
        """Return a validated copy marked as ready for a real immutable run."""

        return replace(self, is_finalized=True)

    def content_hash(self) -> str:
        """Hash canonical JSON so the manifest can name an immutable cache."""

        payload = json.dumps(
            self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
