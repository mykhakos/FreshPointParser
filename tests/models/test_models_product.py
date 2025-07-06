from datetime import datetime
from types import MappingProxyType
from typing import Dict

import pytest
from pydantic import Field

from freshpointparser import get_product_page_url
from freshpointparser.models import (
    Product,
    ProductPage,
)
from freshpointparser.exceptions import ModelTypeError, ModelValueError
from freshpointparser.models._product import DEFAULT_PRODUCT_PIC_URL
from freshpointparser.models.annotations import (
    DiffType,
    ProductPriceUpdateInfo,
    ProductQuantityUpdateInfo,
)

# region Product


@pytest.mark.parametrize(
    'product, expected_attrs',
    [
        pytest.param(
            Product(),
            dict(
                id_=0,
                name='',
                category='',
                is_vegetarian=False,
                is_gluten_free=False,
                quantity=0,
                price_full=0,
                price_curr=0,
                info='',
                pic_url=DEFAULT_PRODUCT_PIC_URL,
                location_id=0,
            ),
            id='default args',
        ),
        pytest.param(
            Product(
                id_=1,
                name='Product',
                category='Category',
                is_vegetarian=True,
                is_gluten_free=True,
                quantity=2,
                price_full=3.0,
                price_curr=4.0,
                info='Info',
                pic_url='https://example.com/pic.jpg',
                location_id=5,
            ),
            dict(
                id_=1,
                name='Product',
                category='Category',
                is_vegetarian=True,
                is_gluten_free=True,
                quantity=2,
                price_full=3.0,
                price_curr=4.0,
                info='Info',
                pic_url='https://example.com/pic.jpg',
                location_id=5,
            ),
            id='custom args',
        ),
    ],
)
def test_product_init(product, expected_attrs):
    assert product.id_ == expected_attrs['id_']
    assert product.name == expected_attrs['name']
    assert product.category == expected_attrs['category']
    assert product.is_vegetarian == expected_attrs['is_vegetarian']
    assert product.is_gluten_free == expected_attrs['is_gluten_free']
    assert product.quantity == expected_attrs['quantity']
    assert product.price_full == expected_attrs['price_full']
    assert product.price_curr == expected_attrs['price_curr']
    assert product.info == expected_attrs['info']
    assert product.pic_url == expected_attrs['pic_url']
    assert product.location_id == expected_attrs['location_id']


@pytest.mark.parametrize(
    'product, expected_price_full, expected_price_curr',
    [
        pytest.param(Product(), 0.0, 0.0, id='no price args'),
        pytest.param(Product(price_full=1.0), 1.0, 1.0, id='price_full'),
        pytest.param(Product(price_curr=2.0), 2.0, 2.0, id='price_curr'),
        pytest.param(
            Product(price_full=0.0, price_curr=0.0),
            0.0,
            0.0,
            id='both prices (zero)',
        ),
        pytest.param(
            Product(price_full=3.0, price_curr=3.0),
            3.0,
            3.0,
            id='both prices (same)',
        ),
        pytest.param(
            Product(price_full=3.0, price_curr=4.0),
            3.0,
            4.0,
            id='both prices (different)',
        ),
    ],
)
def test_product_init_price_resolve(
    product, expected_price_full, expected_price_curr
):
    assert product.price_full == expected_price_full
    assert product.price_curr == expected_price_curr


@pytest.mark.parametrize(
    'name, expected_name_lowercase_ascii',
    [
        pytest.param('', '', id='empty name'),
        pytest.param(
            'BIO Zahradní limonáda bezový květ & meduňka',
            'bio zahradni limonada bezovy kvet & medunka',
            id='regular name (with diacritics)',
        ),
    ],
)
def test_product_prop_name_lowercase_ascii(name, expected_name_lowercase_ascii):
    product = Product(name=name)
    assert product.name_lowercase_ascii == expected_name_lowercase_ascii


@pytest.mark.parametrize(
    'category, expected_category_lowercase_ascii',
    [
        pytest.param('', '', id='empty category'),
        pytest.param(
            'Nápoje',
            'napoje',
            id='regular category (one word, with diacritics)',
        ),
        pytest.param(
            'Hlavní jídla',
            'hlavni jidla',
            id='regular category (two words, with diacritics)',
        ),
    ],
)
def test_product_prop_category_lowercase_ascii(
    category, expected_category_lowercase_ascii
):
    product = Product(category=category)
    assert product.category_lowercase_ascii == expected_category_lowercase_ascii


@pytest.mark.parametrize(
    'product, rate',
    [
        pytest.param(
            Product(price_full=0, price_curr=0), 0, id='both prices (zero)'
        ),
        pytest.param(
            Product(price_full=0, price_curr=10), 0, id='price_curr only'
        ),
        pytest.param(
            Product(price_full=5, price_curr=10),
            0,
            id='price_full < price_curr',
        ),
        pytest.param(
            Product(price_full=10, price_curr=0), 1, id='price_full only'
        ),
        pytest.param(
            Product(price_full=10, price_curr=5),
            0.5,
            id='price_full < price_curr',
        ),
        pytest.param(
            Product(price_full=10, price_curr=10 * 2 / 3),
            0.33,
            id='price_full = 2/3 * price_full',
        ),
        pytest.param(
            Product(price_full=10, price_curr=10),
            0,
            id='price_full = price_curr',
        ),
    ],
)
def test_product_prop_discount_rate(product, rate):
    assert product.discount_rate == rate


