"""Annotations and auxiliary types for FreshPoint data models."""

from ._base import (
    FieldDiff,
    FieldDiffMapping,
    ModelDiffMapping,
)
from ._location import (
    LocationCoordinates,
)
from ._product import (
    ProductPriceUpdateInfo,
    ProductQuantityUpdateInfo,
)

__all__ = [
    'FieldDiff',
    'FieldDiffMapping',
    'LocationCoordinates',
    'ModelDiffMapping',
    'ProductPriceUpdateInfo',
    'ProductQuantityUpdateInfo',
]
