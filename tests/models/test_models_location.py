from datetime import datetime
from types import MappingProxyType

import pytest
from pydantic import ValidationError

from freshpointparser import get_location_page_url
from freshpointparser.exceptions import FreshPointParserTypeError
from freshpointparser.models import Location, LocationPage

# region Location


@pytest.mark.parametrize(
    'location, expected_attrs',
    [
        (
            Location(),
            dict(
                id_=0,
                name='',
                address='',
                latitude=0.0,
                longitude=0.0,
                discount_rate=0.0,
                is_active=True,
                is_suspended=False,
            ),
        ),
        (
            Location(
                id_=1,
                name='Foo',
                address='Bar',
                latitude=1.23,
                longitude=4.56,
                discount_rate=0.5,
                is_active=False,
                is_suspended=True,
            ),
            dict(
                id_=1,
                name='Foo',
                address='Bar',
                latitude=1.23,
                longitude=4.56,
                discount_rate=0.5,
                is_active=False,
                is_suspended=True,
            ),
        ),
    ],
    ids=['default args', 'custom args'],
)
def test_location_init(location, expected_attrs):
    assert location.id_ == expected_attrs['id_']
    assert location.name == expected_attrs['name']
    assert location.address == expected_attrs['address']
    assert location.latitude == expected_attrs['latitude']
    assert location.longitude == expected_attrs['longitude']
    assert location.discount_rate == expected_attrs['discount_rate']
    assert location.is_active == expected_attrs['is_active']
    assert location.is_suspended == expected_attrs['is_suspended']


@pytest.mark.parametrize(
    'name, expected_name_lowercase_ascii',
    [
        ('', ''),
        ('Ušetřeno', 'usetreno'),
    ],
    ids=['empty name', 'regular name'],
)
def test_location_prop_name_lowercase_ascii(name, expected_name_lowercase_ascii):
    location = Location(name=name)
    assert location.name_lowercase_ascii == expected_name_lowercase_ascii


@pytest.mark.parametrize(
    'address, expected_address_lowercase_ascii',
    [
        ('', ''),
        ('Kozomín 501, 277 45', 'kozomin 501, 277 45'),
    ],
    ids=['empty address', 'regular address'],
)
def test_location_prop_address_lowercase_ascii(
    address, expected_address_lowercase_ascii
):
    location = Location(address=address)
    assert location.address_lowercase_ascii == expected_address_lowercase_ascii


@pytest.mark.parametrize(
    'latitude, longitude, expected_coordinates',
    [
        (0.0, 0.0, (0.0, 0.0)),
        (1.23, 4.56, (1.23, 4.56)),
    ],
    ids=['zero coordinates', 'regular coordinates'],
)
def test_location_prop_coordinates(latitude, longitude, expected_coordinates):
    location = Location(latitude=latitude, longitude=longitude)
    assert location.coordinates == expected_coordinates


# region Location - parsing_errors


@pytest.mark.parametrize(
    'location_data, expected_parsing_errors',
    [
        pytest.param(
            {},
            {},
            id='no errors - empty data',
        ),
        pytest.param(
            {'id_': 1, 'name': 'Test'},
            {},
            id='no errors - valid data',
        ),
        pytest.param(
            {'id_': 1, 'name': ValueError('Invalid name')},
            {'name': 'ValueError: Invalid name'},
            id='single parsing error',
        ),
        pytest.param(
            {
                'id_': 1,
                'name': ValueError('Invalid name'),
                'latitude': TypeError('Invalid latitude'),
            },
            {
                'name': 'ValueError: Invalid name',
                'latitude': 'TypeError: Invalid latitude',
            },
            id='multiple parsing errors',
        ),
        pytest.param(
            {
                'id_': 1,
                'discount_rate': AttributeError('Cannot parse discount'),
            },
            {'discount_rate': 'AttributeError: Cannot parse discount'},
            id='parsing error with valid fields',
        ),
    ],
)
def test_location_parsing_errors_initialization(location_data, expected_parsing_errors):
    """Test that parsing errors are correctly captured during initialization."""
    location = Location(**location_data)
    assert location.parsing_errors == expected_parsing_errors


def test_location_parsing_errors_field_is_frozen():
    """Test that parsing_errors field is frozen and cannot be modified."""
    location = Location()
    with pytest.raises(ValidationError, match='frozen_field'):
        location.parsing_errors = {}  # type: ignore[misc]


