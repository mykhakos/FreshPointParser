from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Literal,
    Mapping,
    Optional,
    Tuple,
    TypedDict,
    TypeVar,
    Union,
)

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
)
from pydantic.alias_generators import to_camel

from .._utils import LOCATION_PAGE_URL, get_product_page_url, normalize_text

if sys.version_info >= (3, 11):
    from typing import NamedTuple
else:
    from typing_extensions import NamedTuple


logger = logging.getLogger('freshpointparser.models')
"""Logger of the `freshpointparser.models` package."""


DEFAULT_PRODUCT_PIC_URL = (
    r'https://images.weserv.nl/?url=http://freshpoint.freshserver.cz/'
    r'backend/web/media/photo/1_f587dd3fa21b22.jpg'
)
"""Default picture URL for a product.
The URL points to an image hosted on the FreshPoint server.
"""


MODEL_CONFIG = ConfigDict(alias_generator=to_camel, populate_by_name=True)
"""Pydantic model configuration dictionary for the models in this module."""


TBaseModel = TypeVar('TBaseModel', bound=BaseModel)
"""Type variable for a subclass of `BaseModel`."""


class FieldDiff(NamedTuple):
    """Holds a pair of differing attribute values between two models.

    The first value `value_self` is the attribute value of the model that is
    being compared to the other model, or None if the attribute is not present
    in the model. The second value `value_other` is the attribute value of the
    other model, or None if the attribute is not present in the other model.
    """

    value_self: Any
    """Value of the attribute in the model being compared."""
    value_other: Any
    """Value of the attribute in the other model."""


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


class ProductAttrs(TypedDict, total=False):
    """Provides key names and types for product attributes."""

    id_: int
    name: str
    category: str
    is_vegetarian: bool
    is_gluten_free: bool
    is_promo: bool
    quantity: int
    price_full: float
    price_curr: float
    info: str
    pic_url: str
    location_id: int
    recorded_at: datetime
    name_lowercase_ascii: str
    category_lowercase_ascii: str
    discount_rate: float
    is_on_sale: bool
    is_available: bool
    is_sold_out: bool
    is_last_piece: bool


