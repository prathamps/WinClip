"""Domain-level errors."""


class WinClipError(Exception):
    """Base class for all WinClip domain errors."""


class ClipNotFoundError(WinClipError):
    """Raised when an operation references a clip that does not exist."""

    def __init__(self, clip_id: str) -> None:
        super().__init__(f"clip not found: {clip_id}")
        self.clip_id = clip_id


class InvalidSettingsError(WinClipError):
    """Raised when persisted or supplied settings are invalid."""
