import hashlib
import logging
import operator
import sys
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Generic, Optional, TypeVar, Union

from .._utils import normalize_text
from ..exceptions import FreshPointParserAttributeError, FreshPointParserTypeError
from ..models import BasePage

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

logger = logging.getLogger('freshpointparser.parsers')
"""Logger of the ``freshpointparser.parsers`` package."""

TPage = TypeVar('TPage', bound=BasePage)


class BasePageHTMLParser(ABC, Generic[TPage]):
    """Provides common functionality for parsing HTML content of FreshPoint.cz pages.

    Note: This is a base class that is not intended to be used directly.
    """

    def __init__(self) -> None:
        """Initialize a parser instance with an empty state."""
        self._parse_datetime = datetime.now()
        self._html_hash_sha1 = self._hash_html_sha1('')
        self._parse_status: Union[bool, None] = None

    @staticmethod
    def _match_strings(needle: str, haystack: str, partial_match: bool) -> bool:
        """Check if the needle string is contained in the haystack string
        ignoring case and diacritics.

        Args:
            needle (str): String to search for.
            haystack (str): String to search in.
            partial_match (bool): If True, checks if ``needle`` is a substring of
                ``haystack`` (``needle in haystack``). If False, checks for exact
                match (``needle == haystack``). In both cases, the match is
                case-insensitive and ignores diacritics.

        Raises:
            FreshPointParserTypeError: If the needle is not a string.

        Returns:
            bool: True if the needle is found in the haystack, False otherwise.
        """
        if not isinstance(needle, str):
            raise FreshPointParserTypeError(f'Expected a string, got {type(needle)}.')
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

    def _update_html_hash(self, page_html: Union[str, bytes], force: bool) -> bool:
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

        Implementations should extract relevant data from the HTML content
        and store it in the parser's internal state. This method is called
        when the HTML content is updated or when the parser is forced to
        re-parse the content.

        Args:
            page_html (Union[str, bytes]): HTML content of the page.
        """
        pass

    @abstractmethod
    def _construct_page(self) -> TPage:
        """Construct a page model from the parsed HTML content.

        Implementations should build a **new** page model instance
        using the data extracted from :meth:`_parse_page_html`.  The returned
        model does not have to be cached and repeated calls may therefore yield
        a different object with the same data.  Mutating the returned object has
        no effect on the parser's internal state.

        Returns:
            TPage: A page model containing the parsed data.
        """
        pass

    @property
    def page(self) -> TPage:
        """Page model containing the parsed HTML data.

        ``parse()`` must be called at least once before accessing this property
        to ensure that the parser has valid HTML data to construct the page model.

        Accessing full parsed page data may require additional computation. If you are
        only interested in a subset of the parsed data, consider using
        specific properties or methods of the parser that return only
        the relevant information (see specific parser implementations for details).

        A fresh page model instance is created on every access. Consequently, modifying
        the returned object does not affect the cached parser state.
        """
        return self._construct_page()

    @property
    def parse_datetime(self) -> datetime:
        """Timestamp of the last successful or skipped parse.

        If the parser has never parsed any HTML content, this property will
        raise a :pyexc:`FreshPointParserAttributeError`.
        """
        if self._parse_status is None:
            raise FreshPointParserAttributeError('Parser has not parsed any HTML yet.')
        return self._parse_datetime

    @property
    def parse_status(self) -> Optional[bool]:
        """Tri-state parse status.

        - ``None``: Never parsed (no data available).
        - ``True``: Last parse applied (data changed or parse was forced).
        - ``False``: Last parse skipped (data unchanged).
        """
        return self._parse_status

    def parse(self, page_html: Union[str, bytes], force: bool = False) -> Self:
        """Parse page HTML content.

        **Note**: This method returns the parser instance itself, allowing for
        method call chaining. It does **not** return the parsed page model.
        The result of the parse is cached and can be accessed via the
        :pyattr:`parse_status` property.

        Args:
            page_html (Union[str, bytes]): HTML content of the page.
            force (bool): If True, forces the parser to re-parse the HTML
                content even if the hash of the content matches the hash of the
                previous content. If False, the parser will only re-parse the
                content if the hash has changed. Defaults to False.

        Returns:
            Self: The parser instance.
        """
        if self._update_html_hash(page_html, force):
            self._parse_page_html(page_html)
            self._parse_status = True
        else:
            logger.debug('HTML content unchanged, skipping parsing.')
            self._parse_status = False
        return self
