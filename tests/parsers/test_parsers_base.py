from datetime import datetime
from typing import Union

import pytest

from freshpointparser.exceptions import (
    FreshPointParserValueError,
)
from freshpointparser.models._base import BasePage
from freshpointparser.parsers._base import BasePageHTMLParser


class DummyPageHTMLParser(BasePageHTMLParser[BasePage]):
    def _parse_page_content(self, page_content: Union[str, bytes]) -> BasePage:
        data = {'recorded_at': self._context.parsed_at}
        return BasePage.model_validate(data, context=self._context)


class DummyPageHTMLParserWithErrors(BasePageHTMLParser[BasePage]):
    """Parser that collects errors during parsing."""

    def _parse_page_content(self, page_content: Union[str, bytes]) -> BasePage:
        if isinstance(page_content, str):
            page_content = page_content.encode('utf-8', errors='ignore')
        if b'error' in page_content:
            self._context.register_error(
                FreshPointParserValueError('Simulated parsing error')
            )
        data = {'recorded_at': datetime.now()}
        return BasePage.model_validate(data, context=self._context)


def test_parse_empty_data():
    parser = DummyPageHTMLParser()
    result = parser.parse('<html></html>')
    assert result.page.recorded_at == result.metadata.parsed_at
    assert not result.metadata.errors


def test_parse_caching():
    parser = DummyPageHTMLParser()

    # first call should parse and cache
    result_1 = parser.parse('<html></html>')
    assert result_1.metadata.from_cache is False

    # same input -> no parsing
    result_2 = parser.parse('<html></html>')
    assert result_2.metadata.from_cache is True
    assert result_2.metadata.parsed_at == result_1.metadata.parsed_at


def test_parse_force():
    parser = DummyPageHTMLParser()

    # first call should parse and cache
    result_1 = parser.parse('<html></html>')
    assert result_1.metadata.from_cache is False

    # force re-parse
    result_3 = parser.parse('<html></html>', force=True)
    assert result_3.metadata.from_cache is False
    assert result_3.metadata.parsed_at > result_1.metadata.parsed_at


def test_parse_with_bytes_content():
    """Test parsing with bytes instead of string."""
    parser = DummyPageHTMLParser()
    content_bytes = b'<html><body>Test</body></html>'
    result = parser.parse(content_bytes)
    assert result is not None
    assert result.metadata.content_digest is not None


def test_parse_with_string_content():
    """Test parsing with string content."""
    parser = DummyPageHTMLParser()
    content_str = '<html><body>Test</body></html>'
    result = parser.parse(content_str)
    assert result is not None
    assert result.metadata.content_digest is not None


def test_parse_content_digest_changes():
    """Test that content_digest changes when content changes."""
    parser = DummyPageHTMLParser()

    result_1 = parser.parse('<html>v1</html>')
    digest1 = result_1.metadata.content_digest

    result_2 = parser.parse('<html>v2</html>')
    digest2 = result_2.metadata.content_digest

    assert digest1 != digest2


def test_parse_content_digest_same_for_identical_content():
    """Test that content_digest remains the same for identical content."""
    parser = DummyPageHTMLParser()

    result_1 = parser.parse('<html>test</html>')
    digest1 = result_1.metadata.content_digest

    result_2 = parser.parse('<html>test</html>')

    digest2 = result_2.metadata.content_digest
    assert digest1 == digest2


def test_parse_returns_deep_copy():
    """Test that parse returns a deep copy of the parsed page."""
    parser = DummyPageHTMLParser()
    page1 = parser.parse('<html></html>').page
    page2 = parser.parse('<html></html>').page

    # Should be equal but not the same object
    assert page1 == page2
    assert page1 is not page2


def test_parse_empty_content():
    """Test parsing with empty content."""
    parser = DummyPageHTMLParser()
    # Need to force parse since empty string hash matches initial empty bytes hash
    result = parser.parse('')
    assert result.page is not None


