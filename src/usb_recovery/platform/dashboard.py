"""Customizable dashboard layout (295)."""

from __future__ import annotations

DEFAULT_LAYOUT = [
    {"id": "devices", "title": "Devices", "visible": True, "order": 0},
    {"id": "sessions", "title": "Recent sessions", "visible": True, "order": 1},
    {"id": "jobs", "title": "Jobs", "visible": True, "order": 2},
    {"id": "resources", "title": "Resources", "visible": False, "order": 3},
    {"id": "risk", "title": "Acquisition risk", "visible": True, "order": 4},
]


def arrange_dashboard(layout: list[dict] | None = None) -> list[dict]:
    items = list(layout or DEFAULT_LAYOUT)
    items.sort(key=lambda i: (not i.get("visible", True), int(i.get("order") or 0)))
    return [i for i in items if i.get("visible", True)]