def test_product_prop_is_on_sale():
    # Default product with no prices is not on sale
    product = Product()
    assert not product.is_on_sale

    # Product with price_curr < price_full is on sale
    product = Product(price_full=10, price_curr=5)
    assert product.is_on_sale

    # Product with price_curr == price_full is not on sale
    product = Product(price_full=10, price_curr=10)
    assert not product.is_on_sale


def test_product_prop_availability():
    p = Product(quantity=1)
    assert p.is_available
    assert not p.is_sold_out
    assert p.is_last_piece


@pytest.mark.parametrize(
    'p1, p2, precision, is_p1_newer_than_p2',
    [
        pytest.param(
            Product(recorded_at=datetime(2025, 3, 28, 12, 30, 15)),
            Product(recorded_at=datetime(2025, 3, 28, 12, 30, 15)),
            None,
            None,
            id='same timestamp - full precision',
        ),
        pytest.param(
            Product(recorded_at=datetime(2025, 3, 28, 12, 30, 16)),
            Product(recorded_at=datetime(2025, 3, 28, 12, 30, 15)),
            None,
            True,
            id='first is newer by a second - full precision',
        ),
        pytest.param(
            Product(recorded_at=datetime(2025, 3, 28, 12, 30, 15)),
            Product(recorded_at=datetime(2025, 3, 28, 12, 30, 15)),
            's',
            None,
            id="same timestamp - precision 's'",
        ),
        pytest.param(
            Product(recorded_at=datetime(2025, 3, 28, 12, 30, 15, 999999)),
            Product(recorded_at=datetime(2025, 3, 28, 12, 30, 15, 1)),
            's',
            None,
            id="same second - precision 's'",
        ),
        pytest.param(
            Product(recorded_at=datetime(2025, 3, 28, 12, 30, 16, 0)),
            Product(recorded_at=datetime(2025, 3, 28, 12, 30, 15, 999999)),
            's',
            True,
            id="first is newer by a second - precision 's'",
        ),
        pytest.param(
            Product(recorded_at=datetime(2025, 3, 28, 12, 30, 14, 999999)),
            Product(recorded_at=datetime(2025, 3, 28, 12, 30, 15, 0)),
            's',
            False,
            id="first is older by a second - precision 's'",
        ),
        pytest.param(
            Product(recorded_at=datetime(2025, 3, 28, 12, 30, 59)),
            Product(recorded_at=datetime(2025, 3, 28, 12, 30, 0)),
            'm',
            None,
            id="same minute - precision 'm'",
        ),
        pytest.param(
            Product(recorded_at=datetime(2025, 3, 28, 12, 31, 0)),
            Product(recorded_at=datetime(2025, 3, 28, 12, 30, 59)),
            'm',
            True,
            id="first is newer by a minute - precision 'm'",
        ),
        pytest.param(
            Product(recorded_at=datetime(2025, 3, 28, 12, 29, 59)),
            Product(recorded_at=datetime(2025, 3, 28, 12, 30, 0)),
            'm',
            False,
            id="first is older by a minute - precision 'm'",
        ),
        pytest.param(
            Product(recorded_at=datetime(2025, 3, 28, 12, 59, 59)),
            Product(recorded_at=datetime(2025, 3, 28, 12, 0, 0)),
            'h',
            None,
            id="same hour - precision 'h'",
        ),
        pytest.param(
            Product(recorded_at=datetime(2025, 3, 28, 13, 0, 0)),
            Product(recorded_at=datetime(2025, 3, 28, 12, 59, 59)),
            'h',
            True,
            id="first is newer by an hour - precision 'h'",
        ),
        pytest.param(
            Product(recorded_at=datetime(2025, 3, 28, 11, 59, 59)),
            Product(recorded_at=datetime(2025, 3, 28, 12, 0, 0)),
            'h',
            False,
            id="first is older by an hour - precision 'h'",
        ),
        pytest.param(
            Product(recorded_at=datetime(2025, 3, 28, 23, 59, 59)),
            Product(recorded_at=datetime(2025, 3, 28, 0, 0, 0)),
            'd',
            None,
            id="same day - precision 'd'",
        ),
        pytest.param(
            Product(recorded_at=datetime(2025, 3, 29, 0, 0, 0)),
            Product(recorded_at=datetime(2025, 3, 28, 23, 59, 59)),
            'd',
            True,
            id="first is newer by a day - precision 'd'",
        ),
        pytest.param(
            Product(recorded_at=datetime(2025, 3, 27, 23, 59, 59)),
            Product(recorded_at=datetime(2025, 3, 28, 0, 0, 0)),
            'd',
            False,
            id="first is older by a day - precision 'd'",
        ),
        pytest.param(
            Product(recorded_at=datetime(2025, 3, 31, 23, 59, 59)),
            Product(recorded_at=datetime(2025, 3, 1, 0, 0, 0)),
            'd',
            True,
            id="first is newer by a month - precision 'd'",
        ),
        pytest.param(
            Product(recorded_at=datetime(2025, 3, 1, 0, 0, 0)),
            Product(recorded_at=datetime(2025, 3, 31, 23, 59, 59)),
            'd',
            False,
            id="first is older by a month - precision 'd'",
        ),
    ],
)
def test_product_is_newer_than(p1, p2, precision, is_p1_newer_than_p2):
    # direct test
    assert p1.is_newer_than(p2, precision=precision) is is_p1_newer_than_p2

    # reverse test
    if is_p1_newer_than_p2 is None:
        is_p2_newer_than_p1 = None
    else:
        is_p2_newer_than_p1 = not is_p1_newer_than_p2
    assert p2.is_newer_than(p1, precision=precision) is is_p2_newer_than_p1

    # test with the product compared to itself
    assert p1.is_newer_than(p1, precision=precision) is None
    assert p2.is_newer_than(p2, precision=precision) is None


