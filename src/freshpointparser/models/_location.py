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
    """Latitude and longitude of a location as a named tuple.

    Immutable and lightweight — not a Pydantic model. Supports tuple
    unpacking::

        lat, lon = location.coordinates
    """

    latitude: float
    """Latitude of the location."""
    longitude: float
    """Longitude of the location."""


class Location(BaseItem):
    """Data model of a FreshPoint vending machine location.

    All fields are ``Optional`` with ``None`` as the sentinel for "not available".
    The ``coordinates`` property returns a ``LocationCoordinates`` named tuple
    when both ``latitude`` and ``longitude`` are set.
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
        description='Location-level discount rate (0-1) applied to products at this location.',
    )
    """Location-level discount rate (0-1) applied to products at this location."""
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
        """Lowercase ASCII representation of ``name``. Empty string when unset."""
        return normalize_text(self.name)

    @property
    def address_lowercase_ascii(self) -> str:
        """Lowercase ASCII representation of ``address``. Empty string when unset."""
        return normalize_text(self.address)

    @property
    def coordinates(self) -> Optional[LocationCoordinates]:
        """Coordinates as a ``LocationCoordinates`` named tuple.

        ``None`` when either ``latitude`` or ``longitude`` is unset.
        """
        if self.latitude is None or self.longitude is None:
            return None
        return LocationCoordinates(self.latitude, self.longitude)


LOCATION_PAGE_URL = 'https://my.freshpoint.cz'


def get_location_page_url() -> str:
    """Get the FreshPoint.cz location page HTTPS URL.

    Returns:
        str: The FreshPoint.cz location page URL.
    """
    return LOCATION_PAGE_URL


class LocationPage(BasePage[Location]):
    """Data model of the FreshPoint location directory (my.freshpoint.cz).

    Contains all known vending machine locations. Use ``find_item`` or
    ``find_items`` to search by name, address, or other attributes.
    """

    @property
    def url(self) -> str:
        """URL of the location directory page."""
        return LOCATION_PAGE_URL
