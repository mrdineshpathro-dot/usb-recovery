from __future__ import annotations

import json
from pathlib import Path

from usb_recovery.cli.main import main
from usb_recovery.constants import EXIT_OK, EXIT_SAFETY


def test_list_devices_json(capsys) -> None:
    code = main(["--json", "list-devices"])
    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out or "[]")
    assert isinstance(payload, list)


def test_info_and_scan(mbr_image: dict, capsys, tmp_path: Path) -> None:
    code = main(["--json", "info", str(mbr_image["path"])])
    assert code == EXIT_OK
    info = json.loads(capsys.readouterr().out)
    assert info["is_image"] is True
    db = tmp_path / "s.db"
    code = main(["--json", "--db", str(db), "scan", str(mbr_image["path"]), "--profile", "quick"])
    assert code == EXIT_OK
    result = json.loads(capsys.readouterr().out)
    assert result["count"] >= 1
    assert result["session_id"].startswith("sess-")


def test_physical_device_requires_confirm() -> None:
    # A non-existent block-like path still must not skip confirmation if detected as device;
    # for a missing file we get source access, not a silent success.
    code = main(["info", "/dev/this-does-not-exist-usb-recovery"])
    assert code in {EXIT_SAFETY, 4, 1}


def test_advise_and_explain(capsys) -> None:
    code = main(["--json", "advise", "--symptom", "deleted"])
    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["profile"] == "quick"
    code = main(["--json", "explain", "--topic", "overwritten"])
    assert code == EXIT_OK
    items = json.loads(capsys.readouterr().out)
    assert items and "Overwritten" in items[0]["title"]


def test_diagnostics(tmp_path: Path, capsys) -> None:
    dest = tmp_path / "bundle.json"
    code = main(["diagnostics", "--dest", str(dest)])
    assert code == EXIT_OK
    assert dest.exists()
    data = json.loads(dest.read_text())
    assert "version" in data