def test_location_parsing_errors_fields_not_set():
    """Test that fields with errors are not set on the model."""
    location = Location(
        id_=123,
        name=ValueError('Bad name'),  # type: ignore[arg-type]
        latitude=TypeError('Bad latitude'),  # type: ignore[arg-type]
    )
    # Fields with errors should use default values
    assert location.name == ''  # noqa: PLC1901
    assert location.latitude == 0.0
    # But ID should be set correctly
    assert location.id_ == 123
    # Errors should be captured
    assert 'name' in location.parsing_errors
    assert 'latitude' in location.parsing_errors


@pytest.mark.parametrize(
    'exception, expected_error_msg',
    [
        pytest.param(
            ValueError('Test error'),
            'ValueError: Test error',
            id='ValueError',
        ),
        pytest.param(
            TypeError('Type mismatch'),
            'TypeError: Type mismatch',
            id='TypeError',
        ),
        pytest.param(
            AttributeError('Missing attribute'),
            'AttributeError: Missing attribute',
            id='AttributeError',
        ),
        pytest.param(
            RuntimeError('Runtime issue'),
            'RuntimeError: Runtime issue',
            id='RuntimeError',
        ),
    ],
)
def test_location_parsing_errors_exception_types(exception, expected_error_msg):
    """Test that different exception types are correctly formatted."""
    location = Location(name=exception)  # type: ignore[arg-type]
    assert location.parsing_errors['name'] == expected_error_msg


def test_location_parsing_errors_serialization():
    """Test that parsing_errors are included in serialization."""
    location = Location(
        id_=1,
        name=ValueError('Bad name'),  # type: ignore[arg-type]
        address='Valid address',
    )
    data = location.model_dump()
    assert 'parsing_errors' in data
    assert data['parsing_errors'] == {'name': 'ValueError: Bad name'}
    assert data['address'] == 'Valid address'


def test_location_parsing_errors_with_explicit_field():
    """Test that parsing_errors are preserved when errors exist in fields."""
    location = Location(
        id_=1,
        name=ValueError('Name error'),  # type: ignore[arg-type]
        address='Valid address',
    )
    # The error should be captured
    assert 'name' in location.parsing_errors
    assert location.parsing_errors['name'] == 'ValueError: Name error'
    # Other fields should work normally
    assert location.address == 'Valid address'


# endregion Location - parsing_errors

# endregion Location

# region LocationPage


@pytest.mark.parametrize(
    'page, expected_attrs',
    [
        pytest.param(
            LocationPage(),
            {'items': {}},
            id='empty page',
        ),
        pytest.param(
            LocationPage(
                items={1: Location(id_=1, recorded_at=datetime(2025, 6, 1))},
            ),
            {'items': {1: Location(id_=1, recorded_at=datetime(2025, 6, 1))}},
            id='regular page',
        ),
    ],
)
def test_location_page_init(page, expected_attrs):
    for key, value in expected_attrs.items():
        assert getattr(page, key) == value


@pytest.mark.parametrize(
    'page',
    [
        pytest.param(
            LocationPage(),
            id='empty page',
        ),
        pytest.param(
            LocationPage(items={1: Location(id_=1)}),
            id='regular page',
        ),
    ],
)
def test_location_page_prop_url(page):
    assert page.url == get_location_page_url()


@pytest.fixture(scope='module')
def locations():
    return [
        Location(
            id_=0,
            name='AAC TECHNOLOGIES SOLUTIONS',
            address='Kozomín 501, 277 45',
            latitude=50.2467181,
            longitude=14.3676439,
            discount_rate=30,
            is_active=True,
            is_suspended=False,
        ),
        Location(
            id_=1,
            name='ABB',
            address='Vyskočilova 1561/4a, Praha Michle',
            latitude=50.0481331,
            longitude=14.4573994,
            discount_rate=20,
            is_active=False,
            is_suspended=False,
        ),
        Location(
            id_=2,
            name='ABS Jets',
            address='K letišti 549, Praha 6 - Ruzyně, Praha 614, 16100',
            latitude=50.0957250,
            longitude=14.2838994,
            discount_rate=0,
            is_active=True,
            is_suspended=False,
        ),
    ]


@pytest.fixture(scope='module')
def locations_page(locations):
    return LocationPage(items={loc.id_: loc for loc in locations})


