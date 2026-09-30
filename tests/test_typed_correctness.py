"""R2 precision and granularity scoring tests."""

from __future__ import annotations

import unittest
from pathlib import Path

from calibread.io import read_jsonl
from calibread.leakage import normalized_question_hash
from calibread.schema import Example
from calibread.typed_correctness import (
    date_match,
    numeric_match,
    significant_digit_count,
    typed_match,
)


class NumericScoringTests(unittest.TestCase):
    def test_tolerance_and_written_precision_are_independent(self) -> None:
        self.assertTrue(numeric_match("1,234.50", ("1234.5",)))
        self.assertTrue(
            numeric_match("3.142", ("3.1416",), absolute_tolerance="0.001")
        )
        self.assertFalse(
            numeric_match(
                "3.1",
                ("3.100",),
                absolute_tolerance="0",
                required_decimal_places=3,
            )
        )

    def test_invalid_prediction_is_incorrect_and_invalid_policy_fails(self) -> None:
        self.assertFalse(numeric_match("approximately ten", ("10",)))
        self.assertFalse(numeric_match("NaN", ("10",)))
        with self.assertRaises(ValueError):
            numeric_match("10", ("10",), absolute_tolerance="-1")
        with self.assertRaises(ValueError):
            numeric_match("10", ("bad gold",))
        with self.assertRaises(ValueError):
            numeric_match("10", ("10",), required_decimal_places=-1)
        with self.assertRaises(ValueError):
            numeric_match("10", ("10",), required_decimal_places=1.5)  # type: ignore[arg-type]


    def test_significant_digits_are_distinct_from_numeric_closeness(self) -> None:
        self.assertEqual(significant_digit_count('1.20e3'), 3)
        self.assertEqual(significant_digit_count('0.00450'), 3)
        self.assertEqual(significant_digit_count('0.00'), 2)
        self.assertEqual(significant_digit_count('1000'), 4)
        with self.assertRaises(ValueError):
            significant_digit_count('approximately ten')

        self.assertTrue(
            numeric_match(
                '3.14',
                ('3.140',),
                required_significant_digits=3,
                maximum_significant_digits=3,
            )
        )
        self.assertFalse(
            numeric_match('3.1', ('3.1',), required_significant_digits=3)
        )
        self.assertFalse(
            numeric_match('3.1400', ('3.1400',), maximum_significant_digits=3)
        )
        self.assertTrue(
            typed_match(
                '3.14',
                ('3.140',),
                answer_type='numeric',
                required_significant_digits=3,
                maximum_significant_digits=3,
            )
        )

    def test_invalid_significant_digit_policies_fail_closed(self) -> None:
        invalid_calls = (
            lambda: numeric_match('1', ('1',), required_significant_digits=-1),
            lambda: numeric_match('1', ('1',), required_significant_digits=True),
            lambda: numeric_match('1', ('1',), maximum_significant_digits=1.5),
            lambda: numeric_match(
                '1',
                ('1',),
                required_significant_digits=3,
                maximum_significant_digits=2,
            ),
        )
        for call in invalid_calls:
            with self.subTest(call=call), self.assertRaises(ValueError):
                call()


class ExampleRecordCoherenceTests(unittest.TestCase):
    def test_example_is_scoreable_and_uses_canonical_lineage_keys(self) -> None:
        path = Path(__file__).parents[1] / 'data' / 'EXAMPLE_RECORD.jsonl'
        row = read_jsonl(path)[0]
        example = Example.from_dict(row)
        metadata = example.metadata
        for field in (
            'entity_id',
            'chain_id',
            'template_id',
            'source_fact_id',
            'question_hash',
        ):
            self.assertIn(field, metadata)
        self.assertEqual(
            metadata['question_hash'], normalized_question_hash(example.question)
        )
        self.assertTrue(
            typed_match(
                example.accepted_answers[0],
                example.accepted_answers,
                answer_type='date',
                date_granularity='month',
            )
        )
        constituents = metadata['dimension_provenance']['R5'][
            'constituent_example_ids'
        ]
        self.assertNotIn(example.example_id, constituents)


class DateAndDispatchTests(unittest.TestCase):
    def test_iso_date_granularity_is_enforced(self) -> None:
        self.assertTrue(date_match("2026", ("2026",), granularity="year"))
        self.assertTrue(date_match("2026-08", ("2026-08",), granularity="month"))
        self.assertFalse(date_match("2026-8", ("2026-08",), granularity="month"))
        self.assertTrue(date_match("2026-08-11", ("2026-08-11",), granularity="day"))
        self.assertFalse(date_match("2026-02-31", ("2026-02-28",), granularity="day"))

    def test_dispatch_preserves_categorical_aliases(self) -> None:
        self.assertTrue(
            typed_match(
                "The United States",
                ("United States", "USA"),
                answer_type="categorical",
            )
        )
        with self.assertRaises(ValueError):
            typed_match("x", ("x",), answer_type="unsupported")


if __name__ == "__main__":
    unittest.main()
