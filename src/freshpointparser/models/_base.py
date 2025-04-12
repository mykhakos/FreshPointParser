from __future__ import annotations

import logging
import sys
from datetime import datetime
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Literal,
    Mapping,
    Optional,
    Protocol,
    TypeAlias,
    TypedDict,
    TypeVar,
    Union,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)
from pydantic.alias_generators import to_camel

if sys.version_info >= (3, 11):
    from typing import NamedTuple
else:
    from typing_extensions import NamedTuple

logger = logging.getLogger('freshpointparser.models')
"""Logger of the `freshpointparser.models` package."""


# default values for the type variables are only available in pydantic>=2.11,
# https://github.com/pydantic/pydantic/pull/10789


T = TypeVar('T')
"""Type variable to annotate generic types."""


TField = TypeVar(
    'TField',
    bound=str,
    # default=str,
)
"""Type variable to annotate attribute names (e.g., a Literal string)."""


TFieldMapping = TypeVar(
    'TFieldMapping',
    bound=Mapping[str, Any],
    # default=dict,
)
"""Type variable to annotate attribute mappings (e.g, a TypedDict)."""


# region BaseRecord


# str must be used here to allow using stings that are not specified as literals
BaseRecordField: TypeAlias = Union[str, Literal['recorded_at']]
"""Field names of the base record class."""


class HasRecordedAt(Protocol):
    """Protocol for classes that have a `recorded_at` datetime attribute."""

    recorded_at: datetime
    """Datetime when the data has been recorded."""


class BaseRecordFieldMapping(TypedDict, total=False):
    """Provides key names and types for the base record class attributes."""

    recorded_at: datetime
    """Datetime when the data has been recorded."""


class BaseRecord(BaseModel):
    """Base data model of a FreshPoint record."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    recorded_at: datetime = Field(
        default_factory=datetime.now,
        title='Recorded At',
        description='Datetime when the data has been recorded.',
    )
    """Datetime when the data has been recorded."""

    def is_newer_than(
        self,
        other: HasRecordedAt,
        precision: Optional[Literal['s', 'm', 'h', 'd']] = None,
    ) -> Optional[bool]:
        """Check if the record datetime of this instance is newer than another's.

        Compares the `recorded_at` datetime of this instance with another
        instance, considering the specified precision. Note that precision here
        means truncating the datetime to the desired level (e.g., cutting off
        seconds, minutes, etc.), not rounding it.

        Args:
            other (BaseRecord): The record to compare against. Must contain a
                `recorded_at` datetime attribute.
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
                - True if this model's record datetime is newer than the other's
                - False if this model's record datetime is older than the other's
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


# endregion BaseRecord

# region BaseItem\


BaseItemField: TypeAlias = Union[BaseRecordField, Literal['id_']]


class BaseItemFieldMapping(BaseRecordFieldMapping):
    """Provides key names and types for the base item class attributes."""

    id_: int
    """Unique numeric identifier."""


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


class BaseItem(BaseRecord, Generic[TField]):
    """Base data model of a FreshPoint item (listing)."""

    id_: int = Field(
        default=0,
        serialization_alias='id',
        validation_alias='id',
        title='ID',
        description='Unique numeric identifier.',
    )
    """Unique numeric identifier."""

    def diff(self, other: BaseItem, **kwargs: Any) -> Dict[TField, FieldDiff]:
        """Compare this model with the other one to identify differences.

        This method compares the fields of this model with the fields of
        another model instance to identify which fields have different
        values. If a field is not present in one of the models, it is considered
        to have a value of None in that model.

        By default, the `recorded_at` field is excluded from comparison. However,
        if any keyword arguments (`kwargs`) are provided, *no default exclusions
        are applied*, and the caller is responsible for specifying exclusions
        explicitly. If you provide additional keyword arguments and still want
        to exclude the `recorded_at` field, set `exclude={'recorded_at'}` or
        equivalent in `kwargs`.

        The data is serialized according to the models' configurations
        using the `model_dump` method.

        Args:
            other (model): The model to compare against.
            **kwargs: Additional keyword arguments to pass to the `model_dump`
                calls to control the serialization process, such as 'exclude',
                'include', 'by_alias', and others. If provided, the default
                exclusion of the `recorded_at` field is suppressed.

        Returns:
            Dict[TField, DiffPair]: A dictionary with string keys as field names and
                values as namedtuples containing pairs of the differing values
                between the two models. The first value is the one of this
                model and is accessible as `value_self`, and the second value
                is the one of the other model and is accessible as `value_other`.
                If a field is present in one model but not in the other,
                the corresponding value in the namedtuple is set to None.
        """
        # get self's and other's data, optionally remove the timestamps
        if not kwargs:
            kwargs['exclude'] = {'recorded_at'}
        self_asdict = self.model_dump(**kwargs)
        other_asdict = other.model_dump(**kwargs)
        # compare self to other
        diff = {}
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


TItem = TypeVar(
    'TItem',
    bound=BaseItem,
    # default=BaseItem,
)

# endregion BaseItem

# region BasePage


