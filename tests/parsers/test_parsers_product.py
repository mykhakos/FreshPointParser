import logging
import os

import pytest
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from freshpointparser.models import ProductPage
from freshpointparser.parsers import ProductPageHTMLParser

logger = logging.getLogger(__name__)


class ProductPageMeta(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    product_page_location_id: int
    product_page_location_name: str
    product_quantity_total: int
    product_quantity_available: int
    product_quantity_is_vegetarian: int
    product_quantity_is_gluten_free: int
    product_quantity_is_promo: int
    product_quantity_is_on_sale: int


@pytest.fixture(scope='module')
def product_page_html_text():
    path = os.path.join(os.path.dirname(__file__), 'product_page.html')
    with open(path, encoding='utf-8') as file:
        page_html_text = file.read()
    return page_html_text


@pytest.fixture(scope='module')
def product_page_html_parser_persistent(product_page_html_text):
    parser = ProductPageHTMLParser()
    parser.parse(product_page_html_text)
    return parser


@pytest.fixture(scope='function')
def product_page_html_parser_new(product_page_html_text):
    parser = ProductPageHTMLParser()
    parser.parse(product_page_html_text)
    return parser


@pytest.fixture(scope='module')
def product_page():
    path = os.path.join(os.path.dirname(__file__), 'product_page.json')
    with open(path, encoding='utf-8') as file:
        page = file.read()
    return ProductPage.model_validate_json(page)


@pytest.fixture(scope='module')
def product_page_expected_meta():
    path = os.path.join(os.path.dirname(__file__), 'product_page_meta.json')
    with open(path, encoding='utf-8') as file:
        page_meta = file.read()
    return ProductPageMeta.model_validate_json(page_meta)


# region Empty parser


def test_parse_empty_data():
    parser = ProductPageHTMLParser()
    with pytest.raises(ValueError):
        parser.location_id
        parser.location_name
        assert parser.page
    product_id = 1573
    product_name = 'BIO Zahradní limonáda bezový květ & meduňka'
    assert parser.products == []
    assert parser.find_product_by_id(product_id) is None
    assert parser.find_product_by_name(product_name) is None
    assert parser.find_products_by_name(product_name) == []


# endregion Empty parser


# region Parser properties


def test_validate_parsed_products(
    product_page_html_parser_persistent, product_page
):
    # assert each product in the parser is in the reference
    product_ids = set()
    for product in product_page_html_parser_persistent.products:
        assert product.id_ in product_page.items
        product_reference = product_page.items[product.id_]
        assert not product.diff(product_reference, exclude='recorded_at')
        product_ids.add(product.id_)
    # assert each product in the reference is in the parser
    assert product_ids == set(product_page.items.keys())


def test_validate_parsed_location_id(
    product_page_html_parser_persistent, product_page_expected_meta
):
    assert (
        product_page_html_parser_persistent.location_id
        == product_page_expected_meta.product_page_location_id
    )


def test_validate_parsed_location_name(
    product_page_html_parser_persistent, product_page_expected_meta
):
    assert (
        product_page_html_parser_persistent.location_name
        == product_page_expected_meta.product_page_location_name
    )


def test_validate_parsed_products_count(
    product_page_html_parser_persistent, product_page_expected_meta
):
    assert (
        len(product_page_html_parser_persistent.products)
        == product_page_expected_meta.product_quantity_total
    )


def test_validate_parsed_products_count_available(
    product_page_html_parser_persistent, product_page_expected_meta
):
    assert (
        len([
            product
            for product in product_page_html_parser_persistent.products
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
            for product in product_page_html_parser_persistent.products
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
            for product in product_page_html_parser_persistent.products
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
            for product in product_page_html_parser_persistent.products
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
            for product in product_page_html_parser_persistent.products
            if product.is_on_sale
        ])
        == product_page_expected_meta.product_quantity_is_on_sale
    )


def test_validate_generated_product_page(
    product_page_html_parser_persistent, product_page
):
    parser = product_page_html_parser_persistent
    assert parser.page.location_id == product_page.location_id
    assert parser.page.location_name == product_page.location_name
    product_ids_reference = set(p_id for p_id in product_page.items)
    product_ids_parsed = set(p_id for p_id in parser.page.items)
    assert product_ids_parsed == product_ids_reference


# endregion Parser properties

# region Find by ID


def test_find_product_by_id_int_exists(
    product_page_html_parser_new, product_page
):
    parser = product_page_html_parser_new
    for product_id in product_page.items:
        assert parser.find_product_by_id(product_id) is not None
        assert parser.find_product_by_id(product_id).id_ == product_id


def test_find_product_by_id_str_exists(
    product_page_html_parser_new, product_page
):
    parser = product_page_html_parser_new
    for product_id in product_page.items:
        assert parser.find_product_by_id(str(product_id)) is not None
        assert parser.find_product_by_id(str(product_id)).id_ == product_id


@pytest.mark.parametrize('product_id', [0, 999999])
def test_find_product_by_id_not_found(product_page_html_parser_new, product_id):
    parser = product_page_html_parser_new
    assert parser.find_product_by_id(product_id) is None


@pytest.mark.parametrize('product_id', [-1, '-1', '13.5', '1480a', 'id'])
def test_find_product_by_id_invalid_value(
    product_page_html_parser_new, product_id
):
    parser = product_page_html_parser_new
    with pytest.raises(ValueError):
        assert parser.find_product_by_id(product_id) is None


@pytest.mark.parametrize('product_id', [13.5, None, {}])
def test_find_product_by_id_invalid_type(
    product_page_html_parser_new, product_id
):
    parser = product_page_html_parser_new
    with pytest.raises(TypeError):
        assert parser.find_product_by_id(product_id) is None


# endregion Find by ID

# region Find by name


def test_find_products_by_name_exists_full_match(
    product_page_html_parser_new, product_page
):
    parser = product_page_html_parser_new
    for product in product_page.items.values():
        assert (
            parser.find_product_by_name(product.name, partial_match=False)
            is not None
        )
        assert (
            parser.find_product_by_name(product.name, partial_match=False).name
            == product.name
        )
        products = parser.find_products_by_name(
            product.name, partial_match=False
        )
        # assert len(products) == 1  # name may not be unique, assertion removed
        assert products[0].name == product.name


def test_find_products_by_name_exists_partial_match(
    product_page_html_parser_new, product_page
):
    parser = product_page_html_parser_new
    product_name = 'limonada'
    if any(
        product.name_lowercase_ascii == product_name
        for product in product_page.items.values()
    ):
        raise RuntimeError(
            f'Invalid test setup: product with name "{product_name}" exists'
        )
    if not any(
        product_name in product.name_lowercase_ascii
        for product in product_page.items.values()
    ):
        raise RuntimeError(
            f'Invalid test setup: no product contains "{product_name}" in its name'
        )
    assert (
        parser.find_product_by_name(product_name, partial_match=True)
        is not None
    )
    assert (
        parser.find_product_by_name(product_name, partial_match=False) is None
    )
    assert parser.find_products_by_name(product_name, partial_match=True) != []
    assert parser.find_products_by_name(product_name, partial_match=False) == []


@pytest.mark.parametrize(
    'product_name',
    ['   zahradní    limonada    bezovy   květ   ', 'alpwd,apwd,a'],
)
def test_find_products_by_name_not_found(
    product_page_html_parser_new, product_name
):
    parser = product_page_html_parser_new
    assert parser.find_product_by_name(product_name) is None
    assert parser.find_products_by_name(product_name) == []
    assert (
        parser.find_product_by_name(product_name, partial_match=False) is None
    )
    assert parser.find_products_by_name(product_name, partial_match=False) == []


@pytest.mark.parametrize(
    'product_name',
    [None, 1480, {}],
)
def test_find_products_by_name_invalid_type(
    product_page_html_parser_new, product_name
):
    parser = product_page_html_parser_new
    with pytest.raises(ValueError):
        parser.find_product_by_name(product_name)
        parser.find_products_by_name(product_name)


# endregion Find by name


# region Parse data from internet


@pytest.mark.is_parser_up_to_date
@pytest.mark.parametrize(
    'product_page_id',
    [pytest.param(id_, id=f'ID={id_}') for id_ in range(0, 1000)],
)
def test_parse_data_from_internet(
    product_page_html_parser_persistent, product_page_id
):
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
            response = httpx.get(url)
            if response.is_redirect:
                logger.warning(
                    f'Location {loc_url} does not exist (redirected)'
                )
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
        assert parser.page != ProductPage(), (
            f'Did not parse any data from {loc_url}'
        )


# endregion Parse data from internet
