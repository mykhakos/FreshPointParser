from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Optional, Union

from pydantic import Field, NonNegativeFloat, NonNegativeInt, model_validator

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

from freshpointparser.exceptions import FreshPointParserValueError

from .._utils import normalize_text
from ._base import BaseItem, BasePage


@dataclass
class ProductQuantityUpdateInfo:
    """Summarizes the details of stock quantity changes in a product."""

    quantity_decrease: int = 0
    """Decrease in stock quantity. Represents how many items
    are fewer in the new product compared to the old product.
    A value of 0 implies no decrease.
    """
    quantity_increase: int = 0
    """Increase in stock quantity. Indicates how many items
    are more in the new product compared to the old product.
    A value of 0 implies no increase.
    """
    is_last_piece: bool = False
    """A flag indicating the product is the last piece in stock.
    True if the new product's stock quantity is one while the old
    product's stock was greater than one.
    """
    is_depleted: bool = False
    """A flag indicating complete depletion of the product stock.
    True if the new product's stock quantity is zero while the old
    product's stock was greater than zero.
    """
    is_restocked: bool = False
    """A flag indicating the product has been restocked.
    True if the new product's stock quantity is greater than zero
    while the old product's stock was zero.
    """


@dataclass
class ProductPriceUpdateInfo:
    """Summarizes the details of pricing changes of a product."""

    price_full_decrease: float = 0.0
    """Decrease in the full price of the product. Represents the difference
    between its old full price and its new full price.
    A value of 0.0 indicates no decrease.
    """
    price_full_increase: float = 0.0
    """Increase of the full price of the product. Represents the difference
    between its new full price and its old full price.
    A value of 0.0 indicates no increase.
    """
    price_curr_decrease: float = 0.0
    """Decrease in the current selling price of the product. Represents
    the difference between its old selling price and its new selling price.
    A value of 0.0 indicates no decrease.
    """
    price_curr_increase: float = 0.0
    """Increase in the current selling price of the product. Represents
    the difference between its new selling price and its old selling price.
    A value of 0.0 indicates no increase.
    """
    discount_rate_decrease: float = 0.0
    """Decrease in the discount rate of the product. Indicates the reduction
    of the discount rate in the new product compared to the old product.
    A value of 0.0 indicates that the discount rate has not decreased.
    """
    discount_rate_increase: float = 0.0
    """Increase in the discount rate of the product. Indicates the increment
    of the discount rate in the new product compared to the old product.
    A value of 0.0 indicates that the discount rate has not increased.
    """
    has_sale_started: bool = False
    """A flag indicating whether a sale has started on the product.
    True if the new product is on sale and the old product was not.
    """
    has_sale_ended: bool = False
    """A flag indicating whether a sale has ended on the product.
    True if the new product is not on sale and the old product was.
    """


