"""Diagnostics for database-like composition of calibrated atomic Reads."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite, prod
from typing import Sequence


@dataclass(frozen=True)
class CompositionReport:
    total: int
    chain_accuracy: float
    all_atoms_correct_rate: float
    chain_accuracy_given_all_atoms: float | None
    synthesis_loss: float | None
    mean_product_prediction: float | None
    product_calibration_gap: float | None
    mean_union_bound: float | None

    def to_dict(self) -> dict[str, int | float | None]:
        return asdict(self)


def _binary(value: bool | int, name: str) -> int:
    if value in (True, 1):
        return 1
    if value in (False, 0):
        return 0
    raise ValueError(f"{name} must contain only booleans or 0/1 values")


def composition_report(
    atom_correctness_rows: Sequence[Sequence[bool | int]],
    chain_correctness: Sequence[bool | int],
    atom_confidence_rows: Sequence[Sequence[float]] | None = None,
) -> CompositionReport:
    """Summarize whether correctness and confidence survive multi-fact composition.

    Product probabilities are an independence diagnostic, not a coverage guarantee. The union-bound
    lower bound is conservative for the event that every atomic answer is correct; neither quantity
    alone guarantees that the final synthesis step is correct.
    """

    if not atom_correctness_rows:
        raise ValueError("atom_correctness_rows must not be empty")
    if len(atom_correctness_rows) != len(chain_correctness):
        raise ValueError("atom rows and chain correctness must have the same length")
    if atom_confidence_rows is not None and len(atom_confidence_rows) != len(chain_correctness):
        raise ValueError("confidence rows and chain correctness must have the same length")

    chain = [_binary(value, "chain_correctness") for value in chain_correctness]
    atom_all_correct: list[int] = []
    product_predictions: list[float] = []
    union_bounds: list[float] = []
    for index, correctness_row in enumerate(atom_correctness_rows):
        if not correctness_row:
            raise ValueError("atomic correctness rows must not be empty")
        atoms = [_binary(value, "atom_correctness_rows") for value in correctness_row]
        atom_all_correct.append(int(all(atoms)))
        if atom_confidence_rows is not None:
            confidence_row = [float(value) for value in atom_confidence_rows[index]]
            if len(confidence_row) != len(atoms):
                raise ValueError("each confidence row must match its atomic correctness row")
            if any(not isfinite(value) or not 0.0 <= value <= 1.0 for value in confidence_row):
                raise ValueError("atomic confidences must be finite and lie in [0, 1]")
            product_predictions.append(prod(confidence_row))
            union_bounds.append(max(0.0, 1.0 - sum(1.0 - value for value in confidence_row)))

    total = len(chain)
    chain_accuracy = sum(chain) / total
    eligible = [value for value, all_correct in zip(chain, atom_all_correct) if all_correct]
    conditional_accuracy = sum(eligible) / len(eligible) if eligible else None
    mean_product = sum(product_predictions) / total if product_predictions else None
    return CompositionReport(
        total=total,
        chain_accuracy=chain_accuracy,
        all_atoms_correct_rate=sum(atom_all_correct) / total,
        chain_accuracy_given_all_atoms=conditional_accuracy,
        synthesis_loss=None if conditional_accuracy is None else 1.0 - conditional_accuracy,
        mean_product_prediction=mean_product,
        product_calibration_gap=(
            None if mean_product is None else mean_product - chain_accuracy
        ),
        mean_union_bound=(sum(union_bounds) / total if union_bounds else None),
    )
