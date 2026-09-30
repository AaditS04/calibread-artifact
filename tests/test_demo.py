"""Offline end-to-end smoke coverage for the synthetic CalibRead pipeline."""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout

from calibread.demo import main, run_demo


class DemoTests(unittest.TestCase):
    def test_demo_is_deterministic_and_exercises_both_calibrators(self) -> None:
        first = run_demo(seed=7, alpha=0.1)
        second = run_demo(seed=7, alpha=0.1)
        self.assertEqual(first, second)
        self.assertEqual(first['calibration_size'], 240)
        self.assertEqual(first["test_size"], 120)
        for method in ("global", "mondrian"):
            report = first[method]
            self.assertGreaterEqual(report["coverage"], 0.0)
            self.assertLessEqual(report["coverage"], 1.0)
            self.assertIn('R1=head', report['group_coverage'])
            self.assertIn('R1=tail', report['group_coverage'])
            self.assertGreaterEqual(report["mean_size"], 0.0)

    def test_demo_is_explicitly_an_all_dimension_software_smoke(self) -> None:
        report = run_demo(seed=11, alpha=0.1)
        self.assertEqual(report['artifact_kind'], 'synthetic_r1_r7_software_smoke')
        self.assertFalse(report['research_evidence'])
        self.assertEqual(
            report['dimensions_exercised'],
            ['R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7'],
        )
        expected_policy = {
            'tau_0_50',
            'tau_0_70',
            'tau_0_90',
            'tau_0_95',
            'tau_0_99',
        }
        self.assertEqual(set(report['r7_policy']), expected_policy)
        for code in ('R1', 'R2', 'R3', 'R4', 'R5', 'R6'):
            for level in report['dimension_levels'][code]:
                group = f'{code}={level}'
                self.assertIn(group, report['mondrian']['group_coverage'])

    def test_main_prints_valid_json(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            result = main([])
        self.assertEqual(result, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["seed"], 7)
        self.assertIn("point_confidence", payload)


if __name__ == "__main__":
    unittest.main()
