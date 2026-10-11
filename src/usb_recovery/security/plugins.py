"""HMAC / SHA-256 allow-list verification for third-party plugins (259)."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

from usb_recovery.exceptions import PluginVerificationError


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def verify_plugin(
    plugin: str | Path,
    *,
    trust_store: str | Path | None = None,
    hmac_key: bytes | None = None,
) -> dict:
    path = Path(plugin)
    if not path.is_file():
        raise PluginVerificationError(f"Plugin not found: {path}")
    digest = sha256_file(path)
    sig_path = path.with_suffix(path.suffix + ".sig")
    store_hit = False
    if trust_store and Path(trust_store).is_file():
        store = json.loads(Path(trust_store).read_text(encoding="utf-8"))
        allowed = store.get("plugins") or {}
        entry = allowed.get(path.name) or allowed.get(path.stem)
        if not entry:
            raise PluginVerificationError(f"{path.name} is not in the trust store")
        expected = (entry.get("sha256") or "").lower()
        if expected != digest:
            raise PluginVerificationError(f"SHA-256 mismatch for {path.name}")
        if entry.get("allowed") is False:
            raise PluginVerificationError(f"{path.name} is revoked in the trust store")
        store_hit = True
    if hmac_key:
        if not sig_path.is_file():
            raise PluginVerificationError(f"Missing HMAC signature {sig_path.name}")
        expect = sig_path.read_text(encoding="utf-8").strip().lower()
        actual = hmac.new(hmac_key, path.read_bytes(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expect, actual):
            raise PluginVerificationError("HMAC signature mismatch")
        store_hit = True
    if not store_hit:
        raise PluginVerificationError(
            "No trust store or HMAC key provided; refusing to load an unsigned plugin"
        )
    return {"path": str(path), "sha256": digest, "verified": True}
