"""Small dependency-free uncertainty summaries for experiment reports."""

from __future__ import annotations

from collections import defaultdict
from math import exp, isfinite, lgamma, log, log1p, sqrt
from random import Random
from statistics import NormalDist, fmean
from typing import Hashable, Iterable, Sequence

# Exact binomial helpers follow.


def _validate_binomial_inputs(
    successes: int,
    total: int,
    confidence: float,
) -> None:
    if isinstance(successes, bool) or not isinstance(successes, int):
        raise ValueError('successes must be an integer')
    if isinstance(total, bool) or not isinstance(total, int):
        raise ValueError('total must be an integer')
    if total < 1 or successes < 0 or successes > total:
        raise ValueError('require 0 <= successes <= total and total >= 1')
    if not 0.0 < confidence < 1.0:
        raise ValueError('confidence must lie strictly between 0 and 1')


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    maximum_iterations = 300
    epsilon = 3e-14
    tiny = 1e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    result = d
    for iteration in range(1, maximum_iterations + 1):
        even = 2 * iteration
        coefficient = iteration * (b - iteration) * x / (
            (qam + even) * (a + even)
        )
        d = 1.0 + coefficient * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + coefficient / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        result *= d * c
        coefficient = -(a + iteration) * (qab + iteration) * x / (
            (a + even) * (qap + even)
        )
        d = 1.0 + coefficient * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + coefficient / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        result *= delta
        if abs(delta - 1.0) <= epsilon:
            return result
    raise ArithmeticError('incomplete beta continued fraction did not converge')


def _regularized_beta(x: float, a: float, b: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = exp(
        lgamma(a + b) - lgamma(a) - lgamma(b)
        + a * log(x) + b * log1p(-x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _beta_continued_fraction(a, b, x) / a
    return 1.0 - front * _beta_continued_fraction(b, a, 1.0 - x) / b


def _beta_quantile(probability: float, a: float, b: float) -> float:
    if probability <= 0.0:
        return 0.0
    if probability >= 1.0:
        return 1.0
    lower = 0.0
    upper = 1.0
    for _ in range(100):
        midpoint = (lower + upper) / 2.0
        if _regularized_beta(midpoint, a, b) < probability:
            lower = midpoint
        else:
            upper = midpoint
    return (lower + upper) / 2.0


def clopper_pearson_interval(
    successes: int,
    total: int,
    *,
    confidence: float = 0.95,
) -> tuple[float, float]:
    '''Return the exact equal-tailed Clopper-Pearson binomial interval.

    Exact refers to the coverage construction. Beta quantiles are inverted
    numerically without a third-party dependency.
    '''

    _validate_binomial_inputs(successes, total, confidence)
    tail = (1.0 - confidence) / 2.0
    lower = 0.0 if successes == 0 else _beta_quantile(
        tail, float(successes), float(total - successes + 1)
    )
    upper = 1.0 if successes == total else _beta_quantile(
        1.0 - tail, float(successes + 1), float(total - successes)
    )
    return lower, upper


def wilson_interval(
    successes: int, total: int, *, confidence: float = 0.95
) -> tuple[float, float]:
    """Return a two-sided Wilson score interval for a binomial proportion."""

    if total < 1 or successes < 0 or successes > total:
        raise ValueError("require 0 <= successes <= total and total >= 1")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must lie strictly between 0 and 1")
    z = NormalDist().inv_cdf(0.5 + confidence / 2.0)
    proportion = successes / total
    denominator = 1.0 + z * z / total
    center = (proportion + z * z / (2.0 * total)) / denominator
    radius = (
        z
        * sqrt(proportion * (1.0 - proportion) / total + z * z / (4.0 * total * total))
        / denominator
    )
    lower = max(0.0, center - radius)
    upper = min(1.0, center + radius)
    if lower < 1e-15:
        lower = 0.0
    if upper > 1.0 - 1e-15:
        upper = 1.0
    return lower, upper


def bootstrap_mean_interval(
    values: Iterable[float],
    *,
    confidence: float = 0.95,
    n_resamples: int = 2000,
    seed: int = 0,
) -> tuple[float, float]:
    """Return a deterministic percentile-bootstrap interval for a sample mean."""

    sample = [float(value) for value in values]
    if not sample:
        raise ValueError("values must not be empty")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must lie strictly between 0 and 1")
    if n_resamples < 2:
        raise ValueError("n_resamples must be at least 2")
    random = Random(seed)
    size = len(sample)
    estimates = sorted(
        fmean(sample[random.randrange(size)] for _ in range(size))
        for _ in range(n_resamples)
    )
    tail = (1.0 - confidence) / 2.0
    lower_index = max(0, int(tail * n_resamples))
    upper_index = min(n_resamples - 1, int((1.0 - tail) * n_resamples) - 1)
    return estimates[lower_index], estimates[upper_index]


def holm_adjusted_pvalues(p_values: Iterable[float]) -> list[float]:
    '''Return Holm family-wise-error adjusted p-values in input order.'''

    values = [float(value) for value in p_values]
    if any(not isfinite(value) or value < 0.0 or value > 1.0 for value in values):
        raise ValueError('p-values must be finite and lie in [0, 1]')
    if not values:
        return []
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    adjusted = [0.0] * len(values)
    running = 0.0
    for rank, (original_index, p_value) in enumerate(ordered):
        candidate = min(1.0, (len(values) - rank) * p_value)
        running = max(running, candidate)
        adjusted[original_index] = running
    return adjusted


def clustered_paired_bootstrap_difference(
    first: Sequence[float],
    second: Sequence[float],
    clusters: Sequence[Hashable],
    *,
    confidence: float = 0.95,
    n_resamples: int = 2000,
    seed: int = 0,
) -> tuple[float, float, float]:
    '''Return mean(first-second) and a cluster-bootstrap percentile interval.'''

    if not first or len(first) != len(second) or len(first) != len(clusters):
        raise ValueError('paired values and clusters must be nonempty and aligned')
    if not 0.0 < confidence < 1.0:
        raise ValueError('confidence must lie strictly between 0 and 1')
    if n_resamples < 2:
        raise ValueError('n_resamples must be at least 2')
    differences = [float(a) - float(b) for a, b in zip(first, second)]
    if any(not isfinite(value) for value in differences):
        raise ValueError('paired values must be finite')
    members: dict[Hashable, list[int]] = defaultdict(list)
    for index, cluster in enumerate(clusters):
        try:
            hash(cluster)
        except TypeError as error:
            raise ValueError('cluster identifiers must be hashable') from error
        members[cluster].append(index)
    cluster_ids = list(members)
    estimate = fmean(differences)
    random = Random(seed)
    estimates: list[float] = []
    for _ in range(n_resamples):
        sampled_indices: list[int] = []
        for _ in cluster_ids:
            sampled_indices.extend(members[random.choice(cluster_ids)])
        estimates.append(fmean(differences[index] for index in sampled_indices))
    estimates.sort()
    tail = (1.0 - confidence) / 2.0
    lower_index = max(0, int(tail * n_resamples))
    upper_index = min(n_resamples - 1, int((1.0 - tail) * n_resamples) - 1)
    return estimate, estimates[lower_index], estimates[upper_index]
