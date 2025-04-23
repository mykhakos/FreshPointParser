import hashlib
import logging
import operator
from abc import ABC, abstractmethod
from datetime import datetime
from typing import (
    Union,
)

from .._utils import normalize_text

logger = logging.getLogger('freshpointparser.parsers')
"""Logger of the `freshpointparser.parsers` package."""


class BasePageHTMLParser(ABC):
    """Base class for parsing HTML content of FreshPoint.cz pages.

    This class provides common functionality for parsing HTML content.
    It is not intended to be used directly but serves as a base class
    for more specific parsers.
    """

    def __init__(self) -> None:
        """Initialize a parser instance with an empty state."""
        self._parse_datetime = datetime.now()
        self._html_hash_sha1 = self._hash_html_sha1('')

    @staticmethod
    def _match_strings(needle: str, haystack: str, partial_match: bool) -> bool:
        """Check if the needle string is contained in the haystack string
        ignoring case and diacritics.

        Args:
            needle (str): String to search for.
            haystack (str): String to search in.
            partial_match (bool): If True, checks if `needle` is a substring of
                `haystack` (`needle in haystack`). If False, checks for exact
                match (`needle == haystack`). In both cases, the match is
                case-insensitive and ignores diacritics.

        Raises:
            TypeError: If the needle is not a string.

        Returns:
            bool: True if the needle is found in the haystack, False otherwise.
        """
        if not isinstance(needle, str):
            raise TypeError(f'Expected a string, got {type(needle)}.')
        op = operator.contains if partial_match else operator.eq
        return op(normalize_text(haystack), normalize_text(needle))

    @staticmethod
    def _hash_html_sha1(page_html: Union[str, bytes]) -> str:
        """Hash the given text using the SHA-1 algorithm and return the
        hexadecimal representation of the hash.

        Args:
            page_html (Union[str, bytes]): The text to be hashed.

        Returns:
            str: The hexadecimal representation of the SHA-1 hash of the text.
        """
        if isinstance(page_html, str):
            page_html = page_html.encode('utf-8')
        return hashlib.sha1(page_html).hexdigest()  # noqa: S324

    def _update_html_hash(
        self, page_html: Union[str, bytes], force: bool
    ) -> bool:
        """Update the HTML hash if the page HTML has changed.

        Args:
            page_html (Union[str, bytes]): The HTML content of
                the page.
            force (bool): If True, forces the parser to re-parse the HTML
                content even if the hash of the content matches the previous
                hash.

        Returns:
            bool: True if the HTML hash was updated, False otherwise.
        """
        html_hash_sha1 = self._hash_html_sha1(page_html)
        if force or html_hash_sha1 != self._html_hash_sha1:
            self._html_hash_sha1 = html_hash_sha1
            self._parse_datetime = datetime.now()
            logger.debug('HTML hash updated: %s', html_hash_sha1)
            return True
        return False

    @abstractmethod
    def _parse_page_html(self, page_html: Union[str, bytes]) -> None:
        """Parse the HTML content of the page.

        Args:
            page_html (Union[str, bytes]): HTML content of the page.
        """
        pass

    def parse(self, page_html: Union[str, bytes], force: bool = False) -> bool:
        """Parse page HTML content.

        Args:
            page_html (Union[str, bytes]): HTML content of the page to parse.
            force (bool): If True, forces the parser to re-parse the HTML
                content even if the hash of the content matches the hash of the
                previous content. If False, the parser will only re-parse the
                content if the hash has changed. Defaults to False.

        Returns:
            bool: True if the HTML content differed from the previous content
            and was parsed or was forced to be re-parsed, False otherwise.
        """
        if self._update_html_hash(page_html, force):
            self._parse_page_html(page_html)
            return True
        return False
