'''TOML configuration for API-backed CalibRead inference.'''

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
from math import isfinite
from pathlib import Path
import tomllib
from typing import Mapping
from urllib.parse import urlparse


R5_LEVELS: tuple[str, ...] = (
    'one_hop',
    'two_hop',
    'three_hop',
    'four_plus_hop',
)


@dataclass(frozen=True)
class DatasetConfig:
    dataset_id: str
    examples: Path
    workloads: Path


@dataclass(frozen=True)
class ProviderConfig:
    kind: str
    base_url: str
    api_key_env: str
    timeout_seconds: float
    max_retries: int
    concurrency: int
    http_referer: str
    app_title: str
    keep_alive: str = '5m'
    local_only: bool = False
    minimum_interval_seconds: float = 0.0


@dataclass(frozen=True)
class ModelConfig:
    requested_model: str
    temperature: float
    max_tokens: int
    require_logprobs: bool
    top_logprobs: int
    provider_order: tuple[str, ...]
    allow_fallbacks: bool
    require_parameters: bool
    data_collection: str
    decoding_seed: int = 0
    num_ctx: int | None = None
    reasoning_effort: str | None = None


@dataclass(frozen=True)
class PromptConfig:
    template_id: str
    system: str
    user_template: str


@dataclass(frozen=True)
class BudgetConfig:
    max_cost_usd: float
    max_requests: int
    prompt_usd_per_million: float
    completion_usd_per_million: float


@dataclass(frozen=True)
class RunConfig:
    run_id: str
    split: str
    seed: int
    limit_per_level: int | None
    output_dir: Path
    resume: bool
    include_levels: tuple[str, ...] = R5_LEVELS
    chain_complete: bool = False
    parent_experiment_id: str | None = None
    required_human_audit_manifests: tuple[Path, ...] = ()
    promotion_approved: bool = True


def _validate_ollama_endpoint(base_url: str) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme != 'http' or parsed.username or parsed.password:
        raise ValueError('Ollama requires an unauthenticated http loopback base_url')
    if parsed.query or parsed.fragment or parsed.path.rstrip('/') not in {'', '/api'}:
        raise ValueError('Ollama base_url must end at the server root or /api')
    host = parsed.hostname
    loopback = host == 'localhost'
    if host and not loopback:
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = False
    if not loopback:
        raise ValueError('Ollama execution requires a loopback-only base_url')


def _looks_like_cloud_model(model: str) -> bool:
    return 'cloud' in model.casefold()


