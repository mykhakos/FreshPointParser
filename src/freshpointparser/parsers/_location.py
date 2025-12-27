import json
import re
from typing import Any, Dict, List, Union

from ..exceptions import FreshPointParserValueError
from ..models import Location, LocationPage
from ._base import BasePageHTMLParser, ParseContext


class LocationPageHTMLParser(BasePageHTMLParser[LocationPage]):
    """Parses HTML content of a FreshPoint location webpage ``my.freshpoint.cz``."""

    _RE_SEARCH_PATTERN_STR = re.compile(r'devices\s*=\s*("\[.*\]");')
    """Regex pattern to search for the location data in the HTML string."""
    _RE_SEARCH_PATTERN_BYTES = re.compile(rb'devices\s*=\s*("\[.*\]");')
    """Regex pattern to search for the location data in the HTML bytes."""

    def __init__(self) -> None:
        """Initialize a LocationPageHTMLParser instance with an empty state."""
        super().__init__()

    def _load_json(self, page_content: Union[str, bytes]) -> List[Dict]:
        r"""Extract the JSON location data embedded in the HTML.

        The location data is stored in the page HTML as a JavaScript string
        variable: ``devices = "[{\"prop\":{...}}]";``

        Regex is used to find this variable assignment and extract the JSON string.
        A double JSON parsing approach is used because the data is essentially
        double-quoted in the source (a JSON string within a JavaScript string).

        Args:
            page_content (Union[str, bytes]): The HTML content of the
                location page.

        Raises:
            FreshPointParserValueError: If the location data cannot be found or parsed.

        Returns:
            List[Dict]: Raw location data dictionaries extracted from
                the JavaScript variable in the HTML content.
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
        except IndexError as err:
            raise FreshPointParserValueError(
                'Unable to parse the location data in the HTML '
                '(regex data group is missing).'
            ) from err
        except Exception as exc:
            raise FreshPointParserValueError(
                'Unable to parse the location data in the HTML '
                '(Unexpected error during JSON parsing).'
            ) from exc
        if not isinstance(data, list):
            raise FreshPointParserValueError(
                'Unable to parse the location data in the HTML (data is not a list).'
            )
        return data

    def _parse_location(
        self, location_data: Dict[str, Any], context: ParseContext
    ) -> Location:
        """Parse a single location item from the raw location data.

        The data is expected to contain both 'prop' and 'location' keys, but only
        the 'prop' data is used for parsing as it contains all necessary information.
        The 'recorded_at' timestamp is added to the data before validation.

        Args:
            location_data (Dict[str, Any]): Raw location data dictionary.
            context (ParseContext): Parsing context containing metadata.

        Raises:
            FreshPointParserValueError: Raised when the 'prop' key is missing or
                when other parsing errors occur.

        Returns:
            Location: Parsed and validated Location model instance.
        """
        parsed_data = self._new_base_record_data_from_context(context)
        try:
            parsed_data.update(location_data['prop'])
            return Location.model_validate(parsed_data, context=context)
        except KeyError as err:
            raise FreshPointParserValueError(
                f"Missing 'prop' key in location item: {location_data}"
            ) from err
        except Exception as exc:
            raise FreshPointParserValueError(
                f'Error parsing location item: {location_data}'
            ) from exc

    def _parse_locations(
        self, locations_data: List[Dict[str, Any]], context: ParseContext
    ) -> List[Location]:
        """Parse multiple location items from the raw location data list.

        Args:
            locations_data (List[Dict[str, Any]]): Raw list of
                location data dictionaries.
            context (ParseContext): Parsing context containing metadata.

        Returns:
            List[Location]: Parsed and validated Location model instances.
        """
        locations = []
        for location_data in locations_data:
            location = self._safe_parse(
                self._parse_location,
                context,
                location_data=location_data,
                context=context,
            )
            if location is not None:
                locations.append(location)
        return locations

    def _parse_page_content(
        self, page_content: Union[str, bytes], context: ParseContext
    ) -> LocationPage:
        """Parse the HTML content of the location page to a Pydantic model.

        This method fully parses the raw JSON data extracted from the HTML content to
        a structured LocationPage model.

        Args:
            page_content (Union[str, bytes]): HTML content of
                the location page to parse.
            context (ParseContext): Parsing context containing metadata.

        Returns:
            LocationPage: The location page model containing all parsed locations.
        """
        parsed_data = self._new_base_record_data_from_context(context)

        locations_data = self._safe_parse(
            self._load_json, context, page_content=page_content
        )
        if locations_data is not None:
            locations = self._safe_parse(
                self._parse_locations,
                context,
                locations_data=locations_data,
                context=context,
            )
            if locations is not None:
                parsed_data['items'] = locations

        return LocationPage.model_validate(parsed_data, context=context)


def parse_location_page(page_content: Union[str, bytes]) -> LocationPage:
    """Parse the HTML content of a FreshPoint location webpage
    ``my.freshpoint.cz`` to a structured LocationPage model.

    Args:
        page_content (Union[str, bytes]): HTML content of the location page.

    Returns:
        LocationPage: Parsed and validated location page data.
    """
    return LocationPageHTMLParser().parse(page_content)
