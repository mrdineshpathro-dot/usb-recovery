"""Fragmented JPEG reconstruction using markers and the structural validator (331)."""

from __future__ import annotations

from usb_recovery.carving.validators import validate_jpeg


def _markers(data: bytes) -> dict:
    return {
        "soi": data.find(b"\xff\xd8"),
        "sof": data.find(b"\xff\xc0"),
        "sos": data.find(b"\xff\xda"),
        "eoi": data.find(b"\xff\xd9"),
        "app0": data.find(b"\xff\xe0"),
    }


def reconstruct_jpeg_fragments(fragments: list[bytes]) -> dict:
    """Evaluate fragments and concatenations against JPEG marker rules."""
    pieces = []
    for i, frag in enumerate(fragments):
        marks = _markers(frag)
        pieces.append({"index": i, "size": len(frag), **marks})
    trials = []
    blobs: list[tuple[str, bytes]] = []
    for i, frag in enumerate(fragments):
        blobs.append((f"fragment-{i}", frag))
    if len(fragments) >= 2:
        blobs.append(("concat-order", b"".join(fragments)))
        # header-looking first, EOI-looking last
        heads = [f for f in fragments if f.startswith(b"\xff\xd8")]
        tails = [f for f in fragments if b"\xff\xd9" in f and not f.startswith(b"\xff\xd8")]
        if heads and tails:
            blobs.append(("soi+others+eoi", heads[0] + b"".join(f for f in fragments if f not in (heads[0], tails[0])) + tails[0]))
    best = None
    for name, blob in blobs:
        ok, notes = validate_jpeg(blob)
        trial = {"name": name, "ok": ok, "notes": notes, "size": len(blob), "markers": _markers(blob)}
        trials.append(trial)
        if ok and best is None:
            best = {**trial, "data": blob}
    return {
        "pieces": pieces,
        "trials": [{k: v for k, v in t.items() if k != "data"} for t in trials],
        "ok": best is not None,
        "best_name": None if best is None else best["name"],
        "best": None if best is None else bytes(best["data"]),
        "note": "A passing SOI/SOS/EOI walk is not a decoded photograph. Fragment order is a guess.",
    }
