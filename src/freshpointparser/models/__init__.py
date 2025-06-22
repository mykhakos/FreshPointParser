"""Pydantic models and other data containers of the `freshpointparser` library.
The ``annotations`` submodule is available for additional data types.
"""

from . import annotations
from ._base import BaseItem, BasePage, BaseRecord, logger
from ._location import (
    Location,
    LocationPage,
)
from ._product import (
    Product,
    ProductPage,
)

__all__ = []


__all__ = [
    'BaseItem',
    'BasePage',
    'BaseRecord',
    'Location',
    'LocationPage',
    'Product',
    'ProductPage',
    'annotations',
    'logger',
]
