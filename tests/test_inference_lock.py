'''Cross-process locking tests for inference run directories.'''

from __future__ import annotations

import json
import multiprocessing
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from calibread.inference.runner import (
    RunDirectoryLockedError,
    _RunDirectoryLock,
    run_inference,
)


def _hold_run_lock(path: str, ready: object, release: object) -> None:
    with _RunDirectoryLock(Path(path), 'holder-run'):
        ready.set()
        if not release.wait(15):
            raise TimeoutError('test holder did not receive release signal')


def _contend_for_run_lock(path: str, result: object) -> None:
    try:
        with _RunDirectoryLock(Path(path), 'contender-run'):
            result.put(('acquired', ''))
    except RunDirectoryLockedError as error:
        result.put(('locked', str(error)))


def _crash_with_run_lock(path: str, ready: object) -> None:
    lock = _RunDirectoryLock(Path(path), 'crashed-run')
    lock.__enter__()
    ready.set()
    os._exit(23)


class InferenceRunLockTests(unittest.TestCase):
    @staticmethod
    def _context() -> multiprocessing.context.BaseContext:
        return multiprocessing.get_context('spawn')

    def test_two_processes_contend_and_lock_is_cleaned_on_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            context = self._context()
            ready = context.Event()
            release = context.Event()
            result = context.Queue()
            holder = context.Process(
                target=_hold_run_lock,
                args=(str(output), ready, release),
            )
            contender = context.Process(
                target=_contend_for_run_lock,
                args=(str(output), result),
            )
            holder.start()
            try:
                self.assertTrue(ready.wait(10), 'holder never acquired the run lock')
                contender.start()
                status, message = result.get(timeout=10)
                contender.join(10)
                self.assertFalse(contender.is_alive())
                self.assertEqual(contender.exitcode, 0)
                self.assertEqual(status, 'locked')
                self.assertIn('another live process', message)
                self.assertIn('run_id=' + repr('holder-run'), message)
            finally:
                release.set()
                holder.join(10)
                if holder.is_alive():
                    holder.terminate()
                    holder.join(10)
                if contender.is_alive():
                    contender.terminate()
                    contender.join(10)
                result.close()
                result.join_thread()
            self.assertEqual(holder.exitcode, 0)

            lock_path = output / _RunDirectoryLock.filename
            self.assertEqual(lock_path.read_bytes(), b'\x00')
            with _RunDirectoryLock(output, 'next-run'):
                with lock_path.open('rb') as stream:
                    stream.seek(1)
                    owner = json.loads(stream.read().decode('utf-8'))
                self.assertEqual(owner['run_id'], 'next-run')
            self.assertEqual(lock_path.read_bytes(), b'\x00')

    def test_run_fails_before_provider_preflight_when_contended(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            config = SimpleNamespace(
                validate_for_execution=lambda: None,
                budget=SimpleNamespace(max_requests=1, max_cost_usd=0.0),
                run=SimpleNamespace(
                    output_dir=output,
                    run_id='blocked-run',
                    promotion_approved=True,
                ),
            )
            plan = {'requests': 0, 'estimated_upper_cost_usd': 0.0}
            with _RunDirectoryLock(output, 'holder-run'):
                with (
                    patch('calibread.inference.runner.plan_run', return_value=plan),
                    patch(
                        'calibread.inference.runner._required_human_audit_evidence',
                        return_value=[],
                    ),
                    patch('calibread.inference.runner._provider') as provider,
                ):
                    with self.assertRaisesRegex(
                        RunDirectoryLockedError,
                        'another live process',
                    ):
                        run_inference(config)
                    provider.assert_not_called()

    def test_exception_and_process_death_both_release_os_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            with self.assertRaisesRegex(ValueError, 'deliberate'):
                with _RunDirectoryLock(output, 'exception-run'):
                    raise ValueError('deliberate')
            with _RunDirectoryLock(output, 'after-exception'):
                pass

            context = self._context()
            ready = context.Event()
            process = context.Process(
                target=_crash_with_run_lock,
                args=(str(output), ready),
            )
            process.start()
            self.assertTrue(ready.wait(10), 'crashing process never acquired lock')
            process.join(10)
            if process.is_alive():
                process.terminate()
                process.join(10)
                self.fail('crashing process did not exit')
            self.assertEqual(process.exitcode, 23)

            # The stale owner bytes are harmless: the kernel lock died with the
            # process, so acquisition succeeds without age/PID heuristics.
            with _RunDirectoryLock(output, 'after-crash'):
                pass
            self.assertEqual(
                (output / _RunDirectoryLock.filename).read_bytes(),
                b'\x00',
            )


if __name__ == '__main__':
    unittest.main()
