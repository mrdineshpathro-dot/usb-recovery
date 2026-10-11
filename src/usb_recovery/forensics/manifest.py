"""Signed evidence manifest and source-to-output provenance (351, 352)."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Iterable

from usb_recovery.models import Candidate, RecoveryResult
from usb_recovery.util import isoformat, sha256_file


def sign_manifest(
    payload: dict,
    dest: str | Path,
    *,
    key: bytes | None = None,
) -> Path:
    """Write a JSON manifest. HMAC-SHA256 if a key is given; else a SHA-256 checksum."""
    body = dict(payload)
    body.setdefault("created_at", isoformat())
    body["signed"] = bool(key)
    if key:
        body.setdefault("note", "HMAC-SHA256 of the manifest body. Not a public-key identity.")
    else:
        body.setdefault(
            "note",
            "SHA-256 checksum of the manifest body. Provide --key for HMAC-SHA256. "
            "This is not a public-key signature.",
        )
    canonical = json.dumps(body, sort_keys=True, default=str).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    body["sha256"] = digest
    if key:
        body["hmac_sha256"] = hmac.new(key, canonical, hashlib.sha256).hexdigest()
    path = Path(dest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, indent=2, default=str), encoding="utf-8")
    return path


def verify_manifest(path: str | Path, *, key: bytes | None = None) -> dict:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    stored = raw.get("sha256")
    hmac_stored = raw.get("hmac_sha256")
    body = {k: v for k, v in raw.items() if k not in {"sha256", "hmac_sha256"}}
    canonical = json.dumps(body, sort_keys=True, default=str).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    ok = stored == digest
    hmac_ok = None
    if key and hmac_stored:
        actual = hmac.new(key, canonical, hashlib.sha256).hexdigest()
        hmac_ok = hmac.compare_digest(actual, hmac_stored)
        ok = ok and hmac_ok
    return {"ok": ok, "sha256_match": stored == digest, "hmac_match": hmac_ok, "signed": bool(raw.get("signed"))}


def provenance_chain(
    *,
    source_path: str,
    candidates: Iterable[Candidate],
    results: Iterable[RecoveryResult] | None = None,
    operations: list[dict] | None = None,
) -> dict:
    """Trace source ranges → operations → output files (352)."""
    links = []
    by_id = {r.candidate_id: r for r in (results or [])}
    for item in candidates:
        rec = by_id.get(item.id)
        links.append(
            {
                "candidate_id": item.id,
                "name": item.name,
                "source": source_path,
                "source_offset": item.source_offset,
                "source_size": item.size,
                "method": item.method,
                "output": rec.dest_path if rec else None,
                "output_sha256": rec.sha256 if rec else item.sha256,
                "status": rec.status if rec else item.status,
            }
        )
    return {
        "source": source_path,
        "operations": operations or [],
        "links": links,
        "note": "Provenance records what this tool did. It is not a chain of custody by itself.",
    }
