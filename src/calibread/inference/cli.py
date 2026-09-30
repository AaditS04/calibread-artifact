'''Command-line entry point for planning, running, scoring, and reporting inference.'''

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .audit import finalize_human_audit
from .calibration import calibrate_run, fit_calibrator
from .calibration_report import calibration_report
from .composition_report import build_composition_report
from .config import load_inference_config
from .decisions import decide_r7
from .r1_report import build_r1_report
from .report import report_run
from .runner import plan_run, run_inference
from .scoring import score_run


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('validate-config', 'plan', 'run', 'score', 'report'):
        child = commands.add_parser(name)
        child.add_argument('config', type=Path)
    fit = commands.add_parser('fit-calibrator')
    fit.add_argument('config', type=Path)
    fit.add_argument(
        '--calibrator',
        type=Path,
        help=(
            'output CALIBRATOR.json path or directory; defaults to the '
            'calibration subdirectory of the run output'
        ),
    )
    for name in ('calibrate', 'decide-r7', 'calibration-report'):
        child = commands.add_parser(name)
        child.add_argument('config', type=Path)
        child.add_argument(
            '--calibrator',
            type=Path,
            required=True,
            help='frozen CALIBRATOR.json path or containing directory',
        )
    r1_report = commands.add_parser('r1-report')
    r1_report.add_argument('config', type=Path)
    composition = commands.add_parser('composition-report')
    composition.add_argument('config', type=Path)
    composition.add_argument(
        '--calibrated',
        type=Path,
        help='optional calibrated_results.csv used for constituent-product diagnostics',
    )
    composition.add_argument(
        '--bootstrap-samples',
        type=int,
        default=2000,
        help='connected-chain bootstrap replicates (default: 2000)',
    )
    finalize = commands.add_parser('finalize-audit')
    finalize.add_argument('manifest', type=Path)
    finalize.add_argument('--reviewer', required=True)
    finalize.add_argument('--protocol', required=True)
    args = parser.parse_args(argv)
    if args.command == 'finalize-audit':
        print(
            finalize_human_audit(
                args.manifest,
                reviewer=args.reviewer,
                protocol=args.protocol,
            )
        )
        return 0
    config = load_inference_config(args.config)
    if args.command == 'validate-config':
        config.validate_for_execution()
        print(json.dumps({'valid': True, 'provider': config.provider.kind, 'run_id': config.run.run_id}, indent=2))
    elif args.command == 'plan':
        print(json.dumps(plan_run(config), indent=2, sort_keys=True))
    elif args.command == 'run':
        print(json.dumps(run_inference(config), indent=2, sort_keys=True))
    elif args.command == 'score':
        print(score_run(config))
    elif args.command == 'report':
        print(report_run(config))
    elif args.command == 'r1-report':
        print(build_r1_report(config))
    elif args.command == 'fit-calibrator':
        print(fit_calibrator(config, args.calibrator))
    elif args.command == 'calibrate':
        print(calibrate_run(config, args.calibrator))
    elif args.command == 'decide-r7':
        print(decide_r7(config, args.calibrator))
    elif args.command == 'calibration-report':
        print(calibration_report(config, args.calibrator))
    elif args.command == 'composition-report':
        print(
            build_composition_report(
                config,
                calibrated_path=args.calibrated,
                bootstrap_samples=args.bootstrap_samples,
            )
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
