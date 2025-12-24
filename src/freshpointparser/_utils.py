from __future__ import annotations

import hashlib
import logging
from typing import Any, Callable, Optional, TypeVar, Union

from unidecode import unidecode

from .exceptions import FreshPointParserValueError

logger = logging.getLogger('freshpointparser')
"""Top-level logger of the ``freshpointparser`` package."""


T = TypeVar('T')


def try_call(func: Callable[..., T], *args: Any, **kwargs: Any) -> Union[T, Exception]:
    """Call the given function with the provided arguments safely and return
    either the result or the exception that was raised.

    Args:
        func (Callable[..., T]): The function to be called.
        *args (Any): Positional arguments to be passed to the function.
        **kwargs (Any): Keyword arguments to be passed to the function.

    Returns:
        Union[T, Exception]: The result of the function call or the exception raised.
    """
    try:
        return func(*args, **kwargs)
    except Exception as exc:
        logger.warning('Exception was raised during parsing: %s', exc, exc_info=True)
        return exc


def format_exception(exc: Exception) -> str:
    """Format an exception into a string that includes the exception type
    and message.

    Args:
        exc (Exception): The exception to be formatted.

    Returns:
        str: A string representation of the exception, including its type
            and message.
    """
    return f'{type(exc).__name__}: {exc!s}'


def normalize_text(text: Any) -> str:
    """Normalize the given text by removing diacritics, leading/trailing
    whitespace, and converting it to lowercase. Non-string values are
    converted to strings. ``None`` values are converted to empty strings.

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
    except Exception as exc:
        raise FreshPointParserValueError(f'Failed to normalize text "{text}".') from exc


def ensure_field_set(field: str, value: Optional[T]) -> T:
    if value is None:
        raise FreshPointParserValueError(f"Required field '{field}' is not set.")
    return value


def hash_sha1(content: Union[str, bytes]) -> bytes:
    """Hash the given text using the SHA-1 algorithm and return the
    hexadecimal representation of the hash.

    Args:
        content (Union[str, bytes]): The text to be hashed.

    Returns:
        bytes: The SHA-1 hash of the text.
    """
    if isinstance(content, str):
        content = content.encode('utf-8')
    return hashlib.sha1(content).digest()  # noqa: S324