def test_is_newer_than_invalid_precision():
    p1 = Product(recorded_at=datetime(2024, 1, 1))
    p2 = Product(recorded_at=datetime(2024, 1, 2))
    with pytest.raises(ModelValueError):
        p1.is_newer_than(p2, precision='q')  # type: ignore[reportArgumentType]


def test_recorded_at_serialize_excluded():
    product = Product()

    data = product.model_dump(context={'__exclude_recorded_at__': True})
    assert data['recorded_at'] is None

    for data in (
        product.model_dump(),
        product.model_dump(mode='json'),
        product.model_dump(context={'__exclude_recorded_at__': False}),
    ):
        assert data['recorded_at'] is not None


@pytest.mark.parametrize(
    'product_this, product_other, diff',
    [
        pytest.param(
            Product(id_=123, name='foo', quantity=0, price_full=5),
            Product(id_=321, name='bar', quantity=5, price_full=10),
            {
                'id_': {
                    'type': DiffType.UPDATED,
                    'values': {'left': 123, 'right': 321},
                },
                'name': {
                    'type': DiffType.UPDATED,
                    'values': {'left': 'foo', 'right': 'bar'},
                },
                'quantity': {
                    'type': DiffType.UPDATED,
                    'values': {'left': 0, 'right': 5},
                },
                'price_full': {
                    'type': DiffType.UPDATED,
                    'values': {'left': 5, 'right': 10},
                },
                'price_curr': {
                    'type': DiffType.UPDATED,
                    'values': {'left': 5, 'right': 10},
                },
            },
            id='different products',
        ),
        pytest.param(
            Product(category='foo'),
            Product(category='bar'),
            {
                'category': {
                    'type': DiffType.UPDATED,
                    'values': {'left': 'foo', 'right': 'bar'},
                }
            },
            id='different category',
        ),
        pytest.param(
            Product(id_=123, quantity=4, price_full=10),
            Product(id_=123, quantity=4, price_full=10),
            {},
            id='same product',
        ),
        pytest.param(
            Product(id_=123, quantity=4, price_full=10, price_curr=10),
            Product(id_=123, quantity=4, price_full=10, price_curr=5),
            {
                'price_curr': {
                    'type': DiffType.UPDATED,
                    'values': {'left': 10, 'right': 5},
                }
            },
            id='same product, different price_curr',
        ),
        pytest.param(
            Product(id_=123, quantity=4, price_full=10, price_curr=5),
            Product(id_=123, quantity=4, price_full=10, price_curr=10),
            {
                'price_curr': {
                    'type': DiffType.UPDATED,
                    'values': {'left': 5, 'right': 10},
                }
            },
            id='same product, different price_curr (reversed)',
        ),
        pytest.param(
            Product(id_=123, quantity=5, price_full=10, price_curr=10),
            Product(id_=123, quantity=0, price_full=10, price_curr=10),
            {
                'quantity': {
                    'type': DiffType.UPDATED,
                    'values': {'left': 5, 'right': 0},
                }
            },
            id='same product, different quantity',
        ),
    ],
)
def test_product_diff(product_this, product_other, diff):
    assert product_this.diff(product_other) == diff
    assert product_this.diff(product_other, exclude={'recorded_at'}) == diff


