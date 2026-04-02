import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Callable, Generic, List, Optional, TypeVar, Union

from ..exceptions import FreshPointParserError, ParseError
from ..models._base import BasePage

logger = logging.getLogger('freshpointparser.parsers')
"""Logger for the ``freshpointparser.parsers`` package."""

TPage = TypeVar('TPage', bound=BasePage)


@dataclass
class ParseContext:
    """Accumulates errors and timestamps during a single parse operation.

    Passed as ``context=`` to Pydantic's ``model_validate`` so that
    ``BestEffortModel`` can register validation errors here rather than
    raising. Callers do not interact with ``ParseContext`` directly —
    errors surface in ``ParseResult.metadata.errors``.
    """

    parsed_at: datetime = field(default_factory=datetime.now)
    """Timestamp of when the parsing operation was performed."""

    errors: List[Exception] = field(default_factory=list)
    """Exceptions encountered during the parsing operation."""

    def register_error(self, error: Exception) -> None:
        """Append an error to the context error list."""
        self.errors.append(error)


@dataclass(frozen=True, eq=True)
class ParseMetadata:
    """Metadata produced by a single ``BasePageHTMLParser.parse`` call.

    Reports the content digest, when parsing occurred, whether the result
    was served from cache, and any soft errors collected. An empty ``errors``
    list means the parse completed cleanly.
    """

    content_digest: bytes
    """SHA-1 hash digest of the page HTML content that was parsed.

    Use ``.hex()`` to get a human-readable hex string representation,
    e.g. for logging or storage.
    """

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
    """Result of a single ``parse`` call.

    ``page`` contains the structured data; ``metadata`` provides diagnostics
    (digest, timestamp, cache status, errors). ``errors`` is a convenience
    shortcut for ``metadata.errors``.
    """

    page: TPage
    """Parsed page data."""

    metadata: ParseMetadata
    """Metadata of the parsing operation."""

    @property
    def errors(self) -> List[Exception]:
        """Shortcut for ``metadata.errors``."""
        return self.metadata.errors


class BasePageHTMLParser(ABC, Generic[TPage]):
    """Abstract base parser for FreshPoint HTML pages.

    Maintains a SHA-1 digest of the last parsed content and returns a cached
    deep copy when the content has not changed, making it efficient for
    polling scenarios.

    Prefer the stateless convenience functions (``parse_product_page``,
    ``parse_location_page``) for one-off parsing. Instantiate a subclass
    directly when parsing the same page URL repeatedly.
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
        """Return the SHA-1 digest of ``content`` as bytes."""
        if isinstance(content, str):
            content = content.encode('utf-8')
        return hashlib.sha1(content).digest()  # noqa: S324

    def _reset_context(self) -> None:
        """Replace the current parse context with a fresh empty one."""
        self._context = ParseContext()

    def _safe_parse(self, parser_func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Call ``parser_func`` and return its result, or ``None`` on any exception.

        ``FreshPointParserError`` is logged at INFO; any other exception is wrapped
        as ``ParseError`` (preserving ``__cause__``) and logged at WARNING. All
        exceptions are registered in the current parse context.
        """
        try:
            return parser_func(*args, **kwargs)
        except FreshPointParserError as err:
            logger.info(
                "Parsing error in '%s': %s",
                getattr(parser_func, '__name__', repr(parser_func)),
                err,
            )
            self._context.register_error(err)
            return None
        except Exception as exc:
            wrapped = ParseError(f'Unexpected error in parser operation: {exc}')
            wrapped.__cause__ = exc
            logger.warning(
                "Unexpected exception wrapped as ParseError in '%s'",
                getattr(parser_func, '__name__', repr(parser_func)),
                exc_info=True,
            )
            self._context.register_error(wrapped)
            return None

    @abstractmethod
    def _parse_page_content(self, page_content: Union[str, bytes]) -> TPage:
        """Parse HTML into a page model. Must not raise — collect errors into context."""
        pass

    def parse(
        self, page_content: Union[str, bytes], force: bool = False
    ) -> ParseResult[TPage]:
        """Parse HTML content into a structured page model.

        Returns a deep copy of the result so the caller can mutate it freely.
        When ``page_content`` has the same SHA-1 digest as the previous call,
        the cached result is returned immediately with ``metadata.from_cache``
        set to ``True``.

        Args:
            page_content (Union[str, bytes]): HTML content of the page.
            force (bool): Force the parser to re-parse the content even if
                its hash digest matches the one of the previous content.
                Defaults to False.

        Returns:
            ParseResult[TPage]: Parsed page data and parsing metadata.

        Example:
            Stateful caching pattern for a polling loop::

                import time
                import httpx
                from freshpointparser.parsers import ProductPageHTMLParser
                from freshpointparser import get_product_page_url

                parser = ProductPageHTMLParser()
                url = get_product_page_url(296)

                while True:
                    result = parser.parse(httpx.get(url).text)
                    if not result.metadata.from_cache:
                        process(result.page)  # page content changed
                    time.sleep(60)
        """
        content_digest = self._hash_sha1(page_content)

        if (
            self._parsed_page is None
            or force
            or content_digest != self._metadata.content_digest
        ):
            logger.debug(
                "'%s': parsing HTML content (force=%s).",
                type(self).__name__,
                force,
            )
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
            logger.debug(
                "'%s': HTML content is unchanged, returning cached result.",
                type(self).__name__,
            )
            self._metadata = replace(
                self._metadata,
                from_cache=True,
            )

        return ParseResult(
            page=self._parsed_page.model_copy(deep=True),
            metadata=replace(self._metadata, errors=self._metadata.errors.copy()),
        )