@pytest.mark.parametrize(
    'constraint, expected_location_ids',
    [
        pytest.param({}, [0, 1, 2], id='dict constraint: empty'),
        pytest.param({'id_': 0}, [0], id='dict constraint: id_'),
        pytest.param({'name': 'ABB'}, [1], id='dict constraint: name'),
        pytest.param(
            {'address': 'Vyskočilova 1561/4a, Praha Michle'},
            [1],
            id='dict constraint: address',
        ),
        pytest.param(
            {'address_lowercase_ascii': 'kozomin 501, 277 45'},
            [0],
            id='dict constraint: address_lowercase_ascii',
        ),
        pytest.param(
            {'latitude': 50.0957250, 'longitude': 14.2838994},
            [2],
            id='dict constraint: latitude and longitude',
        ),
        pytest.param(
            {'discount_rate': 30, 'is_active': True, 'is_suspended': False},
            [0],
            id='dict constraint: discount_rate, is_active, is_suspended',
        ),
        pytest.param(
            {'coordinates': (50.0957250, 14.2838994)},
            [2],
            id='dict constraint: coordinates',
        ),
        pytest.param(
            MappingProxyType({'name_lowercase_ascii': 'abs jets'}),
            [2],
            id='MappingProxyType constraint: name_lowercase_ascii',
        ),
        pytest.param(lambda loc: loc, [0, 1, 2], id='lambda constraint: any location'),
        pytest.param(lambda loc: loc.id_ == 1, [1], id='lambda constraint: id_'),
        pytest.param(
            lambda loc: 'AB' in loc.name,
            [1, 2],
            id='lambda constraint: partial name',
        ),
        pytest.param(
            lambda loc: 'praha' in loc.address_lowercase_ascii,
            [1, 2],
            id='lambda constraint: partial address_lowercase_ascii',
        ),
        pytest.param(
            lambda loc: loc.discount_rate > 0 and loc.is_active,
            [0],
            id='lambda constraint: discount_rate and is_active',
        ),
        pytest.param(
            lambda loc: not loc.is_suspended,
            [0, 1, 2],
            id='lambda constraint: is_suspended and not is_active',
        ),
        pytest.param(
            lambda loc: loc.coordinates == (50.0957250, 14.2838994),
            [2],
            id='lambda constraint: coordinates',
        ),
    ],
)
def test_location_page_find_items(locations_page, constraint, expected_location_ids):
    locations_page.find_items
    locations = locations_page.find_items(constraint=constraint)
    assert [loc.id_ for loc in locations] == expected_location_ids
    location = locations_page.find_item(constraint=constraint)
    assert location.id_ == expected_location_ids[0]


@pytest.mark.parametrize(
    'constraint',
    [
        pytest.param({'': 'ABB'}, id='dict constraint: empty string key'),
        pytest.param(
            {'addr': 'Vyskočilova 1561/4a, Praha Michle'},
            id='dict constraint: partial key',
        ),
        pytest.param(
            {'nema': 'AAC TECHNOLOGIES SOLUTIONS'},
            id='dict constraint: misspelled key',
        ),
        pytest.param({'id': 1}, id='dict constraint: pydantic validation alias key'),
        pytest.param(
            {'name': 'ABB', 'addr': 'Vyskočilova 1561/4a, Praha Michle'},
            id='dict constraint: multiple keys, one invalid',
        ),
        pytest.param(
            {'adress_lowercase_asci': 'kozomin 501, 277 45'},
            id='dict constraint: misspelled property key',
        ),
        pytest.param({'id_': 99}, id='dict constraint: wrong id_'),
        pytest.param({'name': 'XYZ'}, id='dict constraint: wrong name'),
        pytest.param({'address': 'Foo'}, id='dict constraint: wrong address'),
        pytest.param(
            {'address_lowercase_ascii': 'bar'},
            id='dict constraint: wrong address_lowercase_ascii',
        ),
        pytest.param(
            {'latitude': 0.0, 'longitude': 0.0},
            id='dict constraint: wrong latitude and longitude',
        ),
        pytest.param(
            {'discount_rate': 100, 'is_active': False, 'is_suspended': True},
            id='dict constraint: multiple parameters (no match)',
        ),
        pytest.param(
            {'coordinates': (0.0, 0.0)}, id='dict constraint: wrong coordinates'
        ),
        pytest.param(
            MappingProxyType({'name_lowercase_ascii': 'xyz'}),
            id='MappingProxyType constraint: wrong name_lowercase_ascii',
        ),
        pytest.param(lambda loc: loc.id_ == 123, id='lambda constraint: wrong id_'),
        pytest.param(
            lambda loc: 'XYZ' in loc.name,
            id='lambda constraint: partial name (no match)',
        ),
        pytest.param(
            lambda loc: 'foo' in loc.address_lowercase_ascii,
            id='lambda constraint: partial address_lowercase_ascii (no match)',
        ),
        pytest.param(
            lambda loc: loc.discount_rate < 0 and loc.is_active,
            id='lambda constraint: discount_rate and is_active (no match)',
        ),
        pytest.param(
            lambda loc: loc.is_suspended and not loc.is_active,
            id='lambda constraint: is_suspended and not is_active (no match)',
        ),
        pytest.param(
            lambda loc: loc.coordinates == (0.0, 0.0),
            id='lambda constraint: wrong coordinates',
        ),
    ],
)
def test_location_page_find_items_no_match(locations_page, constraint):
    locations = list(locations_page.find_items(constraint=constraint))
    assert locations == []
    location = locations_page.find_item(constraint=constraint)
    assert location is None