class Product(BaseItem):
    """Data model of a FreshPoint product."""

    name: Optional[str] = Field(
        default=None,
        title='Name',
        description='Name of the product.',
    )
    """Name of the product."""
    category: Optional[str] = Field(
        default=None,
        title='Category',
        description='Category of the product.',
    )
    """Category of the product."""
    is_vegetarian: Optional[bool] = Field(
        default=None,
        title='Vegetarian',
        description='Indicates if the product is vegetarian.',
    )
    """Indicates if the product is vegetarian."""
    is_gluten_free: Optional[bool] = Field(
        default=None,
        title='Gluten Free',
        description='Indicates if the product is gluten-free.',
    )
    """Indicates if the product is gluten-free."""
    is_promo: Optional[bool] = Field(
        default=None,
        title='Promo',
        description=(
            'Indicates if the product is being promoted. Note that the '
            'product being on a promo does not guarantee that the product '
            'currently has a discount and vice versa.'
        ),
    )
    """Indicates whether the product is being promoted.

    **The product being a promo does not guarantee that the product currently
    has a discount and vice versa.** Use ``is_on_sale`` to check if the product is
    on sale.
    """
    quantity: Optional[NonNegativeInt] = Field(
        default=None,
        title='Quantity',
        description='Quantity of product items in stock.',
    )
    """Quantity of product items in stock."""
    price_full: Optional[NonNegativeFloat] = Field(
        default=None,
        title='Full Price',
        description='Full price of the product.',
    )
    """Full price of the product."""
    price_curr: Optional[NonNegativeFloat] = Field(
        default=None,
        title='Current Price',
        description='Current selling price of the product.',
    )
    """Current selling price of the product."""
    info: Optional[str] = Field(
        default=None,
        title='Information',
        description=(
            'Additional information about the product such as ingredients '
            'or nutritional values.'
        ),
    )
    """Additional information about the product such as ingredients or nutritional values."""
    pic_url: str = Field(
        default=(
            r'https://images.weserv.nl/?url=http://freshpoint.freshserver.cz/'
            r'backend/web/media/photo/1_f587dd3fa21b22.jpg'
        ),
        title='Illustrative Product Picture URL',
        description='URL of the illustrative product image.',
    )
    """URL of the illustrative product image."""
    location_id: Optional[int] = Field(
        default=None,
        title='Location ID',
        description=(
            'Unique identifier or the product location (also known as '
            'the page ID or the device ID).'
        ),
    )
    """Unique identifier or the product location (also known as the page ID or the device ID)."""

    @model_validator(mode='after')
    def _validate_price(self) -> Self:
        """Ensure that both full price and current price are set."""
        if self.price_full is None or self.price_curr is None:
            return self
        if self.price_full < self.price_curr:
            raise FreshPointParserValueError(
                f'Full price ({self.price_full}) cannot be lower than '
                f'current price ({self.price_curr}).'
            )
        return self

    @property
    def name_lowercase_ascii(self) -> str:
        """Lowercase ASCII representation of the product name.

        If the name is not set, the representation is an empty string.
        """
        return normalize_text(self.name)

    @property
    def category_lowercase_ascii(self) -> str:
        """Lowercase ASCII representation of the product category.

        If the category is not set, the representation is an empty string.
        """
        return normalize_text(self.category)

    @property
    def discount_rate(self) -> float:
        """Discount rate (<0; 1>) of the product, calculated based on
        the difference between the full price and the current selling price.

        Precision is up to two decimal places (whole percentage points).
        """
        if not self.price_full or self.price_curr is None:
            return 0
        return round((self.price_full - self.price_curr) / self.price_full, 2)

    @property
    def is_on_sale(self) -> bool:
        """A product is considered on sale if
        its current selling price is lower than its full price.
        """
        if not self.price_full or self.price_curr is None:
            return False
        return self.price_curr < self.price_full

    @property
    def is_available(self) -> bool:
        """A product is considered available if
        its quantity is greater than zero.
        """
        return self.quantity is not None and self.quantity != 0

    @property
    def is_sold_out(self) -> bool:
        """A product is considered sold out if its quantity equals zero."""
        return self.quantity is not None and self.quantity == 0

    @property
    def is_last_piece(self) -> bool:
        """A product is considered the last piece if its quantity is one."""
        return self.quantity is not None and self.quantity == 1

    def compare_quantity(self, new: Product) -> ProductQuantityUpdateInfo:
        """Compare the stock availability of the product in two different
        points in time.

        This comparison is meaningful primarily when the ``new`` argument
        represents the same product at a different state or time, such as
        after a stock update.

        Args:
            new (Product): The instance of the product to compare against. It
                should represent the same product at a different state or time.

        Returns:
            ProductQuantityUpdateInfo: A dataclass containing information about
                changes in stock quantity of this product when compared to
                the provided product, such as decreases, increases, depletion,
                or restocking.
        """
        self_quantity = self.quantity or 0
        new_quantity = new.quantity or 0

        if self_quantity > new_quantity:
            decrease = self_quantity - new_quantity
            increase = 0
            last_piece = new.quantity == 1 and self_quantity > 1
            depleted = new.quantity == 0
            restocked = False
        elif self_quantity < new_quantity:
            decrease = 0
            increase = new_quantity - self_quantity
            last_piece = False
            depleted = False
            restocked = self_quantity == 0
        else:
            decrease = 0
            increase = 0
            last_piece = False
            depleted = False
            restocked = False

        return ProductQuantityUpdateInfo(
            decrease, increase, last_piece, depleted, restocked
        )

    def compare_price(self, new: Product) -> ProductPriceUpdateInfo:
        """Compare the pricing details of the product in two different points
        in time.

        This comparison is meaningful primarily when the ``new`` argument
        represents the same product but in a different pricing state, such as
        after a price adjustment.

        Args:
            new (Product): The instance of the product to compare against. It
                should represent the same product at a different state or time.

        Returns:
            ProductPriceUpdateInfo: A dataclass containing information about
                changes in pricing between this product and the provided
                product, such as changes in full price, current price, discount
                rates, and flags indicating the start or end of a sale.
        """
        self_price_full = self.price_full or 0.0
        new_price_full = new.price_full or 0.0
        self_price_curr = self.price_curr or 0.0
        new_price_curr = new.price_curr or 0.0
        self_discount_rate = self.discount_rate or 0.0
        new_discount_rate = new.discount_rate or 0.0

        # Compare full prices
        if self_price_full > new_price_full:
            price_full_decrease = self_price_full - new_price_full
            price_full_increase = 0.0
        elif self_price_full < new_price_full:
            price_full_decrease = 0.0
            price_full_increase = new_price_full - self_price_full
        else:
            price_full_decrease = 0.0
            price_full_increase = 0.0

        # compare current prices
        if self_price_curr > new_price_curr:
            price_curr_decrease = self_price_curr - new_price_curr
            price_curr_increase = 0.0
        elif self_price_curr < new_price_curr:
            price_curr_decrease = 0.0
            price_curr_increase = new_price_curr - self_price_curr
        else:
            price_curr_decrease = 0.0
            price_curr_increase = 0.0

        # compare discount rates
        if self_discount_rate > new_discount_rate:
            discount_rate_decrease = self_discount_rate - new_discount_rate
            discount_rate_increase = 0.0
        elif self_discount_rate < new_discount_rate:
            discount_rate_decrease = 0.0
            discount_rate_increase = new_discount_rate - self_discount_rate
        else:
            discount_rate_decrease = 0.0
            discount_rate_increase = 0.0

        return ProductPriceUpdateInfo(
            price_full_decrease,
            price_full_increase,
            price_curr_decrease,
            price_curr_increase,
            discount_rate_decrease,
            discount_rate_increase,
            has_sale_started=(not self.is_on_sale and new.is_on_sale),
            has_sale_ended=(self.is_on_sale and not new.is_on_sale),
        )


