"""Differential recovery testing and golden-dataset regression (355, 356)."""

from __future__ import annotations

from pathlib import Path

from usb_recovery.devtools.corpus import Corpus
from usb_recovery.devtools.validator import validate_expected
from usb_recovery.models import Candidate


def differential_results(a: list[Candidate], b: list[Candidate]) -> dict:
    """Compare two result sets (versions or methods) without claiming a winner."""
    by_a = {(c.source_offset, c.name, c.method): c for c in a}
    by_b = {(c.source_offset, c.name, c.method): c for c in b}
    keys_a, keys_b = set(by_a), set(by_b)
    only_a = [by_a[k].id for k in sorted(keys_a - keys_b)]
    only_b = [by_b[k].id for k in sorted(keys_b - keys_a)]
    changed = []
    for key in keys_a & keys_b:
        ca, cb = by_a[key], by_b[key]
        if ca.size != cb.size or ca.status != cb.status or ca.sha256 != cb.sha256:
            changed.append({"a": ca.id, "b": cb.id, "size": (ca.size, cb.size), "status": (ca.status, cb.status)})
    return {
        "only_a": only_a,
        "only_b": only_b,
        "changed": changed,
        "same": len(keys_a & keys_b) - len(changed),
        "note": "A difference is not automatically a regression or an improvement.",
    }


def golden_regression(corpus_root: str | Path, recovered_root: str | Path | None = None) -> dict:
    """Run expected-result checks against a controlled corpus (356)."""
    corpus = Corpus(Path(corpus_root))
    reports = []
    all_ok = True
    recovered = Path(recovered_root) if recovered_root else None
    for item in corpus.items():
        expected = item.get("expected") or {}
        names = expected.get("names") or []
        checks = [{"name": n} for n in names if n]
        if recovered and recovered.is_dir() and checks:
            result = validate_expected(recovered, checks)
        else:
            result = {"ok": True, "skipped": True, "item": item.get("label")}
        reports.append({"label": item.get("label"), "result": result})
        if result.get("ok") is False:
            all_ok = False
    return {
        "ok": all_ok,
        "items": reports,
        "count": len(reports),
        "note": "Golden cases are synthetic. Passing them does not guarantee recovery of a real device.",
    }
