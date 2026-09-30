"""Load and validate frozen CalibRead P03 TOML study configurations."""

from __future__ import annotations

import argparse
from math import isfinite
import re
import tomllib
from pathlib import Path
from typing import Mapping, Sequence

from .dimensions import DIMENSION_REGISTRY, R7_THRESHOLD_LEVELS
from .leakage import (
    DEFAULT_DISJOINT_KEYS,
    LINEAGE_EXEMPTION_FIELD,
    LINEAGE_EXEMPTION_REASONS,
    NON_EXEMPTABLE_DISJOINT_KEYS,
    QUESTION_HASH_METHOD,
)

REQUIRED_DIMENSIONS = frozenset(f"R{index}" for index in range(1, 8))
CANONICAL_DIMENSIONS = tuple(DIMENSION_REGISTRY)
CANONICAL_INTERACTIONS = ("R1xR5", "R3xR6", "R4xR7")
CANONICAL_TRACKS = ("finite_label_certified", "open_ended_stress")
CANONICAL_ESTIMANDS = {
    "OP-R1": "tail minus head risk and calibration contrast",
    "OP-R2": "fine minus coarse typed-error risk contrast",
    "OP-R3": "each post-cutoff band minus pre-cutoff risk and calibration contrast",
    "OP-R4": "ambiguity-level risk, set-size, and consistency contrasts",
    "OP-R5": "depth trend, synthesis loss, and factorized residual",
    "OP-R6": "expert minus general risk and calibration contrast",
    "OP-R7": "risk-coverage, answer-rate, set-size, abstention, and AURC frontier",
    "OP-I15": "non-additive R1 by R5 long-tail synthesis effect",
    "OP-I36": "R3 recency effect difference by R6 domain specificity",
    "OP-I47": "R4 ambiguity-dependent R7 policy-frontier difference",
    "OP-CPR": "finite-label coverage gap and efficiency with open-ended oracle recall separate",
    "OP-CONTRACT": "risk and action utility under answer, set, abstain, and unsupported decisions",
}
REQUIRED_ESTIMANDS = frozenset(CANONICAL_ESTIMANDS)

_DIMENSION_FIELDS = {
    "R1": (
        ("frequency_value", "frequency_source", "frequency_unit"),
        "r1_frequency_level",
        "middle",
    ),
    "R2": (
        ("answer_type", "required_granularity", "numeric_tolerance"),
        "r2_precision_level",
        "medium",
    ),
    "R3": (
        ("event_date", "model_cutoff_date", "months_from_cutoff"),
        "r3_recency_level",
        "pre_cutoff",
    ),
    "R4": (
        ("interpretation_count", "accepted_interpretation_ids"),
        "r4_ambiguity_level",
        "unambiguous",
    ),
    "R5": (
        ("hop_count", "chain_id", "constituent_example_ids"),
        "r5_synthesis_level",
        "one_hop",
    ),
    "R6": (
        ("domain_name", "domain_taxonomy", "specificity_score"),
        "r6_domain_level",
        "general",
    ),
    "R7": (
        ("confidence_source", "threshold"),
        "r7_policy_level",
        0.70,
    ),
}
_REQUIRED_DISJOINT_KEYS = frozenset(DEFAULT_DISJOINT_KEYS)
_CANONICAL_STRATA_KEYS = tuple(
    _DIMENSION_FIELDS[code][1] for code in CANONICAL_DIMENSIONS if code != "R7"
) + ("r1_x_r5_cell", "r3_x_r6_cell")
_MAPPING_METHODS = {
    "R1": "frozen_frequency_source_cutpoints",
    "R2": "typed_answer_precision_rubric",
    "R6": "frozen_domain_taxonomy_specificity_cutpoints",
}
_DEVELOPMENT_MAPPING_HASH = "tbd_before_main_inference"
_FINAL_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
_FULL_BREADTH_LEVELS = {
    "R1": list(DIMENSION_REGISTRY["R1"].levels),
    "R2": list(DIMENSION_REGISTRY["R2"].levels),
    "R3": list(DIMENSION_REGISTRY["R3"].levels),
    "R4": ["unambiguous", "three_plus"],
    "R5": ["one_hop", "four_plus_hop"],
    "R6": ["general", "expert"],
    "R7": list(DIMENSION_REGISTRY["R7"].levels),
}


