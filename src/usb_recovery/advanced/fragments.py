"""Fragment graph, constraints, boundaries, and reconstruction hypotheses (312, 313, 316, 317)."""

from __future__ import annotations

from usb_recovery.carving.validators import run_validator
from usb_recovery.models import Candidate


def fragment_graph(candidates: list[Candidate], proximity: int = 1_048_576) -> dict:
    """Map possible relationships between fragments (312). Heuristic only."""
    nodes = [
        {
            "id": c.id,
            "offset": c.source_offset,
            "size": c.size,
            "type": c.file_type,
            "method": c.method,
        }
        for c in candidates
    ]
    edges: list[dict] = []
    ordered = sorted(candidates, key=lambda c: c.source_offset)
    for i, a in enumerate(ordered):
        a_end = a.source_offset + max(a.size, 1)
        for b in ordered[i + 1 :]:
            gap = b.source_offset - a_end
            if gap > proximity:
                break
            kinds: list[str] = []
            if a.file_type and a.file_type == b.file_type:
                kinds.append("same-type")
            if gap == 0:
                kinds.append("adjacent")
            elif gap < 0:
                kinds.append("overlap")
            elif gap <= proximity:
                kinds.append("nearby")
            if a.sha256 and a.sha256 == b.sha256:
                kinds.append("identical-hash")
            if not kinds:
                continue
            edges.append(
                {
                    "a": a.id,
                    "b": b.id,
                    "gap": gap,
                    "kinds": kinds,
                }
            )
    return {
        "nodes": nodes,
        "edges": edges,
        "note": "Edges are possible relationships, not proof that fragments belong to one file.",
    }


def reconstruct_with_constraints(fragments: list[bytes], file_type: str) -> dict:
    """Try concatenations that satisfy format-specific validators (313)."""
    trials: list[dict] = []
    if not fragments:
        return {"ok": False, "trials": [], "best": None}
    sequences = [("single-0", fragments[0])]
    if len(fragments) >= 2:
        sequences.append(("concat", b"".join(fragments)))
        sequences.append(("concat-swap-first-two", fragments[1] + fragments[0] + b"".join(fragments[2:])))
    best = None
    for name, blob in sequences:
        ok, notes = run_validator(file_type, blob)
        trial = {"name": name, "ok": ok, "notes": notes, "size": len(blob)}
        trials.append(trial)
        if ok and best is None:
            best = trial
    return {
        "ok": best is not None,
        "trials": trials,
        "best": best,
        "file_type": file_type,
        "note": "Constraint checks never write; a passing validator is not a guarantee of a complete file.",
    }


def boundary_confidence(data: bytes, file_type: str, claimed_size: int | None = None) -> dict:
    """Estimate start/end confidence from magic, footer, and trailing padding (316)."""
    kind = (file_type or "").lower()
    start_ok = False
    end_ok = False
    reasons: list[str] = []
    if kind == "jpeg":
        start_ok = data.startswith(b"\xff\xd8")
        end_ok = data.rstrip(b"\x00").endswith(b"\xff\xd9")
        reasons.append("JPEG SOI/EOI")
    elif kind == "png":
        start_ok = data.startswith(b"\x89PNG\r\n\x1a\n")
        end_ok = b"IEND" in data[-16:]
        reasons.append("PNG signature/IEND")
    elif kind == "pdf":
        start_ok = data.startswith(b"%PDF-")
        end_ok = b"%%EOF" in data[-2048:]
        reasons.append("PDF header/%%EOF")
    elif kind in {"zip", "docx", "xlsx", "pptx"}:
        start_ok = data.startswith(b"PK\x03\x04") or data.startswith(b"PK\x05\x06")
        end_ok = data.rfind(b"PK\x05\x06") >= 0
        reasons.append("ZIP local header/EOCD")
    elif kind == "mp4":
        start_ok = len(data) >= 8 and data[4:8] == b"ftyp"
        end_ok = b"mdat" in data
        reasons.append("MP4 ftyp/mdat")
    else:
        start_ok = bool(data)
        end_ok = False
        reasons.append("no format-specific footer known")
    pad = 0
    if data:
        i = len(data)
        while i > 0 and data[i - 1] == 0:
            i -= 1
        pad = len(data) - i
    size_ok = claimed_size is None or abs(len(data) - claimed_size) <= 16
    score = 20
    if start_ok:
        score += 40
    if end_ok:
        score += 30
    if size_ok:
        score += 10
    if pad > 64:
        score -= 5
        reasons.append(f"{pad} trailing zero bytes")
    return {
        "start_ok": start_ok,
        "end_ok": end_ok,
        "size_ok": size_ok,
        "padding": pad,
        "score": max(0, min(100, score)),
        "reasons": reasons,
        "note": "Boundary scores are heuristic. Missing footers often mean a truncated candidate.",
    }


def compare_hypotheses(fragments: list[bytes], file_type: str) -> dict:
    """Generate alternative reconstructions and score them with validators (317)."""
    result = reconstruct_with_constraints(fragments, file_type)
    ranked = sorted(result["trials"], key=lambda t: (t["ok"] is True, t["ok"] is not False), reverse=True)
    return {
        "hypotheses": ranked,
        "preferred": ranked[0] if ranked else None,
        "note": "Alternative layouts are compared; none is asserted as the original file.",
        "file_type": file_type,
    }
