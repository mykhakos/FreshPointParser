import logging
from typing import Any

from unidecode import unidecode

logger = logging.getLogger('freshpointparser')
"""Top-level logger of the ``freshpointparser`` package."""


def normalize_text(text: Any) -> str:
    """Normalize the given text by removing diacritics, leading/trailing
    whitespace, and converting it to lowercase. Non-string values are
    converted to strings. ``None`` values are converted to empty strings.

    Args:
        text (Any): The text to be normalized.

    Returns:
        str: The normalized text.

    Raises:
        ValueError: If the text cannot be normalized due to an unexpected error,
            such as encoding issues.
    """
    if text is None:
        return ''
    try:
        return unidecode(str(text).strip()).casefold()
    except Exception as exc:
        raise ValueError(f'Failed to normalize text "{text}".') from exc
