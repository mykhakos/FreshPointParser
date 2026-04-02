import html
import re
from typing import List, Tuple, Union

import bs4

from .._utils import normalize_text
from ..exceptions import ParseError
from ..models import Product, ProductPage
from ._base import BasePageHTMLParser, ParseResult, logger


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

    @classmethod
    def _find_id_safe(cls, product_data: bs4.Tag) -> str:
        """Extract the product ID number from the given product data. If the ID
        is not found, catch the raised exception and return a placeholder.
        """
        try:
            return product_data['data-id']  # type: ignore[return-value]
        except Exception as exc:
            logger.warning(
                'Unable to extract product ID from the provided html data (%s).', exc
            )
            return '?'

    @classmethod
    def _get_attr_value(cls, attr_name: str, tag: bs4.Tag) -> str:
        """Get the value of a specified attribute from a Tag.

        Args:
            attr_name (str): The name of the attribute to retrieve.
            tag (bs4.Tag): The Tag to extract the attribute from.

        Returns:
            str: The value of the specified attribute.

        Raises:
            ParseError: If the attribute is missing or
                the attribute value cannot be converted to a string.
        """
        try:
            attr = tag[attr_name]
        except KeyError as err:
            raise ParseError(
                f"Data of product with id='{cls._find_id_safe(tag)}' "
                f"does not contain keyword '{attr_name}'."
            ) from err
        return str(attr).strip()

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
        """Determine whether the product is being promoted from the given product data."""
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
    def find_allergens(cls, product_data: bs4.Tag) -> List[str]:
        """Extract allergen information from the given product data."""
        raw = html.unescape(cls._get_attr_value('data-allergens', product_data))
        if not raw:
            return []
        return [a.strip() for a in raw.split(',') if a.strip()]

    @classmethod
    def find_pic_url(cls, product_data: bs4.Tag) -> str:
        """Extract the URL of the product's picture from the given product data."""
        return cls._get_attr_value('data-photourl', product_data)

    @classmethod
    def find_category(cls, product_data: bs4.Tag) -> str:
        """Extract the product category from the given product data."""
        category_tag = product_data.find_previous('h2')
        if category_tag is None:
            raise ParseError(
                f'Unable to extract product category name for product '
                f'"id={cls._find_id_safe(product_data)}" from the provided '
                f'html data (no preceding <h2/> tag found).'
            )
        category = category_tag.get_text(strip=True)
        if not category:
            raise ParseError(
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
        quantity_str = normalize_text(quantity)
        if 'posledn' in quantity_str:  # products that have only 1 item in stock
            return 1  # have "posledni" in the quantity text
        return int(quantity_str.split()[0])  # regular ("2 kusy", "5 kusu")

    @classmethod
    def find_price(cls, product_data: bs4.Tag) -> Tuple[float, float]:
        """Extract the full and current price of the product from the given product data."""
        prices = product_data.find_all(
            string=(
                lambda text: bool(
                    text and cls._RE_PATTERN_FIND_PRICE.match(normalize_text(text))
                )
            ),
        )
        if len(prices) == 1:
            price_full = float(prices[0])
            return price_full, price_full
        if len(prices) == 2:
            price_full = float(prices[0])
            price_curr = float(prices[1])
            if price_curr > price_full:
                id_ = cls._find_id_safe(product_data)
                raise ParseError(
                    f'Unexpected product "id={id_}" parsing results: '
                    f'current price "{price_curr}" is greater than '
                    f'the regular full price "{price_full}".'
                )
            # Note: price_curr < price_full does not require is_promo to be set.
            # data-isPromo is unreliable and does not reliably correlate with discounts.
            return price_full, price_curr
        raise ParseError(
            f'Unexpected number of elements in the ResultSet'
            f'(expected 1 or 2, got {len(prices)}).'
        )


class ProductPageHTMLParser(BasePageHTMLParser[ProductPage]):
    """Parses HTML content of a FreshPoint product webpage
    ``my.freshpoint.cz/device/product-list/<pageId>``.
    """

    _RE_PATTERN_DEVICE_ID = re.compile(r'deviceId\s*=\s*\"(.*?)\"')
    """Regex pattern to search for the device ID in the HTML string."""

    def _parse_location_id(self, bs4_parser: bs4.BeautifulSoup) -> str:
        """Extract the ID number of the location (also known as the page ID or
        the device ID) from the page HTML content.

        Args:
            bs4_parser (bs4.BeautifulSoup): The BeautifulSoup parser
                initialized with the page HTML content.

        Returns:
            str: The ID number of the location.

        Raises:
            ParseError: If the page ID cannot be parsed.
        """
        script = bs4_parser.find(string=self._RE_PATTERN_DEVICE_ID)
        if script is None:
            raise ParseError(
                'Unable to parse page ID '
                '(script tag with "deviceId" text was not found).'
            )
        match = self._RE_PATTERN_DEVICE_ID.search(script)
        if not match:
            raise ParseError(
                'Unable to parse page ID '
                '("deviceId" text within the script tag was not matched).'
            )
        try:
            return str(match.group(1))
        except Exception as exc:
            raise ParseError('Unable to parse page ID.') from exc

    def _parse_location_name(self, bs4_parser: bs4.BeautifulSoup) -> str:  # noqa: PLR6301
        """Extract the name of the location (also known as the page title)
        from the page HTML content.

        Args:
            bs4_parser (bs4.BeautifulSoup): The BeautifulSoup parser
                initialized with the page HTML content.

        Returns:
            str: The name of the location.

        Raises:
            ParseError: If the location name cannot be parsed.
        """
        title_tag = bs4_parser.find('title')
        if not title_tag:
            raise ParseError(
                'Unable to parse location name (<title/> tag  was not found).'
            )
        try:
            return title_tag.get_text().split('|')[0].strip()
        except Exception as exc:
            raise ParseError('Unable to parse location name.') from exc

    def _parse_product(self, product_data: bs4.Tag) -> Product:
        """Parse the a single product item to a Product model.

        Args:
            product_data (bs4.Tag): The Tag containing the product data.


        Returns:
            Product: Parsed and validated Product model instance.
        """
        parsed_data = {}

        for field, parser_func in (
            ('id_', ProductHTMLParser.find_id),
            ('name', ProductHTMLParser.find_name),
            ('category', ProductHTMLParser.find_category),
            ('is_vegetarian', ProductHTMLParser.find_is_vegetarian),
            ('is_gluten_free', ProductHTMLParser.find_is_gluten_free),
            ('is_promo', ProductHTMLParser.find_is_promo),
            ('quantity', ProductHTMLParser.find_quantity),
            ('info', ProductHTMLParser.find_info),
            ('allergens', ProductHTMLParser.find_allergens),
            ('pic_url', ProductHTMLParser.find_pic_url),
        ):
            value = self._safe_parse(parser_func, product_data=product_data)
            if value is not None:
                parsed_data[field] = value

        value = self._safe_parse(
            ProductHTMLParser.find_price, product_data=product_data
        )
        if value is not None:
            parsed_data['price_full'] = value[0]
            parsed_data['price_curr'] = value[1]

        return Product.model_validate(parsed_data, context=self._context)

    def _parse_products(self, bs4_parser: bs4.BeautifulSoup) -> List[Product]:
        """Parse all products from the page HTML content.

        Args:
            bs4_parser (bs4.BeautifulSoup): The BeautifulSoup parser
                initialized with the page HTML content.

        Returns:
            List[Product]: Parsed and validated Product model instances.
        """
        products = []
        for product_data in bs4_parser.find_all('div', class_='product'):
            product = self._safe_parse(self._parse_product, product_data=product_data)
            if product is not None:
                products.append(product)
        logger.debug('Parsed %d product(s).', len(products))
        return products

    def _parse_page_content(self, page_content: Union[str, bytes]) -> ProductPage:
        """Parse the HTML content of a product page to a Pydantic model.

        A new BeautifulSoup parser is initialized with the provided HTML content.

        Args:
            page_content (Union[str, bytes]): HTML content of
                the product page to parse.
        """
        parsed_data = {'recorded_at': self._context.parsed_at}

        bs4_parser = bs4.BeautifulSoup(page_content, 'lxml')

        location_id = self._safe_parse(self._parse_location_id, bs4_parser=bs4_parser)
        if location_id is not None:
            parsed_data['location_id'] = location_id

        location_name = self._safe_parse(
            self._parse_location_name, bs4_parser=bs4_parser
        )
        if location_name is not None:
            parsed_data['location_name'] = location_name

        products = self._safe_parse(self._parse_products, bs4_parser=bs4_parser)
        if products is not None:
            parsed_data['items'] = products

        logger.debug(
            "Product page parsed: location_id='%s', location_name='%s', products=%d.",
            parsed_data.get('location_id'),
            parsed_data.get('location_name'),
            len(products) if products is not None else 0,
        )
        return ProductPage.model_validate(parsed_data, context=self._context)


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
