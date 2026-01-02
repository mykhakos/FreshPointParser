import pytest

from freshpointparser._utils import normalize_text


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