@pytest.mark.parametrize(
    'product_this, product_other, kwargs, expected_diff_true, expected_diff_false',
    [
        pytest.param(
            Product(recorded_at=datetime(2024, 1, 1, 12, 0, 0)),
            Product(recorded_at=datetime(2024, 1, 2, 12, 0, 0)),
            {},
            {},
            {
                'recorded_at': {
                    'type': DiffType.UPDATED,
                    'values': {
                        'left': datetime(2024, 1, 1, 12, 0, 0),
                        'right': datetime(2024, 1, 2, 12, 0, 0),
                    },
                }
            },
            id='only recorded_at differs',
        ),
        pytest.param(
            Product(name='Apple', recorded_at=datetime(2024, 1, 1, 12, 0, 0)),
            Product(name='Banana', recorded_at=datetime(2024, 1, 2, 12, 0, 0)),
            {},
            {
                'name': {
                    'type': DiffType.UPDATED,
                    'values': {'left': 'Apple', 'right': 'Banana'},
                }
            },
            {
                'name': {
                    'type': DiffType.UPDATED,
                    'values': {'left': 'Apple', 'right': 'Banana'},
                },
                'recorded_at': {
                    'type': DiffType.UPDATED,
                    'values': {
                        'left': datetime(2024, 1, 1, 12, 0, 0),
                        'right': datetime(2024, 1, 2, 12, 0, 0),
                    },
                },
            },
            id='recorded_at and name differ',
        ),
        pytest.param(
            Product(name='Apple', recorded_at=datetime(2024, 1, 1, 12, 0, 0)),
            Product(name='Banana', recorded_at=datetime(2024, 1, 2, 12, 0, 0)),
            {'exclude': {'name'}},
            {},
            {
                'recorded_at': {
                    'type': DiffType.UPDATED,
                    'values': {
                        'left': datetime(2024, 1, 1, 12, 0, 0),
                        'right': datetime(2024, 1, 2, 12, 0, 0),
                    },
                }
            },
            id='exclude name, only recorded_at diff',
        ),
        pytest.param(
            Product(recorded_at=datetime(2024, 1, 1, 12, 0, 0), name='Apple'),
            Product(recorded_at=datetime(2024, 1, 2, 12, 0, 0), name='Apple'),
            {'include': {'recorded_at'}},
            {},
            {
                'recorded_at': {
                    'type': DiffType.UPDATED,
                    'values': {
                        'left': datetime(2024, 1, 1, 12, 0, 0),
                        'right': datetime(2024, 1, 2, 12, 0, 0),
                    },
                }
            },
            id='include only recorded_at',
        ),
        pytest.param(
            Product(recorded_at=datetime(2024, 1, 1, 12, 0, 0), name='Apple'),
            Product(recorded_at=datetime(2024, 1, 2, 12, 0, 0), name='Banana'),
            {'include': {'recorded_at', 'name'}},
            {
                'name': {
                    'type': DiffType.UPDATED,
                    'values': {'left': 'Apple', 'right': 'Banana'},
                }
            },
            {
                'name': {
                    'type': DiffType.UPDATED,
                    'values': {'left': 'Apple', 'right': 'Banana'},
                },
                'recorded_at': {
                    'type': DiffType.UPDATED,
                    'values': {
                        'left': datetime(2024, 1, 1, 12, 0, 0),
                        'right': datetime(2024, 1, 2, 12, 0, 0),
                    },
                },
            },
            id='include recorded_at and name',
        ),
        pytest.param(
            Product(recorded_at=datetime(2024, 1, 1, 12, 0, 0)),
            Product(recorded_at=datetime(2024, 1, 2, 12, 0, 0)),
            {'by_alias': True},
            {},
            {
                'recordedAt': {
                    'type': DiffType.UPDATED,
                    'values': {
                        'left': datetime(2024, 1, 1, 12, 0, 0),
                        'right': datetime(2024, 1, 2, 12, 0, 0),
                    },
                }
            },
            id='by_alias kwarg',
        ),
        pytest.param(
            Product(recorded_at=datetime(2024, 1, 1, 12, 0, 0), name='Apple'),
            Product(recorded_at=datetime(2024, 1, 2, 12, 0, 0), name='Banana'),
            {'exclude': {'recorded_at'}},
            {
                'name': {
                    'type': DiffType.UPDATED,
                    'values': {'left': 'Apple', 'right': 'Banana'},
                }
            },
            {
                'name': {
                    'type': DiffType.UPDATED,
                    'values': {'left': 'Apple', 'right': 'Banana'},
                }
            },
            id='exclude kwarg includes recorded_at',
        ),
        pytest.param(
            Product(recorded_at=datetime(2024, 1, 1, 12, 0, 0), name='Apple'),
            Product(recorded_at=datetime(2024, 1, 2, 12, 0, 0), name='Banana'),
            {'exclude': {'recorded_at'}},
            {
                'name': {
                    'type': DiffType.UPDATED,
                    'values': {'left': 'Apple', 'right': 'Banana'},
                }
            },
            {
                'name': {
                    'type': DiffType.UPDATED,
                    'values': {'left': 'Apple', 'right': 'Banana'},
                }
            },
            id='exclude kwarg includes recorded_at',
        ),
    ],
)
def test_product_diff_exclude_recorded_at_with_kwargs(
    product_this, product_other, kwargs, expected_diff_true, expected_diff_false
):
    # exclude_recorded_at=True
    assert (
        product_this.diff(product_other, exclude_recorded_at=True, **kwargs)
        == expected_diff_true
    )
    # exclude_recorded_at=False
    assert (
        product_this.diff(product_other, exclude_recorded_at=False, **kwargs)
        == expected_diff_false
    )


