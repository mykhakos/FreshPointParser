import html
import json
import logging
import re
from typing import (
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

import bs4

from .._utils import hash_text_sha1, normalize_text
from ..models._models import (
    Location,
    LocationPage,
    Product,
    ProductPage,
)

logger = logging.getLogger('freshpointparser.parsers')
"""Logger of the `freshpointparser.parsers` package."""


T = TypeVar('T')


class ProductHTMLParser:
    """A parser utility for extracting product information from HTML tags.

    This class provides static methods to parse various attributes of a product
    from its HTML representation. It's designed to work with BeautifulSoup
    `Tag` objects, extracting data such as product name, ID number, pricing,
    availability, etc.
    """

    @staticmethod
    def _extract_single_tag(resultset: bs4.ResultSet) -> bs4.Tag:
        """Get a single Tag in a ResultSet.

        Args:
            resultset (bs4.ResultSet): A `bs4.ResultSet` object
                expected to contain exactly one `bs4.Tag` object.

        Returns:
            bs4.Tag: The Tag contained in the provided `resultset`.

        Raises:
            ValueError: If `resultset` does not contain exactly one Tag.
            TypeError: If the extracted element is not a `bs4.Tag` object.
        """
        if len(resultset) == 0:
            raise ValueError('ResultSet is empty (expected one Tag element).')
        if len(resultset) != 1:
            raise ValueError(
                f'Unexpected number of elements in the ResultSet'
                f'(expected 1, got {len(resultset)}).'
            )
        if not isinstance(resultset[0], bs4.Tag):
            raise TypeError(
                f'The element in the ResultSet is not a Tag object. '
                f'(got type "{type(resultset[0]).__name__}").'
            )
        return resultset[0]

    @staticmethod
    def _get_attr_value(attr_name: str, tag: bs4.Tag) -> str:
        """Get the value of a specified attribute from a Tag.

        Args:
            attr_name (str): The name of the attribute to retrieve.
            tag (bs4.Tag): The Tag to extract the attribute from.

        Returns:
            str: The value of the specified attribute.

        Raises:
            KeyError: If the attribute is missing.
            ValueError: If the attribute is not a string.
        """
        try:
            attr = tag[attr_name]
        except KeyError as err:
            raise KeyError(
                f'Product attributes do not contain keyword "{attr_name}".'
            ) from err
        if not isinstance(attr, str):
            raise ValueError(
                f'Unexpected "{attr_name}" attribute parsing results: '
                f'attribute value is expected to be a string '
                f'(got type "{type(attr).__name__}").'
            )
        return attr.strip()

    @classmethod
    def find_name(cls, product_data: bs4.Tag) -> str:
        """Extract the product name from the given product data."""
        return html.unescape(cls._get_attr_value('data-name', product_data))

    @classmethod
    def find_id(cls, product_data: bs4.Tag) -> int:
        """Extract the product ID number from the given product data."""
        return int(cls._get_attr_value('data-id', product_data))

    @classmethod
    def find_is_vegetarian(cls, product_data: bs4.Tag) -> bool:
        """Determine whether the product is vegetarian
        from the given product data.
        """
        return cls._get_attr_value('data-veggie', product_data) == '1'

    @classmethod
    def find_is_gluten_free(cls, product_data: bs4.Tag) -> bool:
        """Determine whether the product is gluten-free
        from the given product data.
        """
        return cls._get_attr_value('data-glutenfree', product_data) == '1'

    @classmethod
    def find_is_promo(cls, product_data: bs4.Tag) -> bool:
        """Determine whether the product is being promoted
        from the given product data.
        """
        return cls._get_attr_value('data-ispromo', product_data) == '1'

    @classmethod
    def find_info(cls, product_data: bs4.Tag) -> str:
        """Extract the product info from the given product data."""
        text = html.unescape(cls._get_attr_value('data-info', product_data))
        lines = []
        for line in text.split('\n'):
            line_stripped = line.rstrip()
            if line_stripped.endswith('<br />'):
                line_stripped = line_stripped[:-6]
            line_stripped = line_stripped.strip()
            if line_stripped:
                lines.append(line_stripped)
        return '\n'.join(lines)

    @classmethod
    def find_pic_url(cls, product_data: bs4.Tag) -> str:
        """Extract the URL of the product's picture
        from the given product data.
        """
        return cls._get_attr_value('data-photourl', product_data)

    @classmethod
    def find_category(cls, product_data: bs4.Tag) -> str:
        """Extract the product category from the given product data."""
        if product_data.parent is None:
            raise AttributeError(
                f'Unable to extract product category name for product '
                f'"id={cls._find_id_safe(product_data)}" from the provided '
                f'html data (parent data is missing).'
            )
        # 'string=bool' filters out empty strings and None values
        category = product_data.parent.find_all(name='h2', string=bool)
        try:
            return cls._extract_single_tag(category).text.strip()  # type: ignore
        except Exception as exp:
            raise ValueError(
                f'Unable to extract product category name for product '
                f'"id={cls._find_id_safe(product_data)}" from the provided '
                f'html data ({exp}).'
            ) from exp

    @classmethod
    def _find_id_safe(cls, product_data: bs4.Tag) -> str:
        """Extract the product ID number from the given product data. If the ID
        is not found, catch the raised exception and return a placeholder.
        """
        try:
            return str(cls.find_id(product_data))
        except Exception as e:
            logger.warning(
                f'Unable to extract product ID from the provided html data '
                f'({e}).'
            )
            return '?'

    @classmethod
    def _run_converter(
        cls, converter: Callable[[], T], product_data: bs4.Tag
    ) -> T:
        """Run the given converter function and return the converted value.

        Args:
            converter (Callable[[], T]): The converter function
                to be executed.
            product_data (bs4.Tag): The product data to be passed to
                the converter function.

        Returns:
            T: The converted value.

        Raises:
            ValueError: If an error occurs during the conversion process.
        """
        try:
            return converter()
        except Exception as exc:
            raise ValueError(
                f'Unable to convert a parsed value for the product '
                f'"id={cls._find_id_safe(product_data)}".'
            ) from exc

    @classmethod
    def find_quantity(cls, product_data: bs4.Tag) -> int:
        """Extract the quantity of the product from the given product data."""
        if 'sold-out' in product_data.attrs.get('class', {}):
            return 0
        result = product_data.find_all(
            name='span',
            string=(
                lambda text: bool(
                    text
                    and re.match(
                        pattern=r'^((posledni)|(\d+))\s(kus|kusy|kusu)!?$',
                        string=normalize_text(text),
                    )
                )
            ),
        )
        if not result:  # sold out products don't have the quantity text
            return 0  # (should be caught by the "sold-out" check above)
        quantity = normalize_text(cls._extract_single_tag(result).text)
        if 'posledn' in quantity:  # products that have only 1 item in stock
            return 1  # have "posledni" in the quantity text
        return cls._run_converter(
            lambda: int(quantity.split()[0]),  # regular ("2 kusy", "5 kusu")
            product_data,
        )

    @classmethod
    def find_price(cls, product_data: bs4.Tag) -> Tuple[float, float]:
        """Extract the full and current price of the product
        from the given product data.
        """
        result = product_data.find_all(
            name='span',
            string=(
                lambda text: bool(
                    text
                    and re.match(
                        pattern=r'^\d+\.\d+$', string=normalize_text(text)
                    )
                )
            ),
        )
        if len(result) == 1:
            price_full = cls._run_converter(
                lambda: float(result[0].text),
                product_data,  # price_full_str
            )
            return price_full, price_full
        if len(result) == 2:
            price_full = cls._run_converter(
                lambda: float(result[0].text),
                product_data,  # price_full_str
            )
            price_curr = cls._run_converter(
                lambda: float(result[1].text),
                product_data,  # price_curr_str
            )
            if price_curr > price_full:
                id_ = cls._find_id_safe(product_data)
                raise ValueError(
                    f'Unexpected product "id={id_}" parsing results: '
                    f'current price "{price_curr}" is greater than '
                    f'the regular full price "{price_full}".'
                )
            # elif price_curr < price_full:  # "data-isPromo" is unreliable
            #     if not cls.find_is_promo(product_data):
            #         id_ = cls._find_id_safe(product_data)
            #         raise ValueError(
            #             f'Unexpected product "id={id_}" parsing results: '
            #             f'current price "{price_curr}" is different from '
            #             f'the regular full price "{price_full}", '
            #             f'but the "isPromo" flag is not set.'
            #             )
            return price_full, price_curr
        raise ValueError(
            f'Unexpected number of elements in the ResultSet'
            f'(expected 1 or 2, got {len(result)}).'
        )


class ProductPageHTMLParser:
    """Parses HTML contents of a FreshPoint.cz product web page
    (`my.freshpoint.cz/device/product-list/<pageId>`). Allows extracting
    the product page data and searching for products by name or ID.

    Example:
    ```python
    parser = ProductPageHTMLParser()  # create a new parser instance

    parser.parse(page_html=...)  # parse the HTML contents

    print(parser.location_id)  # get the location ID
    print(parser.location_name)  # get the location name

    product = parser.find_product_by_id(480)  # find a product by ID number
    print(product.name)  # print the name of the found product

    products = parser.find_products_by_name('sendvic')  # find products by name
    for product in products:
        print(product.name)  # print the names of the found products

    page = parser.product_page  # get the parsed product page data
    print(len(page.products))  # print the number of products on the page
    ```
    """

    def __init__(self) -> None:
        """Initialize a ProductPageHTMLParser instance with an empty state."""
        self._bs4_parser = bs4.BeautifulSoup()
        self._product_page = ProductPage()
        self._all_products_found: bool = False

    def _find_product_data(self) -> bs4.ResultSet[bs4.Tag]:
        """Find all product data elements in the page HTML.

        Returns:
            bs4.ResultSet: A ResultSet containing the data of all products
                as Tags.
        """
        result = self._bs4_parser.find_all('div', class_='product')
        return result  # type: ignore

    def _find_product_data_by_id(self, id_: int) -> Optional[bs4.Tag]:
        """Find product data matching the specified ID.
        The data is checked for uniqueness.

        Args:
            id_ (int): The ID of the product to search for.

        Raises:
            ValueError: If the product with the specified ID is not unique.

        Returns:
            Optional[bs4.Tag]: A Tag containing the data of the matched product.
                If the product is not found, returns None.
        """

        def attr_filter_id(value: str) -> bool:
            if not value:
                return False
            try:
                return int(value) == id_
            except ValueError as e:
                raise ValueError(
                    f'Unable to parse the product ID "{value}".'
                ) from e

        result = self._bs4_parser.find_all(
            'div',
            class_='product',
            attrs={'data-id': attr_filter_id},
        )
        if len(result) == 0:
            return None
        if len(result) != 1:
            raise ValueError(f'ID="{id_}" is not unique.')
        return result[0]  # type: ignore

    def _find_product_data_by_name(self, name: str) -> bs4.ResultSet[bs4.Tag]:
        """Find product data matching the specified name.

        Args:
            name (str): The name of the product(s) to search for.

        Returns:
            bs4.ResultSet: The ResultSet containing the data of the matched
                products as Tags.
        """

        def attr_filter_name(value: str) -> bool:
            if not value:
                return False
            try:
                return normalize_text(name) in normalize_text(value)
            except Exception as e:
                raise ValueError(
                    f'Unable to parse the product name "{value}".'
                ) from e

        result = self._bs4_parser.find_all(
            'div',
            class_='product',
            attrs={'data-name': attr_filter_name},
        )
        return result  # type: ignore

    def _parse_product_data(self, data: bs4.Tag) -> Product:
        """Parse the product data to a `Product` model.

        Args:
            data (bs4.Tag): The Tag containing the product data.

        Returns:
            Product: An instance of the Product model
                containitng the parsed and validated data.
        """
        price_full, price_curr = ProductHTMLParser.find_price(data)
        return Product(
            id_=ProductHTMLParser.find_id(data),
            name=ProductHTMLParser.find_name(data),
            category=ProductHTMLParser.find_category(data),
            is_vegetarian=ProductHTMLParser.find_is_vegetarian(data),
            is_gluten_free=ProductHTMLParser.find_is_gluten_free(data),
            is_promo=ProductHTMLParser.find_is_promo(data),
            quantity=ProductHTMLParser.find_quantity(data),
            price_curr=price_curr,
            price_full=price_full,
            info=ProductHTMLParser.find_info(data),
            pic_url=ProductHTMLParser.find_pic_url(data),
            location_id=self.location_id,
        )

    def _update_product_cache(self, product: Product) -> None:
        """Update the product cache with the given product model. The product
        model deep copy is added to the cache with the product ID as the key.

        Args:
            product (Product): The product data to be added to the cache.
        """
        self._product_page.products[product.id_] = product.model_copy(deep=True)

    @property
    def location_id(self) -> int:
        """Location ID (also known as the page ID or the device ID) extracted
        from the page HTML.

        The value is cached after the first extraction until the page HTML
        changes.
        """
        if 'location_id' in self._product_page.model_fields_set:  # cached
            return self._product_page.location_id
        script_tag = self._bs4_parser.find(
            'script', string=re.compile(r'deviceId')
        )
        if not script_tag:
            raise ValueError(
                'Unable to parse page ID '
                '(<script/> tag with "deviceId" text was not found).'
            )
        script_text = script_tag.get_text()
        match = re.search(r'deviceId\s*=\s*"(.*?)"', script_text)
        if not match:
            raise ValueError(
                'Unable to parse page ID ("deviceId" text '
                'within the <script/> tag was not matched).'
            )
        try:
            location_id = int(match.group(1))
            self._product_page.location_id = location_id
            return location_id
        except Exception as e:
            raise ValueError('Unable to parse page ID.') from e

    @property
    def location_name(self) -> str:
        """The name of the location (also known as the page title) extracted
        from the page HTML.

        The value is cached after the first extraction until the page HTML
        changes.
        """
        if 'location_name' in self._product_page.model_fields_set:  # cached
            return self._product_page.location_name
        title_tag = self._bs4_parser.find('title')
        if not title_tag:
            raise ValueError(
                'Unable to parse location name (<title/> tag  was not found).'
            )
        title_text = title_tag.get_text()
        try:
            location_name = title_text.split('|')[0].strip()
            self._product_page.location_name = location_name
            return location_name
        except Exception as e:
            raise ValueError('Unable to parse location name.') from e

    @property
    def products(self) -> List[Product]:
        """Product data parsed and validated from the page HTML.

        The data is cached after the first extraction until the page HTML
        changes.
        """
        if self._all_products_found:
            return [
                product.model_copy(deep=True)  # copy for cache immutability
                for product in self._product_page.products.values()
            ]
        products = []
        for product_data in self._find_product_data():
            product_id = ProductHTMLParser.find_id(product_data)
            if product_id in self._product_page.products:
                product = self._product_page.products[product_id]
                product = product.model_copy(deep=True)
            else:
                product = self._parse_product_data(product_data)
                self._update_product_cache(product)
            products.append(product)
        self._all_products_found = True
        return products

    @property
    def product_page(self) -> ProductPage:
        """All product page data parsed and validated from the HTML contents.

        The data is cached after the first extraction until the page HTML
        changes.
        """
        return ProductPage(
            html_hash_sha1=self._product_page.html_hash_sha1,
            location_id=self.location_id,
            location_name=self.location_name,
            products={product.id_: product for product in self.products},
        )

    def parse(
        self, page_html: Union[str, bytes, bytearray], force: bool = False
    ) -> None:
        """Parse HTML contents of a product page.

        After parsing, the product data can be accessed using:
        - `find_xx` parser methods;
        - `location_id`, `location_name`, `products`, and `product_page` parser
        properties.

        Args:
            page_html (Union[str, bytes, bytearray]): HTML contents of
                the product page.
            force (bool): If True, forces the parser to re-parse the HTML
                contents even if the hash of the contents matches the previous
                hash. If False, the parser will only re-parse the contents if
                the hash has changed.
        """
        html_hash_sha1 = hash_text_sha1(page_html)
        if force or html_hash_sha1 != self._product_page.html_hash_sha1:
            self._bs4_parser = bs4.BeautifulSoup(page_html, 'lxml')
            self._product_page = ProductPage(html_hash_sha1=html_hash_sha1)
            self._all_products_found = False

    def find_product_by_id(self, id_: int) -> Optional[Product]:
        """Find a single product based on the specified ID. The product ID
        is expected to be unique.

        Args:
            id_ (int): The ID of the product to filter by.

        Returns:
            Optional[Product]: A product with the specified ID. If the product
                is not found, returns None.
        """
        if id_ in self._product_page.products:  # found in cache
            product = self._product_page.products[id_]
            return product.model_copy(deep=True)  # copy for cache immutability
        if self._all_products_found:  # no new products to parse, cache is final
            return None
        product_data = self._find_product_data_by_id(id_)
        if product_data is None:
            return None
        product = self._parse_product_data(product_data)
        self._update_product_cache(product)
        return product

    def find_product_by_name(self, name: str) -> Optional[Product]:
        """Find a single product based on the specified name. The match is
        case-insensitive and can be partial. If multiple products match
        the name, the first one is returned.

        Args:
            name (str): The name of the product to filter by. Note that product
                names are normalized to lowercase ASCII characters.

        Returns:
            Optional[Product]: A product matching the specified name.
                If the product is not found, returns None. If multiple products
                match the name, the first one is returned.
        """
        product = self._product_page.find_product(
            lambda product: normalize_text(name) in normalize_text(product.name)
        )
        if product is not None:  # found in cache
            return product.model_copy(deep=True)  # copy for cache immutability
        if self._all_products_found:  # no new products to parse, cache is final
            return None
        product_data = self._find_product_data_by_name(name)
        if len(product_data) == 0:  # no products found in the HTML
            return None
        product = self._parse_product_data(product_data[0])  # first match
        self._update_product_cache(product)
        return product

    def find_products_by_name(self, name: str) -> List[Product]:
        """Find products based on the specified name. The match is
        case-insensitive and can be partial.

        Args:
            name (str): The name of the product to filter by. Note that product
                names are normalized to lowercase ASCII characters.

        Returns:
            List[Product]: Products matching the specified name. If no products
                are found, an empty list is returned.
        """
        if self._all_products_found:  # use cache if all products are parsed
            products = self._product_page.find_products(
                lambda product: normalize_text(name)
                in normalize_text(product.name)
            )
            # copy for cache immutability
            return [product.model_copy(deep=True) for product in products]
        products = []
        for product_data in self._find_product_data_by_name(name):
            product = self._parse_product_data(product_data)
            self._update_product_cache(product)
            products.append(product)
        return products


def parse_product_page(page_html: Union[str, bytes, bytearray]) -> ProductPage:
    """Parse the HTML contents of a FreshPoint.cz product web page
    (`my.freshpoint.cz/device/product-list/<pageId>`) and extract
    product information.

    Args:
        page_html (Union[str, bytes, bytearray]): HTML contents of the product
            page.

    Returns:
        ProductPage: The parsed product page data.
    """
    parser = ProductPageHTMLParser()
    parser.parse(page_html)
    return parser.product_page


class LocationPageHTMLParser:
    """Parses HTML contents of a FreshPoint.cz location web page
    (`my.freshpoint.cz`). Allows extracting the location page data and searching
    for locations by name or ID.

    Example:
    ```python
    parser = LocationPageHTMLParser()  # create a new parser instance

    parser.parse(page_html=...)  # parse the HTML contents

    location = parser.find_location_by_id(296)  # find a location by ID number
    print(location)  # print the found location data

    locations = parser.find_locations_by_name('praha')  # find locations by name
    for location in locations:
        print(location)

    page = parser.location_page  # get the parsed location page data
    print(len(page.locations))  # print the number of locations on the page
    ```
    """

    _RE_SEARCH_PATTERN_STR = re.compile(r'devices\s*=\s*("\[.*\]");')
    _RE_SEARCH_PATTERN_BYTES = re.compile(rb'devices\s*=\s*("\[.*\]");')

    def __init__(self) -> None:
        """Initialize a LocationPageHTMLParser instance with an empty state."""
        self._location_page = LocationPage()

    def _load_json(self, page_html: Union[str, bytes, bytearray]) -> List[Dict]:
        """Extract and parse the JSON location data embedded in the HTML.

        Args:
            page_html (str): The HTML content of the location page.

        Raises:
            ValueError: If the location data cannot be found or parsed.

        Returns:
            List[Dict]: A list of location data dictionaries.
        """
        if isinstance(page_html, str):
            match = re.search(self._RE_SEARCH_PATTERN_STR, page_html)
        else:
            match = re.search(self._RE_SEARCH_PATTERN_BYTES, page_html)
        if not match:
            raise ValueError(
                'Unable to find the location data in the HTML '
                '(regex pattern not matched).'
            )
        try:
            # double JSON parsing is required
            data = json.loads(json.loads(match.group(1)))
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

    @staticmethod
    def _parse_json(data: List[Dict]) -> LocationPage:
        """Convert the extracted JSON data into a structured LocationPage model.

        Args:
            data (List[Dict]): The extracted location data.

        Returns:
            LocationPage: The structured location page model.
        """
        data_processed = {
            'locations': {item['prop']['id']: item['prop'] for item in data}
        }
        return LocationPage.model_validate(data_processed)

    @property
    def locations(self) -> List[Location]:
        """All locations parsed from the page HTML contents."""
        # page is fully parsed on `parse` call. Copy for cache immutability
        return [
            location.model_copy(deep=True)
            for location in self._location_page.locations.values()
        ]

    @property
    def location_page(self) -> LocationPage:
        """The location page data parsed from the HTML contents."""
        # page is fully parsed on `parse` call. Copy for cache immutability
        return self._location_page.model_copy(deep=True)

    def parse(
        self, page_html: Union[str, bytes, bytearray], force: bool = False
    ) -> None:
        """Parse HTML contents of a location page.

        After parsing, the location data can be accessed using:
        - `find_location_by_xx` parser methods;
        - `locations` and `location_page` parser properties.

        Args:
            page_html (Union[str, bytes, bytearray]): HTML contents of
                the location page.
            force (bool): If True, forces the parser to re-parse the HTML
                contents even if the hash of the contents matches the previous
                hash. If False, the parser will only re-parse the contents if
                the hash has changed.
        """
        html_hash_sha1 = hash_text_sha1(page_html)
        if force or html_hash_sha1 != self._location_page.html_hash_sha1:
            json_data = self._load_json(page_html)
            self._location_page = self._parse_json(json_data)
            self._location_page.html_hash_sha1 = html_hash_sha1

    def find_location_by_id(self, id_: int) -> Optional[Location]:
        """Find a location by its unique identifier.

        Args:
            id_ (int): The unique ID of the location.

        Returns:
            Optional[Location]: The location with the specified ID.
                If the location is not found, returns None.
        """
        try:
            location = self._location_page.locations[id_]
            return location.model_copy(deep=True)  # copy for cache immutability
        except KeyError:
            return None

    def find_location_by_name(self, name: str) -> Optional[Location]:
        """Find a location by its name. The match is case-insensitive
        and can be partial.

        Args:
            name (str): The name of the location to search for.

        Returns:
            Optional[Location]: The location with the specified name.
                If the location is not found, returns None.
        """
        # wrapper over `LocationPage.find_location` method
        location = self._location_page.find_location(
            lambda location: normalize_text(name)
            in normalize_text(location.name)
        )
        if location is None:
            return None
        return location.model_copy(deep=True)  # copy for cache immutability

    def find_locations_by_name(self, name: str) -> List[Location]:
        """Find locations by their name. The match is case-insensitive
        and can be partial.

        Args:
            name (str): The name of the locations to search for.

        Returns:
            List[Location]: Locations with the specified name.
                If no locations are found, an empty list is returned.
        """
        # wrapper over `LocationPage.find_locations` method
        locations = self._location_page.find_locations(
            lambda location: normalize_text(name)
            in normalize_text(location.name)
        )
        # copy for cache immutability
        return [location.model_copy(deep=True) for location in locations]


def parse_location_page(
    page_html: Union[str, bytes, bytearray],
) -> LocationPage:
    """Parse the HTML contents of a FreshPoint.cz location web page
    (`my.freshpoint.cz`) and extract location information.

    Args:
        page_html (Union[str, bytes, bytearray]): HTML contents of the location
            page.

    Returns:
        LocationPage: The parsed location page data.
    """
    parser = LocationPageHTMLParser()
    parser.parse(page_html)
    return parser.location_page
