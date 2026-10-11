"""Local feature-based candidate classifier (341).

No neural network is shipped. An optional JSON weight file can be supplied;
otherwise a built-in linear model over measurable features is used.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from usb_recovery.models import Candidate

DEFAULT_WEIGHTS: dict[str, dict[str, float]] = {
    "jpeg": {"bias": -0.2, "magic_jpeg": 3.5, "entropy": 0.4, "printable": -1.0},
    "png": {"bias": -0.2, "magic_png": 3.5, "entropy": 0.3, "printable": -0.8},
    "pdf": {"bias": -0.2, "magic_pdf": 3.5, "printable": 0.4},
    "zip": {"bias": -0.2, "magic_zip": 3.5, "entropy": 0.5},
    "text": {"bias": 0.1, "printable": 2.5, "entropy": -1.2, "magic_jpeg": -1.0, "magic_png": -1.0},
    "unknown": {"bias": 0.4},
}


def _entropy(data: bytes) -> float:
    if not data:
        return 0.0
    freq = [0] * 256
    for b in data[:8192]:
        freq[b] += 1
    n = min(len(data), 8192)
    ent = 0.0
    for c in freq:
        if c:
            p = c / n
            ent -= p * math.log2(p)
    return ent / 8.0  # 0..1


def extract_features(data: bytes, name: str = "") -> dict[str, float]:
    sample = data[:8192]
    printable = sum(1 for b in sample if 32 <= b < 127 or b in (9, 10, 13)) / max(len(sample), 1)
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return {
        "entropy": _entropy(sample),
        "printable": printable,
        "size_log": math.log2(max(len(data), 1)),
        "magic_jpeg": 1.0 if data.startswith(b"\xff\xd8") else 0.0,
        "magic_png": 1.0 if data.startswith(b"\x89PNG") else 0.0,
        "magic_pdf": 1.0 if data.startswith(b"%PDF-") else 0.0,
        "magic_zip": 1.0 if data.startswith(b"PK") else 0.0,
        "ext_known": 1.0 if ext in {"jpg", "jpeg", "png", "pdf", "zip", "docx", "txt"} else 0.0,
    }


def _load_weights(model_path: str | Path | None) -> dict[str, dict[str, float]]:
    if model_path and Path(model_path).is_file():
        raw = json.loads(Path(model_path).read_text(encoding="utf-8"))
        weights = raw.get("weights") or raw
        if isinstance(weights, dict):
            return {k: {kk: float(vv) for kk, vv in v.items()} for k, v in weights.items() if isinstance(v, dict)}
    return DEFAULT_WEIGHTS


def classify_candidate(
    data: bytes,
    name: str = "",
    *,
    model_path: str | Path | None = None,
) -> dict:
    features = extract_features(data, name)
    weights = _load_weights(model_path)
    scores: dict[str, float] = {}
    for label, w in weights.items():
        s = w.get("bias", 0.0)
        for key, value in features.items():
            s += w.get(key, 0.0) * value
        scores[label] = s
    # Stable softmax-ish ranking without overflowing.
    m = max(scores.values()) if scores else 0.0
    exp = {k: math.exp(v - m) for k, v in scores.items()}
    z = sum(exp.values()) or 1.0
    probs = {k: exp[k] / z for k in exp}
    label = max(probs, key=probs.get) if probs else "unknown"
    return {
        "label": label,
        "scores": {k: round(v, 4) for k, v in probs.items()},
        "features": {k: round(v, 4) for k, v in features.items()},
        "model": "local-linear",
        "note": (
            "Optional local linear model over measurable features. "
            "No neural network is shipped; recovery is not inferred from the label."
        ),
    }


def classify_session_candidate(candidate: Candidate, *, model_path: str | Path | None = None) -> dict:
    content = candidate.extra.get("content")
    data = bytes(content) if isinstance(content, (bytes, bytearray)) else b""
    result = classify_candidate(data, candidate.name, model_path=model_path)
    result["id"] = candidate.id
    return result
