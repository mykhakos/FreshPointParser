from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Union

from pydantic import (
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    ValidationInfo,
    field_validator,
)

from .._utils import normalize_text
from ._base import BaseItem, BasePage


@dataclass
class ProductQuantityChange:
    """Result of comparing the stock quantity of a product at two points in time.

    Produced by ``Product.compare_quantity``. The comparison is symmetric:
    ``a.compare_quantity(b)`` produces the mirror of ``b.compare_quantity(a)``.
    Fields with zero or ``False`` values indicate no change in that dimension.
    """

    quantity_decrease: int = 0
    """How many fewer units exist compared to the other product. Zero means no decrease."""
    quantity_increase: int = 0
    """How many more units exist compared to the other product. Zero means no increase."""
    is_last_piece: bool = False
    """Transition flag: quantity crossed from greater than one to exactly one.

    Captures the transition to last-piece status, not just the state.
    Use ``Product.is_last_piece`` to check current state instead.
    """
    is_depleted: bool = False
    """Transition flag: quantity crossed from greater than zero to zero."""
    is_restocked: bool = False
    """Transition flag: quantity crossed from zero to greater than zero."""


@dataclass
class ProductPriceChange:
    """Result of comparing the pricing of a product at two points in time.

    Produced by ``Product.compare_price``. The comparison is symmetric:
    ``a.compare_price(b)`` produces the mirror of ``b.compare_price(a)``.
    Fields with zero or ``False`` values indicate no change in that dimension.
    """

    price_full_decrease: float = 0.0
    """How much the full price decreased. Zero means no decrease."""
    price_full_increase: float = 0.0
    """How much the full price increased. Zero means no increase."""
    price_curr_decrease: float = 0.0
    """How much the current selling price decreased. Zero means no decrease."""
    price_curr_increase: float = 0.0
    """How much the current selling price increased. Zero means no increase."""
    discount_rate_decrease: float = 0.0
    """How much the discount rate decreased (0-1 scale). Zero means no decrease."""
    discount_rate_increase: float = 0.0
    """How much the discount rate increased (0-1 scale). Zero means no increase."""
    has_sale_started: bool = False
    """Transition flag: the product moved from not on sale to on sale."""
    has_sale_ended: bool = False
    """Transition flag: the product moved from on sale to not on sale."""