def get_product_page_url(location_id: Union[int, str]) -> str:
    """Generate a FreshPoint.cz product page HTTPS URL for a given location ID.

    Args:
        location_id (Union[int, str]): The ID of the location (also known as
            the page ID and the device ID) for which to generate the URL. This is
            the number that uniquely identifies the location in the FreshPoint.cz
            system. It is the last part of the product page URL, after the last slash.
            For example, in https://my.freshpoint.cz/device/product-list/296,
            the ID is 296.

    Raises:
        FreshPointParserValueError: If the object does not represent a non-negative
            integer (e.g., a negative integer, a float, or a non-numeric string).

    Returns:
        str: The full page URL for the given location ID.
    """
    if not str(location_id).isdigit():
        raise FreshPointParserValueError(
            f'Location ID must respresent a non-negative integer, got: {location_id!r}'
        )
    return f'https://my.freshpoint.cz/device/product-list/{location_id}'


class ProductPage(BasePage[Product]):
    """Data model of a FreshPoint product webpage."""

    location_id: Optional[int] = Field(
        default=None,
        title='Location ID',
        description=(
            'Unique identifier or the product location '
            '(also known as the page ID or the device ID).'
        ),
    )
    """Unique identifier or the product location (also known as the page ID or the device ID)."""
    location_name: Optional[str] = Field(
        default=None,
        title='Location Name',
        description='Name of the product location.',
    )
    """Name of the product location."""

    @property
    def url(self) -> str:
        """URL of the product page."""
        if self.location_id is None:
            raise FreshPointParserValueError(
                'Cannot generate product page URL: location ID is not set.'
            )
        return get_product_page_url(self.location_id)

    @property
    def location_name_lowercase_ascii(self) -> str:
        """Lowercase ASCII representation of the location name.

        If the name is not set, the representation is an empty string.
        """
        return normalize_text(self.location_name)