@dataclass(frozen=True)
class InferenceConfig:
    path: Path
    run: RunConfig
    provider: ProviderConfig
    model: ModelConfig
    prompt: PromptConfig
    budget: BudgetConfig
    datasets: tuple[DatasetConfig, ...]

    def validate_for_execution(self) -> None:
        if self.provider.kind == 'openrouter':
            lowered = self.model.requested_model.casefold()
            if any(
                token in lowered
                for token in (
                    'replace',
                    'latest',
                    'openrouter/auto',
                    'openrouter/free',
                )
            ):
                raise ValueError('real inference requires a concrete non-moving model slug')
            if ':online' in lowered:
                raise ValueError('closed-book inference forbids OpenRouter :online models')
            if lowered.endswith(':free'):
                if (
                    self.budget.prompt_usd_per_million != 0
                    or self.budget.completion_usd_per_million != 0
                    or self.budget.max_cost_usd != 0
                ):
                    raise ValueError(
                        'a concrete OpenRouter :free route requires zero frozen '
                        'prices and max_cost_usd=0'
                    )
                if len(self.model.provider_order) != 1 or self.model.allow_fallbacks:
                    raise ValueError(
                        'a concrete OpenRouter :free route requires exactly one '
                        'pinned provider and allow_fallbacks=false'
                    )
                if not self.model.require_parameters:
                    raise ValueError(
                        'OpenRouter :free execution requires require_parameters=true'
                    )
                if not self.model.require_logprobs or self.model.top_logprobs < 1:
                    raise ValueError(
                        'CalibRead OpenRouter :free execution requires logprobs '
                        'and at least one top logprob'
                    )
                if self.provider.concurrency != 1:
                    raise ValueError('OpenRouter :free execution requires concurrency=1')
                if self.provider.minimum_interval_seconds < 3.0:
                    raise ValueError(
                        'OpenRouter :free execution requires '
                        'minimum_interval_seconds>=3.0'
                    )
                if self.budget.max_requests > 40:
                    raise ValueError(
                        'OpenRouter :free execution caps actual HTTP attempts at 40 '
                        'per invocation'
                    )
            elif (
                self.budget.prompt_usd_per_million <= 0
                or self.budget.completion_usd_per_million <= 0
            ):
                raise ValueError('OpenRouter execution requires positive frozen pricing values')
        elif self.provider.kind == 'ollama':
            model = self.model.requested_model
            if 'replace' in model.casefold():
                raise ValueError('Ollama execution requires an installed local model name')
            if _looks_like_cloud_model(model):
                raise ValueError('Ollama cloud models are forbidden for local-only inference')
            if not self.provider.local_only:
                raise ValueError('Ollama inference requires provider.local_only=true')
            _validate_ollama_endpoint(self.provider.base_url)
            if self.model.provider_order or self.model.allow_fallbacks:
                raise ValueError('Ollama local-only inference forbids provider routing/fallbacks')
            if self.model.data_collection != 'deny':
                raise ValueError('Ollama local-only inference requires data_collection=deny')
            if self.budget.prompt_usd_per_million or self.budget.completion_usd_per_million:
                raise ValueError('local Ollama token pricing must be zero')
        for dataset in self.datasets:
            if not dataset.examples.is_file() or not dataset.workloads.is_file():
                raise FileNotFoundError(f'missing dataset artifacts for {dataset.dataset_id}')


def _table(payload: Mapping[str, object], name: str) -> Mapping[str, object]:
    value = payload.get(name)
    if not isinstance(value, Mapping):
        raise ValueError(f'missing [{name}] table')
    return value


def _text(table: Mapping[str, object], name: str, default: str = '') -> str:
    value = table.get(name, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a nonempty string')
    return value.strip()


def _boolean(table: Mapping[str, object], name: str, default: bool) -> bool:
    value = table.get(name, default)
    if not isinstance(value, bool):
        raise ValueError(f'{name} must be a boolean')
    return value


def _integer(table: Mapping[str, object], name: str, default: int) -> int:
    value = table.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f'{name} must be an integer')
    return value


def _number(table: Mapping[str, object], name: str, default: float) -> float:
    value = table.get(name, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name} must be a finite number')
    normalized = float(value)
    if not isfinite(normalized):
        raise ValueError(f'{name} must be a finite number')
    return normalized


