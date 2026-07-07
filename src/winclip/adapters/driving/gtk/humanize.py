"""Presentation helper: relative timestamps for the history panel."""

from __future__ import annotations

from datetime import datetime


def relative_time(moment: datetime, now: datetime) -> str:
    delta = now - moment
    seconds = int(delta.total_seconds())
    if seconds < 0:
        seconds = 0
    if seconds < 60:
        return "Just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} h ago"
    days = hours // 24
    if days == 1:
        return "Yesterday"
    if days < 7:
        return f"{days} days ago"
    return moment.astimezone().strftime("%d %b %Y")
