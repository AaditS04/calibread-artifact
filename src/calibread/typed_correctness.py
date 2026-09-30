"""Type-aware deterministic scoring for the R2 precision sweep."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Sequence

from .correctness import exact_match

_DATE_PATTERNS = {
    "year": re.compile(r"^\d{4}$"),
    "month": re.compile(r"^\d{4}-(0[1-9]|1[0-2])$"),
    "day": re.compile(r"^\d{4}-(0[1-9]|1[0-2])-([0-2]\d|3[01])$"),
}
_DATE_FORMATS = {"year": "%Y", "month": "%Y-%m", "day": "%Y-%m-%d"}


_NUMERIC_LITERAL = re.compile(
    r'^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$',
    re.IGNORECASE,
)


def _decimal(text: str) -> Decimal:
    normalized = str(text).strip().replace(",", "")
    try:
        value = Decimal(normalized)
    except InvalidOperation as error:
        raise ValueError(f"not a decimal number: {text!r}") from error
    if not value.is_finite():
        raise ValueError(f"decimal number must be finite: {text!r}")
    return value


def significant_digit_count(text: str) -> int:
    '''Return significant digits explicitly written in a decimal literal.'''

    normalized = str(text).strip().replace(',', '')
    if not _NUMERIC_LITERAL.fullmatch(normalized):
        raise ValueError(f'not a decimal literal: {text!r}')
    _decimal(normalized)
    mantissa = normalized.lower().split('e', maxsplit=1)[0].lstrip('+-')
    integer, separator, fraction = mantissa.partition('.')
    digits = integer + fraction
    for index, digit in enumerate(digits):
        if digit != '0':
            return len(digits) - index
    return max(1, len(fraction)) if separator else 1


def _validate_precision_count(name: str, value: int | None) -> None:
    if value is not None and (
        isinstance(value, bool) or not isinstance(value, int) or value < 0
    ):
        raise ValueError(f'{name} must be a non-negative integer')


def numeric_match(
    prediction: str,
    accepted_values: Sequence[str],
    *,
    absolute_tolerance: str | float | Decimal = "0",
    required_decimal_places: int | None = None,
    required_significant_digits: int | None = None,
    maximum_significant_digits: int | None = None,
) -> bool:
    """Score a numeric response using a frozen tolerance and optional precision floor."""

    if not accepted_values:
        raise ValueError("accepted_values must not be empty")
    tolerance = _decimal(str(absolute_tolerance))
    if tolerance < 0:
        raise ValueError("absolute_tolerance must be non-negative")
    if required_decimal_places is not None and (
        isinstance(required_decimal_places, bool)
        or not isinstance(required_decimal_places, int)
        or required_decimal_places < 0
    ):
        raise ValueError("required_decimal_places must be a non-negative integer")
    _validate_precision_count(
        'required_significant_digits', required_significant_digits
    )
    _validate_precision_count(
        'maximum_significant_digits', maximum_significant_digits
    )
    if (
        required_significant_digits is not None
        and maximum_significant_digits is not None
        and required_significant_digits > maximum_significant_digits
    ):
        raise ValueError('significant-digit floor must not exceed its ceiling')
    references: list[Decimal] = []
    for reference in accepted_values:
        try:
            references.append(_decimal(reference))
        except ValueError as error:
            raise ValueError(f"invalid accepted numeric value: {reference!r}") from error
    try:
        predicted = _decimal(prediction)
    except ValueError:
        return False
    if required_decimal_places is not None:
        written = str(prediction).strip().replace(",", "")
        fraction = written.lower().split("e", maxsplit=1)[0].partition(".")[2]
        if len(fraction) < required_decimal_places:
            return False
    if required_significant_digits is not None or maximum_significant_digits is not None:
        try:
            written_digits = significant_digit_count(prediction)
        except ValueError:
            return False
        if (
            required_significant_digits is not None
            and written_digits < required_significant_digits
        ):
            return False
        if (
            maximum_significant_digits is not None
            and written_digits > maximum_significant_digits
        ):
            return False
    return any(abs(predicted - reference) <= tolerance for reference in references)


def date_match(
    prediction: str,
    accepted_dates: Sequence[str],
    *,
    granularity: str,
) -> bool:
    """Score ISO-normalized dates at year, month, or day granularity."""

    if granularity not in _DATE_PATTERNS:
        raise ValueError("granularity must be year, month, or day")
    if not accepted_dates:
        raise ValueError("accepted_dates must not be empty")
    value = str(prediction).strip()
    if not _DATE_PATTERNS[granularity].fullmatch(value):
        return False
    try:
        datetime.strptime(value, _DATE_FORMATS[granularity])
    except ValueError:
        return False
    normalized_references: set[str] = set()
    for reference in accepted_dates:
        normalized = str(reference).strip()
        if not _DATE_PATTERNS[granularity].fullmatch(normalized):
            raise ValueError("accepted dates must match the declared ISO granularity")
        try:
            datetime.strptime(normalized, _DATE_FORMATS[granularity])
        except ValueError as error:
            raise ValueError(f"invalid accepted calendar date: {normalized!r}") from error
        normalized_references.add(normalized)
    return value in normalized_references


def typed_match(
    prediction: str,
    accepted_answers: Sequence[str],
    *,
    answer_type: str,
    required_significant_digits: int | None = None,
    maximum_significant_digits: int | None = None,
    absolute_tolerance: str | float | Decimal = "0",
    required_decimal_places: int | None = None,
    date_granularity: str = "day",
) -> bool:
    """Dispatch a frozen categorical, numeric, or ISO-date correctness rule."""

    if answer_type == "categorical":
        return exact_match(prediction, accepted_answers)
    if answer_type == "numeric":
        return numeric_match(
            prediction,
            accepted_answers,
            absolute_tolerance=absolute_tolerance,
            required_decimal_places=required_decimal_places,
            required_significant_digits=required_significant_digits,
            maximum_significant_digits=maximum_significant_digits,
        )
    if answer_type == "date":
        return date_match(prediction, accepted_answers, granularity=date_granularity)
    raise ValueError("answer_type must be categorical, numeric, or date")
