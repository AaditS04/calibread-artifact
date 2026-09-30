"""Deterministic exact-match scoring for closed-book short answers."""

from __future__ import annotations

import re
import unicodedata
from typing import Sequence

from .schema import Example, Prediction

_ARTICLES = re.compile(r"\b(a|an|the)\b", flags=re.IGNORECASE)


def normalize_answer(text: str) -> str:
    """Case-fold text, remove punctuation/articles, and collapse whitespace."""

    normalized = unicodedata.normalize("NFKC", str(text)).casefold()
    normalized = "".join(
        " " if unicodedata.category(character).startswith("P") else character
        for character in normalized
    )
    normalized = _ARTICLES.sub(" ", normalized)
    return " ".join(normalized.split())


def exact_match(prediction: str, accepted_answers: Sequence[str]) -> bool:
    """Return whether prediction matches any normalized reference answer."""

    if not accepted_answers:
        raise ValueError("accepted_answers must not be empty")
    normalized_prediction = normalize_answer(prediction)
    return any(
        normalized_prediction == normalize_answer(reference)
        for reference in accepted_answers
    )


def score_prediction(prediction: Prediction, example: Example) -> int:
    """Score an aligned prediction as 1 (correct) or 0 (incorrect)."""

    if prediction.example_id != example.example_id:
        raise ValueError(
            f"prediction id {prediction.example_id!r} does not match "
            f"example id {example.example_id!r}"
        )
    return int(exact_match(prediction.answer, example.accepted_answers))
