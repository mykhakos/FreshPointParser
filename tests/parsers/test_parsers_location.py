import os

import pytest
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from freshpointparser import parse_location_page
from freshpointparser.models import LocationPage
from freshpointparser.parsers import LocationPageHTMLParser


class ProductPageMeta(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    location_count: int
    location_count_active: int
    location_count_suspended: int


@pytest.fixture(scope='module')
def location_page_html_text():
    path = os.path.join(os.path.dirname(__file__), 'location_page.html')
    with open(path, encoding='utf-8') as file:
        page_html_text = file.read()
    return page_html_text


@pytest.fixture(scope='module')
def location_page_html_parser_persistent(location_page_html_text):
    parser = LocationPageHTMLParser()
    parser.parse(location_page_html_text)
    return parser


@pytest.fixture(scope='function')
def location_page_html_parser_new(location_page_html_text):
    parser = LocationPageHTMLParser()
    parser.parse(location_page_html_text)
    return parser


@pytest.fixture(scope='module')
def location_page():
    path = os.path.join(os.path.dirname(__file__), 'location_page.json')
    with open(path, encoding='utf-8') as file:
        page = file.read()
    return LocationPage.model_validate_json(page)


@pytest.fixture(scope='module')
def location_page_expected_meta():
    path = os.path.join(os.path.dirname(__file__), 'location_page_meta.json')
    with open(path, encoding='utf-8') as file:
        page_meta = file.read()
    return ProductPageMeta.model_validate_json(page_meta)


# region Empty parser


def test_parse_empty_data():
    parser = LocationPageHTMLParser()
    location_id = 2
    location_name = 'Partners'
    assert parser.locations == []
    assert parser.page == LocationPage(recorded_at=parser.page.recorded_at)
    assert parser.find_location_by_id(location_id) is None
    assert parser.find_location_by_name(location_name) is None
    assert parser.find_locations_by_name(location_name) == []


# endregion Empty parser

# region Parser parsing


def test_parse_force_and_caching(location_page_html_text):
    parser = LocationPageHTMLParser()

    # first call should parse and cache
    assert parser.parse(location_page_html_text) is True
    ts_first = parser._parse_datetime

    # same input -> no parsing
    assert parser.parse(location_page_html_text) is False
    assert parser._parse_datetime == ts_first

    # force re-parse
    assert parser.parse(location_page_html_text, force=True) is True
    assert parser._parse_datetime > ts_first


def test_load_json_errors():
    parser = LocationPageHTMLParser()
    # pattern not found
    with pytest.raises(ValueError):
        parser._load_json('<html></html>')

    # invalid JSON in the matched text
    faulty = 'devices = "[{]" ;'
    with pytest.raises(ValueError):
        parser._load_json(faulty)

    # data not a list
    not_list = 'devices = "{}";'
    with pytest.raises(ValueError):
        parser._load_json(not_list)


def test_parse_location_page_function(location_page_html_text):
    page = parse_location_page(location_page_html_text)
    assert isinstance(page, LocationPage)
    assert page.items  # some data parsed


# endregion Parser parsing

# region Parser properties


def test_validate_parsed_locations(
    location_page_html_parser_persistent, location_page
):
    # assert each location in the parser is in the reference
    location_ids = set()
    for location in location_page_html_parser_persistent.locations:
        assert location.id_ in location_page.items
        location_reference = location_page.items[location.id_]
        assert not location.diff(location_reference)
        location_ids.add(location.id_)
    # assert each location in the reference is in the parser
    assert location_ids == set(location_page.items.keys())


def test_validate_parsed_location_count(
    location_page_html_parser_persistent, location_page_expected_meta
):
    assert (
        len(location_page_html_parser_persistent.locations)
        == location_page_expected_meta.location_count
    )


def test_validate_parsed_location_count_active(
    location_page_html_parser_persistent, location_page_expected_meta
):
    assert (
        len([
            location
            for location in location_page_html_parser_persistent.locations
            if location.is_active
        ])
        == location_page_expected_meta.location_count_active
    )


def test_validate_parsed_location_count_suspended(
    location_page_html_parser_persistent, location_page_expected_meta
):
    assert (
        len([
            location
            for location in location_page_html_parser_persistent.locations
            if location.is_suspended
        ])
        == location_page_expected_meta.location_count_suspended
    )


def test_validate_generated_location_page(
    location_page_html_parser_persistent, location_page
):
    parser_page = location_page_html_parser_persistent.page
    assert not parser_page.item_diff(location_page)


# endregion Parser properties


# region Find by ID


def test_find_location_by_id_int_exists(
    location_page_html_parser_new, location_page
):
    parser = location_page_html_parser_new
    for location_id in location_page.items:
        assert parser.find_location_by_id(location_id) is not None
        assert parser.find_location_by_id(location_id).id_ == location_id


def test_find_location_by_id_str_exists(
    location_page_html_parser_new, location_page
):
    parser = location_page_html_parser_new
    for location_id in location_page.items:
        assert parser.find_location_by_id(str(location_id)) is not None
        assert parser.find_location_by_id(str(location_id)).id_ == location_id


@pytest.mark.parametrize('location_id', [0, 999999])
def test_find_location_by_id_not_found(
    location_page_html_parser_new, location_id
):
    parser = location_page_html_parser_new
    assert parser.find_location_by_id(location_id) is None


@pytest.mark.parametrize('location_id', [-1, '-1', '13.5', '1480a', 'id'])
def test_find_location_by_id_invalid_value(
    location_page_html_parser_new, location_id
):
    parser = location_page_html_parser_new
    with pytest.raises(ValueError):
        assert parser.find_location_by_id(location_id) is None


@pytest.mark.parametrize('location_id', [13.5, None, {}])
def test_find_location_by_id_invalid_type(
    location_page_html_parser_new, location_id
):
    parser = location_page_html_parser_new
    with pytest.raises(TypeError):
        assert parser.find_location_by_id(location_id) is None


# endregion Find by ID


# region Find by name


def test_find_location_by_name_exists_full_match(
    location_page_html_parser_new, location_page
):
    parser = location_page_html_parser_new
    for location in location_page.items.values():
        assert (
            parser.find_location_by_name(location.name, partial_match=False)
            is not None
        )
        assert (
            parser.find_location_by_name(
                location.name, partial_match=False
            ).name
            == location.name
        )
        locations = parser.find_locations_by_name(
            location.name, partial_match=False
        )
        # assert len(locations) == 1  # name may not be unique, assertion removed
        assert locations[0].name == location.name


def test_find_location_by_name_exists_partial_match(
    location_page_html_parser_new, location_page
):
    parser = location_page_html_parser_new
    location_name = 'cpi'
    if any(
        location.name_lowercase_ascii == location_name
        for location in location_page.items.values()
    ):
        raise RuntimeError(
            f'Invalid test setup: location with name "{location_name}" exists'
        )
    if not any(
        location_name in location.name_lowercase_ascii
        for location in location_page.items.values()
    ):
        raise RuntimeError(
            f'Invalid test setup: no location contains "{location_name}" in its name'
        )
    assert (
        parser.find_location_by_name(location_name, partial_match=True)
        is not None
    )
    assert (
        parser.find_location_by_name(location_name, partial_match=False) is None
    )
    assert (
        parser.find_locations_by_name(location_name, partial_match=True) != []
    )
    assert (
        parser.find_locations_by_name(location_name, partial_match=False) == []
    )


@pytest.mark.parametrize(
    'location_name',
    ['   cpi    May', 'alpwd,apwd,a'],
)
def test_find_location_by_name_not_found(
    location_page_html_parser_new, location_name
):
    parser = location_page_html_parser_new
    assert parser.find_location_by_name(location_name) is None
    assert parser.find_locations_by_name(location_name) == []
    assert (
        parser.find_location_by_name(location_name, partial_match=False) is None
    )
    assert (
        parser.find_locations_by_name(location_name, partial_match=False) == []
    )


@pytest.mark.parametrize(
    'location_name',
    [None, 1480, {}],
)
def test_find_location_by_name_invalid_type(
    location_page_html_parser_new, location_name
):
    parser = location_page_html_parser_new
    with pytest.raises(TypeError):
        parser.find_location_by_name(location_name)
        parser.find_locations_by_name(location_name)


# endregion Find by name

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
    page = parse_location_page(page_html=response.text)
    assert page != LocationPage()


# endregion Parse data from internet
