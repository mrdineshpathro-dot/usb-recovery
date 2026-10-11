"""Accessibility navigation hints (300)."""

from __future__ import annotations

SHORTCUTS = [
    ("Ctrl+O", "Open disk image"),
    ("F5", "Refresh device list"),
    ("Ctrl+F", "Focus search"),
    ("Ctrl+R", "Start scan"),
    ("Esc", "Cancel running job"),
    ("Tab / Shift+Tab", "Move focus between controls"),
]


def accessibility_hints() -> dict:
    return {
        "shortcuts": [{"keys": k, "action": a} for k, a in SHORTCUTS],
        "focus": "Buttons and tables are keyboard-focusable. High-contrast themes are under Toggle theme.",
        "screen_reader": (
            "Qt accessibility is used when the platform plugin provides it. "
            "This is not a certified WCAG audit."
        ),
    }
