"""WinClip application layer: use cases and ports."""

from .use_cases import (
    ActivateClip,
    ActivationResult,
    CaptureClipboard,
    ManageHistory,
    ManageSettings,
    QueryHistory,
)

__all__ = [
    "ActivateClip",
    "ActivationResult",
    "CaptureClipboard",
    "ManageHistory",
    "ManageSettings",
    "QueryHistory",
]