def test_parse_special_characters():
    """Test parsing content with special characters."""
    parser = DummyPageHTMLParser()
    content = '<html>Special: äöü ñ 中文 🎉</html>'
    result = parser.parse(content)
    assert result.page is not None


def test_parse_with_unicode_bytes():
    """Test parsing with unicode encoded as bytes."""
    parser = DummyPageHTMLParser()
    content = '<html>Unicode: 中文</html>'.encode()
    result = parser.parse(content)
    assert result.page is not None


def test_parse_whitespace_content():
    """Test parsing with various whitespace content."""
    parser = DummyPageHTMLParser()

    contents = [
        ' ',
        '\n',
        '\t',
        '   \n\t   ',
        '<html>  \n\t  </html>',
    ]

    for content in contents:
        result = parser.parse(content)
        assert result.page is not None


def test_parse_errors_collected_in_metadata():
    """Test that parsing errors are collected in metadata."""
    parser = DummyPageHTMLParserWithErrors()
    result = parser.parse('<html>error here</html>')

    assert len(result.metadata.errors) == 1
    assert isinstance(result.metadata.errors[0], FreshPointParserValueError)


def test_parse_errors_cleared_on_successful_parse():
    """Test that parse errors are replaced when parsing new content."""
    parser = DummyPageHTMLParserWithErrors()

    # First parse with errors (contains 'error' keyword)
    result = parser.parse('<html>error here</html>')
    assert len(result.metadata.errors) == 1
    first_error = result.metadata.errors[0]

    # Second parse without errors - content doesn't contain 'error'
    result = parser.parse('<html>success</html>')
    assert len(result.metadata.errors) == 0

    # Third parse with errors again - should have new error
    result = parser.parse('<html>another error</html>')
    assert len(result.metadata.errors) == 1
    # Verify it's a different error instance
    assert result.metadata.errors[0] is not first_error


def test_parse_multiple_sequential_different_content():
    """Test multiple sequential parses with different content."""
    parser = DummyPageHTMLParser()

    contents = ['<html>v1</html>', '<html>v2</html>', '<html>v3</html>']
    for content in contents:
        result = parser.parse(content)
        assert result.page is not None
        assert result.metadata.from_cache is False


def test_safe_parse_method():
    """Test the _safe_parse static method functionality."""

    # Test successful parsing
    def success_func(value: int) -> int:
        return value * 2

    parser = DummyPageHTMLParser()
    result = parser._safe_parse(success_func, value=5)
    assert result == 10
    assert len(parser._context.errors) == 0

    # Test with FreshPointParserError
    def error_func() -> None:
        raise FreshPointParserValueError('Test error')

    parser = DummyPageHTMLParser()
    result = parser._safe_parse(error_func)
    assert result is None
    assert len(parser._context.errors) == 1
    assert isinstance(parser._context.errors[0], FreshPointParserValueError)


def test_safe_parse_non_freshpoint_error_propagates():
    """Test that non-FreshPointParser errors are not caught by _safe_parse."""

    def error_func() -> None:
        raise ValueError('Regular ValueError')

    with pytest.raises(ValueError):
        DummyPageHTMLParser()._safe_parse(error_func)


def test_parse_alternating_content():
    """Test parsing with alternating content to verify cache behavior."""
    parser = DummyPageHTMLParser()
    content_a = '<html>A</html>'
    content_b = '<html>B</html>'

    # Parse A
    result = parser.parse(content_a)
    assert result.metadata.from_cache is False

    # Parse A again (cache hit)
    result = parser.parse(content_a)
    assert result.metadata.from_cache is True

    # Parse B (cache miss)
    result = parser.parse(content_b)
    assert result.metadata.from_cache is False

    # Parse B again (cache hit)
    result = parser.parse(content_b)
    assert result.metadata.from_cache is True

    # Parse A again (cache miss, content changed back)
    result = parser.parse(content_a)
    assert result.metadata.from_cache is False