def load_inference_config(path: str | Path) -> InferenceConfig:
    source = Path(path)
    with source.open('rb') as stream:
        payload = tomllib.load(stream)
    run = _table(payload, 'run')
    provider = _table(payload, 'provider')
    model = _table(payload, 'model')
    prompt = _table(payload, 'prompt')
    budget = _table(payload, 'budget')
    raw_datasets = payload.get('datasets')
    if not isinstance(raw_datasets, list) or not raw_datasets:
        raise ValueError('at least one [[datasets]] table is required')
    datasets: list[DatasetConfig] = []
    dataset_ids: set[str] = set()
    for raw in raw_datasets:
        if not isinstance(raw, Mapping):
            raise ValueError('datasets entries must be tables')
        dataset_id = _text(raw, 'dataset_id')
        if dataset_id in dataset_ids:
            raise ValueError(f'duplicate datasets.dataset_id {dataset_id!r}')
        dataset_ids.add(dataset_id)
        datasets.append(
            DatasetConfig(
                dataset_id=dataset_id,
                examples=Path(_text(raw, 'examples')),
                workloads=Path(_text(raw, 'workloads')),
            )
        )
    limit = run.get('limit_per_level')
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 1):
        raise ValueError('limit_per_level must be a positive integer or omitted')
    raw_levels = run.get('include_levels', list(R5_LEVELS))
    if not isinstance(raw_levels, list) or not raw_levels:
        raise ValueError('run.include_levels must be a nonempty array of canonical R5 levels')
    if any(not isinstance(value, str) for value in raw_levels):
        raise ValueError('run.include_levels must contain only strings')
    requested_levels = tuple(value.strip() for value in raw_levels)
    if any(not value for value in requested_levels):
        raise ValueError('run.include_levels must contain only nonempty strings')
    if len(set(requested_levels)) != len(requested_levels):
        raise ValueError('run.include_levels must not contain duplicates')
    unknown_levels = sorted(set(requested_levels) - set(R5_LEVELS))
    if unknown_levels:
        raise ValueError(
            'run.include_levels contains unknown R5 levels: '
            + ', '.join(unknown_levels)
        )
    include_levels = tuple(level for level in R5_LEVELS if level in requested_levels)
    raw_chain_complete = run.get('chain_complete', False)
    if not isinstance(raw_chain_complete, bool):
        raise ValueError('run.chain_complete must be a boolean')
    raw_parent_experiment_id = run.get('parent_experiment_id')
    if raw_parent_experiment_id is not None and (
        not isinstance(raw_parent_experiment_id, str)
        or not raw_parent_experiment_id.strip()
    ):
        raise ValueError('run.parent_experiment_id must be a nonempty string or omitted')
    parent_experiment_id = (
        None
        if raw_parent_experiment_id is None
        else raw_parent_experiment_id.strip()
    )
    raw_audit_manifests = run.get('required_human_audit_manifests', [])
    if not isinstance(raw_audit_manifests, list) or any(
        not isinstance(value, str) or not value.strip()
        for value in raw_audit_manifests
    ):
        raise ValueError(
            'run.required_human_audit_manifests must be an array of nonempty paths'
        )
    audit_manifest_paths = tuple(Path(value.strip()) for value in raw_audit_manifests)
    if len(set(audit_manifest_paths)) != len(audit_manifest_paths):
        raise ValueError('run.required_human_audit_manifests must not contain duplicates')
    kind = _text(provider, 'kind')
    if kind not in {'openrouter', 'ollama', 'mock'}:
        raise ValueError('provider.kind must be openrouter, ollama, or mock')
    split = _text(run, 'split')
    if split not in {'development', 'calibration', 'test'}:
        raise ValueError('run.split must be development, calibration, or test')
    data_collection = _text(model, 'data_collection', 'deny')
    if data_collection not in {'allow', 'deny'}:
        raise ValueError('data_collection must be allow or deny')
    default_base_url = (
        'http://127.0.0.1:11434/api'
        if kind == 'ollama'
        else 'https://openrouter.ai/api/v1'
    )
    default_key_env = 'OPENROUTER_API_KEY' if kind == 'openrouter' else ''
    key_value = provider.get('api_key_env', default_key_env)
    if not isinstance(key_value, str):
        raise ValueError('api_key_env must be a string')
    api_key_env = key_value.strip()
    if kind == 'openrouter' and not api_key_env:
        raise ValueError('OpenRouter requires a nonempty api_key_env')
    raw_num_ctx = model.get('num_ctx')
    if raw_num_ctx is not None and (
        isinstance(raw_num_ctx, bool) or not isinstance(raw_num_ctx, int)
    ):
        raise ValueError('num_ctx must be a positive integer or omitted')
    raw_decoding_seed = model.get('decoding_seed', 0)
    if isinstance(raw_decoding_seed, bool) or not isinstance(raw_decoding_seed, int):
        raise ValueError('decoding_seed must be an integer')
    raw_reasoning_effort = model.get('reasoning_effort')
    if raw_reasoning_effort is not None and (
        not isinstance(raw_reasoning_effort, str)
        or raw_reasoning_effort not in {
            'none',
            'minimal',
            'low',
            'medium',
            'high',
            'xhigh',
            'max',
        }
    ):
        raise ValueError('reasoning_effort must be a supported effort or omitted')
    raw_provider_order = model.get('provider_order', [])
    if not isinstance(raw_provider_order, list) or any(
        not isinstance(value, str) or not value.strip()
        for value in raw_provider_order
    ):
        raise ValueError('provider_order must be an array of nonempty strings')
    configuration = InferenceConfig(
        path=source,
        run=RunConfig(
            run_id=_text(run, 'run_id'),
            split=split,
            seed=_integer(run, 'seed', 7),
            limit_per_level=limit,
            output_dir=Path(_text(run, 'output_dir')),
            resume=_boolean(run, 'resume', True),
            include_levels=include_levels,
            chain_complete=raw_chain_complete,
            parent_experiment_id=parent_experiment_id,
            required_human_audit_manifests=audit_manifest_paths,
            promotion_approved=_boolean(run, 'promotion_approved', True),
        ),
        provider=ProviderConfig(
            kind=kind,
            base_url=_text(provider, 'base_url', default_base_url),
            api_key_env=api_key_env,
            timeout_seconds=_number(provider, 'timeout_seconds', 120),
            max_retries=_integer(provider, 'max_retries', 6),
            concurrency=_integer(provider, 'concurrency', 1),
            http_referer=str(provider.get('http_referer', '')).strip(),
            app_title=str(provider.get('app_title', 'CalibRead')).strip(),
            keep_alive=str(provider.get('keep_alive', '5m')).strip(),
            local_only=_boolean(provider, 'local_only', kind == 'ollama'),
            minimum_interval_seconds=_number(
                provider, 'minimum_interval_seconds', 0
            ),
        ),
        model=ModelConfig(
            requested_model=_text(model, 'requested_model'),
            temperature=_number(model, 'temperature', 0),
            max_tokens=_integer(model, 'max_tokens', 64),
            require_logprobs=_boolean(model, 'require_logprobs', False),
            top_logprobs=_integer(model, 'top_logprobs', 1),
            provider_order=tuple(value.strip() for value in raw_provider_order),
            allow_fallbacks=_boolean(model, 'allow_fallbacks', False),
            require_parameters=_boolean(model, 'require_parameters', True),
            data_collection=data_collection,
            decoding_seed=raw_decoding_seed,
            num_ctx=raw_num_ctx,
            reasoning_effort=raw_reasoning_effort,
        ),
        prompt=PromptConfig(
            template_id=_text(prompt, 'template_id'),
            system=_text(prompt, 'system'),
            user_template=_text(prompt, 'user_template'),
        ),
        budget=BudgetConfig(
            max_cost_usd=_number(budget, 'max_cost_usd', 0),
            max_requests=_integer(budget, 'max_requests', 0),
            prompt_usd_per_million=_number(budget, 'prompt_usd_per_million', 0),
            completion_usd_per_million=_number(
                budget, 'completion_usd_per_million', 0
            ),
        ),
        datasets=tuple(datasets),
    )
    if configuration.provider.timeout_seconds <= 0 or configuration.provider.max_retries < 0:
        raise ValueError('timeout must be positive and max_retries nonnegative')
    if configuration.provider.minimum_interval_seconds < 0:
        raise ValueError('minimum_interval_seconds must be nonnegative')
    if configuration.provider.concurrency < 1:
        raise ValueError('concurrency must be positive')
    if configuration.provider.kind == 'ollama' and not configuration.provider.keep_alive:
        raise ValueError('Ollama keep_alive must be nonempty')
    if configuration.model.temperature < 0:
        raise ValueError('temperature must be nonnegative')
    if configuration.model.max_tokens < 1 or configuration.model.top_logprobs < 0:
        raise ValueError('max_tokens must be positive and top_logprobs nonnegative')
    if configuration.model.num_ctx is not None and configuration.model.num_ctx < 1:
        raise ValueError('num_ctx must be a positive integer or omitted')
    if (
        configuration.budget.max_cost_usd < 0
        or configuration.budget.max_requests < 1
        or configuration.budget.prompt_usd_per_million < 0
        or configuration.budget.completion_usd_per_million < 0
    ):
        raise ValueError(
            'budget requires nonnegative costs/prices and positive max_requests'
        )
    if '{question}' not in configuration.prompt.user_template:
        raise ValueError('prompt.user_template must contain {question}')
    return configuration