@pytest.mark.parametrize(
    'constraint',
    [
        pytest.param({None: 'ABB'}, id='dict constraint: None key'),
        pytest.param({1: 'ABB'}, id='dict constraint: int key'),
        pytest.param({1: 1}, id='dict constraint: int wrong key and value'),
        pytest.param(
            {'name': 'ABB', 1: 1},
            id='dict constraint: str key (valid) and int key',
        ),
        pytest.param(None, id='None constraint'),
        pytest.param([('name', 'ABB')], id='list of tuples constraint'),
        pytest.param(
            lambda: 'ABB', id='invalid signature function constraint (no args)'
        ),
        pytest.param('Kozomín 501, 277 45', id='string constraint'),
        pytest.param(
            lambda l1, l2: True,
            id='invalid signature string constraint (too many args)',
        ),
        pytest.param(object(), id='object constraint'),
        pytest.param(object, id='uninstantiated class constraint'),
    ],
)
def test_location_page_find_items_invalid_constraint(locations_page, constraint):
    with pytest.raises(FreshPointParserTypeError):
        list(locations_page.find_items(constraint))
    with pytest.raises(FreshPointParserTypeError):
        locations_page.find_item(constraint)


@pytest.mark.parametrize(
    'constraint',
    [
        pytest.param(
            lambda p: p.nam == 'ABB', id='lambda constraint: partial attribute'
        ),
        pytest.param(
            lambda p: p.nema == 'ABB',
            id='lambda constraint: misspelled attribute',
        ),
        pytest.param(
            lambda p: p.name == 'ABB' and p.addr == 'Vyskočilova 1561/4a, Praha Michle',
            id='lambda constraint: multiple attributes, one partial',
        ),
        pytest.param(
            lambda p: p.neam == 'ABB'
            or p.address == 'Vyskočilova 1561/4a, Praha Michle',
            id='lambda constraint: multiple attributes, one misspelled',
        ),
    ],
)
def test_location_page_find_items_invalid_lambda_attribute(locations_page, constraint):
    with pytest.raises(AttributeError):
        list(locations_page.find_items(constraint))
    with pytest.raises(AttributeError):
        locations_page.find_item(constraint)


# region LocationPage - parsing_errors


def test_location_page_parsing_errors():
    """Test that parsing_errors work at the page level."""
    page = LocationPage(
        items={
            1: Location(id_=1, name='Valid Location'),
            2: Location(
                id_=2,
                name=ValueError('Bad name'),  # type: ignore[arg-type]
                latitude=TypeError('Bad latitude'),  # type: ignore[arg-type]
            ),
        }
    )

    # The page itself should have no parsing errors
    assert page.parsing_errors == {}

    # But individual items can have parsing errors
    assert page.items[1].parsing_errors == {}
    assert page.items[2].parsing_errors == {
        'name': 'ValueError: Bad name',
        'latitude': 'TypeError: Bad latitude',
    }


def test_location_page_with_parsing_errors_serialization():
    """Test serialization of a page with items containing parsing errors."""
    page = LocationPage(
        items={
            1: Location(id_=1, name='Valid'),
            2: Location(id_=2, name=ValueError('Invalid')),  # type: ignore[arg-type]
        }
    )

    data = page.model_dump()
    assert data['items'][1]['parsing_errors'] == {}
    assert data['items'][2]['parsing_errors'] == {'name': 'ValueError: Invalid'}


def test_location_page_find_items_with_parsing_errors():
    """Test that find_items can search by parsing_errors."""
    page = LocationPage(
        items={
            1: Location(id_=1, name='Valid'),
            2: Location(id_=2, name=ValueError('Error1')),  # type: ignore[arg-type]
            3: Location(id_=3, latitude=TypeError('Error2')),  # type: ignore[arg-type]
        }
    )

    # Find items with no parsing errors
    no_errors = list(page.find_items(lambda loc: not loc.parsing_errors))
    assert [loc.id_ for loc in no_errors] == [1]

    # Find items with parsing errors
    has_errors = list(page.find_items(lambda loc: bool(loc.parsing_errors)))
    assert [loc.id_ for loc in has_errors] == [2, 3]

    # Find items with specific error in name field
    name_errors = list(page.find_items(lambda loc: 'name' in loc.parsing_errors))
    assert [loc.id_ for loc in name_errors] == [2]


# endregion LocationPage - parsing_errors


# endregion LocationPage
