import logging
import os

import bs4
import pytest
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from freshpointparser import parse_product_page
from freshpointparser.exceptions import (
    FreshPointParserKeyError,
    FreshPointParserValueError,
)
from freshpointparser.models import Product, ProductPage
from freshpointparser.parsers import ProductPageHTMLParser
from freshpointparser.parsers._base import ParseContext
from freshpointparser.parsers._product import ProductHTMLParser

logger = logging.getLogger(__name__)


class ProductPageMeta(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    product_page_location_id: str
    product_page_location_name: str
    product_quantity_total: int
    product_quantity_available: int
    product_quantity_is_vegetarian: int
    product_quantity_is_gluten_free: int
    product_quantity_is_promo: int
    product_quantity_is_on_sale: int


@pytest.fixture(scope='session')
def product_page_html_content():
    path = os.path.join(os.path.dirname(__file__), 'product_page.html')
    with open(path, encoding='utf-8') as file:
        page_html_content = file.read()
    return page_html_content


@pytest.fixture(scope='session')
def product_page_json_content():
    path = os.path.join(os.path.dirname(__file__), 'product_page.json')
    with open(path, encoding='utf-8') as file:
        page_json_content = file.read()
    return page_json_content


@pytest.fixture(scope='session')
def product_page_metadata_json_content():
    path = os.path.join(os.path.dirname(__file__), 'product_page_meta.json')
    with open(path, encoding='utf-8') as file:
        page_metadata_json_content = file.read()
    return page_metadata_json_content


@pytest.fixture(scope='session')
def product_page_html_parser_persistent(product_page_html_content):
    parser = ProductPageHTMLParser()
    parser.parse(product_page_html_content)
    return parser


@pytest.fixture(scope='function')
def product_page_html_parser_new(product_page_html_content):
    parser = ProductPageHTMLParser()
    parser.parse(product_page_html_content)
    return parser


@pytest.fixture(scope='session')
def product_page(product_page_json_content):
    return ProductPage.model_validate_json(product_page_json_content)


@pytest.fixture(scope='session')
def product_page_expected_meta(product_page_metadata_json_content):
    return ProductPageMeta.model_validate_json(product_page_metadata_json_content)


# region ProductHTMLParser tests


def test_find_name_success():
    """Test extracting product name from tag."""
    tag = bs4.BeautifulSoup('<div data-name="Test Product"></div>', 'lxml').div
    assert tag is not None
    name = ProductHTMLParser.find_name(tag)
    assert name == 'Test Product'


def test_find_name_with_html_entities():
    """Test extracting product name with HTML entities."""
    tag = bs4.BeautifulSoup('<div data-name="Test &amp; Product"></div>', 'lxml').div
    assert tag is not None
    name = ProductHTMLParser.find_name(tag)
    assert name == 'Test & Product'


def test_find_name_missing_attribute():
    """Test error when data-name attribute is missing."""
    tag = bs4.BeautifulSoup('<div></div>', 'lxml').div
    with pytest.raises(FreshPointParserKeyError) as exc_info:
        ProductHTMLParser.find_name(tag)  # type: ignore
    assert 'data-name' in str(exc_info.value)


def test_find_id_success():
    """Test extracting product ID."""
    tag = bs4.BeautifulSoup('<div data-id="12345"></div>', 'lxml').div
    assert tag is not None
    id_ = ProductHTMLParser.find_id(tag)
    assert id_ == 12345
    assert isinstance(id_, int)


def test_find_id_missing_attribute():
    """Test error when data-id attribute is missing."""
    tag = bs4.BeautifulSoup('<div></div>', 'lxml').div
    assert tag is not None
    with pytest.raises(FreshPointParserKeyError):
        ProductHTMLParser.find_id(tag)


def test_find_is_vegetarian_true():
    """Test vegetarian flag when set to '1'."""
    tag = bs4.BeautifulSoup('<div data-veggie="1"></div>', 'lxml').div
    assert tag is not None
    assert ProductHTMLParser.find_is_vegetarian(tag) is True


def test_find_is_vegetarian_false():
    """Test vegetarian flag when set to '0'."""
    tag = bs4.BeautifulSoup('<div data-veggie="0"></div>', 'lxml').div
    assert tag is not None
    assert ProductHTMLParser.find_is_vegetarian(tag) is False


def test_find_is_gluten_free_true():
    """Test gluten-free flag when set to '1'."""
    tag = bs4.BeautifulSoup('<div data-glutenfree="1"></div>', 'lxml').div
    assert tag is not None
    assert ProductHTMLParser.find_is_gluten_free(tag) is True


def test_find_is_gluten_free_false():
    """Test gluten-free flag when set to '0'."""
    tag = bs4.BeautifulSoup('<div data-glutenfree="0"></div>', 'lxml').div
    assert tag is not None
    assert ProductHTMLParser.find_is_gluten_free(tag) is False


def test_find_is_promo_true():
    """Test promo flag when set to '1'."""
    tag = bs4.BeautifulSoup('<div data-ispromo="1"></div>', 'lxml').div
    assert tag is not None
    assert ProductHTMLParser.find_is_promo(tag) is True


def test_find_is_promo_false():
    """Test promo flag when set to '0'."""
    tag = bs4.BeautifulSoup('<div data-ispromo="0"></div>', 'lxml').div
    assert tag is not None
    assert ProductHTMLParser.find_is_promo(tag) is False


def test_find_info_simple():
    """Test extracting product info."""
    tag = bs4.BeautifulSoup('<div data-info="Product info"></div>', 'lxml').div
    assert tag is not None
    info = ProductHTMLParser.find_info(tag)
    assert info == 'Product info'


def test_find_info_with_line_breaks():
    """Test extracting product info with line breaks."""
    tag = bs4.BeautifulSoup(
        '<div data-info="Line 1<br />\\nLine 2<br />\\n\\nLine 3"></div>', 'lxml'
    ).div
    assert tag is not None
    info = ProductHTMLParser.find_info(tag)
    assert 'Line 1' in info
    assert 'Line 2' in info
    assert 'Line 3' in info


def test_find_pic_url_success():
    """Test extracting product picture URL."""
    tag = bs4.BeautifulSoup(
        '<div data-photourl="https://example.com/pic.jpg"></div>', 'lxml'
    ).div
    assert tag is not None
    url = ProductHTMLParser.find_pic_url(tag)
    assert url == 'https://example.com/pic.jpg'


def test_find_category_success():
    """Test extracting product category from preceding h2."""
    soup = bs4.BeautifulSoup('<h2>Category Name</h2><div data-id="1"></div>', 'lxml')
    tag = soup.find('div')
    assert tag is not None
    category = ProductHTMLParser.find_category(tag)
    assert category == 'Category Name'


def test_find_category_missing_h2():
    """Test error when no preceding h2 tag exists."""
    tag = bs4.BeautifulSoup('<div data-id="1"></div>', 'lxml').div
    with pytest.raises(FreshPointParserValueError) as exc_info:
        ProductHTMLParser.find_category(tag)  # type: ignore
    assert 'no preceding <h2/> tag' in str(exc_info.value)


def test_find_category_empty_h2():
    """Test error when preceding h2 tag is empty."""
    soup = bs4.BeautifulSoup('<h2>  </h2><div data-id="1"></div>', 'lxml')
    tag = soup.find('div')
    with pytest.raises(FreshPointParserValueError) as exc_info:
        ProductHTMLParser.find_category(tag)  # type: ignore
    assert 'empty' in str(exc_info.value)


def test_find_quantity_sold_out_with_class():
    """Test quantity is 0 when product has sold-out class."""
    tag = bs4.BeautifulSoup('<div class="product sold-out"></div>', 'lxml').div
    assert tag is not None
    quantity = ProductHTMLParser.find_quantity(tag)
    assert quantity == 0


def test_find_quantity_last_piece():
    """Test quantity is 1 when 'posledni' text is found."""
    html = '<div class="product">posledni kus!</div>'
    tag = bs4.BeautifulSoup(html, 'lxml').div
    assert tag is not None
    quantity = ProductHTMLParser.find_quantity(tag)
    assert quantity == 1


def test_find_quantity_regular():
    """Test extracting regular numeric quantity."""
    html = '<div class="product">5 kusy</div>'
    tag = bs4.BeautifulSoup(html, 'lxml').div
    assert tag is not None
    quantity = ProductHTMLParser.find_quantity(tag)
    assert quantity == 5


def test_find_quantity_no_quantity_text():
    """Test quantity is 0 when no quantity text found."""
    tag = bs4.BeautifulSoup('<div class="product"></div>', 'lxml').div
    assert tag is not None
    quantity = ProductHTMLParser.find_quantity(tag)
    assert quantity == 0


def test_find_price_single():
    """Test extracting single price (no discount)."""
    html = '<div class="product"><span>50.00</span></div>'
    tag = bs4.BeautifulSoup(html, 'lxml').div
    assert tag is not None
    price_full, price_curr = ProductHTMLParser.find_price(tag)
    assert price_full == 50.0
    assert price_curr == 50.0


def test_find_price_discounted():
    """Test extracting discounted price (two prices)."""
    html = '<div class="product"><span>100.00</span><span>75.00</span></div>'
    tag = bs4.BeautifulSoup(html, 'lxml').div
    assert tag is not None
    price_full, price_curr = ProductHTMLParser.find_price(tag)
    assert price_full == 100.0
    assert price_curr == 75.0


def test_find_price_invalid_order():
    """Test error when current price is greater than full price."""
    tag = bs4.BeautifulSoup(
        '<div class="product" data-id="1"><span>50.00</span><span>100.00</span></div>',
        'lxml',
    ).div
    with pytest.raises(FreshPointParserValueError) as exc_info:
        ProductHTMLParser.find_price(tag)  # type: ignore
    assert 'greater than' in str(exc_info.value)


def test_find_price_too_many():
    """Test error when too many price elements found."""
    tag = bs4.BeautifulSoup(
        '<div class="product"><span>100.00</span><span>75.00</span><span>50.00</span></div>',
        'lxml',
    ).div
    with pytest.raises(FreshPointParserValueError) as exc_info:
        ProductHTMLParser.find_price(tag)  # type: ignore
    assert 'expected 1 or 2' in str(exc_info.value)


def test_get_attr_value_success():
    """Test _get_attr_value extracts attribute successfully."""
    tag = bs4.BeautifulSoup('<div test-attr="value"></div>', 'lxml').div
    assert tag is not None
    value = ProductHTMLParser._get_attr_value('test-attr', tag)
    assert value == 'value'


def test_get_attr_value_with_whitespace():
    """Test _get_attr_value strips whitespace."""
    tag = bs4.BeautifulSoup('<div test-attr="  value  "></div>', 'lxml').div
    assert tag is not None
    value = ProductHTMLParser._get_attr_value('test-attr', tag)
    assert value == 'value'


def test_get_attr_value_missing():
    """Test _get_attr_value raises error for missing attribute."""
    tag = bs4.BeautifulSoup('<div></div>', 'lxml').div
    with pytest.raises(FreshPointParserKeyError):
        ProductHTMLParser._get_attr_value('missing-attr', tag)  # type: ignore


# endregion ProductHTMLParser tests


# region ProductPageHTMLParser tests


def test_parse_location_id_success():
    """Test extracting location ID from script tag."""
    parser = ProductPageHTMLParser()
    html = '<script>var deviceId = "123";</script>'
    parser._bs4_parser = bs4.BeautifulSoup(html, 'lxml')
    location_id = parser.parse_location_id()
    assert location_id == 123


def test_parse_location_id_no_script():
    """Test error when script with deviceId is not found."""
    parser = ProductPageHTMLParser()
    html = '<html></html>'
    parser._bs4_parser = bs4.BeautifulSoup(html, 'lxml')
    with pytest.raises(FreshPointParserValueError) as exc_info:
        parser.parse_location_id()
    assert 'script tag' in str(exc_info.value)


def test_parse_location_id_no_match():
    """Test error when deviceId pattern doesn't match."""
    parser = ProductPageHTMLParser()
    html = '<script>var other = "123";</script>'
    parser._bs4_parser = bs4.BeautifulSoup(html, 'lxml')
    with pytest.raises(FreshPointParserValueError) as exc_info:
        parser.parse_location_id()
    assert 'deviceId' in str(exc_info.value)


def test_parse_location_name_success():
    """Test extracting location name from title tag."""
    parser = ProductPageHTMLParser()
    html = '<title>Location Name | FreshPoint</title>'
    parser._bs4_parser = bs4.BeautifulSoup(html, 'lxml')
    location_name = parser.parse_location_name()
    assert location_name == 'Location Name'


def test_parse_location_name_no_title():
    """Test error when title tag is missing."""
    parser = ProductPageHTMLParser()
    html = '<html></html>'
    parser._bs4_parser = bs4.BeautifulSoup(html, 'lxml')
    with pytest.raises(FreshPointParserValueError) as exc_info:
        parser.parse_location_name()
    assert 'title' in str(exc_info.value).lower()


def test_parse_product_success():
    """Test _parse_product successfully parses a product tag."""
    parser = ProductPageHTMLParser()
    parser._bs4_parser = bs4.BeautifulSoup(
        '<script>var deviceId = "10";</script>', 'lxml'
    )
    context = ParseContext()

    html = """
    <h2>Category</h2>
    <div class="product" data-id="1" data-name="Test Product"
         data-veggie="1" data-glutenfree="0" data-ispromo="0"
         data-info="Info" data-photourl="http://example.com/pic.jpg">
        <span>50.00</span>
        2 kusy
    </div>
    """
    tag = bs4.BeautifulSoup(html, 'lxml').find('div', class_='product')
    assert tag is not None
    product = parser._parse_product(tag, context)

    assert isinstance(product, Product)
    assert product.id_ == '1'
    assert product.name == 'Test Product'
    assert product.is_vegetarian is True
    assert product.price_full == 50.0
    assert product.quantity == 2
    assert product.location_id == '10'


def test_parse_product_minimal_data():
    """Test _parse_product with minimal required data."""
    parser = ProductPageHTMLParser()
    parser._bs4_parser = bs4.BeautifulSoup('<html></html>', 'lxml')
    context = ParseContext()

    html = '<div class="product" data-id="1" data-name="Test"></div>'
    tag = bs4.BeautifulSoup(html, 'lxml').find('div', class_='product')
    assert tag is not None
    product = parser._parse_product(tag, context)

    assert isinstance(product, Product)
    assert product.id_ == '1'
    assert product.name == 'Test'


def test_parse_products_multiple():
    """Test _parse_products finds and parses multiple products."""
    parser = ProductPageHTMLParser()
    html = """
    <script>var deviceId = "10";</script>
    <h2>Category</h2>
    <div class="product" data-id="1" data-name="Product 1"></div>
    <div class="product" data-id="2" data-name="Product 2"></div>
    <div class="product" data-id="3" data-name="Product 3"></div>
    """
    parser._bs4_parser = bs4.BeautifulSoup(html, 'lxml')
    context = ParseContext()

    products = parser._parse_products(context)
    assert len(products) == 3
    assert products[0].id_ == '1'
    assert products[1].id_ == '2'
    assert products[2].id_ == '3'


def test_parse_products_empty():
    """Test _parse_products with no product divs."""
    parser = ProductPageHTMLParser()
    html = '<html><body></body></html>'
    parser._bs4_parser = bs4.BeautifulSoup(html, 'lxml')
    context = ParseContext()

    products = parser._parse_products(context)
    assert len(products) == 0


def test_parse_products_partial_failure():
    """Test _parse_products handles products with missing optional fields."""
    parser = ProductPageHTMLParser()
    html = """
    <script>var deviceId = "10";</script>
    <h2>Category</h2>
    <div class="product" data-id="1" data-name="Valid Product" data-veggie="1" data-glutenfree="0" data-ispromo="0"></div>
    <div class="product" data-id="2" data-name="Partial Product"></div>
    <div class="product" data-id="3" data-name="Another Valid" data-veggie="0" data-glutenfree="1" data-ispromo="0"></div>
    """
    parser._bs4_parser = bs4.BeautifulSoup(html, 'lxml')
    context = ParseContext()

    products = parser._parse_products(context)
    # All 3 products should be created - missing optional fields get defaults
    assert len(products) == 3
    assert products[0].id_ == '1'
    assert products[1].id_ == '2'
    assert products[2].id_ == '3'
    # Should have collected errors for missing optional fields in product 2
    assert len(context.parse_errors) > 0


def test_parse_page_content_success():
    """Test _parse_page_content with valid HTML."""
    parser = ProductPageHTMLParser()
    context = ParseContext()

    html = """
    <html>
    <head><title>Test Location | FreshPoint</title></head>
    <body>
        <script>var deviceId = "10";</script>
        <h2>Category</h2>
        <div class="product" data-id="1" data-name="Product 1"><span>50.00</span></div>
    </body>
    </html>
    """
    page = parser._parse_page_content(html, context)

    assert isinstance(page, ProductPage)
    assert page.location_id == '10'
    assert page.location_name == 'Test Location'
    assert len(page.items) == 1


def test_parse_page_content_bs4_initialization():
    """Test that _parse_page_content initializes BeautifulSoup."""
    parser = ProductPageHTMLParser()
    context = ParseContext()
    html = '<html><title>Test | FreshPoint</title></html>'

    parser._parse_page_content(html, context)
    assert parser._bs4_parser is not None
    assert isinstance(parser._bs4_parser, bs4.BeautifulSoup)


def test_parse_page_content_with_location_id_error():
    """Test _parse_page_content when location ID parsing fails."""
    parser = ProductPageHTMLParser()
    context = ParseContext()
    html = '<html><body></body></html>'

    page = parser._parse_page_content(html, context)
    assert isinstance(page, ProductPage)
    # Should still create page even if location_id fails
    assert len(context.parse_errors) > 0


def test_parse_page_content_bytes():
    """Test _parse_page_content with bytes input."""
    parser = ProductPageHTMLParser()
    context = ParseContext()
    html = b'<html><title>Test | FreshPoint</title></html>'

    page = parser._parse_page_content(html, context)
    assert isinstance(page, ProductPage)


def test_parse_errors_collected_in_metadata():
    """Test that parse errors are collected in parser metadata."""
    parser = ProductPageHTMLParser()
    html = """
    <html>
    <body>
        <h2>Category</h2>
        <div class="product" data-id="1" data-name="Valid"></div>
        <div class="product" data-id="2"></div>
    </body>
    </html>
    """
    parser.parse(html)
    # Should have errors for missing location info and invalid product
    assert len(parser.metadata.parse_errors) > 0


def test_safe_parse_integration():
    """Test that _safe_parse correctly collects errors while still creating products."""
    parser = ProductPageHTMLParser()
    html = """
    <script>var deviceId = "10";</script>
    <h2>Category</h2>
    <div class="product" data-id="1" data-name="Good Product" data-veggie="1" data-glutenfree="0" data-ispromo="0"></div>
    <div class="product" data-id="2" data-name="Partial Product"></div>
    """
    parser.parse(html)

    # Both products should be created (missing optional fields use defaults)
    items_dict = {p.id_: p for p in parser.parsed_page.items}
    assert len(items_dict) == 2
    assert '1' in items_dict
    assert '2' in items_dict
    # Should have errors for missing location_name and missing optional fields
    assert len(parser.metadata.parse_errors) > 0


def test_parse_product_page_function(product_page_html_content):
    page = parse_product_page(product_page_html_content)
    assert isinstance(page, ProductPage)
    assert page.items  # some data parsed


# endregion ProductPageHTMLParser tests


# region Parser properties


def test_validate_parsed_products(product_page_html_parser_persistent, product_page):
    # assert each product in the parser is in the reference
    parser = product_page_html_parser_persistent
    product_ids = set()
    # Convert reference items list to dict by ID
    reference_items = {p.id_: p for p in product_page.items}
    for product in parser.parsed_page.items:
        assert product.id_ in reference_items
        product_reference = reference_items[product.id_]
        assert not product.diff(product_reference, exclude='recorded_at')
        product_ids.add(product.id_)
    # assert each product in the reference is in the parser
    assert product_ids == set(reference_items.keys())


def test_validate_parsed_location_id(
    product_page_html_parser_persistent, product_page_expected_meta
):
    assert (
        product_page_html_parser_persistent.parsed_page.location_id
        == product_page_expected_meta.product_page_location_id
    )


def test_validate_parsed_location_name(
    product_page_html_parser_persistent, product_page_expected_meta
):
    assert (
        product_page_html_parser_persistent.parsed_page.location_name
        == product_page_expected_meta.product_page_location_name
    )


def test_validate_parsed_products_count(
    product_page_html_parser_persistent, product_page_expected_meta
):
    assert (
        len(product_page_html_parser_persistent.parsed_page.items)
        == product_page_expected_meta.product_quantity_total
    )


def test_validate_parsed_products_count_available(
    product_page_html_parser_persistent, product_page_expected_meta
):
    assert (
        len([
            product
            for product in product_page_html_parser_persistent.parsed_page.items
            if product.is_available
        ])
        == product_page_expected_meta.product_quantity_available
    )


def test_validate_parsed_products_count_vegetarian(
    product_page_html_parser_persistent, product_page_expected_meta
):
    assert (
        len([
            product
            for product in product_page_html_parser_persistent.parsed_page.items
            if product.is_vegetarian
        ])
        == product_page_expected_meta.product_quantity_is_vegetarian
    )


def test_validate_parsed_products_count_gluten_free(
    product_page_html_parser_persistent, product_page_expected_meta
):
    assert (
        len([
            product
            for product in product_page_html_parser_persistent.parsed_page.items
            if product.is_gluten_free
        ])
        == product_page_expected_meta.product_quantity_is_gluten_free
    )


def test_validate_parsed_products_count_promo(
    product_page_html_parser_persistent, product_page_expected_meta
):
    assert (
        len([
            product
            for product in product_page_html_parser_persistent.parsed_page.items
            if product.is_promo
        ])
        == product_page_expected_meta.product_quantity_is_promo
    )


def test_validate_parsed_products_count_on_sale(
    product_page_html_parser_persistent, product_page_expected_meta
):
    assert (
        len([
            product
            for product in product_page_html_parser_persistent.parsed_page.items
            if product.is_on_sale
        ])
        == product_page_expected_meta.product_quantity_is_on_sale
    )


def test_validate_generated_product_page(
    product_page_html_parser_persistent, product_page
):
    parser = product_page_html_parser_persistent
    assert parser.parsed_page.location_id == product_page.location_id
    assert parser.parsed_page.location_name == product_page.location_name
    # Both items are lists, extract IDs
    product_ids_reference = set(p.id_ for p in product_page.items)
    product_ids_parsed = set(p.id_ for p in parser.parsed_page.items)
    assert product_ids_parsed == product_ids_reference


# endregion Parser properties


# region Parse data from internet


@pytest.mark.is_parser_up_to_date
@pytest.mark.parametrize(
    'product_page_id',
    [pytest.param(id_, id=f'ID={id_}') for id_ in range(10, 11)],
)
def test_parse_data_from_internet(product_page_html_parser_persistent, product_page_id):
    """Go through all product pages fetched from the internet and validate them.

    This test aims to validate the parser's ability to parse actual fresh data.
    """
    import time  # noqa: PLC0415

    import httpx  # noqa: PLC0415

    from freshpointparser import get_product_page_url  # noqa: PLC0415

    def get_response_with_retry(url, retries: int = 3) -> httpx.Response:
        if retries <= 0:
            raise RuntimeError(f'Failed to fetch location from {url}')
        try:
            response = httpx.get(url, timeout=60.0)
            if response.is_redirect:
                logger.warning(f'Location {loc_url} does not exist (redirected)')
                return response
            response.raise_for_status()
            return response
        except Exception as e:
            time_to_sleep = int(1 / retries * 10)  # increase with each retry
            logger.warning(f'Failed to fetch location {url}: {e}')
            logger.info(f'Retrying in {time_to_sleep} second(s)')
            time.sleep(time_to_sleep)
            return get_response_with_retry(url, retries - 1)

    parser = product_page_html_parser_persistent
    loc_url = get_product_page_url(product_page_id)
    response = get_response_with_retry(loc_url)
    parser.parse(response.text)  # should be able to parse any page
    if response.is_redirect:
        pytest.skip(f'Location {loc_url} does not exist (redirected)')
    else:
        assert parser.parsed_page != ProductPage(), f'Did not parse data from {loc_url}'


# endregion Parse data from internet
