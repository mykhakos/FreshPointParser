import pytest

from freshpointparser._utils import normalize_text, validate_id


@pytest.mark.parametrize(
    'text, expected',
    [
        ('', ''),
        (None, ''),
        ('foo', 'foo'),
        ('Foo', 'foo'),
        ('FoO', 'foo'),
        ('FOO', 'foo'),
        ('   baR   ', 'bar'),
        (12345, '12345'),
        (1.23, '1.23'),
        ('mě', 'me'),
        ('Hovězí ', 'hovezi'),
        ('  v   zakysané   smetaně  ', 'v   zakysane   smetane'),
        ('Bramborová placka se salámem', 'bramborova placka se salamem'),
    ],
)
def test_normalize_text(text, expected):
    assert normalize_text(text) == expected


@pytest.mark.parametrize(
    'input_value, expected_output',
    [
        ('123', 123),
        (0, 0),
        (456, 456),
        ('0', 0),
        ('999999999999999999999', 999999999999999999999),
        (999999999999999999999, 999999999999999999999),
    ],
    ids=[
        'valid numeric string',
        'zero',
        'valid positive integer',
        'numeric string for zero',
        'large numeric string',
        'large integer',
    ],
)
def test_validate_id(input_value, expected_output):
    assert validate_id(input_value) == expected_output


@pytest.mark.parametrize(
    'input_value, expected_exception, exception_message',
    [
        # Negative cases
        (
            '-123',
            ValueError,
            'ID must be a numeric string representing a non-negative integer (got "-123").',
        ),
        (-1, ValueError, 'ID must be a non-negative integer.'),
        # Invalid string formats
        (
            'abc',
            ValueError,
            'ID must be a numeric string representing a non-negative integer (got "abc").',
        ),
        (
            '12.34',
            ValueError,
            'ID must be a numeric string representing a non-negative integer (got "12.34").',
        ),
        # Unsupported types
        ([], TypeError, "unhashable type: 'list'"),  # due to @lru_cache
        ({}, TypeError, "unhashable type: 'dict'"),  # due to @lru_cache
        (None, TypeError, "ID must be an integer (got <class 'NoneType'>)."),
    ],
    ids=[
        'negative numeric string',
        'negative integer',
        'non-numeric string',
        'float string',
        'list',
        'dict',
        'None',
    ],
)
def test_validate_id_invalid(
    input_value, expected_exception, exception_message
):
    with pytest.raises(expected_exception) as excinfo:
        validate_id(input_value)
    assert str(excinfo.value) == exception_message
