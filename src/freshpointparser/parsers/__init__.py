"""HTML parsers for FreshPoint webpages.

The stateless ``parse_product_page`` and ``parse_location_page`` functions
handle one-off parsing. ``ProductPageHTMLParser`` and
``LocationPageHTMLParser`` are the stateful variants with SHA-1 content
caching, suitable for polling scenarios. ``ParseResult`` and ``ParseMetadata``
are the return types.
"""

from ._base import (
    BasePageHTMLParser,
    ParseMetadata,
    ParseResult,
    logger,
)
from ._location import LocationPageHTMLParser, parse_location_page
from ._product import ProductPageHTMLParser, parse_product_page

__all__ = [
    'BasePageHTMLParser',
    'LocationPageHTMLParser',
    'ParseMetadata',
    'ParseResult',
    'ProductPageHTMLParser',
    'logger',
    'parse_location_page',
    'parse_product_page',
]