def _table(config: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = config.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"configuration requires a [{key}] table")
    return value


def _string_list(
    value: object,
    label: str,
    *,
    expected: Sequence[str] | None = None,
) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{label} must be a list of nonempty strings")
    normalized = [item.strip() for item in value]
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{label} must not contain duplicates")
    if expected is not None and normalized != list(expected):
        raise ValueError(f"{label} differs from the canonical P03 protocol")
    return normalized


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    number = float(value)
    if not isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def _number_list(value: object, label: str) -> list[float]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a nonempty numeric list")
    return [_number(item, label) for item in value]


def _coverage_targets(value: object) -> list[float]:
    supplied = value if isinstance(value, list) else [value]
    targets = [_number(item, "study.target_coverage") for item in supplied]
    if any(not 0.0 < target < 1.0 for target in targets):
        raise ValueError("study.target_coverage values must lie strictly between 0 and 1")
    if targets != sorted(set(targets)):
        raise ValueError("study.target_coverage values must be unique and increasing")
    return targets


def _validate_study(
    config: Mapping[str, object],
) -> tuple[str, bool, list[float]]:
    study = _table(config, "study")
    if not isinstance(study.get("name"), str) or not str(study["name"]).strip():
        raise ValueError("study.name must be a nonempty string")
    stage = study.get("stage")
    if stage not in {"pilot", "full"}:
        raise ValueError("study.stage must be pilot or full")
    finalized = study.get("finalized")
    if not isinstance(finalized, bool):
        raise ValueError("study.finalized must be boolean")
    if not isinstance(study.get("protocol_version"), str) or not str(
        study["protocol_version"]
    ).strip():
        raise ValueError("study.protocol_version must be a nonempty string")
    seed = study.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("study.seed must be an integer")
    expected_design = {
        "pilot": "controlled_one_dimension_sweeps",
        "full": "controlled_sweeps_with_selected_interactions",
    }[stage]
    if study.get("design") != expected_design:
        raise ValueError(f"study.design must be {expected_design!r} for stage {stage}")
    return stage, finalized, _coverage_targets(study.get("target_coverage"))


def _validate_scope(config: Mapping[str, object]) -> None:
    scope = _table(config, "scope")
    dimensions = _string_list(
        scope.get("dimensions"), "scope.dimensions", expected=CANONICAL_DIMENSIONS
    )
    if set(dimensions) != REQUIRED_DIMENSIONS:
        raise ValueError("scope.dimensions must contain each of R1 through R7 exactly once")
    _string_list(
        scope.get("confirmatory_interactions"),
        "scope.confirmatory_interactions",
        expected=CANONICAL_INTERACTIONS,
    )
    _string_list(
        scope.get("tracks"), "scope.tracks", expected=CANONICAL_TRACKS
    )


