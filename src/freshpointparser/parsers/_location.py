import json
import re
from typing import (
    Dict,
    List,
    Optional,
    Union,
)

from freshpointparser._utils import validate_id

from ..models import (
    Location,
    LocationPage,
)
from ._base import BasePageHTMLParser


class LocationPageHTMLParser(BasePageHTMLParser[LocationPage]):
    """Parses HTML content of a FreshPoint location webpage `my.freshpoint.cz`.
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
        self._page = LocationPage()

    def _load_json(self, page_html: Union[str, bytes]) -> List[Dict]:
        r"""Extract and parse the JSON location data embedded in the HTML.

        The location data is stored in the page HTML as a JavaScript string
        variable: `devices = "[{\"prop\":{...}}]";`

        This method uses regex to find this variable assignment and extract
        the JSON string. A double JSON parsing approach is used because the data
        is essentially double-quoted in the source
        (a JSON string within a JavaScript string).

        Args:
            page_html (Union[str, bytes]): The HTML content of the
                location page.

        Raises:
            ValueError: If the location data cannot be found or parsed.

        Returns:
            List[Dict]: A list of location data dictionaries extracted from the
                JavaScript variable in the HTML.
        """
        match_: Union[re.Match[str], re.Match[bytes], None]
        if isinstance(page_html, str):
            match_ = re.search(self._RE_SEARCH_PATTERN_STR, page_html)
        else:
            match_ = re.search(self._RE_SEARCH_PATTERN_BYTES, page_html)
        if not match_:
            raise ValueError(
                'Unable to find the location data in the HTML '
                '(regex pattern not matched).'
            )
        try:
            # double JSON parsing is required because of how the data is
            # embedded in the HTML (a JSON string inside a JavaScript string)
            data = json.loads(json.loads(match_.group(1)))
        except IndexError as e:
            raise ValueError(
                'Unable to parse the location data in the HTML '
                '(regex data group is missing).'
            ) from e
        except Exception as e:
            raise ValueError(
                'Unable to parse the location data in the HTML '
                '(Unexpected error during JSON parsing).'
            ) from e
        if not isinstance(data, list):
            raise ValueError(
                'Unable to parse the location data in the HTML '
                '(data is not a list).'
            )
        return data

    def _parse_json(self, data: List[Dict]) -> LocationPage:
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
            data (List[Dict]): The extracted location data from _load_json.
                Expected format: [{'prop': {...}, 'location': {...}}, ...]

        Returns:
            LocationPage: The structured location page model containing all
                parsed locations.
        """
        locations = {}
        for item in data:
            item['prop']['recordedAt'] = self.parse_datetime
            locations[item['prop']['id']] = item['prop']
        return LocationPage.model_validate(
            {
                'recordedAt': self.parse_datetime,
                'items': locations,
            }
        )

    def _parse_page_html(self, page_html: Union[str, bytes]) -> None:
        """Parse HTML content of a location page.

        This method is fully parses the HTML content to a structured
        LocationPage model.

        Args:
            page_html (Union[str, bytes]): HTML content of
                the location page to parse.
        """
        json_data = self._load_json(page_html)
        self._page = self._parse_json(json_data)

    def _construct_page(self) -> LocationPage:
        """Get the location page data parsed from the HTML content.

        The page is fully parsed during :meth:`parse`. A deep copy of the
        cached model is returned to keep the internal state immutable. Every
        access therefore yields a new :class:`LocationPage` instance.

        Returns:
            LocationPage: Parsed locations and metadata from the HTML content.
        """
        return self._page.model_copy(deep=True)

    @property
    def locations(self) -> List[Location]:
        """All locations parsed from the page HTML content.

        The returned ``Location`` instances are independent of the parser's
        cached data. Changes made to them will not modify the parser state.
        """
        # page is fully parsed on `parse` call. Copy for cache immutability
        return [loc.model_copy(deep=True) for loc in self._page.items.values()]

    def find_location_by_id(self, id_: Union[int, str]) -> Optional[Location]:
        """Find a single location based on the specified ID.

        Args:
            id_ (Union[int, str]): The ID of the location to search for.
                The ID is expected to be a unique non-negative integer or
                a string representation of a non-negative integer.

        Raises:
            TypeError: If the ID is not an integer and cannot be converted to
                an integer.
            ValueError: If the ID is an integer but is negative.

        Returns:
            Optional[Location]: Location with the specified ID or ``None`` if
            the location is not found.  The returned instance is independent of
            the parser's cached data.
        """
        id_ = validate_id(id_)
        location = self._page.items.get(id_)
        if location is None:
            return None
        return location.model_copy(deep=True)  # copy for cache immutability

    def find_location_by_name(
        self, name: str, partial_match: bool = True
    ) -> Optional[Location]:
        """Find a single location based on the specified name.

        Args:
            name (str): The name of the location to search for. Note that
                location names are normalized to lowercase ASCII characters.
                The match is case-insensitive and ignores diacritics regardless
                of the `partial_match` value.
            partial_match (bool): If True, the name match can be partial
                (case-insensitive). If False, the name match must be exact
                (case-insensitive). Defaults to True.

        Raises:
            TypeError: If the location name is not a string.

        Returns:
            Optional[Location]: Location matching the specified name or
            ``None`` if no location is found.  The returned instance is
            independent of the parser's cached data.  If multiple locations
            match, the first one is returned.
        """
        # wrapper over `LocationPage.find_item` method
        location = self._page.find_item(
            lambda loc: self._match_strings(name, loc.name, partial_match)
        )
        if location is None:
            return None
        return location.model_copy(deep=True)  # copy for cache immutability

    def find_locations_by_name(
        self, name: str, partial_match: bool = True
    ) -> List[Location]:
        """Find all locations that match the specified name.

        Args:
            name (str): The name of the location to filter by. Note that location
                names are normalized to lowercase ASCII characters. The match
                is case-insensitive and ignores diacritics regardless of the
                `partial_match` value.
            partial_match (bool): If True, the name match can be partial
                (case-insensitive). If False, the name match must be exact
                (case-insensitive). Defaults to True.

        Raises:
            TypeError: If the location name is not a string.

        Returns:
            List[Location]: Locations matching the specified name. Each
            location in the returned list is detached from the parser's internal
            cache. If no locations are found, an empty list is returned.
        """
        # wrapper over `LocationPage.find_locations` method
        locations = self._page.find_items(
            lambda loc: self._match_strings(name, loc.name, partial_match)
        )
        # return copies to keep cached data immutable
        return [location.model_copy(deep=True) for location in locations]


def parse_location_page(page_html: Union[str, bytes]) -> LocationPage:
    """Parse the HTML content of a FreshPoint location webpage
    `my.freshpoint.cz` to a structured LocationPage model.

    Args:
        page_html (Union[str, bytes]): HTML content of the location page to parse.

    Returns:
        LocationPage: Parsed and validated location page data.
    """
    parser = LocationPageHTMLParser()
    parser.parse(page_html)
    return parser.page
