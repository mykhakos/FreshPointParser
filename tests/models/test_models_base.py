from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from pydantic import ValidationError

from freshpointparser.models._base import BaseRecord


class DummyRecord(BaseRecord):
    """A dummy model for testing purposes with optional fields."""

    field1: Optional[str] = None
    field2: Optional[int] = None
    field3: Optional[List[float]] = None


@dataclass
class MockContext:
    """Mock context object for testing validation error handling.

    NOTE: The validator expects 'parse_errors' attribute name.
    """

    parse_errors: List[Exception] = field(default_factory=list)

    def register_error(self, error: Exception) -> None:
        """Register a validation error in the context."""
        self.parse_errors.append(error)


# region Test _log_failed_validation


def test_log_failed_validation_without_context():
    """Test that validation errors fall back to None when no context is provided."""
    # When validation fails without context, the field should default to None
    record = DummyRecord.model_validate({
        'field1': 'valid',
        'field2': 'invalid_int',
        'field3': [1.0, 2.0],
    })

    # field2 should be None since validation failed
    assert record.field1 == 'valid'
    assert record.field2 is None
    assert record.field3 == [1.0, 2.0]


def test_log_failed_validation_with_context():
    """Test that validation errors are stored in context when provided."""
    context = MockContext()

    # Pass context during validation
    record = DummyRecord.model_validate(
        {'field1': 'valid', 'field2': 'invalid_int', 'field3': [1.0, 2.0]},
        context=context,
    )

    # field2 should be None since validation failed
    assert record.field1 == 'valid'
    assert record.field2 is None
    assert record.field3 == [1.0, 2.0]

    # The validation error should be stored in the context
    assert len(context.parse_errors) == 1
    assert isinstance(context.parse_errors[0], ValidationError)


def test_log_failed_validation_multiple_fields():
    """Test that multiple field validation errors are all handled."""
    context = MockContext()

    record = DummyRecord.model_validate(
        {'field1': 123, 'field2': 'not_an_int', 'field3': 'not_a_list'},
        context=context,
    )

    # All invalid fields should be None
    assert record.field1 is None
    assert record.field2 is None
    assert record.field3 is None

    # All three validation errors should be stored
    assert len(context.parse_errors) == 1
    assert all(isinstance(err, ValidationError) for err in context.parse_errors)


def test_log_failed_validation_valid_data():
    """Test that valid data passes through without errors."""
    context = MockContext()

    record = DummyRecord.model_validate(
        {'field1': 'valid', 'field2': 42, 'field3': [1.0, 2.0, 3.0]},
        context=context,
    )

    # All fields should have their values
    assert record.field1 == 'valid'
    assert record.field2 == 42
    assert record.field3 == [1.0, 2.0, 3.0]

    # No errors should be stored
    assert len(context.parse_errors) == 0


def test_log_failed_validation_context_without_parse_errors():
    """Test validation with context that doesn't have parse_errors attribute."""
    # Pass a context dict without parse_errors
    record = DummyRecord.model_validate(
        {'field1': 'valid', 'field2': 'invalid_int', 'field3': [1.0]},
        context={'some_other_key': 'value'},
    )

    # Should still work, field2 should be None
    assert record.field1 == 'valid'
    assert record.field2 is None
    assert record.field3 == [1.0]


def test_log_failed_validation_mixed_valid_invalid():
    """Test validation with a mix of valid and invalid fields."""
    context = MockContext()

    record = DummyRecord.model_validate(
        {'field1': 'valid_string', 'field2': 'invalid', 'field3': [1.0, 2.5]},
        context=context,
    )

    # Valid fields should have their values
    assert record.field1 == 'valid_string'
    assert record.field3 == [1.0, 2.5]

    # Invalid field should be None
    assert record.field2 is None

    # Only one error should be stored
    assert len(context.parse_errors) == 1


def test_log_failed_validation_preserves_recorded_at():
    """Test that recorded_at field is preserved even when other fields fail validation."""
    context = MockContext()
    test_datetime = datetime(2025, 12, 27, 10, 30, 0)

    record = DummyRecord.model_validate(
        {
            'field1': 'valid',
            'field2': 'invalid',
            'field3': [1.0],
            'recorded_at': test_datetime,
        },
        context=context,
    )

    # recorded_at should be preserved
    assert record.recorded_at == test_datetime

    # Other fields behave as expected
    assert record.field1 == 'valid'
    assert record.field2 is None
    assert record.field3 == [1.0]


def test_log_failed_validation_empty_string_vs_none():
    """Test that None is used for fallback, not empty string."""
    context = MockContext()

    record = DummyRecord.model_validate(
        {'field1': 'valid', 'field2': 'invalid', 'field3': [1.0]},
        context=context,
    )

    # field2 should be None, not 0 or empty string
    assert record.field2 is None
    assert record.field2 != 0
    assert record.field2 != ''  # noqa: PLC1901


# endregion Test _log_failed_validation
