"""Custom exception types for the freshpointparser package."""


class FreshPointParserError(Exception):
    """Base exception for the ``freshpointparser`` library.

    All exceptions raised by this library are instances of this class or a
    subclass. Catch ``FreshPointParserError`` to handle any library failure
    regardless of its specific type.
    """


class ParseError(FreshPointParserError):
    """Raised when HTML extraction or structural parsing fails.

    Not subclassed — all extraction failures carry the same semantic weight
    from a caller's perspective. The error message describes the specific
    failure site and reason.
    """


__all__ = [
    'FreshPointParserError',
    'ParseError',
]
