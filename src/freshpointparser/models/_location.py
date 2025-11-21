from __future__ import annotations

import sys

from pydantic import AliasChoices, Field

from .._utils import normalize_text
from ._base import BaseItem, BasePage

if sys.version_info >= (3, 11):
    from typing import NamedTuple
else:
    from typing_extensions import NamedTuple


class LocationCoordinates(NamedTuple):
    """Holds the latitude and longitude of a location as a pair of floats.
    Latitude is the first value in the pair, and longitude is the second
    value in the pair.
    """

    latitude: float
    """Latitude of the location."""
    longitude: float
    """Longitude of the location."""


class Location(BaseItem):
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


LOCATION_PAGE_URL = 'https://my.freshpoint.cz'


def get_location_page_url() -> str:
    """Get the FreshPoint.cz location page HTTPS URL.

    Returns:
        str: The FreshPoint.cz location page URL.
    """
    return LOCATION_PAGE_URL


class LocationPage(BasePage[Location]):
    """Data model of a FreshPoint location webpage."""

    @property
    def url(self) -> str:
        """URL of the location page."""
        return LOCATION_PAGE_URL
