import os

import pytest
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from freshpointparser import parse_location_page
from freshpointparser.exceptions import (
    FreshPointParserValueError,
)
from freshpointparser.models import Location, LocationPage
from freshpointparser.parsers import LocationPageHTMLParser


class ProductPageMeta(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    location_count: int
    location_count_active: int
    location_count_suspended: int


@pytest.fixture(scope='session')
def location_page_html_content():
    path = os.path.join(os.path.dirname(__file__), 'location_page.html')
    with open(path, encoding='utf-8') as file:
        page_html_content = file.read()
    return page_html_content


@pytest.fixture(scope='session')
def location_page_json_content():
    path = os.path.join(os.path.dirname(__file__), 'location_page.json')
    with open(path, encoding='utf-8') as file:
        page_json_content = file.read()
    return page_json_content


@pytest.fixture(scope='session')
def location_page_metadata_json_content():
    path = os.path.join(os.path.dirname(__file__), 'location_page_meta.json')
    with open(path, encoding='utf-8') as file:
        page_metadata_json_content = file.read()
    return page_metadata_json_content


@pytest.fixture(scope='session')
def location_page_html_parse_result(location_page_html_content):
    parser = LocationPageHTMLParser()
    return parser.parse(location_page_html_content)


@pytest.fixture(scope='session')
def location_page(location_page_json_content):
    return LocationPage.model_validate_json(location_page_json_content)


@pytest.fixture(scope='session')
def location_page_expected_meta(location_page_metadata_json_content):
    return ProductPageMeta.model_validate_json(location_page_metadata_json_content)


# region Parser parsing


def test_load_json_errors():
    parser = LocationPageHTMLParser()
    # pattern not found
    with pytest.raises(FreshPointParserValueError):
        parser._load_json('<html></html>')

    # invalid JSON in the matched text
    faulty = 'devices = "[{]" ;'
    with pytest.raises(FreshPointParserValueError):
        parser._load_json(faulty)

    # data not a list
    not_list = 'devices = "{}";'
    with pytest.raises(FreshPointParserValueError):
        parser._load_json(not_list)


def test_load_json_success_with_string():
    """Test _load_json successfully extracts and parses JSON from string HTML."""
    parser = LocationPageHTMLParser()
    html_content = 'devices = "[{\\"prop\\":{},\\"location\\":{}}]";'
    result = parser._load_json(html_content)
    assert isinstance(result, list)
    assert len(result) == 1
    assert 'prop' in result[0]
    assert 'location' in result[0]


def test_load_json_success_with_bytes():
    """Test _load_json successfully extracts and parses JSON from bytes HTML."""
    parser = LocationPageHTMLParser()
    html_content = b'devices = "[{\\"prop\\":{},\\"location\\":{}}]";'
    result = parser._load_json(html_content)
    assert isinstance(result, list)
    assert len(result) == 1


def test_load_json_empty_list():
    """Test _load_json with empty list."""
    parser = LocationPageHTMLParser()
    html_content = 'devices = "[]";'
    result = parser._load_json(html_content)
    assert isinstance(result, list)
    assert len(result) == 0


def test_load_json_multiple_items():
    """Test _load_json with multiple location items."""
    parser = LocationPageHTMLParser()
    html_content = 'devices = "[{\\"prop\\":{},\\"location\\":{}},{\\"prop\\":{},\\"location\\":{}}]";'
    result = parser._load_json(html_content)
    assert isinstance(result, list)
    assert len(result) == 2


def test_load_json_with_whitespace_variations():
    """Test _load_json with various whitespace patterns around the equals sign."""
    parser = LocationPageHTMLParser()
    test_cases = [
        'devices="[]";',  # no spaces
        'devices   =   "[]";',  # extra spaces around =
        'devices\t=\t"[]";',  # tabs around =
        'devices\n=\n"[]";',  # newlines around =
    ]
    for html_content in test_cases:
        result = parser._load_json(html_content)
        assert isinstance(result, list)


def test_load_json_with_complex_data():
    """Test _load_json with realistic complex location data."""
    parser = LocationPageHTMLParser()
    html_content = """devices = "[{\\"prop\\":{\\"username\\":\\"Test\\",\\"address\\":\\"123 St\\",\\"lat\\":50.0,\\"lon\\":14.0,\\"discount\\":0.2,\\"active\\":true,\\"suspended\\":false},\\"location\\":{}}]";"""
    result = parser._load_json(html_content)
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]['prop']['username'] == 'Test'
    assert result[0]['prop']['lat'] == 50.0


def test_parse_location_success():
    """Test _parse_location successfully parses valid location data."""
    parser = LocationPageHTMLParser()
    location_data = {
        'prop': {
            'username': 'Test Location',
            'address': '123 Main St',
            'lat': 50.0,
            'lon': 14.0,
            'discount': 0.2,
            'active': True,
            'suspended': False,
        },
        'location': {},
    }
    location = parser._parse_location(location_data)
    assert isinstance(location, Location)
    assert location.name == 'Test Location'
    assert location.address == '123 Main St'
    assert location.latitude == 50.0
    assert location.longitude == 14.0
    assert location.discount_rate == 0.2
    assert location.is_active is True
    assert location.is_suspended is False


