from __future__ import annotations

import sys
from typing import Literal, Tuple, Union

from pydantic import (
    AliasChoices,
    Field,
)

from .._utils import (
    LOCATION_PAGE_URL,
    normalize_text,
)
from ._base import BaseItem, BaseItemField, BaseItemFieldMapping, BasePage

if sys.version_info >= (3, 11):
    from typing import NamedTuple
else:
    from typing_extensions import NamedTuple


LocationField = Union[
    BaseItemField,
    Literal[
        'name',
        'address',
        'latitude',
        'longitude',
        'discount_rate',
        'is_active',
        'is_suspended',
        'name_lowercase_ascii',
        'address_lowercase_ascii',
        'coordinates',
    ],
]


class LocationFieldMapping(BaseItemFieldMapping):
    """Provides key names and types for location attributes."""

    name: str
    address: str
    latitude: float
    longitude: float
    discount_rate: float
    is_active: bool
    is_suspended: bool
    name_lowercase_ascii: str
    address_lowercase_ascii: str
    coordinates: Tuple[float, float]


class LocationCoordinates(NamedTuple):
    """Holds the latitude and longitude of a location as a pair of floats.
    Latitude is the first value in the pair, and longitude is the second
    value in the pair.
    """

    latitude: float
    """Latitude of the location."""
    longitude: float
    """Longitude of the location."""


class Location(BaseItem[LocationField]):
    """Data model of a FreshPoint location."""

    name: str = Field(
        default='',
        validation_alias=AliasChoices('username', 'name'),
        title='Name',
        description='Name of the location.',
    )
    """Name of the location."""
    address: str = Field(
        default='',
        title='Address',
        description='Address of the location.',
    )
    """Address of the location."""
    latitude: float = Field(
        default=0.0,
        validation_alias=AliasChoices('lat', 'latitude'),
        title='Latitude',
        description='Latitude of the location.',
    )
    """Latitude of the location."""
    longitude: float = Field(
        default=0.0,
        validation_alias=AliasChoices('lon', 'longitude'),
        title='Longitude',
        description='Longitude of the location.',
    )
    """Longitude of the location."""
    discount_rate: float = Field(
        default=0.0,
        validation_alias=AliasChoices('discount', 'discountRate'),
        title='Discount Rate',
        description='Discount rate applied at the location.',
    )
    """Discount rate applied at the location."""
    is_active: bool = Field(
        default=True,
        validation_alias=AliasChoices('active', 'isActive'),
        title='Active',
        description='Indicates whether the location is active.',
    )
    """Indicates whether the location is active."""
    is_suspended: bool = Field(
        default=False,
        validation_alias=AliasChoices('suspended', 'isSuspended'),
        title='Suspended',
        description='Indicates whether the location is suspended.',
    )
    """Indicates whether the location is suspended."""

    @property
    def name_lowercase_ascii(self) -> str:
        """Lowercase ASCII representation of the location name."""
        return normalize_text(self.name)

    @property
    def address_lowercase_ascii(self) -> str:
        """Lowercase ASCII representation of the location address."""
        return normalize_text(self.address)

    @property
    def coordinates(self) -> LocationCoordinates:
        """Coordinates of the location as tuple (latitude, longitude)."""
        return LocationCoordinates(self.latitude, self.longitude)


class LocationPage(BasePage[Location, LocationField, LocationFieldMapping]):
    """Data model of a FreshPoint location webpage."""

    @property
    def url(self) -> str:
        """URL of the location page."""
        return LOCATION_PAGE_URL
