"""WinClip application layer: use cases and ports."""

from .use_cases import (
    ActivateClip,
    ActivateSnippet,
    ActivationResult,
    CaptureClipboard,
    ManageHistory,
    ManageSettings,
    QueryCommands,
    QueryHistory,
)

__all__ = [
    "ActivateClip",
    "ActivateSnippet",
    "ActivationResult",
    "CaptureClipboard",
    "ManageHistory",
    "ManageSettings",
    "QueryCommands",
    "QueryHistory",
]