@pytest.mark.parametrize(
    'stock_decrease, stock_increase, stock_depleted, stock_restocked',
    [
        pytest.param(0, 0, False, False, id='no change'),
        pytest.param(0, 10, False, True, id='stock increased'),
        pytest.param(5, 0, True, False, id='stock decreased'),
    ],
)
def test_product_quantity_update_info(
    stock_decrease, stock_increase, stock_depleted, stock_restocked
):
    update_info = ProductQuantityUpdateInfo(
        stock_decrease=stock_decrease,
        stock_increase=stock_increase,
        stock_depleted=stock_depleted,
        stock_restocked=stock_restocked,
    )
    assert update_info.stock_decrease == stock_decrease
    assert update_info.stock_increase == stock_increase
    assert update_info.stock_depleted == stock_depleted
    assert update_info.stock_restocked == stock_restocked


@pytest.mark.parametrize(
    'product_this, product_other, info',
    [
        pytest.param(
            Product(quantity=0),
            Product(quantity=0),
            ProductQuantityUpdateInfo(
                stock_decrease=0,
                stock_increase=0,
                stock_depleted=False,
                stock_restocked=False,
            ),
            id='no stock',
        ),
        pytest.param(
            Product(quantity=5),
            Product(quantity=2),
            ProductQuantityUpdateInfo(
                stock_decrease=3,
                stock_increase=0,
                stock_depleted=False,
                stock_restocked=False,
            ),
            id='stock decreased',
        ),
        pytest.param(
            Product(quantity=2),
            Product(quantity=5),
            ProductQuantityUpdateInfo(
                stock_decrease=0,
                stock_increase=3,
                stock_depleted=False,
                stock_restocked=False,
            ),
            id='stock increased',
        ),
        pytest.param(
            Product(quantity=2),
            Product(quantity=0),
            ProductQuantityUpdateInfo(
                stock_decrease=2,
                stock_increase=0,
                stock_depleted=True,
                stock_restocked=False,
            ),
            id='stock depleted',
        ),
        pytest.param(
            Product(quantity=0),
            Product(quantity=2),
            ProductQuantityUpdateInfo(
                stock_decrease=0,
                stock_increase=2,
                stock_depleted=False,
                stock_restocked=True,
            ),
            id='stock restocked',
        ),
    ],
)
def test_product_compare_quantity(product_this, product_other, info):
    assert product_this.compare_quantity(product_other) == info
    info_no_diff = ProductQuantityUpdateInfo()
    assert product_this.compare_quantity(product_this) == info_no_diff


@pytest.mark.parametrize(
    """
    price_full_decrease,
    price_full_increase,
    price_curr_decrease,
    price_curr_increase,
    discount_rate_decrease,
    discount_rate_increase,
    sale_started,
    sale_ended
    """,
    [
        pytest.param(
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False, False, id='no change'
        ),
        pytest.param(
            0.0,
            15.0,
            5.0,
            0.0,
            0.05,
            0.0,
            True,
            False,
            id='price_curr increased',
        ),
        pytest.param(
            0.0,
            0.0,
            0.0,
            10.0,
            0.0,
            0.1,
            False,
            False,
            id='price_full increased',
        ),
    ],
)
def test_product_price_update_info(
    price_full_decrease,
    price_full_increase,
    price_curr_decrease,
    price_curr_increase,
    discount_rate_decrease,
    discount_rate_increase,
    sale_started,
    sale_ended,
):
    update_info = ProductPriceUpdateInfo(
        price_full_decrease=price_full_decrease,
        price_full_increase=price_full_increase,
        price_curr_decrease=price_curr_decrease,
        price_curr_increase=price_curr_increase,
        discount_rate_decrease=discount_rate_decrease,
        discount_rate_increase=discount_rate_increase,
        sale_started=sale_started,
        sale_ended=sale_ended,
    )
    assert update_info.price_full_decrease == price_full_decrease
    assert update_info.price_full_increase == price_full_increase
    assert update_info.price_curr_decrease == price_curr_decrease
    assert update_info.price_curr_increase == price_curr_increase
    assert update_info.discount_rate_decrease == discount_rate_decrease
    assert update_info.discount_rate_increase == discount_rate_increase
    assert update_info.sale_started == sale_started
    assert update_info.sale_ended == sale_ended


