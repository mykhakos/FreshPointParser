import html
import re
from typing import Callable, List, Tuple, TypeVar, Union

import bs4

from .._utils import normalize_text
from ..exceptions import FreshPointParserKeyError, FreshPointParserValueError
from ..models import Product, ProductPage
from ._base import BasePageHTMLParser, ParseContext, ParseResult, logger

T = TypeVar('T')


class ProductHTMLParser:
    """A parser utility for extracting product information from HTML tags.

    This class provides static methods to parse various attributes of a product
    from its HTML representation. It's designed to work with BeautifulSoup
    ``Tag`` objects, extracting data such as product name, ID number, pricing,
    availability, etc.
    """

    _RE_PATTERN_FIND_QUANTITY = re.compile(r'^((posledni)|(\d+))\s(kus|kusy|kusu)!?$')
    """Regex pattern to find the quantity of a product in the HTML string."""
    _RE_PATTERN_FIND_PRICE = re.compile(r'^\d+\.\d+$')
    """Regex pattern to find the price of a product in the HTML string."""

    @staticmethod
    def _get_attr_value(attr_name: str, tag: bs4.Tag) -> str:
        """Get the value of a specified attribute from a Tag.

        Args:
            attr_name (str): The name of the attribute to retrieve.
            tag (bs4.Tag): The Tag to extract the attribute from.

        Returns:
            str: The value of the specified attribute.

        Raises:
            FreshPointParserKeyError: If the attribute is missing.
            FreshPointParserValueError: If the attribute is not a string.
        """
        try:
            attr = tag[attr_name]
        except KeyError as err:
            raise FreshPointParserKeyError(
                f'Product attributes do not contain keyword "{attr_name}".'
            ) from err
        if not isinstance(attr, str):
            raise FreshPointParserValueError(
                f'Unexpected "{attr_name}" attribute parsing results: '
                f'attribute value is expected to be a string '
                f'(got type "{type(attr)}").'
            )
        return attr.strip()

    @classmethod
    def _find_id_safe(cls, product_data: bs4.Tag) -> str:
        """Extract the product ID number from the given product data. If the ID
        is not found, catch the raised exception and return a placeholder.
        """
        try:
            return str(cls.find_id(product_data))
        except Exception as e:
            logger.warning(
                f'Unable to extract product ID from the provided html data ({e}).'
            )
            return '?'

    @classmethod
    def _run_converter(cls, converter: Callable[[], T], product_data: bs4.Tag) -> T:
        """Run the given converter function and return the converted value.

        Args:
            converter (Callable[[], T]): The converter function
                to be executed.
            product_data (bs4.Tag): The product data to be passed to
                the converter function.

        Returns:
            T: The converted value.

        Raises:
            FreshPointParserValueError: If an error occurs during the conversion process.
        """
        try:
            return converter()
        except Exception as exc:
            raise FreshPointParserValueError(
                f'Unable to convert a parsed value for the product '
                f'"id={cls._find_id_safe(product_data)}".'
            ) from exc

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
        category_tag = product_data.find_previous('h2')
        if category_tag is None:
            raise FreshPointParserValueError(
                f'Unable to extract product category name for product '
                f'"id={cls._find_id_safe(product_data)}" from the provided '
                f'html data (no preceding <h2/> tag found).'
            )
        category = category_tag.get_text(strip=True)
        if not category:
            raise FreshPointParserValueError(
                f'Unable to extract product category name for product '
                f'"id={cls._find_id_safe(product_data)}" from the provided '
                f'html data (the preceding <h2/> tag is empty).'
            )
        return category

    @classmethod
    def find_quantity(cls, product_data: bs4.Tag) -> int:
        """Extract the quantity of the product from the given product data."""
        if 'sold-out' in product_data.attrs.get('class', {}):
            return 0
        quantity = product_data.find_next(
            string=(
                lambda text: bool(
                    text and cls._RE_PATTERN_FIND_QUANTITY.match(normalize_text(text))
                )
            ),
        )
        if not quantity:  # sold out products don't have the quantity text
            return 0  # (should be caught by the "sold-out" check above)
        quantity = normalize_text(quantity)
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
        prices = product_data.find_all(
            string=(
                lambda text: bool(
                    text and cls._RE_PATTERN_FIND_PRICE.match(normalize_text(text))
                )
            ),
        )
        if len(prices) == 1:
            price_full = cls._run_converter(
                lambda: float(prices[0]),
                product_data,  # price_full_str
            )
            return price_full, price_full
        if len(prices) == 2:
            price_full = cls._run_converter(
                lambda: float(prices[0]),
                product_data,  # price_full_str
            )
            price_curr = cls._run_converter(
                lambda: float(prices[1]),
                product_data,  # price_curr_str
            )
            if price_curr > price_full:
                id_ = cls._find_id_safe(product_data)
                raise FreshPointParserValueError(
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
        raise FreshPointParserValueError(
            f'Unexpected number of elements in the ResultSet'
            f'(expected 1 or 2, got {len(prices)}).'
        )


class ProductPageHTMLParser(BasePageHTMLParser[ProductPage]):
    """Parses HTML content of a FreshPoint product webpage
    ``my.freshpoint.cz/device/product-list/<pageId>``.
    """

    _RE_PATTERN_DEVICE_ID = re.compile(r'deviceId\s*=\s*\"(.*?)\"')
    """Regex pattern to search for the device ID in the HTML string."""

    def __init__(self) -> None:
        """Initialize a ProductPageHTMLParser instance with an empty state."""
        super().__init__()
        self._bs4_parser = bs4.BeautifulSoup()

    def _parse_product(self, product_data: bs4.Tag, context: ParseContext) -> Product:
        """Parse the a single product item to a Product model.

        Args:
            product_data (bs4.Tag): The Tag containing the product data.
            context (ParseContext): Parsing context containing metadata.

        Returns:
            Product: Parsed and validated Product model instance.
        """
        parsed_data = self._new_base_record_data_from_context(context)

        location_id = self._safe_parse(self.parse_location_id, context)
        if location_id is not None:
            parsed_data['location_id'] = location_id

        for field, parser in (
            ('id_', ProductHTMLParser.find_id),
            ('name', ProductHTMLParser.find_name),
            ('category', ProductHTMLParser.find_category),
            ('is_vegetarian', ProductHTMLParser.find_is_vegetarian),
            ('is_gluten_free', ProductHTMLParser.find_is_gluten_free),
            ('is_promo', ProductHTMLParser.find_is_promo),
            ('quantity', ProductHTMLParser.find_quantity),
            ('info', ProductHTMLParser.find_info),
            ('pic_url', ProductHTMLParser.find_pic_url),
        ):
            value = self._safe_parse(parser, context, product_data=product_data)
            if value is not None:
                parsed_data[field] = value

        value = self._safe_parse(
            ProductHTMLParser.find_price, context, product_data=product_data
        )
        if value is not None:
            parsed_data['price_full'] = value[0]
            parsed_data['price_curr'] = value[1]

        return Product.model_validate(parsed_data, context=context)

    def _parse_products(self, context: ParseContext) -> List[Product]:
        """Parse all products from the page HTML content.

        Args:
            context (ParseContext): Parsing context containing metadata.

        Returns:
            List[Product]: Parsed and validated Product model instances.
        """
        products = []
        for product_data in self._bs4_parser.find_all('div', class_='product'):
            product = self._safe_parse(
                self._parse_product,
                context,
                product_data=product_data,
                context=context,
            )
            if product is not None:
                products.append(product)
        return products

    def _parse_page_content(
        self, page_content: Union[str, bytes], context: ParseContext
    ) -> ProductPage:
        """Parse the HTML content of a product page to a Pydantic model.

        A new BeautifulSoup parser is initialized with the provided HTML content.

        Args:
            page_content (Union[str, bytes]): HTML content of
                the product page to parse.
            context (ParseContext): Parsing context containing metadata.
        """
        self._bs4_parser = bs4.BeautifulSoup(page_content, 'lxml')

        parsed_data = self._new_base_record_data_from_context(context)

        location_id = self._safe_parse(self.parse_location_id, context)
        if location_id is not None:
            parsed_data['location_id'] = location_id

        location_name = self._safe_parse(self.parse_location_name, context)
        if location_name is not None:
            parsed_data['location_name'] = location_name

        items = self._safe_parse(self._parse_products, context, context=context)
        if items is not None:
            parsed_data['items'] = items

        return ProductPage.model_validate(parsed_data, context=context)

    def parse_location_id(self) -> int:
        """Extract the ID number of the location (also known as the page ID or
        the device ID) from the page HTML content.

        Raises:
            FreshPointParserValueError: If the page ID cannot be parsed.

        Returns:
            int: The ID number of the location.
        """
        script = self._bs4_parser.find(string=self._RE_PATTERN_DEVICE_ID)
        if script is None:
            raise FreshPointParserValueError(
                'Unable to parse page ID '
                '(script tag with "deviceId" text was not found).'
            )
        match = self._RE_PATTERN_DEVICE_ID.search(script)
        if not match:
            raise FreshPointParserValueError(
                'Unable to parse page ID '
                '("deviceId" text within the script tag was not matched).'
            )
        try:
            return int(match.group(1))
        except Exception as e:
            raise FreshPointParserValueError('Unable to parse page ID.') from e

    def parse_location_name(self) -> str:
        """Extract the name of the location (also known as the page title)
        from the page HTML content.

        Raises:
            FreshPointParserValueError: If the location name cannot be parsed.

        Returns:
            str: The name of the location.
        """
        title_tag = self._bs4_parser.find('title')
        if not title_tag:
            raise FreshPointParserValueError(
                'Unable to parse location name (<title/> tag  was not found).'
            )
        try:
            return title_tag.get_text().split('|')[0].strip()
        except Exception as e:
            raise FreshPointParserValueError('Unable to parse location name.') from e


def parse_product_page(page_content: Union[str, bytes]) -> ParseResult[ProductPage]:
    """Parse the HTML content of a FreshPoint product webpage
    ``my.freshpoint.cz/device/product-list/<pageId>`` to a structured
    ProductPage model.

    Args:
        page_content (Union[str, bytes]): HTML content of the product page.

    Returns:
        ParseResult[ProductPage]: Parse result containing the page data and metadata.
            Access the page via result.page, metadata via result.metadata.
    """
    return ProductPageHTMLParser().parse(page_content)
