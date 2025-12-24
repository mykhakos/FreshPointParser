"""Pydantic models and other data containers of the ``freshpointparser`` library.
The ``annotations`` submodule is available for additional data types.
"""

from . import types
from ._base import BaseItem, BasePage, BaseRecord
from ._location import Location, LocationPage, get_location_page_url
from ._product import Product, ProductPage, get_product_page_url

__all__ = [
    'BaseItem',
    'BasePage',
    'BaseRecord',
    'Location',
    'LocationPage',
    'Product',
    'ProductPage',
    'get_location_page_url',
    'get_product_page_url',
    'types',
]