@pytest.mark.parametrize(
    'product_this, product_other, info',
    [
        pytest.param(
            Product(),
            Product(),
            ProductPriceUpdateInfo(
                price_full_decrease=0,
                price_full_increase=0,
                price_curr_decrease=0,
                price_curr_increase=0,
                discount_rate_decrease=0,
                discount_rate_increase=0,
                sale_started=False,
                sale_ended=False,
            ),
            id='no price change (default prices)',
        ),
        pytest.param(
            Product(price_full=10, price_curr=10),
            Product(price_full=10, price_curr=10),
            ProductPriceUpdateInfo(
                price_full_decrease=0,
                price_full_increase=0,
                price_curr_decrease=0,
                price_curr_increase=0,
                discount_rate_decrease=0,
                discount_rate_increase=0,
                sale_started=False,
                sale_ended=False,
            ),
            id='no price change (custom prices)',
        ),
        pytest.param(
            Product(price_full=10, price_curr=10),
            Product(price_full=10, price_curr=5),
            ProductPriceUpdateInfo(
                price_full_decrease=0,
                price_full_increase=0,
                price_curr_decrease=5,
                price_curr_increase=0,
                discount_rate_decrease=0,
                discount_rate_increase=0.5,
                sale_started=True,
                sale_ended=False,
            ),
            id='price_curr decreased',
        ),
        pytest.param(
            Product(price_full=10, price_curr=5),
            Product(price_full=10, price_curr=10),
            ProductPriceUpdateInfo(
                price_full_decrease=0,
                price_full_increase=0,
                price_curr_decrease=0,
                price_curr_increase=5,
                discount_rate_decrease=0.5,
                discount_rate_increase=0,
                sale_started=False,
                sale_ended=True,
            ),
            id='price_curr increased',
        ),
        pytest.param(
            Product(price_full=10, price_curr=5),
            Product(price_full=20, price_curr=10),
            ProductPriceUpdateInfo(
                price_full_decrease=0,
                price_full_increase=10,
                price_curr_decrease=0,
                price_curr_increase=5,
                discount_rate_decrease=0,
                discount_rate_increase=0,
                sale_started=False,
                sale_ended=False,
            ),
            id='price_full and price_curr increased',
        ),
        pytest.param(
            Product(price_full=20, price_curr=15),
            Product(price_full=10, price_curr=5),
            ProductPriceUpdateInfo(
                price_full_decrease=10,
                price_full_increase=0,
                price_curr_decrease=10,
                price_curr_increase=0,
                discount_rate_decrease=0.0,
                discount_rate_increase=0.25,
                sale_started=False,
                sale_ended=False,
            ),
            id='price_full and price_curr decreased',
        ),
    ],
)
def test_compare_price(product_this, product_other, info):
    assert product_this.compare_price(product_other) == info
    info_no_diff = ProductPriceUpdateInfo()
    assert product_this.compare_price(product_this) == info_no_diff


# endregion Product

# region ProductPage


@pytest.mark.parametrize(
    'page, expected_attrs',
    [
        pytest.param(
            ProductPage(),
            {
                'items': {},
                'location_id': 0,
                'location_name': '',
            },
            id='empty page',
        ),
        pytest.param(
            ProductPage(
                items={
                    1: Product(
                        id_=1, location_id=296, recorded_at=datetime(2025, 1, 1)
                    )
                },
                location_id=296,
                location_name='foo',
            ),
            {
                'items': {
                    1: Product(
                        id_=1, location_id=296, recorded_at=datetime(2025, 1, 1)
                    )
                },
                'location_id': 296,
                'location_name': 'foo',
            },
            id='regular page',
        ),
    ],
)
def test_product_page_init(page, expected_attrs):
    for key, value in expected_attrs.items():
        assert getattr(page, key) == value


@pytest.mark.parametrize(
    'location_id, expected_url',
    [
        pytest.param(
            0, get_product_page_url(location_id=0), id='location_id=0'
        ),
        pytest.param(
            296, get_product_page_url(location_id=296), id='location_id=296'
        ),
    ],
)
def test_product_page_prop_url(location_id, expected_url):
    page = ProductPage(location_id=location_id)
    assert page.url == expected_url


@pytest.mark.parametrize(
    'location_name, expected_location_name_lowercase_ascii',
    [
        pytest.param('', '', id='empty location name'),
        pytest.param(
            'foo', 'foo', id='location name with ascii charactersonly'
        ),
        pytest.param(
            "L'Oréal Česká republika",
            "l'oreal ceska republika",
            id='location name with non-ascii characters',
        ),
    ],
)
def test_product_page_prop_location_name_lowercase_ascii(
    location_name, expected_location_name_lowercase_ascii
):
    page = ProductPage(location_name=location_name)
    assert (
        page.location_name_lowercase_ascii
        == expected_location_name_lowercase_ascii
    )


