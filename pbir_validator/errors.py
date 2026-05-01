"""Custom exceptions raised by pbir_validator."""

from __future__ import annotations


class NotAPbirError(Exception):
    """Raised when the supplied path does not point at a PBIR report folder."""


class ConfParseError(Exception):
    """Raised when ``conf.md`` cannot be parsed.

    Carries an optional 1-based ``line_number`` for actionable error messages.
    """

    def __init__(self, message: str, *, line_number: int | None = None) -> None:
        super().__init__(message)
        self.line_number = line_number


class WriteError(Exception):
    """Raised when an atomic write of a ``visual.json`` fails.

    Carries the offending file path on the ``path`` attribute.
    """

    def __init__(self, message: str, *, path: object | None = None) -> None:
        super().__init__(message)
        self.path = path
