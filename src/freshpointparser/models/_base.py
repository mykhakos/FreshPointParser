from __future__ import annotations

import logging
import sys
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
    Mapping,
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
    ModelWrapValidatorHandler,
    ValidationError,
    ValidationInfo,
    model_validator,
)
from pydantic.alias_generators import to_camel

if sys.version_info >= (3, 11):
    from typing import Self, TypeAlias
else:
    from typing_extensions import Self, TypeAlias


logger = logging.getLogger('freshpointparser.models')
"""Logger for the ``freshpointparser.models`` package."""


_NoDefaultType = Enum('_NoDefaultType', 'NO_DEFAULT')
_NO_DEFAULT = _NoDefaultType.NO_DEFAULT
"""Placeholder for a default parameter value."""

T = TypeVar('T')


class ToCamel:
    """Alias for the ``to_camel`` function from ``pydantic.alias_generators``."""

    def __repr__(self) -> str:  # nicer formatting for Sphinx docs
        return 'to_camel'

    def __call__(self, string: str) -> str:
        return to_camel(string)


# region BestEffortModel


class ValidationContext(Protocol):
    """Protocol for the validation context expected by ``BestEffortModel``
    and its subclasses.
    """

    def register_error(self, error: Exception) -> None:
        """Register a validation error in the context.

        Args:
            error (Exception): The validation error to register.
        """
        pass


class BestEffortModel(BaseModel):
    """Model that attempts to validate input data, and on validation errors,
    falls back to using default values for the fields that failed validation.
    """

    @model_validator(mode='wrap')
    @classmethod
    def _safe_validate(
        cls, data: Any, handler: ModelWrapValidatorHandler[Self], info: ValidationInfo
    ) -> Self:
        """A wrapper around the standard model validation process that catches
        validation errors and falls back to using default values for the fields
        that failed validation.

        NOTE: A model-level 'wrap' validator in the parent class
        is expected to be called first for any subclasses.

        Args:
            data (Any): Input data to validate (injected by Pydantic).
            handler (ModelWrapValidatorHandler[Self]): The validation handler
                to process the data (injected by Pydantic).
            info (ValidationInfo): Additional validation information
                (injected by Pydantic).

        Returns:
            Self: The validated model instance.

        Raises:
            ValidationError: Raised when validation fails, and the fallback
                mechanism cannot be applied.
        """
        try:
            return handler(data)
        except ValidationError as validation_err:
            if not isinstance(data, Mapping):
                logger.warning(
                    "Cannot fall back in '%s': data is not a mapping (got '%s').",
                    cls.__name__,
                    type(data).__name__,
                )
                raise validation_err

            if info.config and info.config.get('strict'):
                logger.warning(
                    "Cannot fall back in '%s': strict mode is enabled.",
                    cls.__name__,
                )
                raise validation_err

            logger.info(
                "Validation error in model '%s':\n%s", cls.__name__, validation_err
            )
            try:
                context: Optional[ValidationContext] = info.context
                context.register_error(validation_err)  # type: ignore[union-attr]
            except Exception as ctx_err:
                logger.warning(
                    "Failed to record validation error to the context (%s).",
                    ctx_err,
                )

            failed_fields = set()
            for err in validation_err.errors():
                err_loc = err.get('loc')
                if not err_loc:  # usually means a model validator failed
                    logger.debug(
                        "Model-level validator failed in '%s', falling back to all-defaults.",
                        cls.__name__,
                    )
                    return handler({})
                failed_fields.add(err_loc[0])

            logger.debug(
                "Stripped failing fields %s from '%s', retrying with defaults.",
                sorted(str(f) for f in failed_fields),
                cls.__name__,
            )
            cleaned_data = {
                key: value for key, value in data.items() if key not in failed_fields
            }
            return handler(cleaned_data)


# endregion BestEffortModel

# region BaseItem


class FieldDiff(TypedDict):
    """Represents the difference for a single field between two models."""

    left: Any
    """The value from the left model."""
    right: Any
    """The value from the right model."""


FieldDiffMapping: TypeAlias = Dict[str, FieldDiff]
"""Mapping of field names to their difference pairs."""


