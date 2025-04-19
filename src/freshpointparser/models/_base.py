from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Literal,
    Optional,
    Protocol,
    TypeAlias,
    TypedDict,
    TypeVar,
    Union,
)

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

logger = logging.getLogger('freshpointparser.models')
"""Logger of the `freshpointparser.models` package."""


_NO_DEFAULT = object()
"""Sentinel value for the ``default`` argument in ``getattr()``."""


T = TypeVar('T')
"""Type variable to annotate generic types."""


class DynamicFieldsModel(BaseModel):
    """Wraps arbitrary fields in a model to capture unknown or unstructured
    data.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra='allow',
        arbitrary_types_allowed=True,
    )


# region Diff


class DiffType(str, Enum):
    """String enumeration of the types of differences between two items."""

    CREATED = 'Created'
    """The left item is missing"""

    UPDATED = 'Updated'
    """The item has been updated."""

    DELETED = 'Deleted'
    """The right item is missing."""


TLeft = TypeVar('TLeft')
"""Type variable to annotate the left value in a difference."""
TRight = TypeVar('TRight')
"""Type variable to annotate the right value in a difference."""


class DiffValues(TypedDict, Generic[TLeft, TRight]):
    """Typed dictionary to represent the left and the right value in
    a difference comparison.
    """

    left: TLeft
    right: TRight


class FieldDiff(TypedDict, Generic[TLeft, TRight]):
    """Typed dictionary to represent the difference between two fields
    in a model comparison.
    """

    type: DiffType
    values: DiffValues[TLeft, TRight]


FieldDiffMapping: TypeAlias = Dict[str, FieldDiff[Any, Any]]
"""Mapping of field names to their differences."""


class ModelDiff(TypedDict):
    """Typed dictionary to represent the difference between two models
    in a model comparison.
    """

    type: DiffType
    diff: FieldDiffMapping


ModelDiffMapping: TypeAlias = Dict[int, ModelDiff]
"""Mapping of item IDs to their differences."""


def model_diff(
    left: BaseModel, right: BaseModel, **kwargs: Any
) -> FieldDiffMapping:
    """Compare left model with the right model to identify which model fields
    have different values. If a field is not present in one of the models,
    its value is considered to be None in that model.

    The data is serialized according to the models' configurations by calling
    the `model_dump` method on both models.

    Args:
        left (model): The model to compare from.
        right (model): The model to compare to.
        **kwargs: Additional keyword arguments to pass to the `model_dump`
            calls to control the serialization process, such as 'exclude',
            'include', 'by_alias', and others.

    Returns:
        FieldDiffMapping: A dictionary mapping field names to their differences,
        each containing the diff type and a pair of left/right values.
    """
    left_asdict = left.model_dump(**kwargs)
    right_asdict = right.model_dump(**kwargs)
    diff = {}
    # compare left to right
    for field, value_left in left_asdict.items():
        if field in right_asdict:
            diff_type = DiffType.UPDATED
            value_right = right_asdict[field]
        else:
            diff_type = DiffType.DELETED
            value_right = None
        if value_left != value_right:
            diff[field] = FieldDiff(
                type=diff_type,
                values=DiffValues(left=value_left, right=value_right),
            )
    # compare right to left
    if right_asdict.keys() != left_asdict.keys():
        for field, value_right in right_asdict.items():
            if field not in left_asdict:
                diff_type = DiffType.CREATED
                value_left = None
                diff[field] = FieldDiff(
                    type=diff_type,
                    values=DiffValues(left=value_left, right=value_right),
                )
    return diff


# endregion Diff


# region BaseRecord


class HasRecordedAt(Protocol):
    """Protocol for classes that have a `recorded_at` datetime attribute."""

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

# region BaseItem


class BaseItem(BaseRecord):
    """Base data model of a FreshPoint item (listing)."""

    id_: int = Field(
        default=0,
        serialization_alias='id',
        validation_alias='id',
        title='ID',
        description='Unique numeric identifier.',
    )
    """Unique numeric identifier."""

    def diff(self, other: BaseItem, **kwargs: Any) -> FieldDiffMapping:
        """Compare this item with another one to identify which item fields
        have different values.

        If a field exists in both items but its values differ, it is
        marked as *Updated*. If the field is missing in this item, it is
        considered to be *Created*, and if it is missing in the other item, it
        is considered to be *Deleted*. If the field is not present in any of
        the items, its value is considered to be ``None``.

        By default, the `recorded_at` field is excluded from comparison.
        However, **if any keyword arguments are provided, no default exclusions
        are applied**, and the caller is responsible for specifying exclusions
        explicitly. If you provide additional keyword arguments and still want
        to exclude the `recorded_at` field, set ``exclude={'recorded_at'}`` or
        equivalent in ``kwargs``.

        The data is serialized according to the item models' configurations
        using ``model_dump``.

        Args:
            other (BaseItem): The item to compare against.
            **kwargs: Additional keyword arguments passed to each item model's
                ``model_dump`` call, such as `exclude`, `include`,
                `by_alias`, and others. If provided, the default
                exclusion of the `recorded_at` field is suppressed!

        Returns:
            FieldDiffMapping[str]: A dictionary mapping field names to their
            corresponding differences.

            Each dictionary value is a dictionary (FieldDiff) containing
            the `type` and `values` keys.

            - `type` (DiffType): An enumeration value indicating the type of \
            the difference (`Created`, `Updated`, or `Deleted`).

            - `values` (DiffValues): A pair of values - `left` from this model \
            and `right` from the other model. If a field is missing in one model, \
            its value will be ``None``.

            FieldDiffMapping structure example:

            >>> from freshpointparser.models.annotations import DiffType
            >>> {
            ...     'field_common': {
            ...         'type': DiffType.UPDATED,
            ...         'values': {'left': 12.5, 'right': 15.0},
            ...     },
            ...     'field_only_in_this': {
            ...         'type': DiffType.CREATED,
            ...         'values': {'left': 'foo', 'right': None},
            ...     },
            ...     'field_only_in_other': {
            ...         'type': DiffType.DELETED,
            ...         'values': {'left': None, 'right': 'bar'},
            ...     },
            ... }

        """
        if not kwargs:
            kwargs['exclude'] = ('recorded_at',)
        return model_diff(self, other, **kwargs)


# default values for the type variables are only available in pydantic>=2.11,
# https://github.com/pydantic/pydantic/pull/10789
TItem = TypeVar(
    'TItem',
    bound=BaseItem,
    # default=BaseItem,
)
"""Type variable to annotate item models."""

# endregion BaseItem

# region BasePage


class BasePage(BaseRecord, Generic[TItem]):
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

    def item_diff(self, other: BasePage, **kwargs: Any) -> ModelDiffMapping:
        """Compare items between this page and another one to identify which
        items differ. Items are matched by their ID.

        If an item exists in both pages but its field values differ, it is
        marked as *Updated*. If the item is missing in this page, it is
        considered to be *Created*, and if it is missing in the other page, it
        is considered to be *Deleted*. If the item is not present in any of
        the pages, its fields are considered to be ``None``.

        By default, the `recorded_at` field is excluded from comparison.
        However, **if any keyword arguments are provided, no default exclusions
        are applied**, and the caller is responsible for specifying exclusions
        explicitly. If you provide additional keyword arguments and still want
        to exclude the `recorded_at` field, set ``exclude={'recorded_at'}`` or
        equivalent in ``kwargs``.

        The data is serialized according to the item models' configurations
        using ``model_dump``.

        Args:
            other (BasePage): The page to compare against.
            **kwargs: Additional keyword arguments passed to each item model's
                ``model_dump`` call, such as `exclude`, `include`,
                `by_alias`, and others. If provided, the default
                exclusion of the `recorded_at` field is suppressed!

        Returns:
            ModelDiffMapping: A dictionary mapping numeric item IDs to their
            corresponding differences.

            Each dictionary value is a dictionary (ModelDiff) containing
            the `type` and `diff` keys.

            - `type` (DiffType): An enumeration value indicating the type of \
            the difference (`Created`, `Updated`, or `Deleted`).

            - `diff` (FieldDiffMapping): A dictionary mapping field names to \
            `FieldDiff` entries, as described in `BaseItem.diff()`.

            ModelDiff structure example:

            >>> from freshpointparser.models.annotations import DiffType
            >>> {
            ...     1001: {
            ...         'type': DiffType.UPDATED,
            ...         'diff': {
            ...             'field_common': {
            ...                 'type': DiffType.UPDATED,
            ...                 'values': {'left': 12.5, 'right': 15.0},
            ...             },
            ...         },
            ...     },
            ...     1002: {
            ...         'type': DiffType.DELETED,
            ...         'diff': {
            ...             'field_only_in_this': {
            ...                 'type': DiffType.DELETED,
            ...                 'values': {'left': 'foo', 'right': None},
            ...             },
            ...         },
            ...     },
            ...     1003: {
            ...         'type': DiffType.CREATED,
            ...         'diff': {
            ...             'field_only_in_other': {
            ...                 'type': DiffType.CREATED,
            ...                 'values': {'left': None, 'right': 'bar'},
            ...             },
            ...         },
            ...     },
            ... }
        """
        item_missing = DynamicFieldsModel()
        diff = {}
        # compare self to other
        for item_id, item_self in self.items.items():
            item_other = other.items.get(item_id, None)
            if item_other is None:
                diff[item_id] = ModelDiff(
                    type=DiffType.DELETED,
                    diff=model_diff(item_self, item_missing, **kwargs),
                )
            else:
                item_diff = model_diff(item_self, item_other, **kwargs)
                if item_diff:
                    diff[item_id] = ModelDiff(
                        type=DiffType.UPDATED,
                        diff=item_diff,
                    )
        # compare other to self
        if other.items.keys() != self.items.keys():
            for item_id, item_other in other.items.items():
                if item_id not in self.items:
                    diff[item_id] = ModelDiff(
                        type=DiffType.CREATED,
                        diff=model_diff(item_missing, item_other, **kwargs),
                    )
        return diff

    def iter_item_attr(
        self, attr: str, default: T = _NO_DEFAULT, unique: bool = True
    ) -> Iterator[Union[Any, T]]:
        """Iterate over values of a specific attribute from the page's items,
        with optional default fallback and optional uniqueness filtering.

        Tip: To convert the result from an iterator to a list, use
        ``list(page.iter_item_attr(...))``.

        Args:
            attr (str): String name of the attribute to retrieve from
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
        self, constraint: Union[Mapping[str, Any], Callable[[TItem], bool]]
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
        self, constraint: Union[Mapping[str, Any], Callable[[TItem], bool]]
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
