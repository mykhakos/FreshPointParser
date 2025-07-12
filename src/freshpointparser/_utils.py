from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Union

from unidecode import unidecode

from .exceptions import FreshPointParserTypeError, FreshPointParserValueError

logger = logging.getLogger('freshpointparser')
"""Top-level logger of the `freshpointparser` package."""

LOCATION_PAGE_URL = 'https://my.freshpoint.cz'


@lru_cache(maxsize=1024)
def validate_id(id_: Any) -> int:  # noqa: ANN401
    """Validate the given object as an ID integer. If the object is a string,
    it must be a numeric string representing a non-negative integer. If the
    object is an integer, it must be non-negative. The result is cached for
    improved performance on repeated calls with the same input.

    Args:
        id_ (Any): The object to be validated as an ID. This can be
            either a string or an integer.

    Raises:
        FreshPointParserTypeError: If the object is not an integer or not a string.
        FreshPointParserValueError: If the object is a string that is not a numeric
            string representing a non-negative integer, or if the object is
            an integer that is negative.

    Returns:
        int: The validated ID, as a non-negative integer.
    """
    if isinstance(id_, str):
        if id_.isdecimal():
            return int(id_)
        else:
            raise FreshPointParserValueError(
                f'ID must be a numeric string representing a non-negative '
                f'integer (got "{id_}").'
            )
    if not isinstance(id_, int):
        raise FreshPointParserTypeError(f'ID must be an integer (got {type(id_)}).')
    if id_ < 0:
        raise FreshPointParserValueError('ID must be a non-negative integer.')
    return id_


def get_product_page_url(location_id: Union[int, str]) -> str:
    """Generate a FreshPoint.cz product page HTTPS URL for a given location ID.

    Args:
        location_id (Union[int, str]): The ID of the location (also known as
            the page ID and the device ID) for which to generate the URL. This is
            the number that uniquely identifies the location in the FreshPoint.cz
            system. It is the last part of the product page URL, after the last slash.
            For example, in https://my.freshpoint.cz/device/product-list/296,
            the ID is 296.

    Raises:
        FreshPointParserTypeError: If the object is not an integer or not a string.
        FreshPointParserValueError: If the object is a string that is not a numeric
            string representing a non-negative integer, or if the object is
            an integer that is negative.

    Returns:
        str: The full page URL for the given location ID.
    """
    location_id = validate_id(location_id)
    return f'https://my.freshpoint.cz/device/product-list/{location_id}'


def get_location_page_url() -> str:
    """Get the FreshPoint.cz location page HTTPS URL.

    Returns:
        str: The FreshPoint.cz location page URL.
    """
    return LOCATION_PAGE_URL


def normalize_text(text: Any) -> str:  # noqa: ANN401
    """Normalize the given text by removing diacritics, leading/trailing
    whitespace, and converting it to lowercase. Non-string values are
    converted to strings. `None` values are converted to empty strings.

    Args:
        text (Any): The text to be normalized.

    Raises:
        FreshPointParserValueError: If the text cannot be normalized due to an
            unexpected error, such as encoding issues.

    Returns:
        str: The normalized text.
    """
    if text is None:
        return ''
    try:
        return unidecode(str(text).strip()).casefold()
    except Exception as e:
        raise FreshPointParserValueError(f'Failed to normalize text "{text}".') from e
