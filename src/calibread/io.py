"""Auditable JSONL storage helpers for cached experiment artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Iterable, Mapping


def write_jsonl(path: str | Path, rows: Iterable[Mapping[str, object]]) -> None:
    """Atomically write mappings as UTF-8 JSON Lines."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent, text=True
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            for row in rows:
                if not isinstance(row, Mapping):
                    raise TypeError("every JSONL row must be a mapping")
                stream.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True))
                stream.write("\n")
        os.replace(temporary_name, target)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def read_jsonl(path: str | Path) -> list[dict[str, object]]:
    """Read a UTF-8 JSONL file and reject non-object or blank records."""

    rows: list[dict[str, object]] = []
    with Path(path).open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                raise ValueError(f"blank JSONL record at line {line_number}")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"JSONL record {line_number} is not an object")
            rows.append(value)
    return rows


def sha256_file(path: str | Path) -> str:
    """Return a content hash for a manifest, cache, or result artifact."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