class BaseItem(BestEffortModel):
    """Base model of a FreshPoint item."""

    model_config = ConfigDict(alias_generator=ToCamel(), populate_by_name=True)

    id_: Optional[str] = Field(
        default=None,
        serialization_alias='id',  # not using 'alias' to bypass
        validation_alias='id',  # Pyright / Pylance limitations
        coerce_numbers_to_str=True,
        title='ID',
        description='Unique item identifier (numeric unless undefined).',
    )
    """Unique item identifier (numeric unless undefined)."""

    def model_diff(self, other: BaseItem, **kwargs: Any) -> FieldDiffMapping:
        """Compare this item with another one to identify which item fields
        have different values.

        If a field is not present in any of the models, its value is considered
        to be ``None``.

        The data is serialized according to the item models' configurations
        using ``model_dump``.

        Args:
            other (BaseItem): The item to compare against.
            **kwargs: Additional keyword arguments passed to each item model's
                ``model_dump`` call, such as ``exclude``, ``include``,
                ``by_alias``, and others.

        Returns:
            FieldDiffMapping: A dictionary mapping field names to their
            corresponding difference pairs.

            Each field difference is a ``FieldDiff`` dictionary containing the
            ``left`` and ``right`` values from this model and the other model,
            respectively. If a field is missing in any of the models, its value
            is considered to be ``None`` in this model.

            FieldDiffMapping structure example:

            ```python
            {
                'field_common': {'left': 12.5, 'right': 15.0},
                'field_missing_in_other': {'left': 'foo', 'right': None},
                'field_missing_in_self': {'left': None, 'right': 'bar'},
            }
            ```
        """
        if self is other:
            return {}

        as_dict_self = self.model_dump(**kwargs)
        as_dict_other = other.model_dump(**kwargs)
        diff: FieldDiffMapping = {}

        # compare self to other
        for field, value_self in as_dict_self.items():
            value_other = as_dict_other.get(field, None)
            if value_self != value_other:
                diff[field] = FieldDiff(left=value_self, right=value_other)

        # compare other to self (only missing fields)
        fields_missing_in_self = as_dict_other.keys() - as_dict_self.keys()
        for field in fields_missing_in_self:
            value_other = as_dict_other[field]
            if value_other is not None:
                diff[field] = FieldDiff(left=None, right=value_other)

        return diff


# endregion BaseItem

# region BasePage


# default values for the type variables are only available in pydantic>=2.11,
# https://github.com/pydantic/pydantic/pull/10789
TItem = TypeVar(
    'TItem',
    bound=BaseItem,
    # default=BaseItem,
)
"""Type variable to annotate item models."""


ModelDiffMapping: TypeAlias = Dict[str, FieldDiffMapping]
"""Mapping of item IDs to their differences."""


