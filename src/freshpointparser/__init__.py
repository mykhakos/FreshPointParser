"""FreshPointParser — HTML parser for my.freshpoint.cz.

Extracts product and location data from FreshPoint vending machine pages.
The primary entry points are ``parse_product_page`` and ``parse_location_page``,
which accept raw HTML and return a ``ParseResult`` containing structured
Pydantic models. No HTTP client is included; fetching the HTML is the
caller's responsibility.

For repeated calls to the same page URL, use ``ProductPageHTMLParser`` or
``LocationPageHTMLParser`` directly to benefit from SHA-1 content caching.
"""

from . import exceptions, models, parsers
from ._utils import logger
from .models import get_location_page_url, get_product_page_url
from .parsers import parse_location_page, parse_product_page

__all__ = [
    'exceptions',
    'get_location_page_url',
    'get_product_page_url',
    'logger',
    'models',
    'parse_location_page',
    'parse_product_page',
    'parsers',
]
