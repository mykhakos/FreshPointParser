import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Union

from ..exceptions import FreshPointParserError
from ..models._base import BasePage

logger = logging.getLogger('freshpointparser.parsers')
"""Logger for the ``freshpointparser.parsers`` package."""

TPage = TypeVar('TPage', bound=BasePage)


@dataclass
class ParseContext:
    """Holds context information about the parsing operation."""

    parsed_at: datetime = field(default_factory=datetime.now)
    """Timestamp of when the parsing operation was performed."""

    errors: List[Exception] = field(default_factory=list)
    """Exceptions encountered during the parsing operation."""

    def register_error(self, error: Exception) -> None:
        """Register a parsing error in the context.

        NOTE: This method is an implementation of the interface required by
        the validation context used in model validation.

        Args:
            error (Exception): The exception to register.
        """
        self.errors.append(error)


@dataclass(frozen=True, eq=True)
class ParseMetadata:
    """Holds the metadata of a FreshPoint.cz page HTML content parsing operation."""

    content_digest: bytes
    """SHA-1 hash digest of the page HTML content that was parsed."""

    parsed_at: datetime
    """Timestamp of when the page HTML content was last parsed.

    If the content has not changed since the last parsing operation,
    this timestamp may be earlier than the current time.
    """

    from_cache: bool
    """Indicates whether the last parsing operation used cached data."""

    errors: List[Exception] = field(default_factory=list)
    """Exceptions encountered during the page HTML parsing."""


@dataclass(frozen=True, eq=True)
class ParseResult(Generic[TPage]):
    """Holds the result of a FreshPoint.cz page HTML content parsing operation."""

    page: TPage
    """Parsed page data."""

    metadata: ParseMetadata
    """Metadata of the parsing operation."""

    @property
    def errors(self) -> List[Exception]:
        """List of exceptions encountered during the parsing operation.

        This is a convenience property that forwards to the metadata's errors.

        Returns:
            List[Exception]: List of parsing exceptions.
        """
        return self.metadata.errors


class BasePageHTMLParser(ABC, Generic[TPage]):
    """Provides common functionality for parsing HTML content of FreshPoint.cz pages.

    Note: This is a base class that is not intended to be used directly.
    """

    def __init__(self) -> None:
        """Initialize a parser instance with an empty state."""
        self._parsed_page: Optional[TPage] = None
        self._metadata = ParseMetadata(
            content_digest=b'',
            parsed_at=datetime.now(),
            from_cache=False,
            errors=[],
        )
        self._context = ParseContext()

    @staticmethod
    def _hash_sha1(content: Union[str, bytes]) -> bytes:
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

    @staticmethod
    def _new_base_record_data_from_context(context: ParseContext) -> Dict[str, Any]:
        """Create a new base record data dictionary from the parsing context.

        Args:
            context (ParseContext): The parsing context containing metadata.

        Returns:
            Dict[str, Any]: A dictionary containing base record data.
        """
        return {'recorded_at': context.parsed_at}

    def _reset_context(self) -> None:
        """Reset the internal parsing context to a new, empty state."""
        self._context = ParseContext()

    def _safe_parse(self, parser_func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Wrap a parsing function call to safely handle exceptions. The exceptions
        are recorded in the current parsing context instead of being raised.

        Args:
            parser_func (Callable): The parsing function to be called.
            *args: Positional arguments to pass to the parsing function.
            **kwargs: Additional keyword arguments to pass to the parsing function.

        Returns:
            Any: The result of the parsing function, or None if an error occurred.
        """
        try:
            return parser_func(*args, **kwargs)
        except FreshPointParserError as err:
            logger.info('Parsing error occurred: %s', err)
            self._context.register_error(err)
            return None

    @abstractmethod
    def _parse_page_content(self, page_content: Union[str, bytes]) -> TPage:
        """Parse the HTML content of the page to a Pydantic model.

        Implementations should extract relevant data from the HTML content
        and construct a page model instance. This method is called
        when the HTML content is updated or when the parser is forced to
        re-parse the content.

        This method should not raise exceptions directly. Instead, any parsing errors
        should be collected in the current parsing context.

        Args:
            page_content (Union[str, bytes]): The HTML content of the page.

        Returns:
            TPage: A page model containing the parsed data.
        """
        pass

    def parse(
        self, page_content: Union[str, bytes], force: bool = False
    ) -> ParseResult[TPage]:
        """Parse the HTML content of a FreshPoint webpage.

        Args:
            page_content (Union[str, bytes]): HTML content of the page.
            force (bool): Force the parser to re-parse the content even if
                its hash digest matches the one of the previous content.
                Defaults to False.

        Returns:
            ParseResult[TPage]: Parsed page data and parsing metadata.
        """
        content_digest = self._hash_sha1(page_content)

        if (
            self._parsed_page is None
            or force
            or content_digest != self._metadata.content_digest
        ):
            logger.debug('Parsing HTML content (force=%s).', force)
            self._reset_context()
            self._parsed_page = self._parse_page_content(page_content)
            self._metadata = replace(
                self._metadata,
                content_digest=content_digest,
                parsed_at=self._context.parsed_at,
                from_cache=False,
                errors=self._context.errors,
            )
        else:
            logger.debug('HTML content is unchanged, skipping parsing.')
            self._metadata = replace(
                self._metadata,
                from_cache=True,
            )

        return ParseResult(
            page=self._parsed_page.model_copy(deep=True),
            metadata=replace(self._metadata, errors=self._metadata.errors.copy()),
        )
