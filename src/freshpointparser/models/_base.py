from __future__ import annotations

import logging
import sys
from collections.abc import Mapping
from datetime import date, datetime
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
    Set,
    TypedDict,
    TypeVar,
    Union,
    overload,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializationInfo,
    field_serializer,
    model_validator,
)
from pydantic.alias_generators import to_camel

from ..exceptions import FreshPointParserTypeError, FreshPointParserValueError

if sys.version_info >= (3, 11):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias

logger = logging.getLogger('freshpointparser.models')
"""Logger of the ``freshpointparser.models`` package."""

_NoDefaultType = Enum('_NoDefaultType', 'NO_DEFAULT')
_NO_DEFAULT = _NoDefaultType.NO_DEFAULT
"""Sentinel value for the ``default`` argument of ``getattr()``."""


T = TypeVar('T')
"""Type variable to annotate arbitrary generic types."""


class ToCamel:
    """Alias for the ``to_camel`` function from ``pydantic.alias_generators``."""

    def __repr__(self) -> str:  # nicer formatting for Sphinx docs
        return 'to_camel'

    def __call__(self, string: str) -> str:
        return to_camel(string)


class DynamicFieldsModel(BaseModel):
    """Wraps arbitrary fields in a model to capture unknown or unstructured data."""

    model_config = ConfigDict(
        alias_generator=ToCamel(),
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
    """The right item is different from the left item."""

    DELETED = 'Deleted'
    """The right item is missing."""


class DiffValues(TypedDict):
    """Typed dictionary to represent the left and the right value in
    a difference comparison.
    """

    left: Any
    """The left value in the pair."""
    right: Any
    """The right value in the pair."""


class FieldDiff(TypedDict):
    """Typed dictionary to represent the difference between two fields
    in a model comparison.
    """

    type: DiffType
    """The type of the difference."""
    values: DiffValues
    """The left and the right values in the difference comparison."""


FieldDiffMapping: TypeAlias = Dict[str, FieldDiff]
"""Mapping of field names to their differences."""


class ModelDiff(TypedDict):
    """Typed dictionary to represent the difference between two models
    in a model comparison.
    """

    type: DiffType
    """The type of the difference."""
    diff: FieldDiffMapping
    """Mapping of field names to their differences."""


ModelDiffMapping: TypeAlias = Dict[int, ModelDiff]
"""Mapping of item IDs to their differences."""


def model_diff(left: BaseModel, right: BaseModel, **kwargs: Any) -> FieldDiffMapping:
    """Compare the left model with the right model to identify which model
    fields have different values.

    If a field exists in both items but its values differ, it is
    marked as *Updated*. If the field is missing in this item, it is
    considered to be *Created*, and if it is missing in the other item, it
    is considered to be *Deleted*. If the field is not present in any of
    the items, its value is considered to be ``None``.

    The data is serialized according to the item models' configurations
    using ``model_dump``.

    Args:
        left (model): The model to compare.
        right (model): The model to compare with.
        **kwargs: Additional keyword arguments to pass to the ``model_dump``
            calls to control the serialization process, such as ``exclude``,
            ``include``, ``by_alias``, and others.

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
    """Protocol for classes that have the ``recorded_at`` datetime attribute."""

    recorded_at: datetime
    """Datetime when the data has been recorded."""


class BaseRecord(BaseModel):
    """Base model of a FreshPoint record."""

    model_config = ConfigDict(alias_generator=ToCamel(), populate_by_name=True)

    recorded_at: datetime = Field(
        default_factory=datetime.now,
        title='Recorded At',
        description='Datetime when the data has been recorded.',
    )
    """Datetime when the data has been recorded."""

    parsing_errors: Dict[str, str] = Field(
        default_factory=dict,
        title='Parse Errors',
        description='Mapping of field names to error messages encountered during parsing.',
        frozen=True,
    )
    """Mapping of field names to error messages encountered during parsing."""

    @model_validator(mode='before')
    @classmethod
    def _filter_parsing_errors(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return data

        parsing_errors = data.setdefault('parsing_errors', {})
        for key, value in data.items():
            if isinstance(value, Exception):
                parsing_errors[key] = f'{type(value).__name__}: {value!s}'
        for key in parsing_errors:
            del data[key]

        return data

    def is_newer_than(
        self,
        other: HasRecordedAt,
        precision: Optional[Literal['s', 'm', 'h', 'd']] = None,
    ) -> Optional[bool]:
        """Check if this record is newer than another one by comparing
        their ``recorded_at`` fields at the specified precision.

        Note that precision here means truncating the datetime to the desired
        level (e.g., cutting off seconds, minutes, etc.), not rounding it.

        Args:
            other (HasRecordedAt): The record to compare against. Must contain
                the ``recorded_at`` datetime attribute.
            precision (Optional[Literal['s', 'm', 'h', 'd']]): The level of
                precision for the comparison. Supported values:

                - ``None``: full precision (microsecond) (default)
                - ``s``: second precision
                - ``m``: minute precision
                - ``h``: hour precision
                - ``d``: date precision

        Raises:
            FreshPointParserValueError: If the precision is not one of the supported values.

        Returns:
            Optional[bool]: With the specified precision taken into account,
                - True if this model's record datetime is newer than the other's
                - False if this model's record datetime is older than the other's
                - None if the record datetimes are the same
        """
        recorded_at_self: Union[datetime, date]
        recorded_at_other: Union[datetime, date]
        if precision is None:
            recorded_at_self = self.recorded_at
            recorded_at_other = other.recorded_at
        elif precision == 's':
            recorded_at_self = self.recorded_at.replace(microsecond=0)
            recorded_at_other = other.recorded_at.replace(microsecond=0)
        elif precision == 'm':
            recorded_at_self = self.recorded_at.replace(second=0, microsecond=0)
            recorded_at_other = other.recorded_at.replace(second=0, microsecond=0)
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
            raise FreshPointParserValueError(
                f"Invalid precision '{precision}'. Expected one of: 's', 'm', 'h', 'd'."
            )
        if recorded_at_self == recorded_at_other:
            return None
        return recorded_at_self > recorded_at_other


# endregion BaseRecord

# region BaseItem


class BaseItem(BaseRecord):
    """Base model of a FreshPoint item."""

    id_: int = Field(
        default=0,
        serialization_alias='id',  # not using 'alias' to bypass
        validation_alias='id',  # Pyright / Pylance limitations
        title='ID',
        description='Unique numeric identifier.',
    )
    """Unique numeric identifier."""

    @field_serializer('recorded_at')
    def _serialize_recorded_at(  # noqa: PLR6301
        self, value: datetime, info: SerializationInfo
    ) -> Optional[datetime]:
        """Exclude the ``recorded_at`` field from serialization if the context indicates
        that it should not be recorded.
        """
        # This method could be a part of the BaseRecord class, but at the moment
        # there are no use cases to exclude the ``recorded_at`` field there.
        if not info.context:
            return value
        try:
            if info.context.get('__exclude_recorded_at__'):
                return None
        except AttributeError:
            logger.debug(
                "Could not determine if 'recorded_at' should be excluded "
                'from serialization. Returning the value as is.'
            )
            return value
        return value

    def diff(
        self,
        other: BaseItem,
        *,
        exclude_recorded_at: bool = True,
        **kwargs: Any,
    ) -> FieldDiffMapping:
        """Compare this item with another one to identify which item fields
        have different values.

        If a field exists in both items but its values differ, it is
        marked as *Updated*. If the field is missing in this item, it is
        considered to be *Created*, and if it is missing in the other item, it
        is considered to be *Deleted*. If the field is not present in any of
        the items, its value is considered to be ``None``.

        By default, the ``recorded_at`` field is excluded from comparison with
        the ``exclude_recorded_at`` argument set to ``True``. This argument acts
        similar to the standard ``exclude_xx`` Pydantic serialization flags.

        The data is serialized according to the item models' configurations
        using ``model_dump``.

        Args:
            other (BaseItem): The item to compare against.
            exclude_recorded_at (bool): If True, the ``recorded_at`` field is
                excluded from the comparison. Defaults to True.
            **kwargs: Additional keyword arguments passed to each item model's
                ``model_dump`` call, such as ``exclude``, ``include``,
                ``by_alias``, and others.

        Returns:
            FieldDiffMapping: A dictionary mapping field names to their
            corresponding differences.

            Each field difference is a dictionary
            (:class:`~freshpointparser.models.annotations.FieldDiff`) containing
            the ``type`` and ``values`` keys.

            - ``type`` (:class:`~freshpointparser.models.annotations.DiffType`): \
            An enumeration value indicating the type of the difference.

            - ``values`` (:class:`~freshpointparser.models.annotations.DiffValues`): \
            A pair of values - `left` from this model and `right` from the other \
            model. If a field is missing in one model, its value will be ``None``.

            FieldDiffMapping structure example:

            >>> from freshpointparser.models.annotations import DiffType
            >>> {
            ...     'field_common': {
            ...         'type': DiffType.UPDATED,
            ...         'values': {'left': 12.5, 'right': 15.0},
            ...     },
            ...     'field_only_in_this': {
            ...         'type': DiffType.CREATED,
            ...         'values': {'left': ``'foo'``, 'right': None},
            ...     },
            ...     'field_only_in_other': {
            ...         'type': DiffType.DELETED,
            ...         'values': {'left': None, 'right': ``'bar'``},
            ...     },
            ... }

        """
        if exclude_recorded_at:
            context = dict(kwargs.get('context', {}))
            context['__exclude_recorded_at__'] = True
            kwargs['context'] = context
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
            'Dictionary of item IDs as keys and data models on the page as values.'
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

    def item_diff(
        self,
        other: BasePage,
        *,
        exclude_recorded_at: bool = True,
        **kwargs: Any,
    ) -> ModelDiffMapping:
        """Compare items between this page and another one to identify which
        items differ. Items are matched by their ID.

        If an item exists in both pages but its field values differ, it is
        marked as *Updated*. If the item is missing in this page, it is
        considered to be *Created*, and if it is missing in the other page, it
        is considered to be *Deleted*. If the item is not present in any of
        the pages, its fields are considered to be ``None``.

        By default, the ``recorded_at`` field is excluded from comparison with
        the ``exclude_recorded_at`` argument set to ``True``. This argument acts
        similar to the standard ``exclude_xx`` Pydantic serialization flags.

        The data is serialized according to the item models' configurations
        using ``model_dump``.

        Args:
            other (BasePage): The page to compare against.
            exclude_recorded_at (bool): If True, the ``recorded_at`` field is
                excluded from the comparison. Defaults to True.
            **kwargs: Additional keyword arguments passed to each item model's
                ``model_dump`` call, such as ``exclude``, ``include``,
                ``by_alias``, and others.

        Returns:
            ModelDiffMapping: A dictionary mapping numeric item IDs to their
            corresponding differences.

            Each dictionary value is a dictionary (ModelDiff) containing
            the ``type`` and `diff` keys.

            - ``type`` (DiffType): An enumeration value indicating the type of \
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
            ...                 'values': {'left': ``'foo'``, 'right': None},
            ...             },
            ...         },
            ...     },
            ...     1003: {
            ...         'type': DiffType.CREATED,
            ...         'diff': {
            ...             'field_only_in_other': {
            ...                 'type': DiffType.CREATED,
            ...                 'values': {'left': None, 'right': ``'bar'``},
            ...             },
            ...         },
            ...     },
            ... }
        """
        if exclude_recorded_at:
            context = dict(kwargs.get('context', {}))
            context['__exclude_recorded_at__'] = True
            kwargs['context'] = context
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

    @overload
    def iter_item_attr(
        self,
        attr: str,
        *,
        unique: bool = ...,
        unhashable: bool = ...,
    ) -> Iterator[Any]: ...

    @overload
    def iter_item_attr(
        self,
        attr: str,
        default: T,
        *,
        unique: bool = ...,
        unhashable: bool = ...,
    ) -> Iterator[Union[Any, T]]: ...

    def iter_item_attr(
        self,
        attr: str,
        default: Union[T, _NoDefaultType] = _NO_DEFAULT,
        *,
        unique: bool = False,
        unhashable: bool = False,
    ) -> Iterator[Union[Any, T]]:
        """Iterate over values of a specific attribute of the page's items,
        with optional default fallback and optional uniqueness filtering.

        Tip: To convert the result from an iterator to a list, use
        ``list(page.iter_item_attr(...))``.

        Args:
            attr (str): String name of the attribute to retrieve from
                each item on the page.
            default (T, optional): Value to use if the attribute is missing.
                If not provided, missing attributes will raise AttributeError.
            unique (bool, optional): If True, only distinct values will be
                yielded. Defaults to False.
            unhashable (bool, optional): If True, uniqueness is checked
                by comparing values directly, which is useful for unhashable
                types like lists or dictionaries, but is slower. Defaults to False.

        Raises:
            AttributeError: If the attribute is not present in an item
                and `default` is not provided.
            FreshPointParserTypeError: If the attribute values are not hashable and
                `unhashable` is set to False.

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
            if unhashable:
                seen_unhashable: List[Any] = []
                for value in values:
                    if any(value == seen_value for seen_value in seen_unhashable):
                        continue
                    seen_unhashable.append(value)
                    yield value
            else:
                try:
                    seen_hashable: Set[Any] = set()
                    for value in values:
                        if value not in seen_hashable:
                            seen_hashable.add(value)
                            yield value
                except TypeError as e:
                    raise FreshPointParserTypeError(
                        f"Cannot yield unique values for attribute '{attr}': "
                        f'the values are not hashable. '
                        f"Set 'unhashable=True' to compare the values directly."
                    ) from e
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
            constraint (Union[Mapping[str, Any], Callable[[TBaseItem], bool]]):
                One of the following.

                - Mapping of string keys to arbitrary values.

                The mapping should be a dictionary-like object where each key is
                an attribute (or property) name of the item model and its value
                is the expected value. If a key is not present in the item, this
                item is skipped.

                Example: ``{'name': ``'foo'``}`` will match items where
                the ``name`` attribute of the item is equal to ``'foo'``.

                - Callable that receives an item instance and returns a boolean.

                The callable, for example a function, should accept a single
                argument, which is an instance of the item model, and return
                a boolean value indicating whether the item meets the constraint.

                Example: ``lambda item: ``'foo'`` in item.name`` will match items
                where the ``name`` attribute of the item contains the string
                ``'foo'``.

        Raises:
            FreshPointParserTypeError: If the constraint is invalid, i.e., not a
                Mapping or a Callable.

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
            constraint (Union[Mapping[str, Any], Callable[[TBaseItem], bool]]):
                One of the following.

                - Mapping of string keys to arbitrary values.

                The mapping should be a dictionary-like object where each key is
                an attribute (or property) name of the item model and its value
                is the expected value. If a key is not present in the item, this
                item is skipped.

                Example: ``{'name': ``'foo'``}`` will match items where
                the ``name`` attribute of the item is equal to ``'foo'``.

                - Callable that receives an item instance and returns a boolean.

                The callable, for example a function, should accept a single
                argument, which is an instance of the item model, and return
                a boolean value indicating whether the item meets the constraint.

                Example: ``lambda item: ``'foo'`` in item.name`` will match items
                where the ``name`` attribute of the item contains the string
                ``'foo'``.

        Raises:
            FreshPointParserTypeError: If the constraint is invalid, i.e., not a
                Mapping or a Callable.

        Returns:
            Iterator[TBaseItem]: A lazy iterator over all items on the page that
            match the given constraint.
        """
        if callable(constraint):

            def _filter_callable() -> Iterator[TItem]:
                for item in self.items.values():
                    try:
                        if constraint(item):
                            yield item
                    except TypeError as exc:  # invalid callable signature
                        if type(exc) is TypeError:
                            raise FreshPointParserTypeError(str(exc)) from exc
                        raise

            return _filter_callable()

        if isinstance(constraint, Mapping):

            def _filter_mapping() -> Iterator[TItem]:
                for item in self.items.values():
                    try:
                        if all(
                            getattr(item, attr, _NO_DEFAULT) == value
                            for attr, value in constraint.items()
                        ):
                            yield item
                    except TypeError as exc:  # invalid attribute type
                        if type(exc) is TypeError:
                            raise FreshPointParserTypeError(str(exc)) from exc
                        raise

            return _filter_mapping()

        raise FreshPointParserTypeError(
            f'Constraint must be either a Mapping or a Callable. '
            f"Got type '{type(constraint)}' instead."
        )


# endregion BasePage
