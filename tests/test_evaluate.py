"""Tests for evaluation of cached model outputs and its command entry point."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from calibread.evaluate import R7_POLICY_COLUMN, evaluate_rows, main


def identity_fields(
    *,
    condition_hash: str = 'condition-default',
) -> dict[str, str]:
    return {
        'run_id': 'run-primary',
        'model_snapshot_id': 'model@example-revision',
        'evaluation_track': 'finite_label_certified',
        'condition_table_hash': 'condition-table-v1',
        'calibration_object_hash': 'calibration-object-v1',
        'condition_hash': condition_hash,
    }


def probability_row(**values: str) -> dict[str, str]:
    row = {
        **identity_fields(),
        "score_kind": "probability",
        "score_source": "temperature_scaled_sequence_score",
        "calibrator_id": "temperature-v1",
    }
    row.update(values)
    return row


class EvaluateRowsTests(unittest.TestCase):
    def test_global_and_predeclared_group_metrics(self) -> None:
        report = evaluate_rows(
            [
                probability_row(
                    example_id="q1", confidence="0.9", correct="yes", group="head"
                ),
                probability_row(
                    example_id="q2", confidence="0.6", correct="false", group="head"
                ),
                probability_row(
                    example_id="q3", confidence="0.4", correct="true", group="tail"
                ),
                probability_row(
                    example_id="q4", confidence="0.1", correct="no", group="tail"
                ),
            ],
            n_bins=2,
            threshold=0.7,
        )
        self.assertEqual(report["count"], 4)
        self.assertAlmostEqual(report["accuracy"], 0.5)
        self.assertIn("head", report["groups"])
        self.assertIn("tail", report["groups"])
        self.assertIsNotNone(report["auroc"])
        self.assertEqual(report["probability_metrics_status"], "declared_probability")
        self.assertEqual(len(report["policy_frontier"]), 5)

    def test_multiple_dimension_reports_and_requested_interactions(self) -> None:
        rows = [
            probability_row(
                example_id="q1",
                confidence="0.9",
                correct="1",
                r1="head",
                r5="direct",
                r6="general",
            ),
            probability_row(
                example_id="q2",
                confidence="0.7",
                correct="1",
                r1="head",
                r5="deep",
                r6="specialized",
            ),
            probability_row(
                example_id="q3",
                confidence="0.4",
                correct="0",
                r1="tail",
                r5="direct",
                r6="specialized",
            ),
            probability_row(
                example_id="q4",
                confidence="0.2",
                correct="0",
                r1="tail",
                r5="deep",
                r6="general",
            ),
        ]
        report = evaluate_rows(
            rows,
            n_bins=2,
            group_columns=("r1", "r5", "r6"),
            interactions=(("r1", "r5"), ("r1", "r5", "r6")),
        )
        self.assertEqual(report["group_column"], "r1")
        self.assertEqual(set(report["group_reports"]), {"r1", "r5", "r6"})
        self.assertEqual(report["groups"], report["group_reports"]["r1"])
        self.assertEqual(set(report["interactions"]), {"r1*r5", "r1*r5*r6"})
        self.assertIn("r1=tail|r5=deep", report["interactions"]["r1*r5"])

    def test_score_semantics_fail_closed_with_audited_legacy_path(self) -> None:
        legacy_rows = [
            {
                "example_id": "q1",
                "confidence": "0.8",
                "correct": "1",
                "group": "all",
            }
        ]
        with self.assertRaisesRegex(ValueError, "score_kind"):
            evaluate_rows(legacy_rows, legacy_identity_input=True)
        with self.assertRaisesRegex(ValueError, 'run_id'):
            evaluate_rows(legacy_rows, legacy_probability_input=True)
        report = evaluate_rows(
            legacy_rows,
            legacy_probability_input=True,
            legacy_identity_input=True,
        )
        self.assertIsNotNone(report["brier"])
        self.assertEqual(
            report["probability_metrics_status"], "legacy_probability_assumption"
        )
        declared_legacy = [
            {
                **identity_fields(),
                **legacy_rows[0],
                "score_kind": "legacy_probability",
                "score_source": "legacy_confidence",
                "calibrator_id": "legacy_unspecified",
            }
        ]
        with self.assertRaisesRegex(ValueError, "legacy_probability_input"):
            evaluate_rows(declared_legacy)
        self.assertEqual(
            evaluate_rows(
                declared_legacy, legacy_probability_input=True
            )["probability_metrics_status"],
            "legacy_probability_assumption",
        )

    def test_report_identity_is_complete_and_condition_hash_may_vary(self) -> None:
        rows = [
            probability_row(
                example_id='q1',
                confidence='0.9',
                correct='1',
                group='all',
                condition_hash='condition-q1',
            ),
            probability_row(
                example_id='q2',
                confidence='0.2',
                correct='0',
                group='all',
                condition_hash='condition-q2',
            ),
        ]
        identity = evaluate_rows(rows)['report_identity']
        self.assertEqual(identity['validation_mode'], 'strict')
        self.assertEqual(identity['run_id'], 'run-primary')
        self.assertEqual(identity['model_snapshot_id'], 'model@example-revision')
        self.assertEqual(identity['evaluation_track'], 'finite_label_certified')
        self.assertEqual(identity['condition_table_hash'], 'condition-table-v1')
        self.assertEqual(
            identity['calibration_object_hash'], 'calibration-object-v1'
        )
        self.assertEqual(
            identity['score_source'], 'temperature_scaled_sequence_score'
        )
        self.assertEqual(identity['score_kind'], 'probability')
        self.assertEqual(identity['calibrator_id'], 'temperature-v1')
        self.assertIsNone(identity['normalization_contract'])
        self.assertEqual(identity['condition_hash_count'], 2)
        self.assertTrue(identity['condition_hashes_complete'])
        self.assertEqual(identity['missing_linkage_counts'], {})

    def test_missing_or_heterogeneous_primary_identity_is_rejected(self) -> None:
        base = [
            probability_row(
                example_id='q1', confidence='0.9', correct='1', group='all'
            ),
            probability_row(
                example_id='q2', confidence='0.2', correct='0', group='all'
            ),
        ]
        required = (
            'run_id',
            'model_snapshot_id',
            'evaluation_track',
            'condition_table_hash',
            'calibration_object_hash',
            'condition_hash',
            'score_kind',
            'score_source',
            'calibrator_id',
        )
        for field in required:
            rows = [dict(row) for row in base]
            rows[1].pop(field)
            with self.subTest(missing=field), self.assertRaisesRegex(
                ValueError, field
            ):
                evaluate_rows(rows)

        homogeneous = (
            'run_id',
            'model_snapshot_id',
            'evaluation_track',
            'condition_table_hash',
            'calibration_object_hash',
            'score_kind',
            'score_source',
            'calibrator_id',
        )
        for field in homogeneous:
            rows = [dict(row) for row in base]
            rows[1][field] = f'other-{field}'
            with self.subTest(heterogeneous=field), self.assertRaisesRegex(
                ValueError, field
            ):
                evaluate_rows(rows)

        rows = [dict(row) for row in base]
        rows[0]['normalization_contract'] = 'normalizer-a'
        rows[1]['normalization_contract'] = 'normalizer-b'
        with self.assertRaisesRegex(ValueError, 'normalization_contract'):
            evaluate_rows(rows)

    def test_legacy_identity_mode_only_waives_missing_linkage(self) -> None:
        rows = [
            probability_row(
                example_id='q1', confidence='0.9', correct='1', group='all'
            ),
            probability_row(
                example_id='q2', confidence='0.2', correct='0', group='all'
            ),
        ]
        linkage = (
            'run_id',
            'model_snapshot_id',
            'evaluation_track',
            'condition_table_hash',
            'calibration_object_hash',
            'condition_hash',
        )
        for row in rows:
            for field in linkage:
                row.pop(field)
        identity = evaluate_rows(
            rows, legacy_identity_input=True
        )['report_identity']
        self.assertEqual(
            identity['validation_mode'], 'legacy_missing_linkage_allowed'
        )
        self.assertFalse(identity['condition_hashes_complete'])
        self.assertEqual(identity['missing_linkage_counts']['run_id'], 2)
        self.assertEqual(identity['missing_linkage_counts']['condition_hash'], 2)

        for field in ('score_source', 'calibrator_id'):
            mixed = [dict(row) for row in rows]
            mixed[1][field] = f'other-{field}'
            with self.subTest(field=field), self.assertRaisesRegex(
                ValueError, field
            ):
                evaluate_rows(mixed, legacy_identity_input=True)
        mixed = [dict(row) for row in rows]
        mixed[0]['normalization_contract'] = 'normalizer-a'
        mixed[1]['normalization_contract'] = 'normalizer-b'
        with self.assertRaisesRegex(ValueError, 'normalization_contract'):
            evaluate_rows(mixed, legacy_identity_input=True)

    def test_raw_scores_withhold_probability_metrics(self) -> None:
        rows = [
            {
                "example_id": "q1",
                "confidence": "-1.0",
                "correct": "1",
                "group": "all",
                "score_kind": "raw",
                "score_source": "sequence_log_probability",
                "calibrator_id": "",
            },
            {
                "example_id": "q2",
                "confidence": "-4.0",
                "correct": "0",
                "group": "all",
                "score_kind": "raw",
                "score_source": "sequence_log_probability",
                "calibrator_id": "",
            },
        ]
        for row in rows:
            row.update(identity_fields())
        report = evaluate_rows(rows)
        for metric in ("brier", "log_loss", "ece", "ace"):
            self.assertIsNone(report[metric])
        self.assertEqual(report["probability_metrics_status"], "raw_score_metrics_withheld")
        self.assertIsNotNone(report["auroc"])
        self.assertIsNone(report["selective"])
        self.assertEqual(report["policy_frontier"], [])
        self.assertEqual(
            report["policy_metrics_status"],
            "withheld_raw_score_without_normalization",
        )
        self.assertEqual(
            report["groups"]["all"]["probability_metrics_status"],
            "withheld_raw_score",
        )
        with self.assertRaisesRegex(ValueError, "normalization_contract"):
            evaluate_rows(rows, thresholds=(0.9,))

        normalized_rows = [
            {
                **row,
                "confidence": score,
                "score_source": "minmax_sequence_score",
                "normalization_contract": "calibration-minmax-v1",
            }
            for row, score in zip(rows, ("0.8", "0.2"))
        ]
        normalized_report = evaluate_rows(normalized_rows)
        self.assertEqual(len(normalized_report["policy_frontier"]), 5)
        self.assertEqual(
            normalized_report["policy_metrics_status"], "computed_normalized_raw"
        )

    def test_r4_by_r7_is_swept_without_duplicate_input_rows(self) -> None:
        rows = [
            probability_row(
                example_id="q1",
                confidence="0.99",
                correct="1",
                r4_ambiguity_level="unambiguous",
            ),
            probability_row(
                example_id="q2",
                confidence="0.75",
                correct="0",
                r4_ambiguity_level="unambiguous",
            ),
            probability_row(
                example_id="q3",
                confidence="0.92",
                correct="1",
                r4_ambiguity_level="two_way",
            ),
            probability_row(
                example_id="q4",
                confidence="0.55",
                correct="0",
                r4_ambiguity_level="two_way",
            ),
        ]
        expected_r7 = (
            "tau_0_50",
            "tau_0_70",
            "tau_0_90",
            "tau_0_95",
            "tau_0_99",
        )
        report = evaluate_rows(
            rows,
            n_bins=2,
            group_columns=("r4_ambiguity_level", R7_POLICY_COLUMN),
            interactions=(("r4_ambiguity_level", R7_POLICY_COLUMN),),
            expected_levels={
                "r4_ambiguity_level": ("unambiguous", "two_way"),
                R7_POLICY_COLUMN: expected_r7,
            },
            minimum_level_count=2,
            minimum_interaction_count=2,
        )
        self.assertEqual(report["count"], 4)
        self.assertEqual(
            tuple(item["policy_level"] for item in report["policy_frontier"]),
            expected_r7,
        )
        crossed = report["interactions"][
            f"r4_ambiguity_level*{R7_POLICY_COLUMN}"
        ]
        self.assertEqual(len(crossed), 10)
        self.assertIn(
            f"r4_ambiguity_level=two_way|{R7_POLICY_COLUMN}=tau_0_90",
            crossed,
        )
        self.assertTrue(all(cell["input_example_count"] == 2 for cell in crossed.values()))

    def test_expected_level_and_interaction_floors_fail_closed(self) -> None:
        rows = [
            probability_row(
                example_id="q1",
                confidence="0.9",
                correct="1",
                r4_ambiguity_level="unambiguous",
            )
        ]
        with self.assertRaisesRegex(ValueError, "expected-level floor"):
            evaluate_rows(
                rows,
                group_columns=("r4_ambiguity_level",),
                expected_levels={
                    "r4_ambiguity_level": ("unambiguous", "two_way")
                },
            )
        with self.assertRaisesRegex(ValueError, "interaction floor"):
            evaluate_rows(
                rows,
                group_columns=("r4_ambiguity_level",),
                interactions=(("r4_ambiguity_level", R7_POLICY_COLUMN),),
                minimum_interaction_count=2,
            )
        with self.assertRaisesRegex(ValueError, "frozen values"):
            evaluate_rows(rows, thresholds=(0.8,))

    def test_empty_missing_and_malformed_rows_fail(self) -> None:
        for rows in (
            [],
            [{"confidence": "0.5"}],
            [{"confidence": "0.5", "correct": "maybe"}],
            [{"example_id": "", "confidence": "0.5", "correct": "1"}],
            [
                {"example_id": "dup", "confidence": "0.9", "correct": "1"},
                {"example_id": "dup", "confidence": "0.1", "correct": "0"},
            ],
        ):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                evaluate_rows(rows)

    def test_explicit_dimensions_fail_closed_but_legacy_grouping_survives(self) -> None:
        rows = [
            probability_row(example_id="q1", confidence="0.9", correct="1")
        ]
        self.assertIn("all", evaluate_rows(rows, group_column="legacy")["groups"])
        with self.assertRaisesRegex(ValueError, "missing group column"):
            evaluate_rows(rows, group_columns=("r1",))
        with self.assertRaises(ValueError):
            evaluate_rows(rows, group_columns=("r1", "r1"))
        with self.assertRaises(ValueError):
            evaluate_rows(rows, interactions=(("r1",),))


class EvaluateCliTests(unittest.TestCase):
    def test_main_reads_csv_and_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "predictions.csv"
            output_path = Path(directory) / "report.json"
            csv_path.write_text(
                "example_id,confidence,correct,group,score_kind,score_source,calibrator_id\n"
                "q1,0.9,1,head,probability,temperature_scaled,temp-v1\n"
                "q2,0.2,0,tail,probability,temperature_scaled,temp-v1\n",
                encoding="utf-8",
            )
            status = main(
                [
                    str(csv_path),
                    '--legacy-identity-input',
                    '--output',
                    str(output_path),
                    '--bins',
                    '2',
                ]
            )
            self.assertEqual(status, 0)
            report = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(report["count"], 2)
            self.assertEqual(set(report["groups"]), {"head", "tail"})
            self.assertEqual(len(report["policy_frontier"]), 5)

    def test_cli_accepts_dimensions_interaction_and_policy_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "predictions.csv"
            output_path = Path(directory) / "report.json"
            csv_path.write_text(
                "example_id,confidence,correct,r1,r5,score_kind,score_source,calibrator_id\n"
                "q1,0.9,1,head,direct,probability,temperature_scaled,temp-v1\n"
                "q2,0.2,0,tail,deep,probability,temperature_scaled,temp-v1\n",
                encoding="utf-8",
            )
            status = main(
                [
                    str(csv_path),
                    '--legacy-identity-input',
                    "--output",
                    str(output_path),
                    "--group-column",
                    "r1",
                    "--group-column",
                    "r5",
                    "--interaction",
                    "r1,r5",
                    "--threshold",
                    "0.9",
                ]
            )
            self.assertEqual(status, 0)
            report = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(set(report["group_reports"]), {"r1", "r5"})
            self.assertIn("r1=tail|r5=deep", report["interactions"]["r1*r5"])
            self.assertEqual(
                [item["policy_level"] for item in report["policy_frontier"]],
                ["tau_0_90"],
            )


if __name__ == "__main__":
    unittest.main()
