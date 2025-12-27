import time
from datetime import datetime
from typing import Union

import pytest

from freshpointparser.exceptions import (
    FreshPointParserAttributeError,
    FreshPointParserValueError,
)
from freshpointparser.models._base import BasePage
from freshpointparser.parsers._base import BasePageHTMLParser, ParseContext


class DummyPageHTMLParser(BasePageHTMLParser[BasePage]):
    def _parse_page_content(
        self, page_content: Union[str, bytes], context: ParseContext
    ) -> BasePage:
        data = self._new_base_record_data_from_context(context)
        return BasePage.model_validate(data, context=context)


class DummyPageHTMLParserWithErrors(BasePageHTMLParser[BasePage]):
    """Parser that collects errors during parsing."""

    def _parse_page_content(
        self, page_content: Union[str, bytes], context: ParseContext
    ) -> BasePage:
        if isinstance(page_content, str):
            page_content = page_content.encode('utf-8', errors='ignore')
        if b'error' in page_content:
            context.parse_errors.append(
                FreshPointParserValueError('Simulated parsing error')
            )
        data = self._new_base_record_data_from_context(context)
        return BasePage.model_validate(data, context=context)


def test_parse_empty_data():
    parser = DummyPageHTMLParser()
    parser.parse('<html></html>')
    assert parser.parsed_page.recorded_at == parser.metadata.last_parsed_at
    assert not parser.metadata.parse_errors


def test_parse_datetime_access_before_parse():
    parser = DummyPageHTMLParser()
    with pytest.raises(FreshPointParserAttributeError):
        _ = parser.parsed_page


def test_parse_caching():
    parser = DummyPageHTMLParser()

    # first call should parse and cache
    parser.parse('<html></html>')
    assert parser.metadata.was_last_parse_from_cache is False
    ts_first = parser.metadata.last_parsed_at

    # same input -> no parsing
    parser.parse('<html></html>')
    assert parser.metadata.was_last_parse_from_cache is True
    assert parser.metadata.last_parsed_at == ts_first
    assert parser.metadata.last_updated_at > ts_first


def test_parse_force():
    parser = DummyPageHTMLParser()

    # first call should parse and cache
    parser.parse('<html></html>')
    assert parser.metadata.was_last_parse_from_cache is False
    ts_first = parser.metadata.last_parsed_at

    # force re-parse
    parser.parse('<html></html>', force=True)
    assert parser.metadata.was_last_parse_from_cache is False
    assert parser.metadata.last_parsed_at > ts_first


def test_parse_with_bytes_content():
    """Test parsing with bytes instead of string."""
    parser = DummyPageHTMLParser()
    content_bytes = b'<html><body>Test</body></html>'
    parser.parse(content_bytes)
    assert parser.parsed_page is not None
    assert parser.metadata.content_digest is not None


def test_parse_with_string_content():
    """Test parsing with string content."""
    parser = DummyPageHTMLParser()
    content_str = '<html><body>Test</body></html>'
    parser.parse(content_str)
    assert parser.parsed_page is not None
    assert parser.metadata.content_digest is not None


def test_parse_content_digest_changes():
    """Test that content_digest changes when content changes."""
    parser = DummyPageHTMLParser()

    parser.parse('<html>v1</html>')
    digest1 = parser.metadata.content_digest

    parser.parse('<html>v2</html>')
    digest2 = parser.metadata.content_digest

    assert digest1 != digest2


def test_parse_content_digest_same_for_identical_content():
    """Test that content_digest remains the same for identical content."""
    parser = DummyPageHTMLParser()

    parser.parse('<html>test</html>')
    digest1 = parser.metadata.content_digest

    parser.parse('<html>test</html>')
    digest2 = parser.metadata.content_digest

    assert digest1 == digest2


def test_parse_returns_deep_copy():
    """Test that parse returns a deep copy of the parsed page."""
    parser = DummyPageHTMLParser()
    page1 = parser.parse('<html></html>')
    page2 = parser.parse('<html></html>')

    # Should be equal but not the same object
    assert page1 == page2
    assert page1 is not page2


def test_parsed_page_property_returns_new_instance():
    """Test that each access to parsed_page returns a new instance."""
    parser = DummyPageHTMLParser()
    parser.parse('<html></html>')

    page1 = parser.parsed_page
    page2 = parser.parsed_page

    assert page1 == page2
    assert page1 is not page2


def test_parse_empty_content():
    """Test parsing with empty content."""
    parser = DummyPageHTMLParser()
    # Need to force parse since empty string hash matches initial empty bytes hash
    result = parser.parse('', force=True)
    assert result is not None
    assert parser.parsed_page is not None


def test_parse_large_content():
    """Test parsing with large HTML content."""
    parser = DummyPageHTMLParser()
    large_content = '<html>' + 'x' * 100000 + '</html>'
    parser.parse(large_content)
    assert parser.parsed_page is not None


def test_parse_special_characters():
    """Test parsing content with special characters."""
    parser = DummyPageHTMLParser()
    content = '<html>Special: äöü ñ 中文 🎉</html>'
    parser.parse(content)
    assert parser.parsed_page is not None