def _validate_dimensions(
    config: Mapping[str, object], *, finalized: bool
) -> None:
    dimensions = _table(config, "dimensions")
    if set(dimensions) != REQUIRED_DIMENSIONS:
        raise ValueError(
            "configuration requires exactly [dimensions.R1] through [dimensions.R7]"
        )
    for code, spec in DIMENSION_REGISTRY.items():
        value = dimensions.get(code)
        if not isinstance(value, Mapping):
            raise ValueError(f"configuration requires a [dimensions.{code}] table")
        raw_fields, level_field, anchor = _DIMENSION_FIELDS[code]
        if value.get("name") != spec.slug:
            raise ValueError(f"dimensions.{code}.name must be {spec.slug!r}")
        _string_list(
            value.get("raw_fields"),
            f"dimensions.{code}.raw_fields",
            expected=raw_fields,
        )
        if value.get("level_field") != level_field:
            raise ValueError(
                f"dimensions.{code}.level_field must be {level_field!r}"
            )
        _string_list(
            value.get("levels"),
            f"dimensions.{code}.levels",
            expected=spec.levels,
        )
        supplied_anchor = value.get("anchor")
        if isinstance(anchor, float):
            if abs(_number(supplied_anchor, f"dimensions.{code}.anchor") - anchor) > 1e-12:
                raise ValueError(f"dimensions.{code}.anchor differs from the protocol")
        elif supplied_anchor != anchor:
            raise ValueError(f"dimensions.{code}.anchor differs from the protocol")
        if code in _MAPPING_METHODS:
            if value.get("level_mapping_method") != _MAPPING_METHODS[code]:
                raise ValueError(
                    f"dimensions.{code}.level_mapping_method differs from the protocol"
                )
            mapping_hash = value.get("level_mapping_manifest_hash")
            if not isinstance(mapping_hash, str) or not mapping_hash.strip():
                raise ValueError(
                    f"dimensions.{code}.level_mapping_manifest_hash must be nonempty"
                )
            if mapping_hash != _DEVELOPMENT_MAPPING_HASH and not _FINAL_HASH.fullmatch(
                mapping_hash
            ):
                raise ValueError(
                    f"dimensions.{code}.level_mapping_manifest_hash must be the "
                    "development marker or a sha256 digest"
                )
            if finalized and mapping_hash == _DEVELOPMENT_MAPPING_HASH:
                raise ValueError(
                    f"finalized configuration cannot retain a TBD {code} mapping hash"
                )
        if code == "R7":
            thresholds = _number_list(
                value.get("thresholds"), "dimensions.R7.thresholds"
            )
            if thresholds != list(R7_THRESHOLD_LEVELS):
                raise ValueError(
                    "dimensions.R7.thresholds differ from the canonical registry"
                )


def _validate_policy(
    config: Mapping[str, object], target_coverage: Sequence[float]
) -> None:
    policy = _table(config, "policy")
    thresholds = _number_list(policy.get("r7_thresholds"), "policy.r7_thresholds")
    if thresholds != list(R7_THRESHOLD_LEVELS):
        raise ValueError("R7 thresholds must match the frozen P03 policy sweep")
    levels = _string_list(policy.get("r7_levels"), "policy.r7_levels")
    if levels != list(R7_THRESHOLD_LEVELS.values()):
        raise ValueError("R7 levels must correspond one-to-one with frozen thresholds")
    alpha = _number_list(policy.get("conformal_alpha"), "policy.conformal_alpha")
    if any(not 0.0 < value < 1.0 for value in alpha) or len(set(alpha)) != len(alpha):
        raise ValueError("policy.conformal_alpha values must be unique and lie in (0, 1)")
    implied = [1.0 - value for value in alpha]
    if len(implied) != len(target_coverage) or any(
        abs(left - right) > 1e-12
        for left, right in zip(implied, target_coverage)
    ):
        raise ValueError(
            "study.target_coverage must correspond one-to-one with policy.conformal_alpha"
        )


