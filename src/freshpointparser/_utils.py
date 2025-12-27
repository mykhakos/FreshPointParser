from __future__ import annotations

import hashlib
import logging
from typing import Any, TypeVar, Union

from unidecode import unidecode

from .exceptions import FreshPointParserValueError

logger = logging.getLogger('freshpointparser')
"""Top-level logger of the ``freshpointparser`` package."""


T = TypeVar('T')


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