class Product(BaseItem):
    """Data model of a FreshPoint product.

    All fields are ``Optional`` with ``None`` as the sentinel for "not available".
    Computed properties (``price``, ``discount_rate``, ``is_on_sale``, etc.) are
    always safe to access regardless of which fields were successfully parsed.
    """

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
            'Whether the product is marked as a promotional item. Unreliable: '
            'a product may be on sale without this flag set, and vice versa. '
            'Use ``is_on_sale`` to check for an active discount.'
        ),
    )
    """Whether the product is marked as a promotional item.

    Unreliable: a product may be on sale without this flag set, and vice versa.
    Use ``is_on_sale`` to check for an active discount.
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
    allergens: Optional[List[str]] = Field(
        default=None,
        title='Allergens',
        description=(
            "Allergen list parsed from the site's comma-separated string. "
            'An empty list means the attribute was present but blank; '
            '``None`` means the attribute was absent entirely.'
        ),
    )
    """Allergen list parsed from the site's comma-separated string.

    An empty list means the attribute was present but blank; ``None`` means
    the attribute was absent entirely.
    """
    pic_url: Optional[str] = Field(
        default=None,
        title='Illustrative Product Picture URL',
        description='URL of the illustrative product image.',
    )
    """URL of the illustrative product image."""

    @field_validator('price_curr', mode='after')
    @classmethod
    def _validate_price_curr(cls, price_curr: float, info: ValidationInfo) -> float:
        """Validate that the current selling price is not higher than the full price."""
        price_full = info.data.get('price_full')
        if price_full is not None and price_full < price_curr:
            raise ValueError(
                f'Full price ({price_full}) cannot be lower than '
                f'current price ({price_curr}).'
            )
        return price_curr

    @property
    def name_lowercase_ascii(self) -> str:
        """Lowercase ASCII representation of ``name``. Empty string when unset."""
        return normalize_text(self.name)

    @property
    def category_lowercase_ascii(self) -> str:
        """Lowercase ASCII representation of ``category``. Empty string when unset."""
        return normalize_text(self.category)

    @property
    def price(self) -> Optional[float]:
        """The effective selling price.

        Returns ``price_curr`` when set, falls back to ``price_full``.
        ``None`` when neither price is set.
        """
        if self.price_curr is not None:
            return self.price_curr
        if self.price_full is not None:
            return self.price_full
        return None

    @property
    def discount_rate(self) -> Optional[float]:
        """The discount rate as a value between 0 and 1, rounded to two decimal places.

        Calculated as ``(price_full - price_curr) / price_full``. Returns 0.0 when
        ``price_full`` is zero. ``None`` when either price is unset.
        """
        if self.price_full is None or self.price_curr is None:
            return None
        try:
            return round((self.price_full - self.price_curr) / self.price_full, 2)
        except ZeroDivisionError:
            return 0.0

    @property
    def is_on_sale(self) -> bool:
        """``True`` when ``price_curr`` is set and lower than ``price_full``."""
        if self.price_full is None or self.price_curr is None:
            return False
        return self.price_curr < self.price_full

    @property
    def is_available(self) -> bool:
        """``True`` when ``quantity`` is set and greater than zero."""
        return self.quantity is not None and self.quantity != 0

    @property
    def is_sold_out(self) -> bool:
        """``True`` when ``quantity`` is set and equals zero."""
        return self.quantity is not None and self.quantity == 0

    @property
    def is_last_piece(self) -> bool:
        """``True`` when ``quantity`` is set and equals one."""
        return self.quantity is not None and self.quantity == 1

    def compare_quantity(self, other: Product) -> ProductQuantityChange:
        """Compare stock quantity with another product instance.

        This comparison is meaningful primarily when the ``other`` argument
        represents the same product at a different state or time, such as
        after a stock update. The result is symmetric: calling
        ``a.compare_quantity(b)`` produces the mirror of ``b.compare_quantity(a)``.

        If either product does not have quantity information, the comparison
        will indicate no changes in quantity.

        Args:
            other (Product): The instance of the product to compare against. It
                should represent the same product at a different state or time.

        Returns:
            ProductQuantityChange: A dataclass containing information about
                changes in stock quantity of this product when compared to
                the provided product, such as decreases, increases, depletion,
                or restocking.

        Example:
            ::

                morning = Product(id_='42', quantity=5)
                evening = Product(id_='42', quantity=0)
                change = morning.compare_quantity(evening)
                change.is_depleted  # True
                change.quantity_decrease  # 5
        """
        if self.quantity is None or other.quantity is None:
            quantity_decrease = 0
            quantity_increase = 0
            is_last_piece = False
            is_depleted = False
            is_restocked = False
        elif self.quantity > other.quantity:
            quantity_decrease = self.quantity - other.quantity
            quantity_increase = 0
            is_last_piece = other.quantity == 1 and self.quantity > 1
            is_depleted = other.quantity == 0
            is_restocked = False
        elif self.quantity < other.quantity:
            quantity_decrease = 0
            quantity_increase = other.quantity - self.quantity
            is_last_piece = False
            is_depleted = False
            is_restocked = self.quantity == 0
        else:
            quantity_decrease = 0
            quantity_increase = 0
            is_last_piece = False
            is_depleted = False
            is_restocked = False

        return ProductQuantityChange(
            quantity_decrease,
            quantity_increase,
            is_last_piece,
            is_depleted,
            is_restocked,
        )

    def compare_price(self, other: Product) -> ProductPriceChange:
        """Compare pricing details with another product instance.

        This comparison is meaningful primarily when the ``other`` argument
        represents the same product but in a different pricing state, such as
        after a price adjustment. The result is symmetric: calling
        ``a.compare_price(b)`` produces the mirror of ``b.compare_price(a)``.

        If either product does not specify full or current prices, the comparison
        will indicate no changes in those prices and related metrics such as
        discount rates or sale status.

        Args:
            other (Product): The instance of the product to compare against. It
                should represent the same product at a different state or time.

        Returns:
            ProductPriceChange: A dataclass containing information about
                changes in pricing between this product and the provided
                product, such as changes in full price, current price, discount
                rates, and flags indicating the start or end of a sale.

        Example:
            ::

                before = Product(id_='42', price_full=100.0, price_curr=100.0)
                after = Product(id_='42', price_full=100.0, price_curr=75.0)
                change = before.compare_price(after)
                change.has_sale_started  # True
                change.price_curr_decrease  # 25.0
        """
        # compare full prices
        if self.price_full is None or other.price_full is None:
            price_full_decrease = 0.0
            price_full_increase = 0.0
        elif self.price_full > other.price_full:
            price_full_decrease = self.price_full - other.price_full
            price_full_increase = 0.0
        elif self.price_full < other.price_full:
            price_full_decrease = 0.0
            price_full_increase = other.price_full - self.price_full
        else:
            price_full_decrease = 0.0
            price_full_increase = 0.0

        # compare current prices
        if self.price_curr is None or other.price_curr is None:
            price_curr_decrease = 0.0
            price_curr_increase = 0.0
        elif self.price_curr > other.price_curr:
            price_curr_decrease = self.price_curr - other.price_curr
            price_curr_increase = 0.0
        elif self.price_curr < other.price_curr:
            price_curr_decrease = 0.0
            price_curr_increase = other.price_curr - self.price_curr
        else:
            price_curr_decrease = 0.0
            price_curr_increase = 0.0

        # compare discount rates
        self_discount_rate = self.discount_rate
        other_discount_rate = other.discount_rate
        if self_discount_rate is None or other_discount_rate is None:
            discount_rate_decrease = 0.0
            discount_rate_increase = 0.0
        elif self_discount_rate > other_discount_rate:
            discount_rate_decrease = self_discount_rate - other_discount_rate
            discount_rate_increase = 0.0
        elif self_discount_rate < other_discount_rate:
            discount_rate_decrease = 0.0
            discount_rate_increase = other_discount_rate - self_discount_rate
        else:
            discount_rate_decrease = 0.0
            discount_rate_increase = 0.0

        return ProductPriceChange(
            price_full_decrease,
            price_full_increase,
            price_curr_decrease,
            price_curr_increase,
            discount_rate_decrease,
            discount_rate_increase,
            has_sale_started=(not self.is_on_sale and other.is_on_sale),
            has_sale_ended=(self.is_on_sale and not other.is_on_sale),
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

    Returns:
        str: The full page URL for the given location ID.

    Raises:
        ValueError: If the object does not represent a non-negative integer
            (e.g., a negative integer, a float, or a non-numeric string).
    """
    if not str(location_id).isdigit():
        raise ValueError(
            f'Location ID must represent a non-negative integer, got: {location_id!r}'
        )
    return f'https://my.freshpoint.cz/device/product-list/{location_id}'


class ProductPage(BasePage[Product]):
    """Data model of a FreshPoint product page.

    Extends ``BasePage`` with location context (``location_id``, ``location_name``)
    identifying which vending machine the products belong to.
    """

    location_id: Optional[str] = Field(
        default=None,
        coerce_numbers_to_str=True,
        title='Location ID',
        description=(
            'Unique identifier of the product location '
            '(also known as the page ID or the device ID).'
        ),
    )
    """Unique identifier of the product location (also known as the page ID or the device ID)."""
    location_name: Optional[str] = Field(
        default=None,
        title='Location Name',
        description='Name of the product location.',
    )
    """Name of the product location."""

    @property
    def url(self) -> Optional[str]:
        """URL of this product page. ``None`` when ``location_id`` is not set."""
        if self.location_id is None:
            return None
        return get_product_page_url(self.location_id)

    @property
    def location_name_lowercase_ascii(self) -> str:
        """Lowercase ASCII representation of ``location_name``. Empty string when unset."""
        return normalize_text(self.location_name)