@pytest.fixture(scope='module')
def products():
    return [
        Product(
            id_=0,
            name='orange',
            category='fruit',
            quantity=1,
            price_full=2,
            price_curr=2,
            info='very good',
        ),
        Product(
            id_=1,
            name='cheesecake',
            category='dessert',
            quantity=5,
            price_full=1.5,
            price_curr=2.2,
        ),
        Product(
            id_=2,
            name='apple',
            category='fruit',
            quantity=10,
            price_full=1.5,
            price_curr=1.2,
        ),
        Product(
            id_=3,
            name='banana',
            category='fruit',
            quantity=0,
            price_full=0.5,
            price_curr=0.4,
            is_vegetarian=True,
            is_gluten_free=True,
        ),
        Product(
            id_=4,
            name='carrot',
            category='vegetable',
            quantity=15,
            price_full=2.0,
            is_gluten_free=True,
        ),
        Product(
            id_=5,
            name='doughnut',
            category='pastry',
            quantity=5,
            price_full=1.0,
            price_curr=0.8,
            info='try it',
        ),
        Product(
            id_=6,
            name='eggs',
            category='dairy',
            quantity=12,
            price_full=3.0,
            price_curr=2.5,
        ),
        Product(
            id_=7,
            name='fish',
            category='seafood',
            quantity=8,
            price_full=5.0,
            price_curr=4.5,
            pic_url='https://example.com',
        ),
        Product(
            id_=8,
            name='grapes',
            category='fruit',
            quantity=20,
            price_full=2.0,
            price_curr=1.8,
            is_vegetarian=True,
        ),
        Product(
            id_=9,
            name='honey',
            category='sweetener',
            quantity=0,
            price_full=4.0,
            price_curr=3.5,
        ),
        Product(
            id_=10,
            name='ice cream',
            category='dessert',
            quantity=10,
            price_full=2.5,
            price_curr=2.0,
        ),
        Product(
            id_=11,
            name='jam',
            category='spread',
            quantity=7,
            price_full=3.0,
            price_curr=2.5,
            is_gluten_free=True,
        ),
    ]


@pytest.fixture(scope='module')
def product_page(products):
    return ProductPage(items={p.id_: p for p in products})


def test_page_item_helpers(product_page):
    assert product_page.item_count == len(product_page.items)
    assert set(product_page.item_ids) == set(product_page.items)
    assert product_page.item_list == list(product_page.items.values())


