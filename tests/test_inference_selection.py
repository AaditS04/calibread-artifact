'''Inference selection, chain closure, and completeness safety tests.'''

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from calibread.dimensions import DimensionValues
from calibread.inference.audit import finalize_human_audit
from calibread.inference.config import R5_LEVELS, load_inference_config
from calibread.inference.runner import plan_run, run_inference, verify_run_completeness
from calibread.io import sha256_file
from calibread.schema import Example, WorkloadRecord


def _dimensions(hops: int) -> DimensionValues:
    return DimensionValues(
        {
            'R2': {'raw': 'medium', 'level': 'medium'},
            'R4': {'raw': 1, 'level': 'unambiguous'},
            'R5': {'raw': hops, 'level': R5_LEVELS[min(hops, 4) - 1]},
            'R6': {'raw': 0.1, 'level': 'general'},
        }
    )


def _example(
    example_id: str,
    hops: int,
    chain_id: str,
    split: str = 'calibration',
) -> Example:
    return Example(
        example_id=example_id,
        question=f'MOCK_ANSWER={example_id}?',
        accepted_answers=(example_id,),
        split=split,
        metadata={'chain_id': chain_id},
    ).with_dimension_values(_dimensions(hops))


def _workload(
    example: Example,
    hops: int,
    chain_id: str,
    constituents: tuple[str, ...],
) -> WorkloadRecord:
    return WorkloadRecord(
        example_id=example.example_id,
        question=example.question,
        accepted_answers=example.accepted_answers,
        track='open_ended_stress',
        dimensions=_dimensions(hops),
        r4_annotation_hash='4' * 64,
        r5_chain_spec_hash='5' * 64,
        interpretation_answers={'source': example.accepted_answers},
        chain_id=chain_id,
        constituent_example_ids=constituents,
        domain_name='general_knowledge',
        missing_reasons={
            'R1': 'model_condition_record',
            'R3': 'model_condition_record',
        },
    )


def _write_dataset(
    root: Path,
    dataset_id: str,
    rows: list[tuple[Example, WorkloadRecord]],
) -> tuple[Path, Path]:
    directory = root / dataset_id
    directory.mkdir()
    examples = directory / 'examples.jsonl'
    workloads = directory / 'workloads.jsonl'
    examples.write_text(
        ''.join(json.dumps(row.to_dict(), sort_keys=True) + '\n' for row, _ in rows),
        encoding='utf-8',
    )
    workloads.write_text(
        ''.join(json.dumps(row.to_dict(), sort_keys=True) + '\n' for _, row in rows),
        encoding='utf-8',
    )
    return examples, workloads


def _write_config(
    root: Path,
    datasets: list[tuple[str, Path, Path]],
    include_levels: tuple[str, ...] = ('two_hop',),
    chain_complete: bool = True,
    required_human_audit_manifests: tuple[Path, ...] = (),
    promotion_approved: bool = True,
) -> Path:
    dq = chr(34)
    tables = ''
    for name, examples, workloads in datasets:
        tables += '[[datasets]]\n'
        tables += f'dataset_id={dq}{name}{dq}\n'
        tables += f'examples={dq}{examples.as_posix()}{dq}\n'
        tables += f'workloads={dq}{workloads.as_posix()}{dq}\n'
    config = root / 'inference.toml'
    output = (root / 'results').as_posix()
    content = '[run]\n'
    content += f'run_id={dq}selection-fixture{dq}\n'
    content += f'parent_experiment_id={dq}r5-parent{dq}\n'
    content += f'split={dq}calibration{dq}\nseed=13\nlimit_per_level=1\n'
    levels = ','.join(f'{dq}{level}{dq}' for level in include_levels)
    content += f'include_levels=[{levels}]\n'
    content += f'chain_complete={str(chain_complete).lower()}\n'
    content += f'promotion_approved={str(promotion_approved).lower()}\n'
    if required_human_audit_manifests:
        manifests = ','.join(
            f'{dq}{path.as_posix()}{dq}'
            for path in required_human_audit_manifests
        )
        content += f'required_human_audit_manifests=[{manifests}]\n'
    content += f'output_dir={dq}{output}{dq}\nresume=true\n'
    content += f'[provider]\nkind={dq}mock{dq}\n'
    content += f'[model]\nrequested_model={dq}mock/fixed{dq}\n'
    content += 'temperature=0.0\nmax_tokens=8\nrequire_logprobs=true\n'
    content += 'top_logprobs=1\nallow_fallbacks=false\n'
    content += f'require_parameters=true\ndata_collection={dq}deny{dq}\n'
    content += '[prompt]\n'
    content += f'template_id={dq}selection-v1{dq}\n'
    content += f'system={dq}Answer briefly.{dq}\n'
    content += f'user_template={dq}Question: {{question}}{dq}\n'
    content += '[budget]\nmax_cost_usd=0.0\nmax_requests=20\n'
    content += 'prompt_usd_per_million=0.0\ncompletion_usd_per_million=0.0\n'
    config.write_text(content + tables, encoding='utf-8')
    return config