class Product(BaseModel):
    """Data model of a FreshPoint product."""

    model_config = MODEL_CONFIG

    id_: int = Field(
        default=0,
        serialization_alias='id',
        validation_alias='id',
        title='ID',
        description='Unique identifier or the product.',
    )
    """Unique identifier or the product."""
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
    """Additional information about the product such as ingredients or
    nutritional values.
    """
    pic_url: str = Field(
        default=DEFAULT_PRODUCT_PIC_URL,
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
    """Unique identifier or the product location (also known as the page ID
    or the device ID).
    """
    recorded_at: datetime = Field(
        default_factory=datetime.now,
        title='Recorded At',
        description='Datetime when the product data has been recorded',
    )
    """Datetime when the product data has been recorded."""

    def model_post_init(self, __context: object) -> None:
        """Post-initialization hook for the product model. Do not call directly.
        Override with caution and call `super().model_post_init(__context)`.

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

    def is_newer_than(
        self,
        other: Product,
        precision: Optional[Literal['s', 'm', 'h', 'd']] = None,
    ) -> Optional[bool]:
        """Check if this product's record datetime is newer than another's.

        Compares the `recorded_at` datetime of this product with another product,
        considering the specified precision. Note that precision here means
        truncating the datetime to the desired level (e.g., cutting off seconds,
        minutes, etc.), not rounding it.

        Args:
            other (Product): The product to compare against.
            precision (Optional[Literal['s', 'm', 'h', 'd']]): The level of
                precision for the comparison. Supported values:

                - None: full precision (microseconds) (default)
                - 's': second precision
                - 'm': minute precision
                - 'h': hour precision
                - 'd': date precision

        Raises:
            ValueError: If the precision is not one of the supported values.

        Returns:
            Optional[bool]: With the specified precision taken into account,
                - True if this product's record datetime is newer than the other's
                - False if this product's record datetime is older than the other's
                - None if the record datetimes are the same
        """
        if precision is None:
            recorded_at_self = self.recorded_at
            recorded_at_other = other.recorded_at
        elif precision == 's':
            recorded_at_self = self.recorded_at.replace(microsecond=0)
            recorded_at_other = other.recorded_at.replace(microsecond=0)
        elif precision == 'm':
            recorded_at_self = self.recorded_at.replace(second=0, microsecond=0)
            recorded_at_other = other.recorded_at.replace(
                second=0, microsecond=0
            )
        elif precision == 'h':
            recorded_at_self = self.recorded_at.replace(
                minute=0, second=0, microsecond=0
            )
            recorded_at_other = other.recorded_at.replace(
                minute=0, second=0, microsecond=0
            )
        elif precision == 'd':
            recorded_at_self = self.recorded_at.date()
            recorded_at_other = other.recorded_at.date()
        else:
            raise ValueError(
                f"Invalid precision '{precision}'. "
                f"Expected one of: 's', 'm', 'h', 'd'."
            )
        if recorded_at_self == recorded_at_other:
            return None
        return recorded_at_self > recorded_at_other

    def diff(self, other: Product, **kwargs: Any) -> Dict[str, FieldDiff]:
        """Compare this product with the other one to identify differences.

        This method compares the fields of this product with the fields of
        another product instance to identify which fields have different
        values. The data is serialized according to the models' configurations
        using the `model_dump` method.

        By default, the `timestamp` field is excluded from comparison. However,
        if any keyword arguments (`kwargs`) are provided, *no default exclusions
        are applied*, and the caller is responsible for specifying exclusions
        explicitly. If you provide additional keyword arguments and still want
        to exclude the `timestamp` field, set `exclude={'timestamp'}` or
        equivalent in `kwargs`.

        Args:
            other (Product): The product to compare against.
            **kwargs: Additional keyword arguments to pass to the `model_dump`
                calls to control the serialization process, such as 'exclude',
                'include', 'by_alias', and others. If provided, the default
                exclusion of the `timestamp` field is suppressed.

        Returns:
            Dict[str, FieldDiff]: A dictionary with keys as field names and
                values as namedtuples containing pairs of the differing values
                between the two products. The first value is the one of this
                product and is accessible as `value_self`, and the second value
                is the one of the other product and is accessible as `value_other`.
                If a field is present in one product but not in the other,
                the corresponding value in the namedtuple is set to None.

        Examples:
            >>> now, td = datetime.now(), timedelta(seconds=1)
            >>> product1 = Product(id_=1, quantity=10, recorded_at=now)
            >>> product2 = Product(id_=1, quantity=5, recorded_at=now + td)

            >>> diff = product1.diff(product2)
            >>> print(diff)
            {'quantity': FieldDiff(value_self=10, value_other=5)}

            >>> diff = product1.diff(product2, by_alias=True)
            >>> print(diff)
            {
                'quantity': FieldDiff(value_self=10, value_other=5),
                'createdAt': FieldDiff(value_self=now, value_other=now + td)
            }

            >>> diff = product1.diff(product2, exclude={'quantity'})
            >>> print(diff)
            {'recorded_at': FieldDiff(value_self=now, value_other=now + td)}

            >>> diff = product1.diff(
            ...     product2, exclude={'quantity', 'recorded_at'}
            ... )
            >>> print(diff)
            {}

            >>> diff = product1.diff(product2, include={'quantity'})
            >>> print(diff)
            {'quantity': FieldDiff(value_self=10, value_other=5)}
        """
        # get self's and other's data, optionally remove the timestamps
        if not kwargs:
            kwargs['exclude'] = {'recorded_at'}
        self_asdict = self.model_dump(**kwargs)
        other_asdict = other.model_dump(**kwargs)
        # compare self to other
        diff: Dict[str, FieldDiff] = {}
        for field, value_self in self_asdict.items():
            value_other = other_asdict.get(field, None)
            if value_self != value_other:
                diff[field] = FieldDiff(value_self, value_other)
        # compare other to self (may be relevant for subclasses)
        if other_asdict.keys() != self_asdict.keys():
            for field, value_other in other_asdict.items():
                if field not in self_asdict:
                    diff[field] = FieldDiff(None, value_other)
        return diff

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
            depleted = new.quantity == 0
            restocked = False
        elif self.quantity < new.quantity:
            decrease = 0
            increase = new.quantity - self.quantity
            depleted = False
            restocked = self.quantity == 0
        else:
            decrease = 0
            increase = 0
            depleted = False
            restocked = False
        return ProductQuantityUpdateInfo(
            decrease, increase, depleted, restocked
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


class LocationAttrs(TypedDict, total=False):
    """Provides key names and types for location attributes."""

    id_: int
    name: str
    address: str
    latitude: float
    longitude: float
    discount_rate: float
    is_active: bool
    is_suspended: bool
    name_lowercase_ascii: str
    address_lowercase_ascii: str
    coordinates: Tuple[float, float]


class LocationCoordinates(NamedTuple):
    """Holds the latitude and longitude of a location as a pair of floats.
    Latitude is the first value in the pair, and longitude is the second
    value in the pair.
    """

    latitude: float
    """Latitude of the location."""
    longitude: float
    """Longitude of the location."""


class Location(BaseModel):
    """Data model of a FreshPoint location."""

    model_config = MODEL_CONFIG

    id_: int = Field(
        default=0,
        serialization_alias='id',
        validation_alias='id',
        title='ID',
        description='Unique identifier or the location.',
    )
    """Unique identifier or the location."""
    name: str = Field(
        default='',
        validation_alias=AliasChoices('username', 'name'),
        title='Name',
        description='Name of the location.',
    )
    """Name of the location."""
    address: str = Field(
        default='',
        title='Address',
        description='Address of the location.',
    )
    """Address of the location."""
    latitude: float = Field(
        default=0.0,
        validation_alias=AliasChoices('lat', 'latitude'),
        title='Latitude',
        description='Latitude of the location.',
    )
    """Latitude of the location."""
    longitude: float = Field(
        default=0.0,
        validation_alias=AliasChoices('lon', 'longitude'),
        title='Longitude',
        description='Longitude of the location.',
    )
    """Longitude of the location."""
    discount_rate: float = Field(
        default=0.0,
        validation_alias=AliasChoices('discount', 'discountRate'),
        title='Discount Rate',
        description='Discount rate applied at the location.',
    )
    """Discount rate applied at the location."""
    is_active: bool = Field(
        default=True,
        validation_alias=AliasChoices('active', 'isActive'),
        title='Active',
        description='Indicates whether the location is active.',
    )
    """Indicates whether the location is active."""
    is_suspended: bool = Field(
        default=False,
        validation_alias=AliasChoices('suspended', 'isSuspended'),
        title='Suspended',
        description='Indicates whether the location is suspended.',
    )
    """Indicates whether the location is suspended."""

    @property
    def name_lowercase_ascii(self) -> str:
        """Lowercase ASCII representation of the location name."""
        return normalize_text(self.name)

    @property
    def address_lowercase_ascii(self) -> str:
        """Lowercase ASCII representation of the location address."""
        return normalize_text(self.address)

    @property
    def coordinates(self) -> LocationCoordinates:
        """Coordinates of the location as tuple (latitude, longitude)."""
        return LocationCoordinates(self.latitude, self.longitude)


class BasePage(BaseModel):
    """Base data model of a FreshPoint webpage."""

    model_config = MODEL_CONFIG

    @staticmethod
    def _find_all_with_constraint(
        constraint: Union[Mapping[str, Any], Callable[[TBaseModel], bool]],
        data_items: Dict[int, TBaseModel],
    ) -> Iterator[TBaseModel]:
        """Find all values in a dictionary that match a constraint.

        Args:
            constraint (Union[Mapping[str, Any], Callable[[TBaseModel], bool]]): Either
                a function that receives a data item and returns True if the
                item meets the constraint, or a mapping where each key is
                an attribute (or property) name of the data item and its value
                is the expected value.
            data_items (Dict[int, TBaseModel]): A dictionary of data items with unique
                integer IDs as keys and data item instances as values.

        Returns:
            Iterator[TBaseModel]: A lazy iterator over all data items that match the
                given constraint.
        """
        if callable(constraint):
            return filter(constraint, data_items.values())

        if isinstance(constraint, Mapping):
            return filter(
                lambda data_item: all(
                    getattr(data_item, attr) == value
                    for attr, value in constraint.items()
                ),
                data_items.values(),
            )

        raise TypeError(
            f'Constraint must be either a dictionary or a callable function. '
            f"Got type '{type(constraint)}' instead."
        )

    @classmethod
    def _find_first_with_constraint(
        cls,
        constraint: Union[Mapping[str, Any], Callable[[TBaseModel], bool]],
        data_items: Dict[int, TBaseModel],
    ) -> Optional[TBaseModel]:
        """Find the first value in a dictionary that matches a constraint.

        Args:
            constraint (Union[Mapping[str, Any], Callable[[TBaseModel], bool]]): Either
                a function that receives a data item and returns True if the
                item meets the constraint, or a mapping where each key is
                an attribute (or property) name of the data item and its value
                is the expected value.
            data_items (Dict[int, TBaseModel]): A dictionary of data items with unique
                integer IDs as keys and data item instances as values.

        Returns:
            Optional[TBaseModel]: The first data item that matches the given constraint,
                or None if no such data item is found.
        """
        return next(cls._find_all_with_constraint(constraint, data_items), None)


class ProductPage(BasePage):
    """Data model of a FreshPoint product webpage."""

    location_id: int = Field(
        default=0,
        title='Location ID',
        description=(
            'Unique identifier or the product location (also known as '
            'the page ID or the device ID).'
        ),
    )
    """Unique identifier or the product location (also known as the page ID
    or the device ID).
    """
    location_name: str = Field(
        default='',
        title='Location Name',
        description='Name of the product location.',
    )
    """Name of the product location."""
    products: Dict[int, Product] = Field(
        default_factory=dict,
        repr=False,
        title='Products',
        description=(
            'Dictionary of product IDs as keys and data models on the page '
            'as values.'
        ),
    )
    """Dictionary of product IDs as keys and data models on the page
    as values.
    """

    @property
    def url(self) -> str:
        """URL of the product page."""
        return get_product_page_url(self.location_id)

    @property
    def location_name_lowercase_ascii(self) -> str:
        """Lowercase ASCII representation of the location name."""
        return normalize_text(self.location_name)

    @property
    def products_as_list(self) -> List[Product]:
        """Products listed on the page."""
        return list(self.products.values())

    @property
    def product_count(self) -> int:
        """Total number of products on the page."""
        return len(self.products)

    @property
    def product_names(self) -> List[str]:
        """Names of products listed on the page."""
        return [pr.name for pr in self.products.values()]

    @property
    def product_names_lowercase_ascii(self) -> List[str]:
        """Names of products listed on the page normalized to
        lowercase ASCII.
        """
        return [pr.name_lowercase_ascii for pr in self.products.values()]

    @property
    def product_categories(self) -> List[str]:
        """Unique product categories listed on the page."""
        return list(set(pr.category for pr in self.products.values()))

    @property
    def product_categories_lowercase_ascii(self) -> List[str]:
        """Unique product categories listed on the page normalized to
        lowercase ASCII.
        """
        return list(
            set(pr.category_lowercase_ascii for pr in self.products.values())
        )

    def find_products(
        self,
        constraint: Union[
            ProductAttrs, Mapping[str, Any], Callable[[Product], bool]
        ],
    ) -> Iterator[Product]:
        """Find all products that match a constraint.

        Tip: To convert the result from an iterator to a list, use
        `list(page.find_products(...))`.

        Args:
            constraint (Union[ProductAttrs, Mapping[str, Any], Callable[[Product], bool]]):
                Either a callable that receives a Product instance and returns
                True if the product meets the constraint, or a mapping where
                each key is an attribute (or property) name of the Product
                model and its value is the expected value.

        Raises:
            AttributeError: If a product attribute name is invalid.

        Returns:
            Iterator[Product]: A lazy iterator over all products that match
                the given constraint.

        Examples:
            Category 'Dezerty' and available (with dictionary)
            >>> products = page.find_products({
            >>>     'category': 'Dezerty',
            >>>     'is_available': True,
            >>> })
            # finds all available products in the 'Dezerty' category (using a dictionary for parameters)

            >>> products = page.find_products(
            >>>     lambda p: p.category == 'Dezerty' and p.is_available
            >>> )
            # finds all available products in the 'Dezerty' category (using a lambda function)

            >>> products = page.find_products(
            >>>     lambda p: 'sendvic' in p.name_lowercase_ascii and p.price_curr < 100
            >>> )
            # finds all products with 'sendvic' in the name and price less than 100 CZK
        """
        return self._find_all_with_constraint(constraint, self.products)

    def find_product(
        self,
        constraint: Union[
            ProductAttrs, Mapping[str, Any], Callable[[Product], bool]
        ],
    ) -> Optional[Product]:
        """Find a single product that matches a constraint. If more than one
        product matches the constraint, the first one found is returned.

        Note: `product = find_product(...)` is equivalent to
        `product = next(find_products(...), None)`.

        Args:
            constraint (Union[ProductAttrs, Mapping[str, Any], Callable[[Product], bool]]):
                Either a callable that receives a Product instance and returns
                True if the product meets the constraint, or a mapping where
                each key is an attribute (or property) name of the Product
                model and its value is the expected value.

        Raises:
            AttributeError: If a product attribute name is invalid.

        Returns:
            Optional[Product]: The first product that matches the given
                constraint, or None if no such product is found.

        Examples:
            >>> product = page.find_product({
            ...     'name': 'Vícezrnný rohlík se šunkou'
            ... })
            # finds the product named 'Vícezrnný rohlík se šunkou' (using a dictionary for parameters)

            >>> product = page.find_product(
            ...     lambda p: p.name == 'Vícezrnný rohlík se šunkou'
            ... )
            # finds the product named 'Vícezrnný rohlík se šunkou' (using a lambda function)

            >>> product = page.find_product(
            ...     lambda p: 'rohlik' in p.name_lowercase_ascii
            ...     and p.quantity >= 2
            ...     and p.price_curr <= 50
            ... )
            # finds the first product with 'rohlik' in the name, at least 2 items in stock, and price less than 50 CZK
        """
        return self._find_first_with_constraint(constraint, self.products)


class LocationPage(BasePage):
    """Data model of a FreshPoint location webpage."""

    model_config = MODEL_CONFIG

    locations: Dict[int, Location] = Field(
        default_factory=dict,
        repr=False,
        title='Locations',
        description=(
            'Dictionary of location IDs as keys and data models on the page '
            'as values.'
        ),
    )
    """Dictionary of location IDs as keys and data models on the page
    as values.
    """

    @property
    def url(self) -> str:
        """URL of the location page."""
        return LOCATION_PAGE_URL

    @property
    def locations_as_list(self) -> List[Location]:
        """Locations listed on the page."""
        return list(self.locations.values())

    @property
    def location_count(self) -> int:
        """Total number of locations on the page."""
        return len(self.locations)

    @property
    def location_names(self) -> List[str]:
        """Location names listed on the page."""
        return [loc.name for loc in self.locations.values()]

    @property
    def location_names_lowercase_ascii(self) -> List[str]:
        """Location names listed on the page normalized to lowercase ASCII."""
        return [loc.name_lowercase_ascii for loc in self.locations.values()]

    @property
    def location_addresses(self) -> List[str]:
        """Location addresses listed on the page."""
        return [loc.address for loc in self.locations.values()]

    @property
    def location_addresses_lowercase_ascii(self) -> List[str]:
        """Location addresses listed on the page normalized to lowercase ASCII."""
        return [loc.address_lowercase_ascii for loc in self.locations.values()]

    def find_locations(
        self,
        constraint: Union[
            LocationAttrs, Mapping[str, Any], Callable[[Location], bool]
        ],
    ) -> Iterator[Location]:
        """Find all locations that match a constraint.

        Tip: To convert the result from an iterator to a list, use
        `list(page.find_locations(...))`.

        Args:
            constraint (Union[LocationAttrs, Mapping[str, Any], Callable[[Location], bool]]):
                Either a callable that receives a Location instance and
                returns True if the location meets the constraint, or a mapping
                where each key is an attribute (or property) name of
                the Location model and its value is the expected value.

        Raises:
            AttributeError: If a product attribute name is invalid.

        Returns:
            Iterator[Location]: A lazy iterator over all locations that match
            the given constraint.

        Examples:
            >>> locations = page.find_locations({'is_active': True})
            # finds all active locations (using a dictionary for parameters)

            >>> locations = page.find_locations(lambda loc: loc.is_active)
            # finds all active locations (using a lambda function)

            >>> locations = page.find_locations(
            >>>    lambda loc: loc.is_active and 'praha' in loc.address_lowercase_ascii
            >>> )
            # finds all active locations in Prague (using a lambda function)
        """
        return self._find_all_with_constraint(constraint, self.locations)

    def find_location(
        self,
        constraint: Union[
            LocationAttrs, Mapping[str, Any], Callable[[Location], bool]
        ],
    ) -> Optional[Location]:
        """Find a single location that matches the given constraint. If more
        than one location matches the constraint, the first one found is returned.

        Args:
            constraint (Union[LocationAttrs, Mapping[str, Any], Callable[[Location], bool]]):
                Either a callable that receives a Location instance and
                returns True if the location meets the constraint, or a mapping
                where each key is an attribute (or property) name of
                the Location model and its value is the expected value.

        Raises:
            AttributeError: If a product attribute name is invalid.

        Returns:
            Optional[Location]: The first location that matches the given
                constraint, or None if no such location is found.

        Examples:
            >>> location = page.find_location({'name': 'Decathlon Letňany'})
            # finds the location named 'Decathlon Letňany' (using a dictionary for parameters)

            >>> location = page.find_location(
            ...     lambda loc: loc.name == 'Decathlon Letňany'
            ... )
            # finds the location named 'Decathlon Letňany' (using a lambda function)

            >>> location = page.find_location(
            >>>     lambda loc: 'decathlon' in loc.name_lowercase_ascii
            >>>     and 'praha' in loc.address_lowercase_ascii
            >>>     and loc.is_active
            >>> )
            # finds the first active Decathlon location in Prague (using a lambda function)
        """
        return self._find_first_with_constraint(constraint, self.locations)
