"""Annotations and auxiliary types for FreshPoint data models."""

from ._location import (
    LocationCoordinates,
    LocationField,
    LocationFieldMapping,
)
from ._product import (
    ProductField,
    ProductFieldMapping,
    ProductPriceUpdateInfo,
    ProductQuantityUpdateInfo,
)

__all__ = [
    'LocationCoordinates',
    'LocationField',
    'LocationFieldMapping',
    'ProductField',
    'ProductFieldMapping',
    'ProductPriceUpdateInfo',
    'ProductQuantityUpdateInfo',
]