def _composition_config(root: Path) -> Path:
    s1 = _example('socrates:r1', 1, 'socrates:chain')
    s2 = _example('socrates:r2', 1, 'socrates:chain')
    sc = _example('socrates:composed', 2, 'socrates:chain')
    socrates = _write_dataset(
        root,
        'socrates',
        [
            (s1, _workload(s1, 1, 'socrates:chain', ('fact:s1',))),
            (s2, _workload(s2, 1, 'socrates:chain', ('fact:s2',))),
            (sc, _workload(sc, 2, 'socrates:chain', ('socrates:r1', 'socrates:r2'))),
        ],
    )
    m1 = _example('musique:singlehop:1', 1, 'musique:atom:1')
    m2 = _example('musique:singlehop:2', 1, 'musique:atom:2')
    atomic = _write_dataset(
        root,
        'musique_atomic',
        [
            (m1, _workload(m1, 1, 'musique:atom:1', ('fact:m1',))),
            (m2, _workload(m2, 1, 'musique:atom:2', ('fact:m2',))),
        ],
    )
    mc = _example('musique:composed', 2, 'musique:chain')
    musique = _write_dataset(
        root,
        'musique',
        [
            (mc, _workload(
                mc,
                2,
                'musique:chain',
                ('musique:singlehop:1', 'musique:singlehop:2'),
            )),
        ],
    )
    return _write_config(
        root,
        [('socrates', *socrates), ('musique', *musique), ('musique_atomic', *atomic)],
    )


