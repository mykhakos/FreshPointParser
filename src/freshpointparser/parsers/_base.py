from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Union

from .._utils import hash_sha1, logger
from ..exceptions import FreshPointParserError, FreshPointParserValueError
from ..models._base import BasePage

TPage = TypeVar('TPage', bound=BasePage)


@dataclass(frozen=True, eq=True)
class ParseMetadata:
    """Holds the result of parsing a FreshPoint.cz page HTML content."""

    content_digest: bytes
    """SHA-1 hash digest of the page HTML content that was parsed."""

    last_updated_at: datetime
    """Timestamp of when the page HTML content was last updated."""

    last_parsed_at: datetime
    """Timestamp of when the page HTML content was last parsed."""

    was_last_parse_from_cache: bool = False
    """Indicates whether the last parsing operation used cached data."""

    parse_errors: List[Exception] = field(default_factory=list)
    """List of exceptions encountered during the page HTML parsing."""


@dataclass(frozen=True, eq=True)
class ParseContext:
    """Holds context information about the parsing operation."""

    parsed_at: datetime = field(default_factory=datetime.now)
    """Timestamp of when the parsing operation was performed."""

    parse_errors: List[Exception] = field(default_factory=list)
    """List of exceptions encountered during the parsing operation."""


class BasePageHTMLParser(ABC, Generic[TPage]):
    """Provides common functionality for parsing HTML content of FreshPoint.cz pages.

    Note: This is a base class that is not intended to be used directly.
    """

    def __init__(self) -> None:
        """Initialize a parser instance with an empty state."""
        now = datetime.now()
        self._metadata = ParseMetadata(
            content_digest=hash_sha1(b''), last_updated_at=now, last_parsed_at=now
        )
        self._parsed_page: Optional[TPage] = None

    @staticmethod
    def _new_base_record_data_from_context(context: ParseContext) -> Dict[str, Any]:
        """Create a new base record data dictionary from the parsing context.

        Args:
            context (ParseContext): The parsing context containing metadata.

        Returns:
            Dict[str, Any]: A dictionary containing base record data.
        """
        return {'recorded_at': context.parsed_at}

    @abstractmethod
    def _parse_page_content(
        self, page_content: Union[str, bytes], context: ParseContext
    ) -> TPage:
        """Parse the HTML content of the page to a Pydantic model.

        Implementations should extract relevant data from the HTML content
        and construct a page model instance. This method is called
        when the HTML content is updated or when the parser is forced to
        re-parse the content.

        This method should not raise exceptions directly. Instead, any parsing errors
        should be collected in the `context.parse_errors` list.

        Args:
            page_content (Union[str, bytes]): The HTML content of the page.
            context (ParseContext): A context dictionary that can be used
                to store additional information during parsing. For example,
                parsing errors can be collected in a list provided in the
                context under the key defined by
                :data:`freshpointparser.models.PARSE_ERRORS_CONTEXT_KEY`.

        Returns:
            TPage: A page model containing the parsed data.
        """
        pass

    @staticmethod
    def _safe_parse(
        parser_func: Callable, _context: ParseContext, **kwargs: Any
    ) -> Any:
        try:
            return parser_func(**kwargs)
        except FreshPointParserError as err:
            logger.info('Parsing error occurred: %s', err)
            _context.parse_errors.append(err)
            return None

    @property
    def metadata(self) -> ParseMetadata:
        """Get metadata about the last parsing operation.

        Returns:
            ParseMetadata: Metadata about the last parsing operation.
        """
        return self._metadata

    @property
    def parsed_page(self) -> TPage:
        """Get the page data parsed from the HTML content.

        The page is fully parsed during :meth:`parse`. A deep copy of the
        cached model is returned to keep the internal state immutable. Every
        access therefore yields a new :class:`TPage` instance.

        Returns:
            TPage: Parsed data from the HTML content.

        Raises:
            FreshPointParserValueError: If the page has not been parsed yet.
        """
        if self._parsed_page is None:
            raise FreshPointParserValueError('Page has not been parsed yet.')
        return self._parsed_page.model_copy(deep=True)

    def parse(self, page_content: Union[str, bytes], force: bool = False) -> TPage:
        """Parse page HTML content.

        Args:
            page_content (Union[str, bytes]): HTML content of the page.
            force (bool): If True, forces the parser to re-parse the HTML
                content even if the hash of the content matches the hash of the
                previous content. If False, the parser will only re-parse the
                content if the hash has changed. Defaults to False.

        Returns:
            TPage: A page model containing the parsed data.
        """
        content_digest = hash_sha1(page_content)
        if force or content_digest != self._metadata.content_digest:
            logger.debug('Parsing HTML content (force=%s).', force)
            context = ParseContext()
            self._parsed_page = self._parse_page_content(page_content, context)
            self._metadata = replace(
                self._metadata,
                content_digest=content_digest,
                last_updated_at=context.parsed_at,
                last_parsed_at=context.parsed_at,
                was_last_parse_from_cache=False,
                parse_errors=context.parse_errors,
            )
        else:
            logger.debug('HTML content is unchanged, skipping parsing.')
            self._metadata = replace(
                self._metadata,
                last_parsed_at=datetime.now(),
                was_last_parse_from_cache=True,
            )
        return self.parsed_page
