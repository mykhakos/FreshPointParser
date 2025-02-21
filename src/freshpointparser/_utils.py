import hashlib
from typing import Union

from unidecode import unidecode

LOCATION_PAGE_URL = 'https://my.freshpoint.cz'


def get_product_page_url(location_id: int) -> str:
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
    return unidecode(str(text).strip()).casefold()


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