class InferenceSelectionTests(unittest.TestCase):
    def test_include_levels_are_validated_and_canonicalized(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            atom = _example('atom', 1, 'chain')
            workload = _workload(atom, 1, 'chain', ('fact:atom',))
            paths = _write_dataset(root, 'fixture', [(atom, workload)])
            levels = ('three_hop', 'one_hop')
            path = _write_config(
                root, [('fixture', *paths)], levels, False
            )
            config = load_inference_config(path)
            self.assertEqual(config.run.include_levels, ('one_hop', 'three_hop'))
            self.assertEqual(config.run.parent_experiment_id, 'r5-parent')

    def test_config_rejects_coerced_booleans_and_duplicate_dataset_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            atom = _example('atom', 1, 'chain')
            paths = _write_dataset(
                root,
                'fixture',
                [(atom, _workload(atom, 1, 'chain', ('fact:atom',)))],
            )
            bad_boolean = _write_config(
                root,
                [('fixture', *paths)],
                include_levels=('one_hop',),
                chain_complete=False,
            )
            bad_boolean.write_text(
                bad_boolean.read_text(encoding='utf-8').replace(
                    'resume=true', 'resume=1'
                ),
                encoding='utf-8',
            )
            with self.assertRaisesRegex(ValueError, 'resume must be a boolean'):
                load_inference_config(bad_boolean)
            bad_promotion = _write_config(
                root,
                [('fixture', *paths)],
                include_levels=('one_hop',),
                chain_complete=False,
            )
            bad_promotion.write_text(
                bad_promotion.read_text(encoding='utf-8').replace(
                    'promotion_approved=true', 'promotion_approved=1'
                ),
                encoding='utf-8',
            )
            with self.assertRaisesRegex(
                ValueError, 'promotion_approved must be a boolean'
            ):
                load_inference_config(bad_promotion)
            duplicate = _write_config(
                root,
                [('fixture', *paths), ('fixture', *paths)],
                include_levels=('one_hop',),
                chain_complete=False,
            )
            with self.assertRaisesRegex(ValueError, 'duplicate datasets.dataset_id'):
                load_inference_config(duplicate)

    def test_chain_complete_selection_and_exact_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = load_inference_config(_composition_config(root))
            plan = plan_run(config)
            self.assertEqual(plan['requests'], 6)
            self.assertEqual(plan['counts']['socrates:one_hop'], 2)
            self.assertEqual(plan['counts']['socrates:two_hop'], 1)
            self.assertEqual(plan['counts']['musique:two_hop'], 1)
            self.assertEqual(plan['counts']['musique_atomic:one_hop'], 2)
            self.assertEqual(plan['include_levels'], ['two_hop'])
            self.assertTrue(plan['chain_complete'])
            self.assertEqual(len(plan['selected_example_ids_sha256']), 64)
            self.assertEqual(len(plan['selected_chain_membership_sha256']), 64)
            summary = run_inference(config)
            self.assertEqual(summary['completion_status'], 'complete')
            verified = verify_run_completeness(config)
            self.assertEqual(verified['selected'], 6)
            manifest_path = root / 'results' / 'RUN_MANIFEST.json'
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            self.assertEqual(manifest['status'], 'calibration_api_run')
            self.assertEqual(manifest['parent_experiment_id'], 'r5-parent')
            self.assertEqual(manifest['selection'], plan['selection'])
            manifest['selection']['selected_example_ids_sha256'] = '0' * 64
            manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'selection mismatch'):
                verify_run_completeness(config)

    def test_chain_closure_rejects_cross_split_constituent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            atom = _example('atom', 1, 'atom-chain', split='test')
            atom_rows = [(atom, _workload(atom, 1, 'atom-chain', ('fact:atom',)))]
            atomic = _write_dataset(root, 'atomic', atom_rows)
            composite = _example('composite', 2, 'composite-chain')
            workload = _workload(
                composite,
                2,
                'composite-chain',
                ('atom', 'missing-second-atom'),
            )
            composed = _write_dataset(root, 'composed', [(composite, workload)])
            config = load_inference_config(
                _write_config(root, [('composed', *composed), ('atomic', *atomic)])
            )
            with self.assertRaisesRegex(ValueError, 'has split'):
                plan_run(config)

    def test_equal_chain_ids_in_different_datasets_do_not_merge(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            a1 = _example('a1', 1, 'shared-chain')
            a2 = _example('a2', 1, 'shared-chain')
            ac = _example('a-composite', 2, 'shared-chain')
            dataset_a = _write_dataset(
                root,
                'dataset_a',
                [
                    (a1, _workload(a1, 1, 'shared-chain', ('fact:a1',))),
                    (a2, _workload(a2, 1, 'shared-chain', ('fact:a2',))),
                    (ac, _workload(ac, 2, 'shared-chain', ('a1', 'a2'))),
                ],
            )
            b1 = _example('b1', 1, 'shared-chain')
            b2 = _example('b2', 1, 'shared-chain')
            b3 = _example('b3', 1, 'shared-chain')
            bc = _example('b-composite', 3, 'shared-chain')
            dataset_b = _write_dataset(
                root,
                'dataset_b',
                [
                    (b1, _workload(b1, 1, 'shared-chain', ('fact:b1',))),
                    (b2, _workload(b2, 1, 'shared-chain', ('fact:b2',))),
                    (b3, _workload(b3, 1, 'shared-chain', ('fact:b3',))),
                    (bc, _workload(bc, 3, 'shared-chain', ('b1', 'b2', 'b3'))),
                ],
            )
            config = load_inference_config(
                _write_config(
                    root,
                    [('dataset_a', *dataset_a), ('dataset_b', *dataset_b)],
                    include_levels=('two_hop',),
                )
            )
            plan = plan_run(config)
            self.assertEqual(plan['requests'], 3)
            self.assertEqual(
                plan['counts'],
                {'dataset_a:one_hop': 2, 'dataset_a:two_hop': 1},
            )

    def test_required_human_audit_must_be_explicit_and_stays_frozen(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            atom = _example('audited-atom', 1, 'audited-chain')
            paths = _write_dataset(
                root,
                'fixture',
                [(atom, _workload(atom, 1, 'audited-chain', ('fact:atom',)))],
            )
            audit = root / 'audit_sample.csv'
            audit.write_text(
                'example_id,review_status,review_notes\n'
                'audited-atom,pending,\n',
                encoding='utf-8',
            )
            manifest = root / 'AUDIT_MANIFEST.json'
            manifest.write_text(
                json.dumps(
                    {
                        'checks': {'human_audit': 'pending'},
                        'outputs': {
                            'audit_sample.csv': {
                                'sha256': sha256_file(audit),
                                'bytes': audit.stat().st_size,
                            }
                        },
                    }
                ),
                encoding='utf-8',
            )
            config = load_inference_config(
                _write_config(
                    root,
                    [('fixture', *paths)],
                    include_levels=('one_hop',),
                    chain_complete=False,
                    required_human_audit_manifests=(manifest,),
                )
            )
            self.assertEqual(plan_run(config)['requests'], 1)
            with self.assertRaisesRegex(ValueError, 'not approved'):
                run_inference(config)
            audit.write_text(
                'example_id,review_status,review_notes\n'
                'audited-atom,approved,checked by reviewer\n',
                encoding='utf-8',
            )
            finalize_human_audit(
                manifest,
                reviewer='reviewer-1',
                protocol='r5-audit-v1',
            )
            self.assertEqual(run_inference(config)['completion_status'], 'complete')
            audit.write_text(
                audit.read_text(encoding='utf-8') + '\n',
                encoding='utf-8',
            )
            with self.assertRaisesRegex(ValueError, 'no longer matches'):
                verify_run_completeness(config)

    def test_failed_promotion_gate_stops_before_audit_and_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            atom = _example('blocked-atom', 1, 'blocked-chain')
            paths = _write_dataset(
                root,
                'fixture',
                [(atom, _workload(atom, 1, 'blocked-chain', ('fact:atom',)))],
            )
            config = load_inference_config(
                _write_config(
                    root,
                    [('fixture', *paths)],
                    include_levels=('one_hop',),
                    chain_complete=False,
                    promotion_approved=False,
                )
            )
            self.assertFalse(plan_run(config)['promotion_approved'])
            with patch('calibread.inference.runner._provider') as provider:
                with self.assertRaisesRegex(ValueError, 'not approved for promotion'):
                    run_inference(config)
                provider.assert_not_called()
            self.assertFalse(config.run.output_dir.exists())

    def test_resume_rejects_corrupted_cache_before_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = load_inference_config(_composition_config(root))
            self.assertEqual(run_inference(config)['completion_status'], 'complete')
            generations = root / 'results' / 'generations.jsonl'
            rows = [
                json.loads(line)
                for line in generations.read_text(encoding='utf-8').splitlines()
            ]
            rows[0]['run_id'] = 'foreign-run'
            generations.write_text(
                ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows),
                encoding='utf-8',
            )
            with self.assertRaisesRegex(ValueError, 'wrong run identity'):
                run_inference(config)


if __name__ == '__main__':
    unittest.main()
