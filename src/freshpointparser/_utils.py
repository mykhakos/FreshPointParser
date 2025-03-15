import hashlib
from functools import lru_cache
from typing import Union

from unidecode import unidecode

LOCATION_PAGE_URL = 'https://my.freshpoint.cz'


@lru_cache(maxsize=1024)
def validate_id(id_: object) -> int:
    """Validate the given object as an ID integer. If the object is a string,
    it must be a numeric string representing a non-negative integer. If the
    object is an integer, it must be non-negative. The result is cached for
    improved performance on repeated calls with the same input.

    Args:
        id_ (object): The object to be validated as an ID. This can be
            either a string or an integer.

    Raises:
        TypeError: If the object is not an integer and cannot be converted to
            an integer.
        ValueError: If the object is an integer but is negative.

    Returns:
        int: The validated ID, as a non-negative integer.
    """
    if isinstance(id_, str):
        if id_.isnumeric():
            return int(id_)
        else:
            raise TypeError(
                f'ID must be a numeric string representing '
                f'a non-negative integer (got "{id_}").'
            )
    if not isinstance(id_, int):
        type_ = type(id_).__name__
        raise TypeError(f'ID must be an integer (got {type_}).')
    if id_ < 0:
        raise ValueError('ID must be a non-negative integer.')
    return id_


@lru_cache(maxsize=512)
def get_product_page_url(location_id: Union[int, str]) -> str:
    """Generate a FreshPoint.cz product page HTTPS URL for a given location ID.

    Args:
        location_id (int): The ID of the location (also known as page ID and
        device ID) for which to generate the URL. This is the number that
        uniquely identifies the location in the FreshPoint.cz system. It is
        the last part of the location page URL, after the last slash. For
        example, in https://my.freshpoint.cz/device/product-list/296, the ID
        is 296.

    Returns:
        str: The full page URL for the given location ID.
    """
    location_id = validate_id(location_id)
    return f'https://my.freshpoint.cz/device/product-list/{location_id}'


def normalize_text(text: object) -> str:
    """Normalize the given text by removing diacritics, leading/trailing
    whitespace, and converting it to lowercase. Non-string values are
    converted to strings. `None` values are converted to empty strings.

    Args:
        text (Any): The text to be normalized.

    Returns:
        str: The normalized text.
    """
    if text is None:
        return ''
    try:
        return unidecode(str(text).strip()).casefold()
    except Exception as e:
        raise ValueError(f'Failed to normalize text "{text}".') from e


def hash_text_sha1(text: Union[str, bytes, bytearray]) -> str:
    """Hash the given text using the SHA-1 algorithm and return the
    hexadecimal representation of the hash.

    Args:
        text (Union[str, bytes, bytearray]): The text to be hashed.

    Returns:
        str: The hexadecimal representation of the SHA-1 hash of the text.
    """
    if isinstance(text, str):
        text = text.encode('utf-8')
    return hashlib.sha1(text, usedforsecurity=False).hexdigest()