def test_parse_errors_collected_in_metadata():
    """Test that parsing errors are collected in metadata."""
    parser = DummyPageHTMLParserWithErrors()
    parser.parse('<html>error here</html>')

    assert len(parser.metadata.parse_errors) == 1
    assert isinstance(parser.metadata.parse_errors[0], FreshPointParserValueError)


def test_parse_errors_cleared_on_successful_parse():
    """Test that parse errors are replaced when parsing new content."""
    parser = DummyPageHTMLParserWithErrors()

    # First parse with errors (contains 'error' keyword)
    parser.parse('<html>error here</html>')
    assert len(parser.metadata.parse_errors) == 1
    first_error = parser.metadata.parse_errors[0]

    # Second parse without errors - content doesn't contain 'error'
    parser.parse('<html>success</html>')
    assert len(parser.metadata.parse_errors) == 0

    # Third parse with errors again - should have new error
    parser.parse('<html>another error</html>')
    assert len(parser.metadata.parse_errors) == 1
    # Verify it's a different error instance
    assert parser.metadata.parse_errors[0] is not first_error


def test_parse_multiple_sequential_different_content():
    """Test multiple sequential parses with different content."""
    parser = DummyPageHTMLParser()

    contents = ['<html>v1</html>', '<html>v2</html>', '<html>v3</html>']
    for content in contents:
        parser.parse(content)
        assert parser.parsed_page is not None
        assert parser.metadata.was_last_parse_from_cache is False


def test_metadata_last_updated_at_updates_on_cache_hit():
    """Test that last_updated_at is updated even when using cache."""
    parser = DummyPageHTMLParser()

    parser.parse('<html></html>')
    updated_at_first = parser.metadata.last_updated_at

    time.sleep(0.01)  # Small delay to ensure timestamp difference

    parser.parse('<html></html>')
    updated_at_second = parser.metadata.last_updated_at

    assert updated_at_second > updated_at_first
    assert parser.metadata.was_last_parse_from_cache is True


def test_metadata_timestamps_order():
    """Test that metadata timestamps have correct ordering."""
    parser = DummyPageHTMLParser()
    parser.parse('<html></html>')

    metadata = parser.metadata
    assert metadata.last_parsed_at <= metadata.last_updated_at


def test_safe_parse_method():
    """Test the _safe_parse static method functionality."""
    context = ParseContext()

    # Test successful parsing
    def success_func(value: int) -> int:
        return value * 2

    result = DummyPageHTMLParser._safe_parse(success_func, context, value=5)
    assert result == 10
    assert len(context.parse_errors) == 0

    # Test with FreshPointParserError
    def error_func() -> None:
        raise FreshPointParserValueError('Test error')

    result = DummyPageHTMLParser._safe_parse(error_func, context)
    assert result is None
    assert len(context.parse_errors) == 1
    assert isinstance(context.parse_errors[0], FreshPointParserValueError)


def test_safe_parse_non_freshpoint_error_propagates():
    """Test that non-FreshPointParser errors are not caught by _safe_parse."""
    context = ParseContext()

    def error_func() -> None:
        raise ValueError('Regular ValueError')

    with pytest.raises(ValueError):
        DummyPageHTMLParser._safe_parse(error_func, context)


def test_metadata_initialization():
    """Test that parser initializes with correct metadata."""
    parser = DummyPageHTMLParser()
    metadata = parser.metadata

    assert metadata.content_digest is not None
    assert isinstance(metadata.last_updated_at, datetime)
    assert isinstance(metadata.last_parsed_at, datetime)
    assert metadata.was_last_parse_from_cache is False
    assert metadata.parse_errors == []


def test_parse_with_unicode_bytes():
    """Test parsing with unicode encoded as bytes."""
    parser = DummyPageHTMLParser()
    content = '<html>Unicode: 中文</html>'.encode()
    parser.parse(content)
    assert parser.parsed_page is not None


def test_parse_alternating_content():
    """Test parsing with alternating content to verify cache behavior."""
    parser = DummyPageHTMLParser()
    content_a = '<html>A</html>'
    content_b = '<html>B</html>'

    # Parse A
    parser.parse(content_a)
    assert parser.metadata.was_last_parse_from_cache is False

    # Parse A again (cache hit)
    parser.parse(content_a)
    assert parser.metadata.was_last_parse_from_cache is True

    # Parse B (cache miss)
    parser.parse(content_b)
    assert parser.metadata.was_last_parse_from_cache is False

    # Parse B again (cache hit)
    parser.parse(content_b)
    assert parser.metadata.was_last_parse_from_cache is True

    # Parse A again (cache miss, content changed back)
    parser.parse(content_a)
    assert parser.metadata.was_last_parse_from_cache is False


def test_new_base_record_data_from_context():
    """Test the _new_base_record_data_from_context static method."""
    context = ParseContext()
    data = DummyPageHTMLParser._new_base_record_data_from_context(context)

    assert 'recorded_at' in data
    assert isinstance(data['recorded_at'], datetime)
    assert data['recorded_at'] == context.parsed_at


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
        parser.parse(content)
        assert parser.parsed_page is not None
