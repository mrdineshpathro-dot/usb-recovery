from __future__ import annotations

from pathlib import Path

import pytest

from usb_recovery.exceptions import SafetyError, VaultError
from usb_recovery.models import Candidate, RecoveryResult
from usb_recovery.output.destination import check_destination, verify_destination
from usb_recovery.output.naming import apply_template, resolve_collision
from usb_recovery.output.sidecars import write_sidecar
from usb_recovery.output.summary import copy_verified_second, recoverable_summary
from usb_recovery.output.transaction import cleanup_partials, write_transactional
from usb_recovery.output.vault import RecoveryVault


def _cand() -> Candidate:
    return Candidate(
        id="c1",
        name="HELLO.TXT",
        size=5,
        file_type="txt",
        mime="text/plain",
        method="metadata",
        status="deleted",
        source_offset=4096,
        confidence=70,
        sha256="abcd1234ffff",
    )


def test_transactional_and_cleanup(tmp_path: Path) -> None:
    dest = tmp_path / "out.bin"
    write_transactional(dest, b"payload")
    assert dest.read_bytes() == b"payload"
    leftover = tmp_path / "x.ur-partial"
    leftover.write_bytes(b"incomplete")
    removed = cleanup_partials(tmp_path)
    assert any(p.endswith(".ur-partial") for p in removed)
    assert not leftover.exists()


def test_vault_roundtrip(tmp_path: Path) -> None:
    vault = RecoveryVault(tmp_path / "vault", "passphrase-secret")
    stored = vault.store("secret.txt", b"classified", meta={"offset": 1})
    assert stored.suffix == ".urv"
    assert vault.unlock(stored) == b"classified"
    bad = RecoveryVault(tmp_path / "vault", "wrong")
    with pytest.raises(VaultError):
        bad.unlock(stored)


def test_sidecar_naming_dest(tmp_path: Path) -> None:
    dest = tmp_path / "HELLO.TXT"
    dest.write_text("hi")
    cand = _cand()
    result = RecoveryResult(cand.id, str(dest), "recovered", 2, "ab", size_match=True)
    side = write_sidecar(dest, candidate=cand, result=result)
    assert side.name.endswith(".recovery.json")
    assert "c1" in side.read_text()
    name = apply_template("{stem}-{offset}{suffix}", cand)
    assert name.startswith("HELLO-")
    assert name.endswith(".TXT") or name.endswith(".txt") or "HELLO" in name
    first = resolve_collision(tmp_path, "HELLO.TXT", strategy="hash", digest=cand.sha256)
    assert first.name != "HELLO.TXT"
    check = check_destination(tmp_path, needed_bytes=1)
    assert check["ok"] is True
    assert verify_destination(tmp_path)["ok"] is True


def test_summary_and_second_copy(tmp_path: Path) -> None:
    src_file = tmp_path / "a.txt"
    src_file.write_text("ok")
    results = [
        RecoveryResult("1", str(src_file), "recovered", 2, "aa"),
        RecoveryResult("2", None, "failed", 0, None, error="missing"),
    ]
    summary = recoverable_summary(results)
    assert summary["recovered"] == 1
    assert summary["unrecoverable"] == 1
    with pytest.raises(SafetyError):
        copy_verified_second(results, tmp_path / "copy2", source_path=str(src_file), confirm=False)
    copied = copy_verified_second(
        results, tmp_path / "copy2", source_path=str(src_file), confirm=True
    )
    assert copied