def _validate_splits(config: Mapping[str, object]) -> tuple[float, float, float]:
    splits = _table(config, "splits")
    fractions = (
        _number(splits.get("development_fraction"), "splits.development_fraction"),
        _number(splits.get("calibration_fraction"), "splits.calibration_fraction"),
        _number(splits.get("test_fraction"), "splits.test_fraction"),
    )
    if any(value < 0.0 for value in fractions) or abs(sum(fractions) - 1.0) > 1e-12:
        raise ValueError(
            "development/calibration/test fractions must be nonnegative and sum to 1"
        )
    disjoint = _string_list(splits.get("disjoint_keys"), "splits.disjoint_keys")
    missing = _REQUIRED_DISJOINT_KEYS - set(disjoint)
    if missing:
        raise ValueError(
            "splits.disjoint_keys must include entity, chain, template, source-fact, "
            "and question-hash lineage"
        )
    if disjoint != list(DEFAULT_DISJOINT_KEYS):
        raise ValueError(
            "splits.disjoint_keys must use the canonical ordered lineage keys"
        )
    if splits.get("missing_lineage_policy") != (
        "require_value_or_explicit_exemption"
    ):
        raise ValueError(
            "splits.missing_lineage_policy must fail on unexplained missing keys"
        )
    if splits.get("lineage_exemption_field") != LINEAGE_EXEMPTION_FIELD:
        raise ValueError(
            f"splits.lineage_exemption_field must be {LINEAGE_EXEMPTION_FIELD!r}"
        )
    _string_list(
        splits.get("allowed_lineage_exemption_reasons"),
        "splits.allowed_lineage_exemption_reasons",
        expected=LINEAGE_EXEMPTION_REASONS,
    )
    _string_list(
        splits.get("non_exemptable_disjoint_keys"),
        "splits.non_exemptable_disjoint_keys",
        expected=NON_EXEMPTABLE_DISJOINT_KEYS,
    )
    if splits.get("question_hash_method") != QUESTION_HASH_METHOD:
        raise ValueError(
            "splits.question_hash_method differs from the canonical hash method"
        )
    if splits.get("legacy_single_key_mode") is not False:
        raise ValueError(
            "canonical study configs must set legacy_single_key_mode=false"
        )
    strata = _string_list(
        splits.get("strata_keys"),
        "splits.strata_keys",
        expected=_CANONICAL_STRATA_KEYS,
    )
    if set(disjoint) & set(strata):
        raise ValueError("splits.disjoint_keys and splits.strata_keys must not overlap")
    if splits.get("assignment_unit") != "connected_components":
        raise ValueError("splits.assignment_unit must be 'connected_components'")
    if splits.get("stratification") != "marginal_greedy":
        raise ValueError("splits.stratification must be 'marginal_greedy'")
    return fractions


def _validate_target_block(
    gates: Mapping[str, object],
    fractions: Sequence[float],
    *,
    development_key: str,
    calibration_key: str,
    test_key: str,
) -> int:
    targets = (
        _positive_int(gates.get(development_key), f"sample_gates.{development_key}"),
        _positive_int(gates.get(calibration_key), f"sample_gates.{calibration_key}"),
        _positive_int(gates.get(test_key), f"sample_gates.{test_key}"),
    )
    total = sum(targets)
    if any(
        abs(target / total - fraction) > 1e-12
        for target, fraction in zip(targets, fractions)
    ):
        raise ValueError(
            f"{development_key}, {calibration_key}, and {test_key} must exactly "
            "match the configured split fractions"
        )
    return total


