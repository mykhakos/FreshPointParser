"""Pydantic models for FreshPoint products and locations.

The primary models are ``Product``, ``ProductPage``, ``Location``, and
``LocationPage``. ``BestEffortModel`` is available for building custom
fault-tolerant models. Supplementary types are in the ``types`` submodule.
"""

from . import types
from ._base import BaseItem, BasePage, BestEffortModel, logger
from ._location import Location, LocationPage, get_location_page_url
from ._product import Product, ProductPage, get_product_page_url

__all__ = [
    'BaseItem',
    'BasePage',
    'BestEffortModel',
    'Location',
    'LocationPage',
    'Product',
    'ProductPage',
    'get_location_page_url',
    'get_product_page_url',
    'logger',
    'types',
]
