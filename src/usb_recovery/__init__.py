"""USB Recovery Lab — safe recovery of deleted and lost files from USB storage."""

from __future__ import annotations

from usb_recovery.constants import APP_NAME, APP_VERSION

__all__ = ["APP_NAME", "APP_VERSION", "RecoveryLab"]
__version__ = APP_VERSION


def __getattr__(name: str):
    if name == "RecoveryLab":
        from usb_recovery.api import RecoveryLab

        return RecoveryLab
    raise AttributeError(name)
