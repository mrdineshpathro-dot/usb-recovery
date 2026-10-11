from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

import pytest

from usb_recovery.diagnostics import redact_text, write_support_bundle
from usb_recovery.exceptions import PluginVerificationError
from usb_recovery.lab.benchmark import run_benchmark
from usb_recovery.lab.fuzz import fuzz_parsers
from usb_recovery.lab.synthetic import list_scenarios, write_scenario
from usb_recovery.models import Candidate
from usb_recovery.security.plugins import verify_plugin
from usb_recovery.security.preview_isolate import isolated_preview
from usb_recovery.security.privacy import review_privacy
from usb_recovery.security.scanner import scan_offline, suspicious_warning


def test_suspicious_and_privacy() -> None:
    exe = Candidate(
        id="e",
        name="setup.exe",
        size=10,
        file_type="exe",
        mime="application/x-msdownload",
        method="carved",
        status="carved",
        source_offset=0,
        confidence=20,
        extension="exe",
        extra={"content": b"MZ\x90\x00"},
    )
    flags = suspicious_warning(exe, b"MZ\x90\x00")
    assert flags
    priv = review_privacy(
        Candidate(
            id="p",
            name="img.jpg",
            size=10,
            file_type="jpeg",
            mime="image/jpeg",
            method="carved",
            status="carved",
            source_offset=0,
            confidence=40,
            extra={"content": b"GPS" + b"\x00" * 20},
        )
    )
    assert priv["sensitive"] is True


def test_offline_scanner_heuristic(tmp_path: Path) -> None:
    f = tmp_path / "note.txt"
    f.write_text("hello")
    result = scan_offline(f, allow_external=False)
    assert result["engine"] == "heuristic"
    assert result["external"] is False


def test_plugin_hmac_and_allowlist(tmp_path: Path) -> None:
    plugin = tmp_path / "demo.py"
    plugin.write_text("# plugin\n")
    digest = hashlib.sha256(plugin.read_bytes()).hexdigest()
    store = tmp_path / "trust.json"
    store.write_text(json.dumps({"plugins": {"demo.py": {"sha256": digest, "allowed": True}}}))
    assert verify_plugin(plugin, trust_store=store)["verified"] is True
    key = b"unit-test-key"
    sig = hmac.new(key, plugin.read_bytes(), hashlib.sha256).hexdigest()
    plugin.with_suffix(".py.sig").write_text(sig)
    assert verify_plugin(plugin, hmac_key=key)["verified"] is True
    with pytest.raises(PluginVerificationError):
        verify_plugin(plugin)


def test_redacted_bundle(tmp_path: Path) -> None:
    log = tmp_path / "usb-recovery.log"
    log.write_text("serial=ABCDEF path=/home/alice/secret\n")
    dest = tmp_path / "bundle.json"
    write_support_bundle(dest, log, extra={"note": "hi"})
    text = dest.read_text()
    assert "ABCDEF" not in text
    assert "/home/alice" not in text
    assert "<redacted>" in text or "<user>" in text
    assert "alice" not in redact_text("/home/alice/x")


def test_fuzz_and_synthetic_benchmark(tmp_path: Path) -> None:
    assert fuzz_parsers(iterations=24)["ok"] is True
    assert "deleted_fat" in list_scenarios()
    img = tmp_path / "lab.img"
    write_scenario("deleted_fat", img)
    result = run_benchmark(img, expect_names=["HELLO.TXT"], profile="quick")
    assert result["regression_ok"] is True
    assert result["candidates"] >= 1


def test_isolated_preview_jpeg() -> None:
    from tests.fixtures.builder import minimal_jpeg

    out = isolated_preview("jpeg", minimal_jpeg(), timeout=5)
    assert out.get("isolated") is True
    assert out.get("ok") in {True, False}
