from __future__ import annotations

from dataclasses import dataclass

from pydantic import Field, NonNegativeFloat, NonNegativeInt

from .._utils import get_product_page_url, normalize_text
from ._base import BaseItem, BasePage


@dataclass
class ProductQuantityUpdateInfo:
    """Summarizes the details of stock quantity changes in a product."""

    stock_decrease: int = 0
    """Decrease in stock quantity. Represents how many items
    are fewer in the new product compared to the old product.
    A value of 0 implies no decrease.
    """
    stock_increase: int = 0
    """Increase in stock quantity. Indicates how many items
    are more in the new product compared to the old product.
    A value of 0 implies no increase.
    """
    stock_is_last_piece: bool = False
    """A flag indicating the product is the last piece in stock.
    True if the new product's stock quantity is one while the old
    product's stock was greater than one.
    """
    stock_depleted: bool = False
    """A flag indicating complete depletion of the product stock.
    True if the new product's stock quantity is zero while the old
    product's stock was greater than zero.
    """
    stock_restocked: bool = False
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
    sale_started: bool = False
    """A flag indicating whether a sale has started on the product.
    True if the new product is on sale and the old product was not.
    """
    sale_ended: bool = False
    """A flag indicating whether a sale has ended on the product.
    True if the new product is not on sale and the old product was.
    """


class Product(BaseItem):
    """Data model of a FreshPoint product."""

    name: str = Field(
        default='',
        title='Name',
        description='Name of the product.',
    )
    """Name of the product."""
    category: str = Field(
        default='',
        title='Category',
        description='Category of the product.',
    )
    """Category of the product."""
    is_vegetarian: bool = Field(
        default=False,
        title='Vegetarian',
        description='Indicates if the product is vegetarian.',
    )
    """Indicates if the product is vegetarian."""
    is_gluten_free: bool = Field(
        default=False,
        title='Gluten Free',
        description='Indicates if the product is gluten-free.',
    )
    """Indicates if the product is gluten-free."""
    is_promo: bool = Field(
        default=False,
        title='Promo',
        description=(
            'Indicates if the product is being promoted. Note that the '
            'product being on a promo does not guarantee that the product '
            'currently has a discount and vice versa.'
        ),
    )
    """Indicates whether the product is being promoted.

    **The product being a promo does not guarantee that the product currently
    has a discount and vice versa.** Use `is_on_sale` to check if the product is
    on sale.
    """
    quantity: NonNegativeInt = Field(
        default=0,
        title='Quantity',
        description='Quantity of product items in stock.',
    )
    """Quantity of product items in stock."""
    price_full: NonNegativeFloat = Field(
        default=0.0,
        title='Full Price',
        description='Full price of the product.',
    )
    """Full price of the product."""
    price_curr: NonNegativeFloat = Field(
        default=0.0,
        title='Current Price',
        description='Current selling price of the product.',
    )
    """Current selling price of the product."""
    info: str = Field(
        default='',
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
    location_id: int = Field(
        default=0,
        title='Location ID',
        description=(
            'Unique identifier or the product location (also known as '
            'the page ID or the device ID).'
        ),
    )
    """Unique identifier or the product location (also known as the page ID or the device ID)."""

    def model_post_init(self, __context: object) -> None:
        """Post-initialization hook for the product model. Do not call directly.
        Override with caution and call `super().model_post_init(__context)`.

        :meta private:

        Args:
            __context (object): The context of the model instance.
        """
        fields_set = self.model_fields_set
        if 'price_full' in fields_set and 'price_curr' not in fields_set:
            self.price_curr = self.price_full
        elif 'price_curr' in fields_set and 'price_full' not in fields_set:
            self.price_full = self.price_curr

    @property
    def name_lowercase_ascii(self) -> str:
        """Lowercase ASCII representation of the product name."""
        return normalize_text(self.name)

    @property
    def category_lowercase_ascii(self) -> str:
        """Lowercase ASCII representation of the product category."""
        return normalize_text(self.category)

    @property
    def discount_rate(self) -> float:
        """Discount rate (<0; 1>) of the product, calculated based on
        the difference between the full price and the current selling price.
        """
        if self.price_full == 0 or self.price_full < self.price_curr:
            return 0
        return round((self.price_full - self.price_curr) / self.price_full, 2)

    @property
    def is_on_sale(self) -> bool:
        """A product is considered on sale if
        its current selling price is lower than its full price.
        """
        return self.price_curr < self.price_full

    @property
    def is_available(self) -> bool:
        """A product is considered available if
        its quantity is greater than zero.
        """
        return self.quantity != 0

    @property
    def is_sold_out(self) -> bool:
        """A product is considered sold out if its quantity equals zero."""
        return self.quantity == 0

    @property
    def is_last_piece(self) -> bool:
        """A product is considered the last piece if its quantity is one."""
        return self.quantity == 1

    def compare_quantity(self, new: Product) -> ProductQuantityUpdateInfo:
        """Compare the stock availability of the product in two different
        points in time.

        This comparison is meaningful primarily when the `new` argument
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
        if self.quantity > new.quantity:
            decrease = self.quantity - new.quantity
            increase = 0
            last_piece = new.quantity == 1 and self.quantity > 1
            depleted = new.quantity == 0
            restocked = False
        elif self.quantity < new.quantity:
            decrease = 0
            increase = new.quantity - self.quantity
            last_piece = False
            depleted = False
            restocked = self.quantity == 0
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

        This comparison is meaningful primarily when the `new` argument
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
        # Compare full prices
        if self.price_full > new.price_full:
            price_full_decrease = self.price_full - new.price_full
            price_full_increase = 0.0
        elif self.price_full < new.price_full:
            price_full_decrease = 0.0
            price_full_increase = new.price_full - self.price_full
        else:
            price_full_decrease = 0.0
            price_full_increase = 0.0
        # compare current prices
        if self.price_curr > new.price_curr:
            price_curr_decrease = self.price_curr - new.price_curr
            price_curr_increase = 0.0
        elif self.price_curr < new.price_curr:
            price_curr_decrease = 0.0
            price_curr_increase = new.price_curr - self.price_curr
        else:
            price_curr_decrease = 0.0
            price_curr_increase = 0.0
        # compare discount rates
        if self.discount_rate > new.discount_rate:
            discount_rate_decrease = self.discount_rate - new.discount_rate
            discount_rate_increase = 0.0
        elif self.discount_rate < new.discount_rate:
            discount_rate_decrease = 0.0
            discount_rate_increase = new.discount_rate - self.discount_rate
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
            sale_started=(not self.is_on_sale and new.is_on_sale),
            sale_ended=(self.is_on_sale and not new.is_on_sale),
        )


class ProductPage(BasePage[Product]):
    """Data model of a FreshPoint product webpage."""

    location_id: int = Field(
        default=0,
        title='Location ID',
        description=(
            'Unique identifier or the product location '
            '(also known as the page ID or the device ID).'
        ),
    )
    """Unique identifier or the product location (also known as the page ID or the device ID)."""
    location_name: str = Field(
        default='',
        title='Location Name',
        description='Name of the product location.',
    )
    """Name of the product location."""

    @property
    def url(self) -> str:
        """URL of the product page."""
        return get_product_page_url(self.location_id)

    @property
    def location_name_lowercase_ascii(self) -> str:
        """Lowercase ASCII representation of the location name."""
        return normalize_text(self.location_name)