def _validate_sample_gates(
    config: Mapping[str, object],
    fractions: Sequence[float],
    stage: str,
) -> tuple[int, int, int | None]:
    gates = _table(config, "sample_gates")
    if gates.get("quota_mode") != "exact_targets_after_exclusions":
        raise ValueError(
            "sample_gates.quota_mode must be 'exact_targets_after_exclusions'"
        )
    main_total = _validate_target_block(
        gates,
        fractions,
        development_key="target_development_per_level",
        calibration_key="target_calibration_per_level",
        test_key="target_test_per_level",
    )
    interaction_total = _validate_target_block(
        gates,
        fractions,
        development_key="target_development_per_interaction_cell",
        calibration_key="target_calibration_per_interaction_cell",
        test_key="target_test_per_interaction_cell",
    )
    main_floor = _positive_int(
        gates.get("hard_floor_test_per_main_level"),
        "sample_gates.hard_floor_test_per_main_level",
    )
    interaction_floor = _positive_int(
        gates.get("hard_floor_test_per_interaction_cell"),
        "sample_gates.hard_floor_test_per_interaction_cell",
    )
    if main_floor > gates["target_test_per_level"]:
        raise ValueError("main-level test hard floor must not exceed its target")
    if interaction_floor > gates["target_test_per_interaction_cell"]:
        raise ValueError("interaction-cell test hard floor must not exceed its target")
    _positive_int(
        gates.get("human_audit_per_dimension"),
        "sample_gates.human_audit_per_dimension",
    )
    recall = _number(
        gates.get("minimum_candidate_oracle_recall"),
        "sample_gates.minimum_candidate_oracle_recall",
    )
    if not 0.0 < recall <= 1.0:
        raise ValueError("minimum_candidate_oracle_recall must lie in (0, 1]")

    breadth_total: int | None = None
    if stage == "full":
        breadth_total = _validate_target_block(
            gates,
            fractions,
            development_key="breadth_target_development_per_level",
            calibration_key="breadth_target_calibration_per_level",
            test_key="breadth_target_test_per_level",
        )
    return main_total, interaction_total, breadth_total


def _validate_models(
    config: Mapping[str, object], stage: str
) -> tuple[list[str], list[str], Mapping[str, object] | None]:
    models = _table(config, "models")
    families = _string_list(models.get("family_slots"), "models.family_slots")
    full = _string_list(
        models.get("full_suite_family_ids"), "models.full_suite_family_ids"
    )
    if not set(full) <= set(families):
        raise ValueError("models.full_suite_family_ids must be a subset of family_slots")
    if stage == "pilot":
        if len(families) != 1 or full != families:
            raise ValueError("the pilot requires one family that runs the full suite")
        return families, full, None

    if len(families) != 10:
        raise ValueError("the full P03 study requires exactly ten unique family slots")
    if len(full) != 3:
        raise ValueError("the full P03 study requires exactly three full-suite families")
    if models.get("breadth_scope") != "R1_R3_all_R4_R6_anchor_hard_R7_all_fixed":
        raise ValueError("models.breadth_scope differs from the frozen Phase-1 plan")
    if not isinstance(models.get("selection_gate"), str) or not str(
        models["selection_gate"]
    ).strip():
        raise ValueError("models.selection_gate must be a nonempty string")
    breadth = models.get("breadth_levels")
    if not isinstance(breadth, Mapping) or set(breadth) != REQUIRED_DIMENSIONS:
        raise ValueError("models.breadth_levels must define exactly R1 through R7")
    for code, expected in _FULL_BREADTH_LEVELS.items():
        _string_list(
            breadth.get(code),
            f"models.breadth_levels.{code}",
            expected=expected,
        )
    return families, full, breadth


def _validate_evaluation(config: Mapping[str, object]) -> None:
    evaluation = _table(config, "evaluation")
    _positive_int(evaluation.get("confidence_bins"), "evaluation.confidence_bins")
    _positive_int(
        evaluation.get("bootstrap_replicates"), "evaluation.bootstrap_replicates"
    )
    if evaluation.get("unseen_group_policy") != "abstain":
        raise ValueError("evaluation.unseen_group_policy must be 'abstain'")
    if evaluation.get("primary_estimand_registry") != "docs/hypothesis_registry.md":
        raise ValueError(
            "evaluation.primary_estimand_registry must name the authoritative registry"
        )
    if evaluation.get("primary_estimand_registry_authority") != (
        "authoritative_frozen_definitions"
    ):
        raise ValueError(
            "evaluation.primary_estimand_registry_authority must freeze registry authority"
        )
    estimands = evaluation.get("primary_estimands")
    if not isinstance(estimands, Mapping) or set(estimands) != REQUIRED_ESTIMANDS:
        raise ValueError(
            "evaluation.primary_estimands must define every frozen OP-R, OP-I, "
            "OP-CPR, and OP-CONTRACT key"
        )
    for identifier, description in CANONICAL_ESTIMANDS.items():
        if estimands.get(identifier) != description:
            raise ValueError(
                f"evaluation.primary_estimands.{identifier} differs from its "
                "registered operational description"
            )
    _string_list(evaluation.get("secondary_metrics"), "evaluation.secondary_metrics")


