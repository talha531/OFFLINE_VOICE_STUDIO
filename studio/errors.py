"""Exception types. Messages are written to be shown directly to the user."""

from __future__ import annotations


class StudioError(Exception):
    """Base class for expected, user-presentable errors."""


class EngineError(StudioError):
    """A speech engine failed while running."""


class EngineUnavailable(EngineError):
    """A speech engine (or its model files) is not installed or not ready."""


class ExtractionError(StudioError):
    """A document could not be read or contained no usable text."""


class AudioValidationError(StudioError):
    """An audio file could not be read or is unusable as a voice reference."""


class ExportError(StudioError):
    """Writing or encoding an audio file failed."""


class JobCancelled(StudioError):
    """Raised inside a running job when the user cancels it."""
