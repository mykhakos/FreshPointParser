import json
import re
from typing import (
    Any,
    Dict,
    List,
    Union,
)

from .._utils import logger
from ..exceptions import (
    FreshPointParserValueError,
)
from ..models import Location, LocationPage
from ._base import BasePageHTMLParser, ParseContext


class LocationPageHTMLParser(BasePageHTMLParser[LocationPage]):
    """Parses HTML content of a FreshPoint location webpage ``my.freshpoint.cz``.
    Allows accessing the parsed webpage data and searching for locations by name
    or ID.
    """

    _RE_SEARCH_PATTERN_STR = re.compile(r'devices\s*=\s*("\[.*\]");')
    """Regex pattern to search for the location data in the HTML string."""
    _RE_SEARCH_PATTERN_BYTES = re.compile(rb'devices\s*=\s*("\[.*\]");')
    """Regex pattern to search for the location data in the HTML bytes."""

    def __init__(self) -> None:
        """Initialize a LocationPageHTMLParser instance with an empty state."""
        super().__init__()

    def _load_json(self, page_content: Union[str, bytes]) -> List[Dict]:
        r"""Extract and parse the JSON location data embedded in the HTML.

        The location data is stored in the page HTML as a JavaScript string
        variable: ``devices = "[{\"prop\":{...}}]";``

        This method uses regex to find this variable assignment and extract
        the JSON string. A double JSON parsing approach is used because the data
        is essentially double-quoted in the source
        (a JSON string within a JavaScript string).

        Args:
            page_content (Union[str, bytes]): The HTML content of the
                location page.

        Raises:
            FreshPointParserValueError: If the location data cannot be found or parsed.

        Returns:
            List[Dict]: A list of location data dictionaries extracted from the
                JavaScript variable in the HTML.
        """
        match_: Union[re.Match[str], re.Match[bytes], None]
        if isinstance(page_content, str):
            match_ = self._RE_SEARCH_PATTERN_STR.search(page_content)
        else:
            match_ = self._RE_SEARCH_PATTERN_BYTES.search(page_content)
        if not match_:
            raise FreshPointParserValueError(
                'Unable to find the location data in the HTML '
                '(regex pattern not matched).'
            )
        try:
            # double JSON parsing is required because of how the data is
            # embedded in the HTML (a JSON string inside a JavaScript string)
            data = json.loads(json.loads(match_.group(1)))
        except IndexError as e:
            raise FreshPointParserValueError(
                'Unable to parse the location data in the HTML '
                '(regex data group is missing).'
            ) from e
        except Exception as e:
            raise FreshPointParserValueError(
                'Unable to parse the location data in the HTML '
                '(Unexpected error during JSON parsing).'
            ) from e
        if not isinstance(data, list):
            raise FreshPointParserValueError(
                'Unable to parse the location data in the HTML (data is not a list).'
            )
        return data

    def _parse_json(self, page_data: List[Dict[str, Any]]) -> LocationPage:
        """Convert the extracted JSON data into a structured LocationPage model.

        This method transforms the raw JSON data extracted from the HTML into
        a structured LocationPage model. Each location item in the raw data
        contains both 'prop' and 'location' keys, but we only use the 'prop'
        data as it contains all necessary information.

        The method:
        1. Extracts the 'prop' object from each item in the data list
        2. Adds a timestamp for when the data was recorded
        3. Creates a dictionary of locations keyed by their IDs
        4. Constructs and validates a LocationPage model with the locations

        Args:
            page_data (List[Dict]): The extracted location data from _load_json.
                Expected format: [{'prop': {...}, 'location': {...}}, ...]

        Returns:
            LocationPage: The structured location page model containing all
                parsed locations.
        """
        locations = []
        for item in page_data:
            try:
                item_data: Dict[str, Any] = item['prop']
                item_data['recorded_at'] = self._metadata.last_parsed_at
                location = Location.model_validate(item_data)
                locations.append(location)
            except KeyError:
                logger.warning(
                    "Skipping location item due to missing 'prop' key: %s", item
                )
            except Exception as exc:
                logger.warning(
                    'Error parsing location item %s: %s', item, exc, exc_info=True
                )
        return LocationPage(recorded_at=self._metadata.last_parsed_at, items=locations)

    def _parse_page_content(
        self, page_content: Union[str, bytes], context: ParseContext
    ) -> LocationPage:
        """Parse HTML content of a location page.

        This method is fully parses the HTML content to a structured
        LocationPage model.

        Args:
            page_content (Union[str, bytes]): HTML content of
                the location page to parse.
            context (Dict[str, Any]): A context dictionary that can be used
                to store additional information during parsing.
        """
        page_data = self._safe_parse(
            self._load_json, context, page_content=page_content
        )
        if page_data is None:
            return LocationPage(recorded_at=context.parsed_at)

        return self._parse_json(page_data)


def parse_location_page(page_content: Union[str, bytes]) -> LocationPage:
    """Parse the HTML content of a FreshPoint location webpage
    ``my.freshpoint.cz`` to a structured LocationPage model.

    Args:
        page_content (Union[str, bytes]): HTML content of the location page.

    Raises:
        FreshPointParserError: If the HTML does not match the expected structure.

    Returns:
        LocationPage: Parsed and validated location page data.
    """
    return LocationPageHTMLParser().parse(page_content)
