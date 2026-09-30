"""CalibRead reliability evaluation and finite-label conformal utilities."""

from .ambiguity import AmbiguityReport, ambiguity_report
from .certificate import (
    CertificateCoverageScope,
    CertificateGuaranteeStatus,
    READ_CERTIFICATE_SCHEMA_VERSION,
    REQUIRED_CERTIFICATE_ASSUMPTIONS,
    ReadCertificate,
    build_read_certificate,
    validate_read_certificate,
)
from .composition import CompositionReport, composition_report
from .conformal import (
    GroupConformalClassifier,
    SplitConformalClassifier,
    apply_group_prediction_sets,
    conformal_quantile,
    empirical_coverage,
    finite_label_prediction_set,
    group_conformal_quantiles,
    true_label_nonconformity,
)
from .correctness import exact_match, normalize_answer, score_prediction
from .dimensions import (
    DIMENSION_REGISTRY,
    DIMENSIONS_METADATA_KEY,
    DimensionSpec,
    DimensionValue,
    DimensionValues,
    R7_THRESHOLD_LEVELS,
    crossed_group_label,
    dimension_spec,
    dimension_value,
    r1_from_frequency,
    r3_from_dates,
    r3_from_relative_months,
    r4_from_interpretation_count,
    r5_from_hop_count,
    r6_from_specificity,
    r7_from_threshold,
)
from .io import read_jsonl, sha256_file, write_jsonl
from .leakage import (
    assert_no_split_leakage,
    find_split_leakage,
    normalized_question_hash,
)
from .manifest import RunManifest
from .metrics import (
    PairedAURCComparison,
    ReliabilityBin,
    RiskCoveragePoint,
    SelectiveReport,
    adaptive_calibration_error,
    area_under_risk_coverage_curve,
    binary_log_loss,
    brier_score,
    candidate_oracle_recall,
    correctness_auroc,
    expected_calibration_error,
    group_reliability_report,
    paired_aurc_comparison,
    prediction_set_efficiency,
    reliability_bins,
    risk_coverage_curve,
    selective_report,
)
from .read_contract import (
    ReadAction,
    ReadDecision,
    prediction_set_read,
    read_policy,
    selective_read,
)
from .schema import (
    EvaluationTrack,
    Example,
    GenerationRecord,
    ModelConditionRecord,
    Prediction,
    R3_MONTH_TOLERANCE,
    ReadResultRecord,
    ScoreKind,
    WorkloadRecord,
    condition_table_hash,
    decide_generation,
    validate_pipeline_linkage,
)
from .splits import assign_splits, deterministic_split
from .statistics import (
    bootstrap_mean_interval,
    clopper_pearson_interval,
    clustered_paired_bootstrap_difference,
    holm_adjusted_pvalues,
    wilson_interval,
)
from .typed_correctness import (
    date_match,
    numeric_match,
    significant_digit_count,
    typed_match,
)
from .transfer import (
    CalibrationTransferComparison,
    DomainTransferReport,
    calibration_transfer_comparison,
    domain_transfer_report,
)

# Keep the configuration CLI import-safe.  Eagerly importing ``calibread.config`` here makes
# ``python -m calibread.config`` execute a module that is already present in sys.modules.
REQUIRED_DIMENSIONS = frozenset(DIMENSION_REGISTRY)


def load_study_config(path):
    """Lazily load a study configuration without pre-importing the CLI module."""

    from .config import load_study_config as _load_study_config

    return _load_study_config(path)


def validate_study_config(config):
    """Lazily validate a study configuration without pre-importing the CLI module."""

    from .config import validate_study_config as _validate_study_config

    return _validate_study_config(config)

__all__ = [
    "AmbiguityReport",
    "CertificateCoverageScope",
    "CertificateGuaranteeStatus",
    "CompositionReport",
    "CalibrationTransferComparison",
    "DIMENSION_REGISTRY",
    "DIMENSIONS_METADATA_KEY",
    "DimensionSpec",
    "DimensionValue",
    "DimensionValues",
    "DomainTransferReport",
    "EvaluationTrack",
    "Example",
    "GenerationRecord",
    "GroupConformalClassifier",
    "ModelConditionRecord",
    "PairedAURCComparison",
    "Prediction",
    "R3_MONTH_TOLERANCE",
    "READ_CERTIFICATE_SCHEMA_VERSION",
    "REQUIRED_CERTIFICATE_ASSUMPTIONS",
    "ReadAction",
    "ReadCertificate",
    "ReadDecision",
    "ReadResultRecord",
    "REQUIRED_DIMENSIONS",
    "R7_THRESHOLD_LEVELS",
    "ReliabilityBin",
    "RiskCoveragePoint",
    "RunManifest",
    "ScoreKind",
    "SelectiveReport",
    "SplitConformalClassifier",
    "WorkloadRecord",
    "adaptive_calibration_error",
    "ambiguity_report",
    "apply_group_prediction_sets",
    "area_under_risk_coverage_curve",
    "assert_no_split_leakage",
    "assign_splits",
    "binary_log_loss",
    "bootstrap_mean_interval",
    "brier_score",
    "build_read_certificate",
    "candidate_oracle_recall",
    "calibration_transfer_comparison",
    "clopper_pearson_interval",
    "clustered_paired_bootstrap_difference",
    "condition_table_hash",
    "decide_generation",
    "composition_report",
    "conformal_quantile",
    "correctness_auroc",
    "crossed_group_label",
    "date_match",
    "deterministic_split",
    "dimension_spec",
    "dimension_value",
    "domain_transfer_report",
    "empirical_coverage",
    "exact_match",
    "expected_calibration_error",
    "finite_label_prediction_set",
    "find_split_leakage",
    "group_conformal_quantiles",
    "group_reliability_report",
    "holm_adjusted_pvalues",
    "load_study_config",
    "normalize_answer",
    "normalized_question_hash",
    "numeric_match",
    "paired_aurc_comparison",
    "prediction_set_efficiency",
    "prediction_set_read",
    "read_policy",
    "read_jsonl",
    "reliability_bins",
    "risk_coverage_curve",
    "r1_from_frequency",
    "r3_from_dates",
    "r3_from_relative_months",
    "r4_from_interpretation_count",
    "r5_from_hop_count",
    "r6_from_specificity",
    "r7_from_threshold",
    "score_prediction",
    "selective_report",
    "selective_read",
    "sha256_file",
    "significant_digit_count",
    "true_label_nonconformity",
    "typed_match",
    "validate_study_config",
    "validate_read_certificate",
    "validate_pipeline_linkage",
    "wilson_interval",
    "write_jsonl",
]

__version__ = "0.1.0"
