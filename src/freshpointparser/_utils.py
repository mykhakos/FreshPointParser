from __future__ import annotations

import logging
from typing import Any, TypeVar

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
