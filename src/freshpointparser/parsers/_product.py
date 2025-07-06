import html
import re
from typing import (
    Callable,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

import bs4

from .._utils import normalize_text, validate_id
from ..exceptions import (
    ParserAttributeError,
    ParserKeyError,
    ParserTypeError,
    ParserValueError,
)
from ..models import (
    Product,
    ProductPage,
)
from ._base import BasePageHTMLParser, logger

T = TypeVar('T')


class ProductHTMLParser:
    """A parser utility for extracting product information from HTML tags.

    This class provides static methods to parse various attributes of a product
    from its HTML representation. It's designed to work with BeautifulSoup
    `Tag` objects, extracting data such as product name, ID number, pricing,
    availability, etc.
    """

    _RE_PATTERN_FIND_QUANTITY = re.compile(
        r'^((posledni)|(\d+))\s(kus|kusy|kusu)!?$'
    )
    """Regex pattern to find the quantity of a product in the HTML string."""
    _RE_PATTERN_FIND_PRICE = re.compile(r'^\d+\.\d+$')
    """Regex pattern to find the price of a product in the HTML string."""

    @staticmethod
    def _extract_single_tag(resultset: bs4.ResultSet) -> bs4.Tag:
        """Get a single Tag in a ResultSet.

        Args:
            resultset (bs4.ResultSet): A `bs4.ResultSet` object
                expected to contain exactly one `bs4.Tag` object.

        Returns:
            bs4.Tag: The Tag contained in the provided `resultset`.

        Raises:
            ParserValueError: If `resultset` does not contain exactly one Tag.
            ParserTypeError: If the extracted element is not a `bs4.Tag` object.
        """
        if len(resultset) == 0:
            raise ParserValueError(
                'ResultSet is empty (expected one Tag element).'
            )
        if len(resultset) != 1:
            raise ParserValueError(
                f'Unexpected number of elements in the ResultSet'
                f'(expected 1, got {len(resultset)}).'
            )
        if not isinstance(resultset[0], bs4.Tag):
            raise ParserTypeError(
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
            ParserKeyError: If the attribute is missing.
            ParserValueError: If the attribute is not a string.
        """
        try:
            attr = tag[attr_name]
        except KeyError as err:
            raise ParserKeyError(
                f'Product attributes do not contain keyword "{attr_name}".'
            ) from err
        if not isinstance(attr, str):
            raise ParserValueError(
                f'Unexpected "{attr_name}" attribute parsing results: '
                f'attribute value is expected to be a string '
                f'(got type "{type(attr)}").'
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
            raise ParserAttributeError(
                f'Unable to extract product category name for product '
                f'"id={cls._find_id_safe(product_data)}" from the provided '
                f'html data (parent data is missing).'
            )
        # 'string=bool' filters out empty strings and None values
        category = product_data.parent.find_all(name='h2', string=bool)
        try:
            return cls._extract_single_tag(category).text.strip()  # type: ignore
        except Exception as exp:
            raise ParserValueError(
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
            ParserValueError: If an error occurs during the conversion process.
        """
        try:
            return converter()
        except Exception as exc:
            raise ParserValueError(
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
                        pattern=cls._RE_PATTERN_FIND_QUANTITY,
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
                        pattern=cls._RE_PATTERN_FIND_PRICE,
                        string=normalize_text(text),
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
                raise ParserValueError(
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
        raise ParserValueError(
            f'Unexpected number of elements in the ResultSet'
            f'(expected 1 or 2, got {len(result)}).'
        )


class ProductPageHTMLParser(BasePageHTMLParser[ProductPage]):
    """Parses HTML content of a FreshPoint product webpage
    `my.freshpoint.cz/device/product-list/<pageId>`. Allows accessing
    the parsed webpage data and searching for products by name or ID.
    """

    _RE_PATTERN_DEVICE_ID = re.compile(r'deviceId\s*=\s*"(.*?)"')
    """Regex pattern to search for the device ID in the HTML string."""

    def __init__(self) -> None:
        """Initialize a ProductPageHTMLParser instance with an empty state."""
        super().__init__()
        self._bs4_parser = bs4.BeautifulSoup()
        self._page = ProductPage()
        self._all_products_found: bool = False

    def _parse_page_html(self, page_html: Union[str, bytes]) -> None:
        """Parse HTML content of a product page.

        This method initializes the BeautifulSoup parser with the provided
        HTML content and invalidates the cached page data.

        Args:
            page_html (Union[str, bytes]): HTML content of
                the product page to parse.
        """
        self._bs4_parser = bs4.BeautifulSoup(page_html, 'lxml')
        self._page = ProductPage()
        self._all_products_found = False

    def _construct_page(self) -> ProductPage:
        """Return the product page data parsed from the HTML content.

        A new :class:`ProductPage` model is created on each call using the
        cached product list and metadata. Modifying the returned instance does
        not change the parser's internal cache. The data is cached after the
        first extraction until the page HTML changes. If parsing fails,
        a ValueError is raised.

        Returns:
            ProductPage: Parsed and validated page data.
        """
        return ProductPage(
            recorded_at=self._parse_datetime,
            items={product.id_: product for product in self.products},
            location_id=self.location_id,
            location_name=self.location_name,
        )

    def _find_product_data(self) -> bs4.ResultSet[bs4.Tag]:
        """Find all product data elements in the page HTML.

        Returns:
            bs4.ResultSet: A ResultSet containing the data of all products
                as Tags.
        """
        result = self._bs4_parser.find_all('div', class_='product')
        return result  # type: ignore

    def _find_product_data_by_id(self, id_: int) -> Optional[bs4.Tag]:
        """Find product data matching in the page HTML the specified ID.
        The data is checked for uniqueness.

        Args:
            id_ (int): The ID of the product to search for.

        Raises:
            ParserValueError: If the product with the specified ID is not unique.

        Returns:
            Optional[bs4.Tag]: A Tag containing the data of the matched product.
                If the product is not found, returns None.
        """

        def attr_filter_id(value: str) -> bool:
            if not value:
                return False  # assuming zero is not a valid ID
            try:
                return int(value) == id_
            except (ValueError, TypeError) as e:
                raise ParserValueError(
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
            raise ParserValueError(f'ID="{id_}" is not unique.')
        return result[0]  # type: ignore

    def _find_product_data_by_name(
        self, name: str, partial_match: bool
    ) -> bs4.ResultSet[bs4.Tag]:
        """Find product data in the page HTML matching the specified name.

        Args:
            name (str): The name of the product(s) to search for.
            partial_match (bool): If True, the name match can be partial
                (case-insensitive). If False, the name match must be exact
                (case-insensitive).

        Returns:
            bs4.ResultSet: The ResultSet containing the data of the matched
                products as Tags.
        """

        def attr_filter_name(value: str) -> bool:
            try:
                return self._match_strings(name, value, partial_match)
            except ParserTypeError as exc:
                raise exc
            except Exception as e:
                raise ParserValueError(
                    f'Unable to parse the product name "{value}".'
                ) from e

        result = self._bs4_parser.find_all(
            'div',
            class_='product',
            attrs={'data-name': attr_filter_name},
        )
        return result  # type: ignore

    def _parse_product_data(self, data: bs4.Tag) -> Product:
        """Parse the product data to a Product model.

        Args:
            data (bs4.Tag): The Tag containing the product data.

        Returns:
            Product: An instance of the Product model
                containing the parsed and validated data.
        """
        price_full, price_curr = ProductHTMLParser.find_price(data)
        return Product(
            recorded_at=self._parse_datetime,
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
        self._page.items[product.id_] = product.model_copy(deep=True)

    @property
    def location_id(self) -> int:
        """ID number of the location (also known as the page ID or
        the device ID) extracted from the page HTML content.

        The value is cached after the first extraction until the page HTML
        changes. If the value cannot be parsed, a ParserValueError is raised.
        """
        if 'location_id' in self._page.model_fields_set:  # cached
            return self._page.location_id
        script_tag = self._bs4_parser.find(
            name='script', string=self._RE_PATTERN_DEVICE_ID
        )
        if not script_tag:
            raise ParserValueError(
                'Unable to parse page ID '
                '(<script/> tag with "deviceId" text was not found).'
            )
        match = re.search(
            pattern=self._RE_PATTERN_DEVICE_ID, string=script_tag.get_text()
        )
        if not match:
            raise ParserValueError(
                'Unable to parse page ID ("deviceId" text '
                'within the <script/> tag was not matched).'
            )
        try:
            location_id = int(match.group(1))
            self._page.location_id = location_id
            return location_id
        except Exception as e:
            raise ParserValueError('Unable to parse page ID.') from e

    @property
    def location_name(self) -> str:
        """The name of the location (also known as the page title) extracted
        from the page HTML content.

        The value is cached after the first extraction until the page HTML
        changes. If the value cannot be parsed, a ParserValueError is raised.
        """
        if 'location_name' in self._page.model_fields_set:  # cached
            return self._page.location_name
        title_tag = self._bs4_parser.find('title')
        if not title_tag:
            raise ParserValueError(
                'Unable to parse location name (<title/> tag  was not found).'
            )
        title_text = title_tag.get_text()
        try:
            location_name = title_text.split('|')[0].strip()
            self._page.location_name = location_name
            return location_name
        except Exception as e:
            raise ParserValueError('Unable to parse location name.') from e

    @property
    def products(self) -> List[Product]:
        """All products parsed and validated from the page HTML content.

        The data is cached after the first extraction until the page HTML
        changes. The returned ``Product`` instances are detached from the
        parser's cached data, so mutating them does not affect the parser's
        state.
        """
        if self._all_products_found:
            return [
                product.model_copy(deep=True)  # copy for cache immutability
                for product in self._page.items.values()
            ]
        products = []
        for product_data in self._find_product_data():
            product_id = ProductHTMLParser.find_id(product_data)
            if product_id in self._page.items:
                product = self._page.items[product_id]
                product = product.model_copy(deep=True)
            else:
                product = self._parse_product_data(product_data)
                self._update_product_cache(product)
            products.append(product)
        self._all_products_found = True
        return products

    def find_product_by_id(self, id_: Union[int, str]) -> Optional[Product]:
        """Find a single product based on the specified ID.

        Args:
            id_ (Union[int, str]): The ID of the product to search for.
                The ID is expected to be a unique non-negative integer or
                a string representation of a non-negative integer.

        Raises:
            ParserValueError: If the ID is an integer but is negative.
            ParserTypeError: If the ID is not an integer and cannot be
                converted to an integer.

        Returns:
            Optional[Product]: Product with the specified ID or ``None`` if it
            is not found. The returned instance is independent of the parser's
            cached data.
        """
        try:
            id_ = validate_id(id_)
        except ValueError as exc:
            raise ParserValueError(str(exc)) from exc
        except TypeError as exc:
            raise ParserTypeError(str(exc)) from exc
        product = self._page.items.get(id_)
        if product is not None:  # found in cache
            return product.model_copy(deep=True)  # copy for cache immutability
        if self._all_products_found:  # no new products to parse, cache is final
            return None
        product_data = self._find_product_data_by_id(id_)
        if product_data is None:  # not found in the HTML
            return None
        product = self._parse_product_data(product_data)
        self._update_product_cache(product)
        return product

    def find_product_by_name(
        self, name: str, partial_match: bool = True
    ) -> Optional[Product]:
        """Find a single product based on the specified name.

        Args:
            name (str): The name of the product to search for. Note that product
                names are normalized to lowercase ASCII characters. The match
                is case-insensitive and ignores diacritics regardless of the
                `partial_match` value.
            partial_match (bool): If True, the name match can be partial
                (case-insensitive). If False, the name match must be exact
                (case-insensitive). Defaults to True.

        Raises:
            ParserTypeError: If the product name is not a string.

        Returns:
            Optional[Product]: Product matching the specified name or ``None``
            if no product is found. The returned instance does not modify the
            parser's cached data. If multiple products match, the first one is
            returned.
        """
        if not isinstance(name, str):
            raise ParserTypeError(
                f'Expected a string for product name, got {type(name)}.'
            )
        product = self._page.find_item(
            lambda pr: self._match_strings(name, pr.name, partial_match)
        )
        if product is not None:  # found in cache
            return product.model_copy(deep=True)  # copy for cache immutability
        if self._all_products_found:  # no new products to parse, cache is final
            return None
        product_data = self._find_product_data_by_name(name, partial_match)
        if len(product_data) == 0:  # no products found in the HTML
            return None
        product = self._parse_product_data(product_data[0])  # first match
        self._update_product_cache(product)
        return product

    def find_products_by_name(
        self, name: str, partial_match: bool = True
    ) -> List[Product]:
        """Find all products that match the specified name.

        Args:
            name (str): The name of the product to filter by. Note that product
                names are normalized to lowercase ASCII characters. The match
                is case-insensitive and ignores diacritics regardless of the
                `partial_match` value.
            partial_match (bool): If True, the name match can be partial
                (case-insensitive). If False, the name match must be exact
                (case-insensitive). Defaults to True.

        Raises:
            TypeError: If the product name is not a string.

        Returns:
            List[Product]: Products matching the specified name. Items in
            the returned list are independent of the parser's cache. If no
            products are found, an empty list is returned.
        """
        if not isinstance(name, str):
            raise ParserTypeError(
                f'Expected a string for product name, got {type(name)}.'
            )
        if self._all_products_found:  # use cache if all products are parsed
            iter_products = self._page.find_items(
                lambda pr: self._match_strings(name, pr.name, partial_match)
            )
            # copy for cache immutability
            return [product.model_copy(deep=True) for product in iter_products]
        products = []
        product_data_tags = self._find_product_data_by_name(name, partial_match)
        for product_data in product_data_tags:
            product = self._parse_product_data(product_data)
            self._update_product_cache(product)
            products.append(product)
        return products


def parse_product_page(page_html: Union[str, bytes]) -> ProductPage:
    """Parse the HTML content of a FreshPoint product webpage
    `my.freshpoint.cz/device/product-list/<pageId>` to a structured
    ProductPage model.

    Args:
        page_html (Union[str, bytes]): HTML content of the product page to parse.

    Raises:
        ParserError: If the HTML content cannot be parsed or does not
            contain the expected structure.

    Returns:
        ProductPage: Parsed and validated product page data.
    """
    parser = ProductPageHTMLParser()
    parser.parse(page_html)
    return parser.page