class BasePage(BestEffortModel, Generic[TItem]):
    """Base data model of a FreshPoint page."""

    model_config = ConfigDict(alias_generator=ToCamel(), populate_by_name=True)

    recorded_at: datetime = Field(
        default_factory=datetime.now,
        title='Recorded At',
        description='Datetime when the data has been recorded.',
    )
    """Datetime when the data has been recorded."""

    items: List[TItem] = Field(
        default_factory=list,
        repr=False,
        title='Items',
        description='Data models on the page.',
    )
    """Data models on the page."""

    @property
    def item_count(self) -> int:
        """Total number of items on the page."""
        return len(self.items)

    def item_diff(
        self, other: BasePage[TItem], *, exclude_missing: bool = False, **kwargs: Any
    ) -> ModelDiffMapping:
        """Compare items between this page and another one to identify which
        items differ. Items are matched by their ID.

        If a field of any item is not present in any of the models, the value of
        that field is considered to be ``None``. If an item is missing in either
        page, all fields of that item are considered to be ``None``.

        The data is serialized according to the item models' configurations
        using ``model_dump``.

        Args:
            other (BasePage): The page to compare against.
            exclude_missing (bool): Whether to exclude items that are missing in
                either page from the result.
            **kwargs: Additional keyword arguments passed to each item model's
                ``model_dump`` call, such as ``exclude``, ``include``,
                ``by_alias``, and others.

        Returns:
            ModelDiffMapping: A dictionary mapping numeric item IDs to their
            corresponding differences.

            Each item difference is a ``FieldDiffMapping`` dictionary that maps
            fields to the corresponding field differences.

            Each field difference is a ``FieldDiff`` dictionary containing the
            ``left`` and ``right`` values from this model and the other model,
            respectively. If a field is missing in any of the models, its value
            is considered to be ``None`` in this model.

            ModelDiffMapping structure example:

            ```python
            {
                '1001': {
                    'field_common': {'left': 12.5, 'right': 15.0},
                    'field_missing_in_other': {'left': 'foo', 'right': None},
                },
                '1002': {
                    'field_common': {'left': 10.0, 'right': 12.0},
                    'field_missing_in_self': {'left': None, 'right': 'qux'},
                },
            }
            ```
        """
        if self is other:
            return {}

        items_as_dict_self = {
            item.id_: item for item in self.items if item.id_ is not None
        }
        items_as_dict_other = {
            item.id_: item for item in other.items if item.id_ is not None
        }
        item_missing = BaseItem()
        diff: ModelDiffMapping = {}

        # compare self to other
        for item_id, item_self in items_as_dict_self.items():
            item_other = items_as_dict_other.get(item_id, item_missing)
            if item_other is item_missing and exclude_missing:
                continue
            item_diff = item_self.model_diff(item_other, **kwargs)
            if item_diff:
                diff[item_id] = item_diff

        # compare other to self (only items that are missing in self)
        if not exclude_missing:
            item_ids_missing_in_self = (
                items_as_dict_other.keys() - items_as_dict_self.keys()
            )
            for item_id in item_ids_missing_in_self:
                item_other = items_as_dict_other[item_id]
                item_diff = item_missing.model_diff(item_other, **kwargs)
                if item_diff:
                    diff[item_id] = item_diff

        return diff

    @overload
    def iter_item_attr(
        self,
        attr: str,
        *,
        unique: bool = ...,
        hashable: bool = ...,
    ) -> Iterator[Any]: ...

    @overload
    def iter_item_attr(
        self,
        attr: str,
        default: T,
        *,
        unique: bool = ...,
        hashable: bool = ...,
    ) -> Iterator[Union[Any, T]]: ...

    def iter_item_attr(
        self,
        attr: str,
        default: Union[T, _NoDefaultType] = _NO_DEFAULT,
        *,
        unique: bool = False,
        hashable: bool = True,
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
            hashable (bool, optional): If False, uniqueness is checked
                by comparing values directly, which is useful for unhashable
                types like lists or dictionaries, but is slower. Defaults to True.

        Yields:
            Iterator[Union[Any, T]]: Attribute values collected from each item
            on the page.

        Raises:
            AttributeError: If the attribute is not present in an item and
                ``default`` is not provided.
            TypeError: If the attribute values are not hashable and
                ``hashable`` is set to True.
        """
        if default is _NO_DEFAULT:
            values = (getattr(item, attr) for item in self.items)
        else:
            values = (getattr(item, attr, default) for item in self.items)

        if unique:
            if hashable:
                seen_hashable: Set[Any] = set()
                for value in values:
                    if value not in seen_hashable:
                        seen_hashable.add(value)
                        yield value
            else:
                seen_unhashable: List[Any] = []
                for value in values:
                    if value not in seen_unhashable:
                        seen_unhashable.append(value)
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

        Returns:
            Optional[TBaseItem]: The first item on the page that matches
            the given constraint, or None if no such item is found.

        Raises:
            TypeError: If the constraint is not a Mapping or Callable.
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

                Example: ``{'name': 'foo'}`` will match items where
                the ``name`` attribute of the item is equal to ``'foo'``.

                - Callable that receives an item instance and returns a boolean.

                The callable, for example a function, should accept a single
                argument, which is an instance of the item model, and return
                a boolean value indicating whether the item meets the constraint.

                Example: ``lambda item: 'foo' in item.name`` will match items
                where the ``name`` attribute of the item contains ``'foo'``.

        Returns:
            Iterator[TBaseItem]: A lazy iterator over all items on the page that
            match the given constraint.

        Raises:
            TypeError: If the constraint is not a Mapping or Callable.
        """
        if callable(constraint):
            for item in self.items:
                if constraint(item):
                    yield item
        elif isinstance(constraint, Mapping):
            for item in self.items:
                if all(
                    getattr(item, attr, _NO_DEFAULT) == value
                    for attr, value in constraint.items()
                ):
                    yield item
        else:
            raise TypeError(
                f'Constraint must be either a Mapping or a Callable. '
                f"Got type '{type(constraint).__name__}' instead."
            )

    def is_newer_than(
        self,
        other: BasePage,
        precision: Optional[Literal['s', 'm', 'h', 'd']] = None,
    ) -> Optional[bool]:
        """Check if this page is newer than another one by comparing
        their ``recorded_at`` fields at the specified precision.

        Note that precision here means truncating the datetime to the desired
        level (e.g., cutting off seconds, minutes, etc.), not rounding it.

        Args:
            other (BasePage): The page to compare against.
            precision (Optional[Literal['s', 'm', 'h', 'd']]): The level of
                precision for the comparison (``None`` for full precision (default),
                's' for seconds, 'm' for minutes, 'h' for hours, and 'd' for days).

        Returns:
            Optional[bool]: With the specified precision taken into account,
                - True if this model's record datetime is newer than the other's
                - False if this model's record datetime is older than the other's
                - None if the record datetimes are the same

        Raises:
            ValueError: If the precision is not one of the supported values.
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
            raise ValueError(
                f"Invalid precision '{precision!r}'. "
                f"Expected one of: None, 's', 'm', 'h', 'd'."
            )
        if recorded_at_self == recorded_at_other:
            return None
        return recorded_at_self > recorded_at_other


# endregion BasePage
