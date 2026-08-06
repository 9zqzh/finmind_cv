"""Public exception hierarchy for :mod:`gduf_web_api`."""


class GdufError(Exception):
    """Base class for all package-specific errors."""


class NetworkError(GdufError):
    """Raised when a source cannot be fetched successfully."""


class ParseError(GdufError):
    """Raised when a source page no longer matches a supported structure."""


class InvalidPageError(GdufError, ValueError):
    """Raised when a requested page number does not exist."""


class UnsupportedSourceError(GdufError, ValueError):
    """Raised when a requested college source is not registered."""

