"""Errors that are worth distinguishing at the CLI boundary."""

from __future__ import annotations


class BrownfieldError(Exception):
    """Base class. Caught in `cli` and printed without a traceback."""


class ScanError(BrownfieldError):
    """The directory handed to the scanner cannot be scanned."""


class RubricError(BrownfieldError):
    """The rubric file is missing, malformed, or internally inconsistent."""


class SupportTableError(BrownfieldError):
    """The runtime support table is missing, malformed, or lacks provenance."""
