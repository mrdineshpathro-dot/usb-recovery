from __future__ import annotations

from usb_recovery.advanced.dependencies import missing_sections
from usb_recovery.advanced.engine import fuse_methods, rank_multi_evidence, refine_candidates
from usb_recovery.advanced.evidence import explain_evidence
from usb_recovery.advanced.fragments import (
    boundary_confidence,
    compare_hypotheses,
    fragment_graph,
    reconstruct_with_constraints,
)
from usb_recovery.advanced.known import match_known_content
from usb_recovery.devices.image import ImageSource
from usb_recovery.models import Candidate
from usb_recovery.util import sha256_bytes
from tests.fixtures.builder import minimal_jpeg, minimal_png


def _c(**kwargs) -> Candidate:
    base = dict(
        id="1",
        name="a.jpg",
        size=100,
        file_type="jpeg",
        mime="image/jpeg",
        method="carved",
        status="carved",
        source_offset=0,
        confidence=40,
    )
    base.update(kwargs)
    return Candidate(**base)  # type: ignore[arg-type]


def test_multi_evidence_graph_constraints_refine():
    jpeg = minimal_jpeg()
    meta = _c(id="m", method="metadata", status="deleted", confidence=70, extra={"content": jpeg})
    carved = _c(id="c", method="carved", source_offset=0, extra={"content": jpeg}, sha256=sha256_bytes(jpeg))
    junk = _c(id="j", name="x.bin", file_type="jpeg", extra={"content": b"not-a-jpeg"}, confidence=20)
    ranked = rank_multi_evidence([junk, carved, meta])
    assert ranked[0].id in {"m", "c"}
    assert ranked[-1].id == "j"
    graph = fragment_graph([meta, carved, junk])
    assert graph["nodes"]
    fused = fuse_methods([meta, carved])
    assert fused["count"] >= 1
    refined = refine_candidates([carved, meta])
    assert any(c.extra.get("refined") or c.extra.get("multi_evidence_score") for c in refined)
    rec = reconstruct_with_constraints([jpeg[:20], jpeg[20:]], "jpeg")
    assert rec["trials"]
    hyp = compare_hypotheses([jpeg[:20], jpeg[20:]], "jpeg")
    assert hyp["hypotheses"]
    bound = boundary_confidence(jpeg, "jpeg", claimed_size=len(jpeg))
    assert bound["start_ok"] and bound["end_ok"]
    dep = missing_sections(jpeg[:12], "jpeg")
    assert "EOI (FFD9) — truncated image" in dep["missing"] or any("EOI" in m for m in dep["missing"])
    explained = explain_evidence([meta, carved, junk])
    assert explained["candidates"]


def test_known_content_and_png_boundary(tmp_path):
    png = minimal_png()
    path = tmp_path / "x.bin"
    path.write_bytes(b"xxxx" + png)
    cand = _c(id="p", name="a.png", file_type="png", extra={"content": png}, sha256=sha256_bytes(png))
    with ImageSource(str(path)) as src:
        hits = match_known_content(
            candidates=[cand],
            source=src,
            hashes=[sha256_bytes(png)],
            needles=[b"\x89PNG"],
        )
    assert hits["hashes"]
    assert hits["sequences"]
    assert boundary_confidence(png, "png")["start_ok"]
