'''Explicit human-audit finalization for inference data gates.'''

from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Mapping

from ..io import sha256_file


def finalize_human_audit(
    manifest_path: str | Path,
    *,
    reviewer: str,
    protocol: str,
) -> Path:
    '''Record approval only after every audit row is explicitly approved.

    This command does not decide whether a row is good. Reviewers must edit the
    ``review_status`` cells themselves; any pending or rejected row makes the
    finalization fail closed.
    '''

    path = Path(manifest_path)
    reviewer_id = str(reviewer).strip()
    protocol_id = str(protocol).strip()
    if not reviewer_id:
        raise ValueError('reviewer must be nonempty')
    if not protocol_id:
        raise ValueError('protocol must be nonempty')
    if not path.is_file():
        raise FileNotFoundError(f'missing audit manifest: {path}')
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError('audit manifest must contain an object')
    checks = payload.get('checks')
    if not isinstance(checks, dict):
        raise ValueError('audit manifest must contain a checks object')
    if checks.get('human_audit') == 'approved':
        raise ValueError('human audit is already approved; refusing to overwrite attestation')
    outputs = payload.get('outputs')
    if not isinstance(outputs, Mapping):
        raise ValueError('audit manifest must contain an outputs object')
    audit_entry = outputs.get('audit_sample.csv')
    if not isinstance(audit_entry, dict):
        raise ValueError('audit manifest outputs must describe audit_sample.csv')
    audit_path = path.parent / 'audit_sample.csv'
    if not audit_path.is_file():
        raise FileNotFoundError(f'missing audit sample: {audit_path}')
    with audit_path.open('r', encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or 'review_status' not in reader.fieldnames:
            raise ValueError('audit sample must contain a review_status column')
        rows = list(reader)
    if not rows:
        raise ValueError('audit sample must contain at least one row')
    pending = [
        (row.get('example_id') or f'row-{index + 2}')
        for index, row in enumerate(rows)
        if str(row.get('review_status', '')).strip().casefold() != 'approved'
    ]
    if pending:
        raise ValueError(
            'every audit row must be explicitly marked approved; '
            f'not approved: {pending[:10]!r}'
        )
    identifiers = [str(row.get('example_id', '')).strip() for row in rows]
    if any(not value for value in identifiers) or len(identifiers) != len(set(identifiers)):
        raise ValueError('audit sample example_id values must be nonempty and unique')

    digest = sha256_file(audit_path)
    byte_count = audit_path.stat().st_size
    audit_entry['sha256'] = digest
    audit_entry['bytes'] = byte_count
    checks['human_audit'] = 'approved'
    payload['human_audit_review'] = {
        'status': 'approved',
        'reviewer': reviewer_id,
        'protocol': protocol_id,
        'reviewed_at_utc': datetime.now(timezone.utc).isoformat(),
        'reviewed_row_count': len(rows),
        'audit_sample_path': 'audit_sample.csv',
        'audit_sample_sha256': digest,
        'audit_sample_bytes': byte_count,
    }
    temporary = path.with_name(f'.{path.name}.tmp')
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
        newline='\n',
    )
    os.replace(temporary, path)
    return path


__all__ = ['finalize_human_audit']