def test_parse_location_minimal_data():
    """Test _parse_location with minimal required data."""
    parser = LocationPageHTMLParser()
    location_data = {
        'prop': {},
        'location': {},
    }
    location = parser._parse_location(location_data)
    assert isinstance(location, Location)


def test_parse_location_missing_prop_key():
    """Test _parse_location raises error when 'prop' key is missing."""
    parser = LocationPageHTMLParser()
    location_data = {'location': {}}
    with pytest.raises(FreshPointParserValueError) as exc_info:
        parser._parse_location(location_data)
    assert "Missing 'prop' key" in str(exc_info.value)


def test_parse_location_with_alias_fields():
    """Test _parse_location handles field aliases correctly."""
    parser = LocationPageHTMLParser()
    location_data = {
        'prop': {
            'username': 'Location',  # alias for name
            'lat': 50.5,  # alias for latitude
            'lon': 14.5,  # alias for longitude
            'discount': 0.15,  # alias for discount_rate
            'active': False,  # alias for is_active
            'suspended': True,  # alias for is_suspended
        },
        'location': {},
    }
    location = parser._parse_location(location_data)
    assert location.name == 'Location'
    assert location.latitude == 50.5
    assert location.longitude == 14.5
    assert location.discount_rate == 0.15
    assert location.is_active is False
    assert location.is_suspended is True


def test_parse_locations_success_multiple():
    """Test _parse_locations with multiple valid locations."""
    parser = LocationPageHTMLParser()
    html_content = 'devices = "[{\\"prop\\":{\\"username\\":\\"Location 1\\"},\\"location\\":{}},{\\"prop\\":{\\"username\\":\\"Location 2\\"},\\"location\\":{}},{\\"prop\\":{\\"username\\":\\"Location 3\\"},\\"location\\":{}}]";'
    locations = parser._parse_locations(html_content)
    assert isinstance(locations, list)
    assert len(locations) == 3
    assert all(isinstance(loc, Location) for loc in locations)
    assert locations[0].name == 'Location 1'
    assert locations[1].name == 'Location 2'
    assert locations[2].name == 'Location 3'


def test_parse_locations_empty_list():
    """Test _parse_locations with empty list."""
    parser = LocationPageHTMLParser()
    html_content = 'devices = "[]";'
    locations = parser._parse_locations(html_content)
    assert isinstance(locations, list)
    assert len(locations) == 0


def test_parse_locations_partial_failure():
    """Test _parse_locations skips invalid items but keeps valid ones."""
    parser = LocationPageHTMLParser()
    html_content = 'devices = "[{\\"prop\\":{\\"username\\":\\"Valid 1\\"},\\"location\\":{}},{\\"location\\":{}},{\\"prop\\":{\\"username\\":\\"Valid 2\\"},\\"location\\":{}}]";'
    locations = parser._parse_locations(html_content)
    assert len(locations) == 2
    assert locations[0].name == 'Valid 1'
    assert locations[1].name == 'Valid 2'
    # Error should be collected in context
    assert len(parser._context.errors) == 1
    assert isinstance(parser._context.errors[0], FreshPointParserValueError)


def test_parse_locations_all_invalid():
    """Test _parse_locations when all items are invalid."""
    parser = LocationPageHTMLParser()
    html_content = 'devices = "[{\\"location\\":{}},{\\"location\\":{}}]";'
    locations = parser._parse_locations(html_content)
    assert len(locations) == 0
    assert len(parser._context.errors) == 2


def test_parse_page_content_success():
    """Test _parse_page_content with valid HTML content."""
    parser = LocationPageHTMLParser()
    html_content = (
        'devices = "[{\\"prop\\":{\\"username\\":\\"Test\\"},\\"location\\":{}}]";'
    )
    page = parser._parse_page_content(html_content)
    assert isinstance(page, LocationPage)
    assert len(page.items) == 1
    assert page.items[0].name == 'Test'
    assert page.recorded_at == parser._context.parsed_at


def test_parse_page_content_with_load_json_error():
    """Test _parse_page_content when _load_json fails."""
    parser = LocationPageHTMLParser()
    html_content = '<html>no devices variable</html>'
    page = parser._parse_page_content(html_content)
    # Should still return a LocationPage, but empty
    assert isinstance(page, LocationPage)
    assert len(page.items) == 0
    # Error should be collected
    assert len(parser._context.errors) > 0


def test_parse_page_content_with_parse_locations_error():
    """Test _parse_page_content when locations parsing fails."""
    parser = LocationPageHTMLParser()
    # Valid JSON structure but all items invalid
    html_content = 'devices = "[{\\"location\\":{}},{\\"location\\":{}}]";'
    page = parser._parse_page_content(html_content)
    assert isinstance(page, LocationPage)
    assert len(page.items) == 0
    # Errors should be collected
    assert len(parser._context.errors) > 0


