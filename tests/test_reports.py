from __future__ import annotations

from pathlib import Path

from usb_recovery.reports.csv_report import write_csv_report
from usb_recovery.reports.html import write_html_report
from usb_recovery.reports.json_report import write_json_report


def test_reports(tmp_path: Path) -> None:
    session = {"id": "sess-1", "source_path": "/tmp/x.img", "profile": "standard", "status": "scanned"}
    cands = [
        {
            "id": "c1",
            "name": "a.txt",
            "original_path": "/a.txt",
            "size": 12,
            "file_type": "txt",
            "mime": "text/plain",
            "method": "metadata",
            "status": "deleted",
            "confidence": 70,
            "source_offset": 0,
            "sha256": "abc",
        }
    ]
    events = [{"ts": "t", "level": "INFO", "category": "scan", "message": "ok"}]
    html = write_html_report(tmp_path / "r.html", session=session, candidates=cands, events=events)
    js = write_json_report(tmp_path / "r.json", session=session, candidates=cands, events=events)
    csv = write_csv_report(tmp_path / "r.csv", cands)
    assert "sess-1" in html.read_text()
    assert "not guaranteed" in html.read_text().lower() or "not a probability" in html.read_text().lower()
    assert '"session"' in js.read_text()
    assert "a.txt" in csv.read_text()
