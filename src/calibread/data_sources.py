'''Versioned, license-gated dataset acquisition with content manifests.'''

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib
from typing import Mapping
from urllib.request import Request, urlopen
from urllib.error import URLError


REGISTRY_PATH = Path('data/source_registry.toml')
APPROVED_LICENSE_STATUSES = frozenset({'approved'})


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    values: Mapping[str, object]

    def text(self, key: str, default: str = '') -> str:
        value = self.values.get(key, default)
        if not isinstance(value, str):
            raise ValueError(f'{self.source_id}.{key} must be a string')
        return value

    def integer(self, key: str) -> int:
        value = self.values.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f'{self.source_id}.{key} must be an integer')
        return value

    @property
    def filename(self) -> str:
        name = self.text('filename')
        if not name or Path(name).name != name:
            raise ValueError(f'{self.source_id}.filename must be a plain filename')
        return name


def load_registry(path: str | Path = REGISTRY_PATH) -> dict[str, SourceSpec]:
    '''Load and validate the versioned source registry.'''

    with Path(path).open('rb') as stream:
        payload = tomllib.load(stream)
    if payload.get('registry_version') != 1:
        raise ValueError('unsupported source registry version')
    sources = payload.get('sources')
    if not isinstance(sources, Mapping) or not sources:
        raise ValueError('registry must contain a nonempty sources table')
    result: dict[str, SourceSpec] = {}
    for source_id, values in sources.items():
        if not isinstance(values, Mapping):
            raise ValueError(f'source {source_id!r} must be a table')
        spec = SourceSpec(str(source_id), dict(values))
        required = {'title', 'license', 'license_status', 'transport', 'filename', 'adapter'}
        missing = sorted(key for key in required if not spec.text(key))
        if missing:
            raise ValueError(f'{source_id} missing required fields: {missing}')
        if spec.text('license_status') not in {'approved', 'review_required', 'blocked'}:
            raise ValueError(f'{source_id} has invalid license_status')
        if spec.text('transport') not in {'github_file', 'url', 'manual'}:
            raise ValueError(f'{source_id} has invalid transport')
        spec.filename
        spec.integer('max_bytes')
        result[spec.source_id] = spec
    return result


def source_spec(source_id: str, registry_path: str | Path = REGISTRY_PATH) -> SourceSpec:
    try:
        return load_registry(registry_path)[source_id]
    except KeyError as error:
        raise ValueError(f'unknown data source {source_id!r}') from error


def _digest(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def file_fingerprints(path: str | Path) -> dict[str, object]:
    target = Path(path)
    return {
        'bytes': target.stat().st_size,
        'sha256': _digest(target, 'sha256'),
        'md5': _digest(target, 'md5'),
    }


def _json_request(url: str) -> Mapping[str, object]:
    request = Request(url, headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'calibread-data/1'})
    try:
        with urlopen(request, timeout=60) as response:
            value = json.load(response)
    except (URLError, ConnectionError, TimeoutError, OSError):
        curl = shutil.which('curl.exe') or shutil.which('curl')
        if curl is None:
            raise RuntimeError('revision resolution failed and curl fallback is unavailable')
        result = subprocess.run(
            [curl, '-fsSL', '--retry', '3', '-H', 'Accept: application/vnd.github+json', '-H', 'User-Agent: calibread-data/1', url],
            check=True,
            capture_output=True,
            text=True,
        )
        value = json.loads(result.stdout)
    if not isinstance(value, Mapping):
        raise ValueError(f'expected a JSON object from {url}')
    return value


def resolve_source(spec: SourceSpec) -> tuple[str, str | None, str]:
    '''Return requested URL, immutable revision when applicable, and resolved URL.'''

    transport = spec.text('transport')
    if transport == 'url':
        url = spec.text('url')
        return url, None, url
    if transport == 'github_file':
        repository = spec.text('repository')
        revision = spec.text('revision')
        path = spec.text('path')
        requested = f'https://raw.githubusercontent.com/{repository}/{revision}/{path}'
        commit = _json_request(f'https://api.github.com/repos/{repository}/commits/{revision}')
        sha = str(commit.get('sha', '')).strip()
        if len(sha) != 40:
            raise ValueError(f'could not resolve immutable GitHub revision for {spec.source_id}')
        return requested, sha, f'https://raw.githubusercontent.com/{repository}/{sha}/{path}'
    raise ValueError(f'{spec.source_id} is manual and has no remote resolver')