def test_parse_page_content_empty_locations_list():
    """Test _parse_page_content with empty locations list."""
    parser = LocationPageHTMLParser()
    html_content = 'devices = "[]";'
    page = parser._parse_page_content(html_content)
    assert isinstance(page, LocationPage)
    assert len(page.items) == 0
    assert len(parser._context.errors) == 0


def test_regex_pattern_matching_variations():
    """Test that regex patterns match various whitespace variations."""
    parser = LocationPageHTMLParser()
    test_cases = [
        'devices="[]";',  # no spaces
        'devices = "[]";',  # standard spacing
        'devices  =  "[]";',  # extra spaces around =
        'devices\t=\t"[]";',  # tabs around =
        'var x; devices = "[]";',  # with preceding code
        '<script>devices = "[]";</script>',  # in script tag
    ]
    for html_content in test_cases:
        result = parser._load_json(html_content)
        assert isinstance(result, list), f'Failed for: {html_content}'


def test_parse_with_special_characters_in_data():
    """Test parsing with special characters in location data."""
    parser = LocationPageHTMLParser()
    html_content = """devices = "[{\\"prop\\":{\\"username\\":\\"Café Ústí\\",\\"address\\":\\"Nám. 123\\"},\\"location\\":{}}]";"""
    result = parser.parse(html_content)
    assert not result.metadata.errors
    assert isinstance(result.page, LocationPage)
    assert len(result.page.items) == 1
    assert result.page.items[0].name and 'Café' in result.page.items[0].name


def test_parse_errors_collected_in_metadata():
    """Test that parse errors are collected in parser metadata."""
    parser = LocationPageHTMLParser()
    # HTML with some invalid location items
    html_content = 'devices = "[{\\"prop\\":{\\"username\\":\\"Valid\\"},\\"location\\":{}},{\\"location\\":{}}]";'
    result = parser.parse(html_content)
    # Check that errors were collected
    assert len(result.metadata.errors) > 0
    assert isinstance(result.metadata.errors[0], FreshPointParserValueError)


def test_parse_location_page_function(location_page_html_content):
    result = parse_location_page(location_page_html_content)
    assert isinstance(result.page, LocationPage)
    assert result.page.items  # some data parsed
    assert result.metadata.errors == []  # no errors


def test_parse_bytes_content():
    """Test parsing HTML content as bytes."""
    parser = LocationPageHTMLParser()
    html_content = (
        b'devices = "[{\\"prop\\":{\\"username\\":\\"Test\\"},\\"location\\":{}}]";'
    )
    result = parser.parse(html_content)
    assert isinstance(result.page, LocationPage)
    assert len(result.page.items) == 1
    assert result.page.items[0].name == 'Test'
    assert result.metadata.errors == []


def test_safe_parse_integration():
    """Test that _safe_parse correctly handles errors in location parsing."""
    parser = LocationPageHTMLParser()

    # Create HTML with one valid and one invalid location
    html_content = 'devices = "[{\\"prop\\":{\\"username\\":\\"Good\\"},\\"location\\":{}},{\\"no_prop_key\\":{}}]";'

    locations = parser._parse_locations(html_content)

    # Should have one valid location
    assert len(locations) == 1
    assert locations[0].name == 'Good'

    # Should have one error
    assert len(parser._context.errors) == 1


# endregion Parser parsing

# region Parser properties


def test_validate_parsed_location_count(
    location_page_html_parse_result, location_page_expected_meta
):
    assert (
        len(location_page_html_parse_result.page.items)
        == location_page_expected_meta.location_count
    )


def test_validate_parsed_location_count_active(
    location_page_html_parse_result, location_page_expected_meta
):
    assert (
        len([
            location
            for location in location_page_html_parse_result.page.items
            if location.is_active
        ])
        == location_page_expected_meta.location_count_active
    )


def test_validate_parsed_location_count_suspended(
    location_page_html_parse_result, location_page_expected_meta
):
    assert (
        len([
            location
            for location in location_page_html_parse_result.page.items
            if location.is_suspended
        ])
        == location_page_expected_meta.location_count_suspended
    )


def test_validate_generated_location_page(
    location_page_html_parse_result, location_page
):
    parser_page = location_page_html_parse_result.page
    assert not parser_page.item_diff(location_page, exclude={'recorded_at'})


# endregion Parser properties


# region Parse data from internet


@pytest.mark.is_parser_up_to_date
def test_parse_data_from_internet():
    """Fetch location page data from the internet and validate it.

    This test aims to validate the parser's ability to parse actual fresh data.
    """
    import httpx  # noqa: PLC0415

    from freshpointparser import (  # noqa: PLC0415
        get_location_page_url,
        parse_location_page,
    )

    url = get_location_page_url()
    response = httpx.get(url)
    response.raise_for_status()
    page = parse_location_page(response.text)
    assert page != LocationPage()  # not empty


# endregion Parse data from internet