def _validate_budget(
    config: Mapping[str, object],
    *,
    families: Sequence[str],
    full_families: Sequence[str],
    breadth_levels: Mapping[str, object],
    main_total: int,
    interaction_total: int,
    breadth_total: int,
) -> None:
    main_level_count = sum(
        len(DIMENSION_REGISTRY[code].levels)
        for code in CANONICAL_DIMENSIONS
        if code != "R7"
    )
    generated_interaction_cells = (
        len(DIMENSION_REGISTRY["R1"].levels)
        * len(DIMENSION_REGISTRY["R5"].levels)
        + len(DIMENSION_REGISTRY["R3"].levels)
        * len(DIMENSION_REGISTRY["R6"].levels)
    )
    additional_families = len(families) - len(full_families)
    breadth_generated_levels = sum(
        len(breadth_levels[code])  # type: ignore[arg-type]
        for code in CANONICAL_DIMENSIONS
        if code != "R7"
    )
    expected = {
        "main_generated_level_count": main_level_count,
        "main_target_questions_per_level": main_total,
        "full_suite_marginal_pairs": (
            len(full_families) * main_level_count * main_total
        ),
        "generated_interaction_cell_count": generated_interaction_cells,
        "interaction_target_questions_per_cell": interaction_total,
        "full_suite_interaction_pairs": (
            len(full_families)
            * generated_interaction_cells
            * interaction_total
        ),
        "additional_breadth_family_count": additional_families,
        "breadth_generated_level_count": breadth_generated_levels,
        "breadth_target_questions_per_level": breadth_total,
        "additional_breadth_pairs": (
            additional_families * breadth_generated_levels * breadth_total
        ),
    }
    expected["base_pair_budget_before_overcollection"] = (
        expected["full_suite_marginal_pairs"]
        + expected["full_suite_interaction_pairs"]
        + expected["additional_breadth_pairs"]
    )
    budget = _table(config, "budget")
    if set(budget) != set(expected):
        raise ValueError("budget must contain exactly the canonical arithmetic fields")
    for key, value in expected.items():
        configured = _positive_int(budget.get(key), f"budget.{key}")
        if configured != value:
            raise ValueError(
                f"budget.{key} must equal the value implied by models, levels, and targets"
            )


def validate_study_config(config: Mapping[str, object]) -> None:
    """Reject protocol drift in the canonical pilot or full P03 configuration."""

    stage, finalized, target_coverage = _validate_study(config)
    _validate_scope(config)
    _validate_dimensions(config, finalized=finalized)
    _validate_policy(config, target_coverage)
    fractions = _validate_splits(config)
    main_total, interaction_total, breadth_total = _validate_sample_gates(
        config, fractions, stage
    )
    families, full_families, breadth_levels = _validate_models(config, stage)
    _validate_evaluation(config)
    if stage == "full":
        if breadth_total is None or breadth_levels is None:
            raise ValueError("full study requires breadth targets and levels")
        _validate_budget(
            config,
            families=families,
            full_families=full_families,
            breadth_levels=breadth_levels,
            main_total=main_total,
            interaction_total=interaction_total,
            breadth_total=breadth_total,
        )


def load_study_config(path: str | Path) -> dict[str, object]:
    """Load and validate a TOML study configuration."""

    with Path(path).open("rb") as stream:
        config = tomllib.load(stream)
    validate_study_config(config)
    return config


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    arguments = parser.parse_args(argv)
    load_study_config(arguments.config)
    print(f"valid CalibRead P03 configuration: {arguments.config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
