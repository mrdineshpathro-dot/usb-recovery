"""Expected-result validator (303)."""

from __future__ import annotations

from pathlib import Path

from usb_recovery.util import sha256_file


def validate_expected(recovered_dir: Path, expected: list[dict]) -> dict:
    """expected items: {name, sha256?}"""
    missing: list[str] = []
    mismatch: list[str] = []
    ok: list[str] = []
    for item in expected:
        name = item["name"]
        matches = list(Path(recovered_dir).rglob(name))
        if not matches:
            missing.append(name)
            continue
        digest = item.get("sha256")
        if digest:
            actual = sha256_file(matches[0])
            if actual != digest:
                mismatch.append(name)
                continue
        ok.append(name)
    return {
        "ok": not missing and not mismatch,
        "found": ok,
        "missing": missing,
        "hash_mismatch": mismatch,
    }
