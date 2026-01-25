"""Custom exception types for the freshpointparser package."""


class FreshPointParserError(Exception):
    """Base class for all FreshPointParser exceptions."""


class ParseError(FreshPointParserError):
    """FreshPointParser error raised when a parsing operation fails."""


__all__ = [
    'FreshPointParserError',
    'ParseError',
]
