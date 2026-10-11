"""Reusable Python API (feature 173)."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from usb_recovery.config import AppConfig
from usb_recovery.db.store import SessionStore
from usb_recovery.devices.detector import describe_source, list_devices, open_source
from usb_recovery.imaging.dd import image_source
from usb_recovery.models import Candidate, DeviceInfo, ImagingResult, RecoveryResult, ScanOptions
from usb_recovery.recovery.engine import recover_candidates, scan_source
from usb_recovery.advisor.assessment import assess_source, estimate_effort
from usb_recovery.advisor.assistant import advise
from usb_recovery.models import Advice, Assessment
from usb_recovery.reports.csv_report import write_csv_report
from usb_recovery.reports.html import write_html_report
from usb_recovery.reports.json_report import write_json_report
from usb_recovery.workspace.saved import WorkspaceStore


class RecoveryLab:
    """High-level façade used by the CLI, GUI, and external scripts."""

    def __init__(
        self,
        *,
        config: AppConfig | None = None,
        db_path: str | Path | None = None,
    ) -> None:
        self.config = config or AppConfig.load()
        self.store = SessionStore(db_path)
        self.workspace = WorkspaceStore(self.store)

    def list_devices(self, include_non_usb: bool = False) -> list[DeviceInfo]:
        return list_devices(include_non_usb=include_non_usb)

    def describe(self, path: str, confirm: str | None = None) -> DeviceInfo:
        return describe_source(path, confirm=confirm)

    def image(
        self,
        source_path: str,
        dest_path: str,
        *,
        confirm: str | None = None,
        resume: bool = True,
        allow_same_device: bool = False,
        progress=None,
        cancel=None,
    ) -> ImagingResult:
        source = open_source(source_path, confirm=confirm)
        try:
            return image_source(
                source,
                dest_path,
                config=self.config,
                progress=progress,
                cancel=cancel,
                resume=resume,
                allow_same_device=allow_same_device,
            )
        finally:
            source.close()

    def scan(
        self,
        source_path: str,
        *,
        confirm: str | None = None,
        options: ScanOptions | None = None,
        progress=None,
        cancel=None,
    ) -> tuple[str, list[Candidate]]:
        options = options or ScanOptions.from_profile(self.config.default_profile)  # type: ignore[arg-type]
        source = open_source(source_path, confirm=confirm)
        try:
            info = source.info()
            session_id = self.store.create_session(source.path, source.size, options.profile)
            self.store.event(session_id, "INFO", "session", f"scan start profile={options.profile}")
            found = scan_source(
                source,
                options,
                store=self.store,
                session_id=session_id,
                device=info,
                progress=progress,
                cancel=cancel,
            )
            return session_id, found
        finally:
            source.close()

    def recover(
        self,
        source_path: str,
        candidates: Iterable[Candidate],
        destination: str,
        *,
        confirm: str | None = None,
        session_id: str | None = None,
        allow_same_device: bool = False,
        progress=None,
        cancel=None,
        write_sidecars: bool = False,
        filename_template: str | None = None,
    ) -> list[RecoveryResult]:
        source = open_source(source_path, confirm=confirm)
        try:
            return recover_candidates(
                source,
                list(candidates),
                destination,
                config=self.config,
                store=self.store,
                session_id=session_id,
                allow_same_device=allow_same_device,
                progress=progress,
                cancel=cancel,
                write_sidecars=write_sidecars,
                filename_template=filename_template,
            )
        finally:
            source.close()

    def assess(self, path: str, confirm: str | None = None, dest: str | None = None) -> Assessment:
        result = assess_source(path, confirm=confirm)
        return estimate_effort(result, dest=dest)

    def advise(self, symptom: str = "unknown", filesystem: str | None = None) -> Advice:
        return advise(symptom=symptom, filesystem=filesystem)

    def export_report(self, session_id: str, dest: str, fmt: str = "json") -> Path:
        session = self.store.get_session(session_id) or {"id": session_id}
        candidates = self.store.list_candidates(session_id)
        events = self.store.list_events(session_id)
        path = Path(dest)
        if fmt == "html":
            return write_html_report(path, session=session, candidates=candidates, events=events)
        if fmt == "csv":
            return write_csv_report(path, candidates)
        return write_json_report(path, session=session, candidates=candidates, events=events)
