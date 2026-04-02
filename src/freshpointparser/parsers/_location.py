import json
import re
from typing import Any, Dict, List, Union

from ..exceptions import ParseError
from ..models import Location, LocationPage
from ._base import BasePageHTMLParser, ParseResult, logger


class LocationPageHTMLParser(BasePageHTMLParser[LocationPage]):
    """Parser for the FreshPoint location directory (``my.freshpoint.cz``).

    Location data is embedded in the page as a doubly-encoded JSON string
    inside a JavaScript variable (``devices = "[...]";``). Only the ``prop``
    key of each entry is used; the ``location`` key is a confirmed duplicate
    and is ignored. Reuse a single instance across calls for SHA-1 caching.
    """

    _RE_SEARCH_PATTERN_STR = re.compile(
        r'\bdevices\b\s*=\s*("\[(?:\\.|[^"\\])*\]")\s*;',
        re.DOTALL,
    )
    """Regex pattern to search for the location data in the HTML string."""
    _RE_SEARCH_PATTERN_BYTES = re.compile(
        rb'\bdevices\b\s*=\s*("\[(?:\\.|[^"\\])*\]")\s*;',
        re.DOTALL,
    )
    """Regex pattern to search for the location data in the HTML bytes."""

    def _load_json(self, page_content: Union[str, bytes]) -> List[Dict]:
        r"""Extract and doubly-decode the JSON location array from the HTML.

        The source embeds location data as a JSON-encoded string inside a JS
        variable: ``devices = "[{...}]";``. Two ``json.loads`` calls are required.

        Raises:
            ParseError: If the variable is missing, JSON is invalid, or the
                result is not a list.
        """
        match_: Union[re.Match[str], re.Match[bytes], None]
        if isinstance(page_content, str):
            match_ = self._RE_SEARCH_PATTERN_STR.search(page_content)
        else:
            match_ = self._RE_SEARCH_PATTERN_BYTES.search(page_content)
        if not match_:
            raise ParseError(
                'Unable to find the location data in the HTML '
                '(regex pattern not matched).'
            )
        try:
            # double JSON parsing is required because of how the data is
            # embedded in the HTML (a JSON string inside a JavaScript string)
            data = json.loads(json.loads(match_.group(1)))
        except IndexError as err:
            raise ParseError(
                'Unable to parse the location data in the HTML '
                '(regex data group is missing).'
            ) from err
        except Exception as exc:
            raise ParseError(
                'Unable to parse the location data in the HTML '
                '(Unexpected error during JSON parsing).'
            ) from exc
        if not isinstance(data, list):
            raise ParseError(
                'Unable to parse the location data in the HTML (data is not a list).'
            )
        return data

    def _parse_location(self, location_data: Dict[str, Any]) -> Location:
        """Parse a single location entry dict (using its ``'prop'`` key) into a ``Location``.

        Raises:
            ParseError: If the ``'prop'`` key is missing or validation fails.
        """
        # 'location' key duplicates 'prop' data (name, address, lat/lon as strings) — ignored.
        try:
            return Location.model_validate(location_data['prop'], context=self._context)
        except KeyError as err:
            raise ParseError(
                f"Missing 'prop' key in location item: {location_data}"
            ) from err
        except Exception as exc:
            raise ParseError(f'Error parsing location item: {location_data}') from exc

    def _parse_locations(self, page_content: Union[str, bytes]) -> List[Location]:
        """Parse all location entries from the page HTML."""
        locations = []
        for location_data in self._load_json(page_content):
            location = self._safe_parse(
                self._parse_location, location_data=location_data
            )
            if location is not None:
                locations.append(location)
        logger.debug('Parsed %d location(s).', len(locations))
        return locations

    def _parse_page_content(self, page_content: Union[str, bytes]) -> LocationPage:
        """Parse the full location directory HTML into a ``LocationPage`` model."""
        parsed_data = {'recorded_at': self._context.parsed_at}

        locations = self._safe_parse(self._parse_locations, page_content=page_content)
        if locations is not None:
            parsed_data['items'] = locations

        logger.debug(
            'Location page parsed: %d location(s).',
            len(locations) if locations is not None else 0,
        )
        return LocationPage.model_validate(parsed_data, context=self._context)


def parse_location_page(page_content: Union[str, bytes]) -> ParseResult[LocationPage]:
    """Parse the FreshPoint location directory HTML into a ``LocationPage``.

    Convenience function for one-off parsing. Use ``LocationPageHTMLParser``
    directly for repeated calls with caching.

    Args:
        page_content (Union[str, bytes]): Raw HTML of the location directory page.

    Returns:
        ParseResult[LocationPage]: Parsed page and parsing metadata.
            An empty ``result.metadata.errors`` list means parsing was clean.

    Example:
        ```python
        import httpx
        from freshpointparser import parse_location_page, get_location_page_url

        html = httpx.get(get_location_page_url()).text
        result = parse_location_page(html)

        for location in result.page.items:
            print(location.name, location.address)
        ```
    """
    return LocationPageHTMLParser().parse(page_content)
