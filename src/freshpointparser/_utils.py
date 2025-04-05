from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import (
    Any,
    Callable,
    Iterable,
    Iterator,
    Mapping,
    TypeVar,
    Union,
)

from unidecode import unidecode

T = TypeVar('T')

LOCATION_PAGE_URL = 'https://my.freshpoint.cz'


def validate_str(text: object) -> str:
    """Validate the given object as a string. If the object is not a string,
    it raises a TypeError. If the object is a string, it is returned as-is.

    Args:
        text (object): The object to be validated as a string.

    Raises:
        TypeError: If the object is not a string.

    Returns:
        str: The validated string.
    """
    if not isinstance(text, str):
        raise TypeError(f'Expected a string, got {type(text)}.')
    return text


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
        TypeError: If the object is not an integer or not a string.
        ValueError: If the object is a string that is not a numeric string
            representing a non-negative integer, or if the object is an
            integer that is negative.

    Returns:
        int: The validated ID, as a non-negative integer.
    """
    if isinstance(id_, str):
        if id_.isdecimal():
            return int(id_)
        else:
            raise ValueError(
                f'ID must be a numeric string representing a non-negative '
                f'integer (got "{id_}").'
            )
    if not isinstance(id_, int):
        raise TypeError(f'ID must be an integer (got {type(id_)}).')
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
    return hashlib.sha1(text).hexdigest()  # noqa: S324


def filter_by_constraint(
    constraint: Union[Mapping[str, Any], Callable[[T], bool]],
    items: Iterable[T],
) -> Iterator[T]:
    """Find all values in a dictionary that match a constraint.

    Args:
        constraint (Union[Mapping[str, Any], Callable[[T], bool]]): Either
            a function that receives a data item and returns True if the
            item meets the constraint, or a mapping where each key is
            an attribute (or property) name of the data item and its value
            is the expected value.
        items (Iterable[T]): Data items to be filtered.

    Returns:
        Iterator[T]: A lazy iterator over all data items that match the
            given constraint.
    """
    if callable(constraint):
        return filter(constraint, items)

    if isinstance(constraint, Mapping):
        return filter(
            lambda data_item: all(
                getattr(data_item, attr) == value
                for attr, value in constraint.items()
            ),
            items,
        )

    raise TypeError(
        f'Constraint must be either a dictionary or a callable function. '
        f"Got type '{type(constraint)}' instead."
    )
