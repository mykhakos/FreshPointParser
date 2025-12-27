from typing import Union

import pytest

from freshpointparser.exceptions import FreshPointParserAttributeError
from freshpointparser.models._base import BasePage
from freshpointparser.parsers._base import BasePageHTMLParser, ParseContext


class TestPageHTMLParser(BasePageHTMLParser[BasePage]):
    def _parse_page_content(
        self, page_content: Union[str, bytes], context: ParseContext
    ) -> BasePage:
        return BasePage()


def test_parse_empty_data():
    parser = TestPageHTMLParser()
    parser.parse('<html></html>')
    assert parser.parsed_page.recorded_at == parser.metadata.last_parsed_at


def test_parse_datetime_access_before_parse():
    parser = TestPageHTMLParser()
    with pytest.raises(FreshPointParserAttributeError):
        _ = parser.parsed_page


def test_parse_caching():
    parser = TestPageHTMLParser()

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
    parser = TestPageHTMLParser()

    # first call should parse and cache
    parser.parse('<html></html>')
    assert parser.metadata.was_last_parse_from_cache is False
    ts_first = parser.metadata.last_parsed_at

    # force re-parse
    parser.parse('<html></html>', force=True)
    assert parser.metadata.was_last_parse_from_cache is False
    assert parser.metadata.last_parsed_at > ts_first
