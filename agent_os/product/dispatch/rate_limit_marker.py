"""Reading the instant a marker file records."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def marker_timestamp(path: Path) -> datetime | None:
    """The instant a rate-limit marker file records, or None when there is none to read. Same
    shape `latest_event_at` has for events, for a page that writes no event at all."""
    if not path.is_file():
        return None
    try:
        return datetime.fromisoformat(path.read_text().strip())
    except ValueError:
        return None
