"""Annotations and auxiliary types for FreshPoint data models."""

from ._base import (
    FieldDiff,
    FieldDiffMapping,
    ModelDiffMapping,
    ValidationContext,
)
from ._location import (
    LocationCoordinates,
)
from ._product import (
    ProductPriceChange,
    ProductQuantityChange,
)

__all__ = [
    'FieldDiff',
    'FieldDiffMapping',
    'LocationCoordinates',
    'ModelDiffMapping',
    'ProductPriceChange',
    'ProductQuantityChange',
    'ValidationContext',
]
