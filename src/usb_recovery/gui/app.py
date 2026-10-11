"""PySide6 desktop application — wizard + dashboard (features 141–160)."""

from __future__ import annotations

import sys
from pathlib import Path

from usb_recovery.api import RecoveryLab
from usb_recovery.constants import APP_NAME, APP_VERSION, DEVICE_CONFIRM_TOKEN
from usb_recovery.logging_config import setup_logging
from usb_recovery.models import Candidate, DeviceInfo, ScanOptions
from usb_recovery.util import decode_ascii, human_size

try:
    from PySide6.QtCore import QSize, Qt, QThread, QTimer
    from PySide6.QtGui import QAction, QColor, QFont, QImage, QKeySequence, QPixmap, QShortcut
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QFrame,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QSplitter,
        QStackedWidget,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "PySide6 is required for the GUI. Install with: pip install 'usb-recovery-lab[gui]'"
    ) from exc

from usb_recovery.gui.theme import stylesheet
from usb_recovery.gui.workers import RecoverWorker, ScanWorker


def _card() -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    return frame


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.lab = RecoveryLab()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(1180, 760)
        self.setMinimumSize(QSize(960, 640))
        self.theme = self.lab.config.theme
        self.source_path: str | None = None
        self.source_info: DeviceInfo | None = None
        self.session_id: str | None = None
        self.candidates: list[Candidate] = []
        self.confirm_token: str | None = None
        self._thread: QThread | None = None
        self._worker = None
        self._build()
        self._shortcuts()
        self.refresh_devices()

    def _build(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        nav = QVBoxLayout()
        title = QLabel(APP_NAME)
        title.setObjectName("title")
        nav.addWidget(title)
        sub = QLabel("Read-only recovery. Not guaranteed.")
        sub.setObjectName("subtitle")
        sub.setWordWrap(True)
        nav.addWidget(sub)
        self.nav_list = QListWidget()
        for label in ("Home", "Source & safety", "Scan", "Results", "Recover", "Summary", "Assistant"):
            self.nav_list.addItem(QListWidgetItem(label))
        self.nav_list.setCurrentRow(0)
        self.nav_list.currentRowChanged.connect(self._nav)
        nav.addWidget(self.nav_list, 1)
        theme_btn = QPushButton("Toggle theme")
        theme_btn.clicked.connect(self.toggle_theme)
        nav.addWidget(theme_btn)
        nav_wrap = QWidget()
        nav_wrap.setLayout(nav)
        nav_wrap.setFixedWidth(240)

        self.stack = QStackedWidget()
        self.page_home = self._home_page()
        self.page_source = self._source_page()
        self.page_scan = self._scan_page()
        self.page_results = self._results_page()
        self.page_recover = self._recover_page()
        self.page_summary = self._summary_page()
        self.page_assistant = self._assistant_page()
        for page in (
            self.page_home,
            self.page_source,
            self.page_scan,
            self.page_results,
            self.page_recover,
            self.page_summary,
            self.page_assistant,
        ):
            self.stack.addWidget(page)

        layout.addWidget(nav_wrap)
        layout.addWidget(self.stack, 1)
        self.statusBar().showMessage("Ready · offline-first · telemetry disabled")

    def _shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+O"), self, self.open_image)
        QShortcut(QKeySequence("F5"), self, self.refresh_devices)
        QShortcut(QKeySequence("Ctrl+F"), self, lambda: self.search_box.setFocus())
        QShortcut(QKeySequence("Ctrl+R"), self, self.start_scan)
        QShortcut(QKeySequence("Esc"), self, self.cancel_work)

    def _nav(self, row: int) -> None:
        self.stack.setCurrentIndex(max(0, row))

    def toggle_theme(self) -> None:
        self.theme = "light" if self.theme == "dark" else "dark"
        app = QApplication.instance()
        if app:
            app.setStyleSheet(stylesheet(self.theme))

    # --- pages ----------------------------------------------------------
    def _home_page(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.addWidget(QLabel("Connected removable devices"))
        self.device_list = QListWidget()
        self.device_list.itemDoubleClicked.connect(self._pick_device_item)
        box.addWidget(self.device_list, 1)
        row = QHBoxLayout()
        refresh = QPushButton("Refresh devices")
        refresh.clicked.connect(self.refresh_devices)
        open_img = QPushButton("Open disk image…")
        open_img.setObjectName("primary")
        open_img.clicked.connect(self.open_image)
        row.addWidget(refresh)
        row.addWidget(open_img)
        row.addStretch()
        box.addLayout(row)
        hint = QLabel(
            "Work from a sector image whenever the device is unstable. "
            "Never recover onto the source pen drive."
        )
        hint.setObjectName("subtitle")
        hint.setWordWrap(True)
        box.addWidget(hint)
        return page

    def _source_page(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.addWidget(QLabel("Source details & safety check"))
        self.source_detail = QPlainTextEdit()
        self.source_detail.setReadOnly(True)
        box.addWidget(self.source_detail, 1)
        self.confirm_box = QCheckBox(
            f"I understand this app opens devices read-only and will not write to the source. "
            f"Token: {DEVICE_CONFIRM_TOKEN}"
        )
        box.addWidget(self.confirm_box)
        warn = QLabel(
            "A read-only handle does not stop the OS, USB bridge, or flash controller from writing. "
            "Unmount live volumes. Failing flash can worsen with continued reads."
        )
        warn.setObjectName("warn")
        warn.setWordWrap(True)
        box.addWidget(warn)
        next_btn = QPushButton("Continue to scan options")
        next_btn.setObjectName("primary")
        next_btn.clicked.connect(lambda: self._goto(2))
        box.addWidget(next_btn, alignment=Qt.AlignmentFlag.AlignRight)
        return page

    def _scan_page(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.addWidget(QLabel("Scan profile"))
        self.profile = QComboBox()
        self.profile.addItems(["quick", "standard", "deep"])
        self.profile.setCurrentText("standard")
        box.addWidget(self.profile)
        self.chk_meta = QCheckBox("Filesystem metadata recovery")
        self.chk_meta.setChecked(True)
        self.chk_carve = QCheckBox("Signature carving")
        self.chk_carve.setChecked(True)
        box.addWidget(self.chk_meta)
        box.addWidget(self.chk_carve)
        self.progress = QProgressBar()
        self.progress_label = QLabel("Idle")
        self.progress_label.setObjectName("subtitle")
        box.addWidget(self.progress)
        box.addWidget(self.progress_label)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        box.addWidget(self.log_view, 1)
        row = QHBoxLayout()
        start = QPushButton("Start scan")
        start.setObjectName("primary")
        start.clicked.connect(self.start_scan)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.cancel_work)
        row.addWidget(start)
        row.addWidget(cancel)
        row.addStretch()
        box.addLayout(row)
        return page

    def _results_page(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        top = QHBoxLayout()
        top.addWidget(QLabel("Scan results"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter by name or path…")
        self.search_box.textChanged.connect(self.apply_filter)
        top.addWidget(self.search_box, 1)
        self.filter_type = QComboBox()
        self.filter_type.addItems(["all types", "jpeg", "png", "pdf", "zip", "docx", "txt", "carved", "deleted"])
        self.filter_type.currentTextChanged.connect(self.apply_filter)
        top.addWidget(self.filter_type)
        box.addLayout(top)

        split = QSplitter()
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Name", "Path", "Size", "Type", "Method", "Status", "Score"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._preview_selected)
        split.addWidget(self.table)

        preview_wrap = QWidget()
        pv = QVBoxLayout(preview_wrap)
        pv.addWidget(QLabel("Preview (never executed)"))
        self.preview_image = QLabel("No selection")
        self.preview_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image.setMinimumHeight(180)
        pv.addWidget(self.preview_image)
        self.preview_text = QPlainTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setFont(QFont("monospace", 10))
        pv.addWidget(self.preview_text, 1)
        split.addWidget(preview_wrap)
        split.setSizes([700, 360])
        box.addWidget(split, 1)
        go = QPushButton("Recover selected…")
        go.setObjectName("primary")
        go.clicked.connect(lambda: self._goto(4))
        box.addWidget(go, alignment=Qt.AlignmentFlag.AlignRight)
        return page

    def _recover_page(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.addWidget(QLabel("Recovery destination"))
        row = QHBoxLayout()
        self.dest_edit = QLineEdit()
        self.dest_edit.setPlaceholderText("Choose a folder on a different disk")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self.choose_dest)
        row.addWidget(self.dest_edit, 1)
        row.addWidget(browse)
        box.addLayout(row)
        self.dest_warn = QLabel("")
        self.dest_warn.setObjectName("danger")
        self.dest_warn.setWordWrap(True)
        box.addWidget(self.dest_warn)
        self.chk_hierarchy = QCheckBox("Recreate original directory hierarchy when known")
        self.chk_hierarchy.setChecked(True)
        box.addWidget(self.chk_hierarchy)
        self.recover_progress = QProgressBar()
        box.addWidget(self.recover_progress)
        run = QPushButton("Write recovered copies")
        run.setObjectName("primary")
        run.clicked.connect(self.start_recover)
        box.addWidget(run, alignment=Qt.AlignmentFlag.AlignRight)
        box.addStretch()
        return page

    def _assistant_page(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.addWidget(QLabel("Recovery assistant (rule-based, offline)"))
        self.symptom = QComboBox()
        self.symptom.addItems(["deleted", "formatted", "inaccessible", "corrupted", "unknown"])
        box.addWidget(self.symptom)
        run = QPushButton("Advise")
        run.setObjectName("primary")
        run.clicked.connect(self._run_advice)
        box.addWidget(run)
        self.advice_view = QPlainTextEdit()
        self.advice_view.setReadOnly(True)
        box.addWidget(self.advice_view, 1)
        return page

    def _run_advice(self) -> None:
        from usb_recovery.advisor.assistant import advise, format_advice
        from usb_recovery.advisor.explain import explain_limitations

        advice = advise(symptom=self.symptom.currentText(), device=self.source_info)
        extra = explain_limitations("trimmed" if self.symptom.currentText() == "formatted" else "overwritten")
        text = format_advice(advice) + "\n\nLimitations:\n"
        text += "\n".join(f"- {i['title']}: {i['summary']}" for i in extra)
        self.advice_view.setPlainText(text)

    def _summary_page(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.addWidget(QLabel("Session summary"))
        self.summary_text = QPlainTextEdit()
        self.summary_text.setReadOnly(True)
        box.addWidget(self.summary_text, 1)
        row = QHBoxLayout()
        html_btn = QPushButton("Export HTML report")
        html_btn.clicked.connect(lambda: self.export_report("html"))
        json_btn = QPushButton("Export JSON report")
        json_btn.clicked.connect(lambda: self.export_report("json"))
        csv_btn = QPushButton("Export CSV")
        csv_btn.clicked.connect(lambda: self.export_report("csv"))
        row.addWidget(html_btn)
        row.addWidget(json_btn)
        row.addWidget(csv_btn)
        row.addStretch()
        box.addLayout(row)
        return page

    # --- actions --------------------------------------------------------
    def refresh_devices(self) -> None:
        self.device_list.clear()
        try:
            devices = self.lab.list_devices()
        except Exception as exc:
            self.statusBar().showMessage(str(exc))
            return
        if not devices:
            self.device_list.addItem("No removable USB devices detected. Open a disk image instead.")
            return
        for dev in devices:
            item = QListWidgetItem(
                f"{dev.display_name}\n{dev.path} · {human_size(dev.size_bytes)} · {dev.bus}"
            )
            item.setData(Qt.ItemDataRole.UserRole, dev)
            if any(w.severity == "danger" for w in dev.warnings):
                item.setForeground(QColor("#ffa198"))
            self.device_list.addItem(item)

    def _pick_device_item(self, item: QListWidgetItem) -> None:
        dev = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(dev, DeviceInfo):
            return
        self._set_source(dev.path, dev)

    def open_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open disk image", str(Path.home()), "Images (*.dd *.img *.raw *.bin *);;All files (*)"
        )
        if not path:
            return
        try:
            info = self.lab.describe(path)
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
            return
        self._set_source(path, info)

    def _set_source(self, path: str, info: DeviceInfo) -> None:
        self.source_path = path
        self.source_info = info
        lines = [
            f"Path: {info.path}",
            f"Name: {info.display_name}",
            f"Size: {human_size(info.size_bytes)}",
            f"Sector size: {info.sector_size}",
            f"Bus: {info.bus}",
            f"Physical device: {info.is_physical}",
            f"Disk image: {info.is_image}",
            "",
            "Warnings:",
        ]
        if info.warnings:
            for w in info.warnings:
                lines.append(f"  [{w.severity}] {w.message}")
        else:
            lines.append("  none")
        lines += [
            "",
            "Safety rules:",
            "  • Source is opened O_RDONLY only.",
            "  • Recovered files are never written back to the source.",
            "  • Prefer imaging a failing device before a deep scan.",
            "  • Recovery is not guaranteed.",
        ]
        self.source_detail.setPlainText("\n".join(lines))
        self._goto(1)
        self.statusBar().showMessage(f"Source {info.display_name}")

    def _goto(self, index: int) -> None:
        self.nav_list.setCurrentRow(index)
        self.stack.setCurrentIndex(index)

    def start_scan(self) -> None:
        if not self.source_path:
            QMessageBox.information(self, APP_NAME, "Select a device or disk image first.")
            return
        if self.source_info and self.source_info.is_physical and not self.confirm_box.isChecked():
            QMessageBox.warning(
                self,
                APP_NAME,
                "Confirm the safety checkbox before opening a physical device.",
            )
            return
        self.confirm_token = DEVICE_CONFIRM_TOKEN if self.confirm_box.isChecked() else None
        options = ScanOptions.from_profile(self.profile.currentText())  # type: ignore[arg-type]
        options.enable_metadata = self.chk_meta.isChecked()
        options.enable_carving = self.chk_carve.isChecked()
        self._goto(2)
        self.progress.setValue(0)
        self.log_view.appendPlainText("Scan started…")
        worker = ScanWorker(self.lab, self.source_path, options, self.confirm_token)
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progressed.connect(self._on_progress)
        worker.finished.connect(self._on_scan_done)
        worker.failed.connect(self._on_fail)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        self._worker = worker
        self._thread = thread
        thread.start()

    def _on_progress(self, ev) -> None:
        pct = int(ev.ratio * 100)
        self.progress.setValue(pct)
        self.recover_progress.setValue(pct)
        self.progress_label.setText(ev.message)
        self.log_view.appendPlainText(f"{ev.phase}: {ev.message} ({pct}%)")

    def _on_scan_done(self, session_id: str, found: list) -> None:
        self.session_id = session_id
        self.candidates = list(found)
        self._fill_table(self.candidates)
        self.log_view.appendPlainText(f"Done. {len(found)} candidates. Session {session_id}")
        self._goto(3)

    def _on_fail(self, message: str) -> None:
        QMessageBox.warning(self, APP_NAME, message)
        self.log_view.appendPlainText("ERROR: " + message)

    def _fill_table(self, items: list[Candidate]) -> None:
        self.table.setRowCount(0)
        for cand in items:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                cand.name,
                cand.original_path or "",
                human_size(cand.size),
                cand.file_type,
                cand.method,
                cand.status,
                f"{cand.confidence:.0f}",
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, cand)
                if col == 6:
                    score = cand.confidence
                    if score >= 85:
                        cell.setForeground(QColor("#3fb950"))
                    elif score < 40:
                        cell.setForeground(QColor("#e3b341"))
                self.table.setItem(row, col, cell)

    def apply_filter(self) -> None:
        text = self.search_box.text().lower()
        kind = self.filter_type.currentText()
        pool = self.candidates
        if text and any(w in text for w in ("deleted", "larger than", "named", "photos", "jpeg", "carved")):
            from usb_recovery.workspace.search import natural_search

            pool = natural_search(self.candidates, text)
            text = ""
        filtered: list[Candidate] = []
        for cand in pool:
            blob = f"{cand.name} {cand.original_path or ''} {cand.file_type} {cand.method} {cand.status}".lower()
            if text and text not in blob:
                continue
            if kind != "all types":
                if kind in {"carved", "deleted"}:
                    if kind == "carved" and cand.method != "carved":
                        continue
                    if kind == "deleted" and cand.status != "deleted":
                        continue
                elif kind not in {cand.file_type, cand.extension, cand.mime}:
                    continue
            filtered.append(cand)
        self._fill_table(filtered)

    def _selected_candidates(self) -> list[Candidate]:
        seen: dict[str, Candidate] = {}
        for item in self.table.selectedItems():
            cand = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(cand, Candidate):
                seen[cand.id] = cand
        if not seen:
            return list(self.candidates)
        return list(seen.values())

    def _preview_selected(self) -> None:
        items = self._selected_candidates()
        if not items:
            return
        cand = items[0]
        content = cand.extra.get("content") if isinstance(cand.extra, dict) else None
        reasons = "\n".join(cand.confidence_reasons)
        header = (
            f"{cand.name}\n{cand.mime} · {human_size(cand.size)} · offset {cand.source_offset}\n"
            f"Confidence {cand.confidence:.0f} (heuristic, not a probability)\n{reasons}\n"
        )
        if isinstance(content, (bytes, bytearray)) and cand.mime.startswith("image/"):
            image = QImage.fromData(bytes(content))
            if not image.isNull():
                self.preview_image.setPixmap(
                    QPixmap.fromImage(image).scaled(
                        320, 180, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                    )
                )
            else:
                self.preview_image.setText("Image bytes did not decode")
        else:
            self.preview_image.setText(cand.file_type or "no image preview")
        if isinstance(content, (bytes, bytearray)):
            if cand.mime.startswith("text/") or cand.file_type in {"txt", "csv", "log"}:
                self.preview_text.setPlainText(header + "\n" + bytes(content[:8000]).decode("utf-8", errors="replace"))
            else:
                hexdump = _hexdump(bytes(content[:512]), cand.source_offset)
                self.preview_text.setPlainText(header + "\n" + hexdump)
        else:
            self.preview_text.setPlainText(header + "\n(content not buffered — recover to inspect)")

    def choose_dest(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Recovery destination")
        if path:
            self.dest_edit.setText(path)

    def start_recover(self) -> None:
        dest = self.dest_edit.text().strip()
        if not dest or not self.source_path:
            QMessageBox.information(self, APP_NAME, "Choose a destination folder.")
            return
        selected = self._selected_candidates()
        reply = QMessageBox.question(
            self,
            APP_NAME,
            f"Write {len(selected)} recovered copies to\n{dest}\n\n"
            "The source will not be modified. Continue?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        worker = RecoverWorker(
            self.lab,
            self.source_path,
            selected,
            dest,
            self.confirm_token,
            self.session_id,
            False,
        )
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progressed.connect(self._on_progress)
        worker.finished.connect(self._on_recover_done)
        worker.failed.connect(self._on_fail)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        self._worker = worker
        self._thread = thread
        thread.start()

    def _on_recover_done(self, results: list) -> None:
        recovered = sum(1 for r in results if r.status == "recovered")
        partial = sum(1 for r in results if r.status == "partial")
        failed = sum(1 for r in results if r.status == "failed")
        text = [
            f"Session: {self.session_id}",
            f"Source: {self.source_path}",
            f"Candidates scanned: {len(self.candidates)}",
            f"Recovered: {recovered}",
            f"Partial: {partial}",
            f"Failed: {failed}",
            "",
            "Recovery is not guaranteed. Verify important files manually.",
            "Hashes were computed on recovered copies only.",
        ]
        self.summary_text.setPlainText("\n".join(text))
        self._goto(5)

    def export_report(self, fmt: str) -> None:
        if not self.session_id:
            QMessageBox.information(self, APP_NAME, "No session to export.")
            return
        suffix = {"html": "html", "csv": "csv", "json": "json"}[fmt]
        path, _ = QFileDialog.getSaveFileName(self, "Export report", f"report.{suffix}", f"*.{suffix}")
        if not path:
            return
        written = self.lab.export_report(self.session_id, path, fmt=fmt)
        self.statusBar().showMessage(f"Wrote {written}")

    def cancel_work(self) -> None:
        if self._worker is not None and hasattr(self._worker, "cancel"):
            self._worker.cancel.set()
            self.log_view.appendPlainText("Cancel requested…")


def _hexdump(data: bytes, base: int) -> str:
    lines = []
    for i in range(0, len(data), 16):
        chunk = data[i : i + 16]
        hexpart = " ".join(f"{b:02x}" for b in chunk)
        lines.append(f"{base + i:08x}  {hexpart:<48}  {decode_ascii(chunk)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    setup_logging(level="INFO", console=False)
    app = QApplication(argv or sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyleSheet(stylesheet("dark"))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