@pytest.mark.parametrize(
    'constraint, expected_product_ids',
    [
        pytest.param(
            {},
            [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
            id='dict constraint: empty',
        ),
        pytest.param({'name': 'orange'}, [0], id='dict constraint: name'),
        pytest.param({'id_': 4}, [4], id='dict constraint: id'),
        pytest.param(
            {'id_': 4, 'name': 'carrot'},
            [4],
            id='dict constraint: id with other constraint',
        ),
        pytest.param(
            {'name': 'jam', 'category': 'spread'},
            [11],
            id='dict constraint: two constraints',
        ),
        pytest.param(
            {'name': 'honey', 'category': 'sweetener', 'quantity': 0},
            [9],
            id='dict constraint: multiple constraints',
        ),
        pytest.param(
            {'name_lowercase_ascii': 'orange'},
            [0],
            id='dict constraint: property constraint',
        ),
        pytest.param(
            MappingProxyType({'name': 'orange'}),
            [0],
            id='MappingProxyType constraint: name',
        ),
        pytest.param(
            lambda p: p,
            [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
            id='lambda constraint: any product',
        ),
        pytest.param(
            lambda p: 'ice' in p.name,
            [10],
            id='lambda constraint: partial name match',
        ),
        pytest.param(
            lambda p: p.price_full > 3.0,
            [7, 9],
            id='lambda constraint: full price gt',
        ),
        pytest.param(
            lambda p: 1.0 <= p.price_curr <= 2.0,
            [0, 2, 4, 8, 10],
            id='lambda constraint: curr price range',
        ),
        pytest.param(
            lambda p: 5 <= p.quantity <= 10,
            [1, 2, 5, 7, 10, 11],
            id='lambda constraint: quantity range',
        ),
        pytest.param(
            lambda p: p.is_vegetarian and p.is_gluten_free,
            [3],
            id='lambda constraint: vegetarian and gluten free',
        ),
        pytest.param(
            lambda p: p.price_curr < 2.0 and p.quantity > 8,
            [2, 8],
            id='lambda constraint: multiple parameters',
        ),
    ],
)
def test_product_page_find_items(
    product_page, constraint, expected_product_ids
):
    products = product_page.find_items(constraint)
    assert [p.id_ for p in products] == expected_product_ids
    product = product_page.find_item(constraint)
    assert product.id_ == expected_product_ids[0]


@pytest.mark.parametrize(
    'constraint',
    [
        pytest.param({'': 'orange'}, id='dict constraint: empty string key'),
        pytest.param({'cat': 'fruit'}, id='dict constraint: partial key'),
        pytest.param({'nema': 'orange'}, id='dict constraint: misspelled key'),
        pytest.param(
            {'id': 1}, id='dict constraint: pydantic validation alias key'
        ),
        pytest.param(
            {'name': 'orange', 'cat': 'fruit', 'quant': 1},
            id='dict constraint: multiple keys, one invalid',
        ),
        pytest.param(
            {'category_lowercase_asci': 'fruit'},
            id='dict constraint: misspelled property key',
        ),
        pytest.param({'name': ''}, id='dict constraint: empty string name'),
        pytest.param({'name': 'orenge'}, id='dict constraint: wrong name'),
        pytest.param({'name': 'ran'}, id='dict constraint: partial name'),
        pytest.param({'id_': -1}, id='dict constraint: wrong id'),
        pytest.param(
            {'id_': 1, 'name': 'apple'},
            id='dict constraint: id and name mismatch',
        ),
        pytest.param(
            {'name': 'orange', 'category': 'fruit', 'quantity': 2},
            id='dict constraint: multiple parameters (no match)',
        ),
        pytest.param(
            MappingProxyType({'name_lowercase_ascii': 'orenge'}),
            id='MappingProxyType constraint: wrong lowercase ascii name (property)',
        ),
        pytest.param((lambda p: False), id='lambda constraint: False'),
        pytest.param(
            (lambda p: p.price_curr < 10 and p.price_curr > 20),
            id='lambda constraint: wrong price range',
        ),
        pytest.param(
            (lambda p: p.price_curr > 2.0 and p.quantity > 100),
            id='lambda constraint: multiple parameters (no match)',
        ),
        pytest.param(
            (lambda p: p.price_curr == '2.0'),
            id='lambda constraint: wrong type',
        ),
        pytest.param(
            (lambda p: p.price_curr < 2.0 and p.quantity == '10'),
            id='lambda constraint: multiple parameters, wrong type',
        ),
    ],
)
def test_product_page_find_items_no_match(product_page, constraint):
    products = list(product_page.find_items(constraint))
    assert products == []
    product = product_page.find_item(constraint)
    assert product is None


@pytest.mark.parametrize(
    'constraint',
    [
        pytest.param({None: 'orange'}, id='dict constraint: None key'),
        pytest.param({1: 'fruit'}, id='dict constraint: int key'),
        pytest.param({1: 1}, id='dict constraint: int wrong key and value'),
        pytest.param(
            {'name': 'orange', 1: 1},
            id='dict constraint: str key (valid) and int key',
        ),
        pytest.param(None, id='None constraint'),
        pytest.param([('name', 'orange')], id='list of tuples constraint'),
        pytest.param(
            lambda: 'orange',
            id='invalid signature function constraint (no args)',
        ),
        pytest.param(
            'orange', id='invalid signature string constraint (too many args)'
        ),
        pytest.param(lambda p1, p2: True, id='string constraint'),
        pytest.param(object(), id='object constraint'),
        pytest.param(object, id='uninstantiated class constraint'),
    ],
)
def test_product_page_find_items_invalid_constraint(product_page, constraint):
    with pytest.raises(ModelTypeError):
        list(product_page.find_items(constraint))
    with pytest.raises(ModelTypeError):
        product_page.find_item(constraint)


@pytest.mark.parametrize(
    'constraint',
    [
        pytest.param(
            (lambda p: p.nam == 'orange'),
            id='lambda constraint: partial attribute',
        ),
        pytest.param(
            (lambda p: p.nema == 'orange'),
            id='lambda constraint: misspelled attribute',
        ),
        pytest.param(
            (lambda p: p.name == 'orange' and p.cat == 'fruit'),
            id='lambda constraint: multiple attributes, one partial',
        ),
        pytest.param(
            (lambda p: p.price_curr < 2.0 and p.nema == 'orange'),
            id='lambda constraint: multiple attributes, one misspelled',
        ),
    ],
)
def test_product_page_find_items_invalid_lambda_attribute(
    product_page, constraint
):
    with pytest.raises(AttributeError):
        list(product_page.find_items(constraint))
    with pytest.raises(AttributeError):
        product_page.find_item(constraint)


def test_item_diff_created_updated_deleted():
    p_old = ProductPage(
        items={
            1: Product(id_=1, name='Banana'),
            2: Product(id_=2, name='Apple', quantity=2),
        }
    )
    p_new = ProductPage(
        items={
            2: Product(id_=2, name='Apple', quantity=1),
            3: Product(id_=3, name='Orange'),
        }
    )
    diff = p_old.item_diff(p_new)
    assert diff[1]['type'] is DiffType.DELETED
    assert diff[2]['type'] is DiffType.UPDATED
    assert diff[3]['type'] is DiffType.CREATED


def test_iter_item_attr_defaults_and_uniqueness():
    class SubProduct(Product):
        context: Dict[str, str] = Field(default_factory=dict)

    page = ProductPage(
        items={
            1: Product(id_=1, category='c1'),
            2: Product(id_=2, category='c2'),
            3: Product(id_=3, category='c2'),
            4: Product(id_=4, category='c3'),
        }
    )
    # missing attr without default -> raises
    with pytest.raises(AttributeError):
        list(page.iter_item_attr('nonexistent'))

    # missing attr with default -> returns default
    assert list(page.iter_item_attr('nonexistent', default='default')) == [
        'default',
        'default',
        'default',
        'default',
    ]

    # unique, hashable
    assert list(page.iter_item_attr('category', unique=True)) == [
        'c1',
        'c2',
        'c3',
    ]

    # unique with unhashable values
    page.items[5] = SubProduct(id_=5, context={'key': 'value'})
    assert list(
        page.iter_item_attr('context', default={}, unhashable=True)
    ) == [
        {},
        {},
        {},
        {},
        {'key': 'value'},
    ]

    # TypeError on unhashable unique without flag
    with pytest.raises(AttributeError):
        list(page.iter_item_attr('context', unique=True))


# endregion ProductPage