def _verify(spec: SourceSpec, path: Path) -> dict[str, object]:
    fingerprints = file_fingerprints(path)
    if int(fingerprints['bytes']) > spec.integer('max_bytes'):
        raise ValueError(f'{spec.source_id} exceeds its max_bytes safety limit')
    for key in ('sha256', 'md5'):
        expected = spec.text(f'expected_{key}').lower()
        if expected and fingerprints[key] != expected:
            raise ValueError(
                f'{spec.source_id} {key} mismatch: expected {expected}, got {fingerprints[key]}'
            )
    return fingerprints


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(dict(value), stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write('\n')
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _download(url: str, target: Path, max_bytes: int) -> None:
    '''Download with bounded urllib streaming and a Windows TLS fallback.'''

    request = Request(url, headers={'User-Agent': 'calibread-data/1'})
    try:
        with urlopen(request, timeout=120) as response, target.open('wb') as output:
            declared = response.headers.get('Content-Length')
            if declared and int(declared) > max_bytes:
                raise ValueError('remote file exceeds its max_bytes safety limit')
            copied = 0
            while block := response.read(1024 * 1024):
                copied += len(block)
                if copied > max_bytes:
                    raise ValueError('remote file exceeds its max_bytes safety limit')
                output.write(block)
        return
    except (URLError, ConnectionError, TimeoutError, OSError):
        try:
            target.unlink()
        except FileNotFoundError:
            pass
    curl = shutil.which('curl.exe') or shutil.which('curl')
    if curl is None:
        raise RuntimeError('download failed and curl fallback is unavailable')
    subprocess.run(
        [curl, '-fL', '--retry', '3', '--retry-delay', '1', '--output', str(target), url],
        check=True,
    )
    if target.stat().st_size > max_bytes:
        raise ValueError('remote file exceeds its max_bytes safety limit')


def fetch_source(
    source_id: str,
    *,
    registry_path: str | Path = REGISTRY_PATH,
    raw_root: str | Path = Path('data/raw'),
    allow_existing: bool = True,
) -> Path:
    '''Fetch or register one raw source after a fail-closed license check.'''

    spec = source_spec(source_id, registry_path)
    status = spec.text('license_status')
    if status not in APPROVED_LICENSE_STATUSES:
        raise PermissionError(f'{source_id} license status is {status}; acquisition denied')

    directory = Path(raw_root) / source_id
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / spec.filename
    transport = spec.text('transport')
    requested_url = ''
    resolved_url = ''
    resolved_revision: str | None = None

    if transport == 'manual':
        if not target.is_file():
            instructions = spec.text('manual_instructions', 'Place the source file manually.')
            raise FileNotFoundError(f'{target} is required. {instructions}')
    elif not (allow_existing and target.is_file()):
        requested_url, resolved_revision, resolved_url = resolve_source(spec)
        descriptor, temporary = tempfile.mkstemp(prefix=f'.{target.name}.', suffix='.download', dir=directory)
        os.close(descriptor)
        temporary_path = Path(temporary)
        try:
            _download(resolved_url, temporary_path, spec.integer('max_bytes'))
            _verify(spec, temporary_path)
            os.replace(temporary_path, target)
        finally:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
    elif transport != 'manual':
        requested_url, resolved_revision, resolved_url = resolve_source(spec)

    fingerprints = _verify(spec, target)
    manifest: dict[str, object] = {
        'manifest_version': 1,
        'registry_version': 1,
        'source_id': source_id,
        'title': spec.text('title'),
        'license': spec.text('license'),
        'license_status': status,
        'redistribution': bool(spec.values.get('redistribution', False)),
        'requested_url': requested_url,
        'resolved_url': resolved_url,
        'requested_revision': spec.text('revision') or None,
        'resolved_revision': resolved_revision,
        'fetched_at_utc': datetime.now(timezone.utc).isoformat(),
        'file': spec.filename,
        **fingerprints,
    }
    _write_json(directory / 'FETCH_MANIFEST.json', manifest)
    return target


__all__ = [
    'APPROVED_LICENSE_STATUSES',
    'REGISTRY_PATH',
    'SourceSpec',
    'fetch_source',
    'file_fingerprints',
    'load_registry',
    'resolve_source',
    'source_spec',
]
