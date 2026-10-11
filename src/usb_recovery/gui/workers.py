"""Background workers so the UI thread never blocks on disk I/O."""

from __future__ import annotations

import threading
from typing import Any

from usb_recovery.api import RecoveryLab
from usb_recovery.models import Candidate, ProgressEvent, ScanOptions

try:
    from PySide6.QtCore import QObject, Signal, Slot
except ImportError:  # pragma: no cover
    QObject = object  # type: ignore[misc,assignment]

    class Signal:  # type: ignore[no-redef]
        def __init__(self, *args: object) -> None:
            pass

        def emit(self, *args: object) -> None:
            pass

    def Slot(*args: object):  # type: ignore[misc]
        def deco(fn):
            return fn

        return deco


class ScanWorker(QObject):
    progressed = Signal(object)
    finished = Signal(str, list)
    failed = Signal(str)

    def __init__(self, lab: RecoveryLab, source: str, options: ScanOptions, confirm: str | None) -> None:
        super().__init__()
        self.lab = lab
        self.source = source
        self.options = options
        self.confirm = confirm
        self.cancel = threading.Event()

    @Slot()
    def run(self) -> None:
        try:
            def cb(ev: ProgressEvent) -> None:
                self.progressed.emit(ev)

            session_id, found = self.lab.scan(
                self.source, confirm=self.confirm, options=self.options, progress=cb, cancel=self.cancel
            )
            self.finished.emit(session_id, found)
        except Exception as exc:
            self.failed.emit(str(exc))


class RecoverWorker(QObject):
    progressed = Signal(object)
    finished = Signal(list)
    failed = Signal(str)

    def __init__(
        self,
        lab: RecoveryLab,
        source: str,
        candidates: list[Candidate],
        dest: str,
        confirm: str | None,
        session_id: str | None,
        allow_same: bool,
    ) -> None:
        super().__init__()
        self.lab = lab
        self.source = source
        self.candidates = candidates
        self.dest = dest
        self.confirm = confirm
        self.session_id = session_id
        self.allow_same = allow_same
        self.cancel = threading.Event()

    @Slot()
    def run(self) -> None:
        try:
            def cb(ev: ProgressEvent) -> None:
                self.progressed.emit(ev)

            results = self.lab.recover(
                self.source,
                self.candidates,
                self.dest,
                confirm=self.confirm,
                session_id=self.session_id,
                allow_same_device=self.allow_same,
                progress=cb,
                cancel=self.cancel,
            )
            self.finished.emit(results)
        except Exception as exc:
            self.failed.emit(str(exc))


class ImageWorker(QObject):
    progressed = Signal(object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, lab: RecoveryLab, source: str, dest: str, confirm: str | None) -> None:
        super().__init__()
        self.lab = lab
        self.source = source
        self.dest = dest
        self.confirm = confirm
        self.cancel = threading.Event()

    @Slot()
    def run(self) -> None:
        try:
            def cb(ev: ProgressEvent) -> None:
                self.progressed.emit(ev)

            result = self.lab.image(
                self.source, self.dest, confirm=self.confirm, progress=cb, cancel=self.cancel
            )
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
