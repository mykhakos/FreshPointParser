"""Annotations and auxiliary types for FreshPoint data models."""

from ._base import (
    DiffType,
    DiffValues,
    FieldDiff,
    FieldDiffMapping,
    ModelDiff,
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
    'DiffType',
    'DiffValues',
    'FieldDiff',
    'FieldDiffMapping',
    'LocationCoordinates',
    'ModelDiff',
    'ModelDiffMapping',
    'ProductPriceUpdateInfo',
    'ProductQuantityUpdateInfo',
]
