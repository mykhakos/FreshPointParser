import logging
import sys
import time
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Mapping,
    Optional,
    TypedDict,
    TypeVar,
    Union,
)

from pydantic import (
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

T = TypeVar('T', bound=BaseModel)


class DiffValue(NamedTuple):
    """Holds a pair of differing attribute values between two products.
    The first value is the attribute value of the first product, while
    the second value is the attribute value of the second product.

    Args:
        value_self (Any):
            Value of the attribute in the first product. None if
            the attribute is not present in the first product.
        value_other (Any):
            Value of the attribute in the second product. None if
            the attribute is not present in the second product.
    """

    value_self: Any
    """Value of the attribute in the first product."""
    value_other: Any
    """Value of the attribute in the second product."""


@dataclass
class ProductQuantityUpdateInfo:
    """Summarizes the details of stock quantity changes in a product,
    as determined by comparing two instances of this product.
    """

    stock_decrease: int = 0
    """Decrease in stock quantity, representing how many items
    are fewer in the new product compared to the old product.
    A value of 0 implies no decrease.
    """
    stock_increase: int = 0
    """Increase in stock quantity, indicating how many items
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
    """Summarizes the details of pricing changes of a product,
    as determined by comparing two instances of this product.
    """

    price_full_decrease: float = 0.0
    """Decrease in the full price of the product, representing the difference
    between its old full price and its new full price.
    A value of 0.0 indicates no decrease.
    """
    price_full_increase: float = 0.0
    """Increase of the full price of the product, representing the difference
    between its new full price and its old full price.
    A value of 0.0 indicates no increase.
    """
    price_curr_decrease: float = 0.0
    """Decrease in the current selling price of the product, representing
    the difference between its old selling price and its new selling price.
    A value of 0.0 indicates no decrease.
    """
    price_curr_increase: float = 0.0
    """Increase in the current selling price of the product, representing
    the difference between its new selling price and its old selling price.
    A value of 0.0 indicates no increase.
    """
    discount_rate_decrease: float = 0.0
    """Decrease in the discount rate of the product, indicating the reduction
    of the discount rate in the new product compared to the old product.
    A value of 0.0 indicates that the discount rate has not decreased.
    """
    discount_rate_increase: float = 0.0
    """Increase in the discount rate of the product, indicating the increment
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
    quantity: int
    price_full: float
    price_curr: float
    info: str
    pic_url: str
    location_id: int
    timestamp: float
    name_lowercase_ascii: str
    category_lowercase_ascii: str
    discount_rate: float
    is_on_sale: bool
    is_available: bool
    is_sold_out: bool
    is_last_piece: bool


class Product(BaseModel):
    """Data model of a FreshPoint product record.

    Args:
        id_ (int):
            Unique identifier or the product. Defaults to 0.
        name (str):
            Name of the product. Defaults to an empty string.
        category (str):
            Category of the product. Defaults to an empty string.
        is_vegetarian (bool):
            Indicates whether the product is vegetarian. Defaults to False.
        is_gluten_free (bool):
            Indicates whether the product is gluten-free. Defaults to False.
        quantity (int):
            Quantity of product items in stock. Defaults to 0.
        price_full (float):
            Full price of the product. If not provided, matches the current
            selling price if the latter is provided or is set to 0 otherwise.
        price_curr (float):
            Current selling price. If not provided, matches the full price
            if the latter is provided or is set to 0 otherwise.
        info (str):
            Additional information about the product such as ingredients or
            nutritional values. Defaults to an empty string.
        pic_url (str):
            URL of the illustrative product image. Default URL is used if not
            provided.
        location_id (int):
            Unique identifier or the product location (also known as the page ID
            or the device ID). Defaults to 0.
        timestamp (int):
            Timestamp of the product creation with the provided data.
            Defaults to the time of instantiation.
    """

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
        title='Illustrative Picture URL',
        description='URL of the product image.',
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
    timestamp: float = Field(
        default_factory=time.time,
        title='Timestamp',
        description='Timestamp of the product creation with the provided data.',
    )
    """Timestamp of the product creation with the provided data."""

    def model_post_init(self, __context: object) -> None:
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

    def is_newer_than(self, other: 'Product') -> bool:
        """Determine if this product is newer than the given one by
        comparing their creation timestamps.

        Args:
            other (Product): The product to compare against.

        Returns:
            bool: True if this product is newer than the other product,
                False otherwise.
        """
        return self.timestamp > other.timestamp

    def diff(self, other: 'Product', **kwargs: Any) -> Dict[str, DiffValue]:
        """Compare this product with another to identify differences.

        This method compares the fields of this product with the fields of
        another product instance to identify differences between them.
        `model_dump` method is used to extract the data from the product
        instances.

        Args:
            other (Product): The product to compare against.
            **kwargs: Additional keyword arguments to pass to the `model_dump`
                method calls of the product instances.

        Returns:
            Dict[str, DiffValue]: A dictionary with keys as attribute names and
                values as namedtuples containing the differing values between
                this product and the other product.
        """
        # get self's and other's data and remove the timestamps
        self_asdict = self.model_dump(**kwargs)
        other_asdict = other.model_dump(**kwargs)
        # compare self to other
        diff: Dict[str, DiffValue] = {}
        for attr, value in self_asdict.items():
            other_value = other_asdict.get(attr, None)
            if value != other_value:
                diff[attr] = DiffValue(value, other_value)
        # compare other to self (may be relevant for subclasses)
        for attr, value in other_asdict.items():
            if attr not in self_asdict:
                diff[attr] = DiffValue(None, value)
        return diff

    def compare_quantity(self, new: 'Product') -> ProductQuantityUpdateInfo:
        """Compare the stock availability of the product in two different
        points in time.

        This comparison is meaningful primarily when the `new` argument
        represents the same product at a different state or time, such as
        after a stock update.

        Args:
            new (Product): The instance of the product to compare against. It
                should represent the same product at a different state or time.

        Returns:
            ProductQuantityUpdateInfo: An dataclass containing information about
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

    def compare_price(self, new: 'Product') -> ProductPriceUpdateInfo:
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
    coordinates: tuple[float, float]


class LocationCoordinates(NamedTuple):
    """Holds the latitude and longitude of a location as a pair of floats.

    Args:
        latitude (float): Latitude of the location (first value in the pair).
        longitude (float): Longitude of the location (second value in the pair).
    """

    latitude: float
    """Latitude of the location."""
    longitude: float
    """Longitude of the location."""


class Location(BaseModel):
    """Data model of a FreshPoint location record.

    Args:
        id_ (int):
            Unique identifier or the location. Defaults to 0.
        name (str):
            Name of the location. Defaults to an empty string.
        address (str):
            Address of the location. Defaults to an empty string.
        latitude (float):
            Latitude of the location. Defaults to 0.0.
        longitude (float):
            Longitude of the location. Defaults to 0.0.
        discount_rate (float):
            Discount rate applied at the location. Defaults to 0.0.
        is_active (bool):
            Indicates whether the location is active. Defaults to True.
        is_suspended (bool):
            Indicates whether the location is suspended. Defaults to False.
    """

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
        validation_alias='username',
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
        validation_alias='lat',
        title='Latitude',
        description='Latitude of the location.',
    )
    """Latitude of the location."""
    longitude: float = Field(
        default=0.0,
        validation_alias='lon',
        title='Longitude',
        description='Longitude of the location.',
    )
    """Longitude of the location."""
    discount_rate: float = Field(
        default=0.0,
        validation_alias='discount',
        title='Discount Rate',
        description='Discount rate applied at the location.',
    )
    """Discount rate applied at the location."""
    is_active: bool = Field(
        default=True,
        validation_alias='active',
        title='Active',
        description='Indicates whether the location is active.',
    )
    """Indicates whether the location is active."""
    is_suspended: bool = Field(
        default=False,
        validation_alias='suspended',
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
    """Base data model of a FreshPoint webpage.

    Args:
        html_hash_sha1 (str):
            Hexadecimal representation of the SHA-1 hash of the page HTML.
    """

    model_config = MODEL_CONFIG

    html_hash_sha1: str = Field(
        default='',
        title='SHA-1 HTML Hash',
        description=(
            'Hexadecimal representation of the SHA-1 hash of the page HTML.'
        ),
    )
    """Hexadecimal representation of the SHA-1 hash of the page HTML."""

    @staticmethod
    def _find_all_with_constraint(
        constraint: Union[Mapping[str, Any], Callable[[T], bool]],
        data_items: Dict[int, T],
    ) -> Iterator[T]:
        """Find all values in a dictionary that match a constraint.

        Args:
            constraint (Union[Mapping[str, Any], Callable[[T], bool]]): Either
                a function that receives a data item and returns True if the
                item meets the constraint, or a mapping where each key is
                an attribute (or property) name of the data item and its value
                is the expected value.
            data_items (Dict[int, T]): A dictionary of data items with unique
                integer IDs as keys and data item instances as values.

        Returns:
            Iterator[T]: A lazy iterator over all data items that match the
                given constraint.
        """
        if isinstance(constraint, Mapping):
            id_ = constraint.get('id_', None)
            if id_ is not None and id_ not in data_items:
                return iter(tuple())
            return filter(
                lambda data_item: all(
                    getattr(data_item, attr, None) == value
                    for attr, value in constraint.items()
                ),
                data_items.values(),
            )
        return filter(constraint, data_items.values())

    @staticmethod
    def _find_first_with_constraint(
        constraint: Union[Mapping[str, Any], Callable[[T], bool]],
        data_items: Dict[int, T],
    ) -> Optional[T]:
        """Find the first value in a dictionary that matches a constraint.

        Args:
            constraint (Union[Mapping[str, Any], Callable[[T], bool]]): Either
                a function that receives a data item and returns True if the
                item meets the constraint, or a mapping where each key is
                an attribute (or property) name of the data item and its value
                is the expected value.
            data_items (Dict[int, T]): A dictionary of data items with unique
                integer IDs as keys and data item instances as values.

        Returns:
            Optional[T]: The first data item that matches the given constraint,
                or None if no such data item is found.
        """
        return next(
            BasePage._find_all_with_constraint(constraint, data_items), None
        )


class ProductPage(BasePage):
    """Data model of a FreshPoint product webpage.

    Args:
        html_hash_sha1 (str):
            Hexadecimal representation of the SHA-1 hash of the page HTML.
        location_id (int):
            Unique identifier of the product location (also known as the page
            ID or the device ID). Defaults to 0.
        location_name (str):
            Name of the product location.
        products (Dict[int, Product]):
            Dictionary of product IDs as keys and data models on the page
            as values.
    """

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

        Example:
        ```python
        # Category 'Dezerty' and available (with dictionary)
        products = page.find_products({
            'category': 'Dezerty',
            'is_available': True,
        })

        # Category 'Dezerty' and available (with lambda)
        products = page.find_products(
            lambda p: p.category == 'Dezerty' and p.is_available
        )

        # 'sendvic' in the name and price less than 100 CZK
        products = page.find_products(
            lambda p: 'sendvic' in p.name_lowercase_ascii and p.price_curr < 100
        )
        ```

        Tip: To convert the result to a list, use
        `list(page.find_products(...))`.

        Args:
            constraint (Union[ProductAttrs, Mapping[str, Any], Callable[[Product], bool]]):
                Either a callable that receives a `Product` instance and returns
                True if the product meets the constraint, or a mapping where
                each key is an attribute (or property) name of the `Product`
                model and its value is the expected value.

        Returns:
            Iterator[Product]: A lazy iterator over all products that match
                the given constraint.
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

        Example:
        ```python
        # Category 'Dezerty' and available (with dictionary)
        product = page.find_product({
            'category': 'Dezerty',
            'is_available': True,
        })

        # Category 'Dezerty' and available (with lambda)
        product = page.find_product(
            lambda p: p.category == 'Dezerty' and p.is_available
        )

        # 'sendvic' in the name and price less than 100 CZK
        product = page.find_product(
            lambda p: 'sendvic' in p.name_lowercase_ascii and p.price_curr < 100
        )
        ```

        Note:
        ```python
        product = find_product(...)
        ```
        is equivalent to
        ```python
        product = next(find_products(...), None)
        ```

        Args:
            constraint (Union[ProductAttrs, Mapping[str, Any], Callable[[Product], bool]]):
                Either a callable that receives a `Product` instance and returns
                True if the product meets the constraint, or a mapping where
                each key is an attribute (or property) name of the `Product`
                model and its value is the expected value.

        Returns:
            Optional[Product]: The first product that matches the given
                constraint, or None if no such product is found.
        """
        return self._find_first_with_constraint(constraint, self.products)


class LocationPage(BasePage):
    """Data model of a FreshPoint location webpage.

    Args:
        html_hash_sha1 (str):
            Hexadecimal representation of the SHA-1 hash of the page HTML.
        locations (Dict[int, Location]):
            Dictionary of location IDs as keys and data models on the page
            as values.
    """

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

        Example:
        ```python
        # location with ID 296 (with dictionary)
        locations = page.find_locations({'id_': 296})

        # location with ID 296 (with lambda)
        locations = page.find_locations(lambda loc: loc.id_ == 296)

        # location in Prague and active

        locations = page.find_locations(
            lambda loc: loc.is_active and 'praha' in loc.address_lowercase_ascii
        )
        ```

        Tip: To convert the result to a list, use
        `list(page.find_locations(...))`.

        Args:
            constraint (Union[LocationAttrs, Mapping[str, Any], Callable[[Location], bool]]):
                Either a callable that receives a `Location` instance and
                returns True if the location meets the constraint, or a mapping
                where each key is an attribute (or property) name of
                the `Location` model and its value is the expected value.

        Returns:
            Iterator[Location]: A lazy iterator over all locations that match
                the given constraint.
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

        Example:
        ```python
        # location with ID 296 (with dictionary)
        location = page.find_location({'id_': 296})

        # location with ID 296 (with lambda)
        location = page.find_location(lambda loc: loc.id_ == 296)

        # location in Prague and active
        location = page.find_location(
            lambda loc: loc.is_active and 'praha' in loc.address_lowercase_ascii
        )
        ```

        Args:
            constraint (Union[LocationAttrs, Mapping[str, Any], Callable[[Location], bool]]):
                Either a callable that receives a `Location` instance and
                returns True if the location meets the constraint, or a mapping
                where each key is an attribute (or property) name of
                the `Location` model and its value is the expected value.

        Returns:
            Optional[Location]: The first location that matches the given
                constraint, or None if no such location is found.
        """
        return self._find_first_with_constraint(constraint, self.locations)
