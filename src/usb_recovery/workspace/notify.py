"""Local recovery progress notifications (248). No network, no telemetry."""

from __future__ import annotations

from dataclasses import dataclass, field

from usb_recovery.util import isoformat


@dataclass
class Notification:
    ts: str
    kind: str
    message: str


@dataclass
class NotificationLog:
    items: list[Notification] = field(default_factory=list)

    def emit(self, kind: str, message: str) -> Notification:
        note = Notification(ts=isoformat(), kind=kind, message=message)
        self.items.append(note)
        return note

    def scan_finished(self, session_id: str, count: int) -> Notification:
        return self.emit("scan-finished", f"Scan {session_id} finished with {count} candidates")

    def recovery_finished(self, recovered: int, total: int) -> Notification:
        return self.emit("recovery-finished", f"Recovery finished: {recovered}/{total} copies written")

    def needs_attention(self, message: str) -> Notification:
        return self.emit("attention", message)