_NO_DEFAULT = object()
"""Sentinel value for the ``default`` argument in ``getattr()``."""


class BasePage(BaseRecord, Generic[TItem, TField, TFieldMapping]):
    """Base data model of a FreshPoint page."""

    items: Dict[int, TItem] = Field(
        default_factory=dict,
        repr=False,
        title='Items',
        description=(
            'Dictionary of item IDs as keys and data models on the page '
            'as values.'
        ),
    )
    """Dictionary of item IDs as keys and data models on the page as values."""

    @property
    def item_list(self) -> List[TItem]:
        """Items listed on the page."""
        return list(self.items.values())

    @property
    def item_ids(self) -> List[int]:
        """IDs of the items listed on the page."""
        return list(self.items.keys())

    @property
    def item_count(self) -> int:
        """Total number of items on the page."""
        return len(self.items)

    def iter_item_attr(
        self, attr: TField, default: T = _NO_DEFAULT, unique: bool = True
    ) -> Iterator[Union[Any, T]]:
        """Iterate over values of a specific attribute from the page's items,
        with optional default fallback and optional uniqueness filtering.

        Tip: To convert the result from an iterator to a list, use
        ``list(page.iter_item_attr(...))``.

        Args:
            attr (TField): String name of the attribute to retrieve from
                each item on the page.
            default (T, optional): Value to use if the attribute is missing.
                If not provided, missing attributes will raise AttributeError.
            unique (bool, optional): If True, only distinct values will be
                yielded. Defaults to True.

        Yields:
            Iterator[Union[Any, T]]: Attribute values collected from each item
            on the page.
        """
        items = self.items.values()
        if default is _NO_DEFAULT:
            values = (getattr(item, attr) for item in items)
        else:
            values = (getattr(item, attr, default) for item in items)

        if unique:
            seen = set()
            for value in values:
                if value not in seen:
                    seen.add(value)
                    yield value
        else:
            yield from values

    def find_item(
        self,
        constraint: Union[
            TFieldMapping, Mapping[str, Any], Callable[[TItem], bool]
        ],
    ) -> Optional[TItem]:
        """Find a single item on the page that matches a constraint. If more
        than one item matches the constraint, the first one found is returned.

        Note: ``page.find_item(...)`` is equivalent to
        ``next(page.find_items(...), None)``.

        Args:
            constraint (Union[TItemAttrs, Mapping[str, Any], Callable[[TBaseItem], bool]]):
                One of the following.

                - Mapping of string keys to arbitrary values.

                The mapping should be a dictionary-like object where each key is
                an attribute (or property) name of the item model and its value
                is the expected value. If a key is not present in the item, this
                item is skipped.

                Example: ``{'name': 'foo'}`` will match items where
                the `name` attribute of the item is equal to `'foo'`.

                - Callable that receives an item instance and returns a boolean.

                The callable, for example a function, should accept a single
                argument, which is an instance of the item model, and return
                a boolean value indicating whether the item meets the constraint.

                Example: ``lambda item: 'foo' in item.name`` will match items
                where the `name` attribute of the item contains the string
                `'foo'`.

        Raises:
            TypeError: If the constraint is invalid.

        Returns:
            Optional[TBaseItem]: The first item on the page that matches
            the given constraint, or None if no such item is found.
        """
        return next(self.find_items(constraint), None)

    def find_items(
        self,
        constraint: Union[
            TFieldMapping, Mapping[str, Any], Callable[[TItem], bool]
        ],
    ) -> Iterator[TItem]:
        """Find all items on the page that match a constraint.

        Tip: To convert the result from an iterator to a list, use
        ``list(page.find_items(...))``.

        Args:
            constraint (Union[TItemAttrs, Mapping[str, Any], Callable[[TBaseItem], bool]]):
                One of the following.

                - Mapping of string keys to arbitrary values.

                The mapping should be a dictionary-like object where each key is
                an attribute (or property) name of the item model and its value
                is the expected value. If a key is not present in the item, this
                item is skipped.

                Example: ``{'name': 'foo'}`` will match items where
                the `name` attribute of the item is equal to `'foo'`.

                - Callable that receives an item instance and returns a boolean.

                The callable, for example a function, should accept a single
                argument, which is an instance of the item model, and return
                a boolean value indicating whether the item meets the constraint.

                Example: ``lambda item: 'foo' in item.name`` will match items
                where the `name` attribute of the item contains the string
                `'foo'`.

        Raises:
            TypeError: If the constraint is invalid.

        Returns:
            Iterator[TBaseItem]: A lazy iterator over all items on the page that
            match the given constraint.
        """
        if callable(constraint):
            return filter(constraint, self.items.values())

        if isinstance(constraint, Mapping):
            return filter(
                lambda item: all(
                    getattr(item, attr, _NO_DEFAULT) == value
                    for attr, value in constraint.items()
                ),
                self.items.values(),
            )

        raise TypeError(
            f'Constraint must be either a dictionary or a callable function. '
            f"Got type '{type(constraint)}' instead."
        )


# endregion BasePage
