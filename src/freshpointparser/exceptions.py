"""Custom exception types for the freshpointparser package."""


class FreshPointParserError(Exception):
    """Base class for all FreshPointParser exceptions."""


class FreshPointParserTypeError(FreshPointParserError, TypeError):
    """Type error raised in FreshPointParser."""


class FreshPointParserAttributeError(FreshPointParserError, AttributeError):
    """Attribute error raised in FreshPointParser."""


class FreshPointParserKeyError(FreshPointParserError, KeyError):
    """Key error raised in FreshPointParser."""


class FreshPointParserValueError(FreshPointParserError, ValueError):
    """Value error raised in FreshPointParser."""


__all__ = [
    'FreshPointParserAttributeError',
    'FreshPointParserError',
    'FreshPointParserKeyError',
    'FreshPointParserTypeError',
    'FreshPointParserValueError',
]
