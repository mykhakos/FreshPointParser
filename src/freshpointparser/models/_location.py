from __future__ import annotations

import sys
from typing import Optional

from pydantic import AliasChoices, Field

from .._utils import normalize_text
from ._base import BaseItem, BasePage

if sys.version_info >= (3, 11):
    from typing import NamedTuple
else:
    from typing_extensions import NamedTuple


class LocationCoordinates(NamedTuple):
    """Geographic coordinates of a FreshPoint location as a ``(latitude, longitude)`` named pair.

    Immutable and lightweight — not a Pydantic model.
    Supports unpacking: ``lat, lon = location.coordinates``.
    """

    latitude: float
    """Latitude of the location."""
    longitude: float
    """Longitude of the location."""


class Location(BaseItem):
    """Data model of a FreshPoint vending machine location.

    All fields are ``Optional`` with ``None`` as the sentinel for "not available".
    Key computed properties: ``coordinates`` (returns a ``LocationCoordinates``
    named tuple when both lat/lon are set), ``name_lowercase_ascii``, and
    ``address_lowercase_ascii`` for diacritic-insensitive search.
    """

    name: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices('username', 'name'),
        title='Name',
        description='Name of the location.',
    )
    """Name of the location."""
    address: Optional[str] = Field(
        default=None,
        title='Address',
        description='Address of the location.',
    )
    """Address of the location."""
    latitude: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices('lat', 'latitude'),
        title='Latitude',
        description='Latitude of the location.',
    )
    """Latitude of the location."""
    longitude: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices('lon', 'longitude'),
        title='Longitude',
        description='Longitude of the location.',
    )
    """Longitude of the location."""
    discount_rate: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices('discount', 'discountRate'),
        title='Discount Rate',
        description='Discount rate applied at the location.',
    )
    """Discount rate applied at the location."""
    is_active: Optional[bool] = Field(
        default=None,
        validation_alias=AliasChoices('active', 'isActive'),
        title='Active',
        description='Indicates whether the location is active.',
    )
    """Indicates whether the location is active."""
    is_suspended: Optional[bool] = Field(
        default=None,
        validation_alias=AliasChoices('suspended', 'isSuspended'),
        title='Suspended',
        description='Indicates whether the location is suspended.',
    )
    """Indicates whether the location is suspended."""

    @property
    def name_lowercase_ascii(self) -> str:
        """Lowercase ASCII representation of the location name.

        If the name is not set, the representation is an empty string.
        """
        return normalize_text(self.name)

    @property
    def address_lowercase_ascii(self) -> str:
        """Lowercase ASCII representation of the location address.

        If the address is not set, the representation is an empty string.
        """
        return normalize_text(self.address)

    @property
    def coordinates(self) -> Optional[LocationCoordinates]:
        """Coordinates of the location as tuple (latitude, longitude).

        If either latitude or longitude is not set, None is returned.
        """
        if self.latitude is None or self.longitude is None:
            return None
        return LocationCoordinates(self.latitude, self.longitude)


LOCATION_PAGE_URL = 'https://my.freshpoint.cz'


def get_location_page_url() -> str:
    """Return the FreshPoint.cz location directory URL (``https://my.freshpoint.cz``)."""
    return LOCATION_PAGE_URL


class LocationPage(BasePage[Location]):
    """Data model of the FreshPoint location directory (my.freshpoint.cz).

    Contains all known vending machine locations. Extends ``BasePage`` with
    no additional fields. Use ``find_item`` or ``find_items`` to search by
    name, address, or other attributes.
    """

    @property
    def url(self) -> str:
        """URL of the location page."""
        return LOCATION_PAGE_URL
