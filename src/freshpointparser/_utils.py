"""Shared utilities and the root library logger."""

import logging
from typing import Any

from unidecode import unidecode

logger = logging.getLogger('freshpointparser')
"""Top-level logger of the ``freshpointparser`` package."""

logger.addHandler(logging.NullHandler())


def normalize_text(text: Any) -> str:
    """Convert text to a lowercase ASCII representation.

    Strips leading and trailing whitespace, removes diacritics (e.g. Czech
    characters such as ``š``, ``č``, ``ř`` become ``s``, ``c``, ``r``), and
    converts to lowercase. Non-string values are cast to ``str`` first.
    ``None`` returns an empty string.

    Used internally to enable case- and diacritic-insensitive search via
    properties such as ``Product.name_lowercase_ascii``.

    Args:
        text (Any): The value to normalise.

    Returns:
        str: The normalised text, or an empty string for ``None``.

    Raises:
        ValueError: If normalisation fails due to an unexpected encoding error.

    Example:
        ::

            >>> normalize_text('Café Ústí nad Labem')
            'cafe usti nad labem'
            >>> normalize_text(None)
            ''
    """
    if text is None:
        return ''
    try:
        return unidecode(str(text).strip()).casefold()
    except Exception as exc:
        raise ValueError(f'Failed to normalize text "{text}".') from exc
