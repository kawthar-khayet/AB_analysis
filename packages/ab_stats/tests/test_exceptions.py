"""Tests des erreurs structurées."""

from __future__ import annotations

import json

import pytest

from ab_stats.exceptions import (
    ABStatsError,
    DataValidationError,
    InsufficientSampleError,
    InternalConsistencyError,
    InvalidParameterError,
)


@pytest.mark.parametrize(
    ("error_type", "category"),
    [
        (DataValidationError, "DATA_VALIDATION_ERROR"),
        (InsufficientSampleError, "INSUFFICIENT_SAMPLE_ERROR"),
        (InvalidParameterError, "INVALID_PARAMETER_ERROR"),
        (InternalConsistencyError, "INTERNAL_CONSISTENCY_ERROR"),
    ],
)
def test_every_error_has_a_category_and_a_specific_code(error_type, category) -> None:
    error = error_type("SOME_CODE", "Un message.", details={"n": 3})

    assert isinstance(error, ABStatsError)
    assert error.category == category
    assert error.code == "SOME_CODE"
    assert str(error) == "Un message."


def test_error_serializes_to_json() -> None:
    error = DataValidationError(
        "BINARY_VALIDATION_FAILED",
        "Valeurs inattendues.",
        details={"unexpected_values": [{"value": "2", "count": 1}]},
    )

    payload = error.to_dict()

    assert payload == {
        "code": "BINARY_VALIDATION_FAILED",
        "category": "DATA_VALIDATION_ERROR",
        "message": "Valeurs inattendues.",
        "details": {"unexpected_values": [{"value": "2", "count": 1}]},
    }
    assert json.loads(json.dumps(payload)) == payload


def test_details_default_to_empty_and_are_copied() -> None:
    source = {"n": 1}
    error = DataValidationError("CODE", "message", details=source)
    source["n"] = 99

    assert DataValidationError("CODE", "message").details == {}
    assert error.details == {"n": 1}


def test_invalid_parameter_error_is_also_a_value_error() -> None:
    with pytest.raises(ValueError):
        raise InvalidParameterError("CODE", "message")
