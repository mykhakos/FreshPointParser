"""Custom exception types for the freshpointparser package."""


class FreshPointParserError(Exception):
    """Base class for all FreshPointParser exceptions."""


class ParserError(FreshPointParserError):
    """Base class for parser related errors."""


class ParserAttributeError(ParserError, AttributeError):
    """Attribute error raised during parsing."""


class ParserKeyError(ParserError, KeyError):
    """Key error raised during parsing."""


class ParserTypeError(ParserError, TypeError):
    """Type error raised during parsing."""


class ParserValueError(ParserError, ValueError):
    """Value error raised during parsing."""


class ModelError(FreshPointParserError):
    """Base class for model related errors."""


class ModelAttributeError(ModelError, AttributeError):
    """Attribute error raised in models."""


class ModelKeyError(ModelError, KeyError):
    """Key error raised in models."""


class ModelTypeError(ModelError, TypeError):
    """Type error raised in models."""


class ModelValueError(ModelError, ValueError):
    """Value error raised in models."""


__all__ = [
    'FreshPointParserError',
    'ModelAttributeError',
    'ModelError',
    'ModelKeyError',
    'ModelTypeError',
    'ModelValueError',
    'ParserAttributeError',
    'ParserError',
    'ParserKeyError',
    'ParserTypeError',
    'ParserValueError',
]
