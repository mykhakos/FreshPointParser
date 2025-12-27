import pytest

from freshpointparser._utils import hash_sha1, normalize_text


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
    'content, expected_hex',
    [
        ('hello', 'aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d'),
        (b'hello', 'aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d'),
        ('', 'da39a3ee5e6b4b0d3255bfef95601890afd80709'),
        (b'', 'da39a3ee5e6b4b0d3255bfef95601890afd80709'),
        (
            'The quick brown fox jumps over the lazy dog',
            '2fd4e1c67a2d28fced849ee1bb76e7391b93eb12',
        ),
        (
            b'The quick brown fox jumps over the lazy dog',
            '2fd4e1c67a2d28fced849ee1bb76e7391b93eb12',
        ),
    ],
)
def test_hash_sha1(content, expected_hex):
    result = hash_sha1(content)
    assert result.hex() == expected_hex
