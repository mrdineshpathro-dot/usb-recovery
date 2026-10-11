from __future__ import annotations

from usb_recovery.models import Candidate, TimestampSet
from usb_recovery.reconstruct.archive import salvage_zip, scan_embedded
from usb_recovery.reconstruct.documents import validate_document
from usb_recovery.reconstruct.matching import match_candidates
from usb_recovery.reconstruct.photos import group_photos
from usb_recovery.reconstruct.preview import preview_partial
from usb_recovery.reconstruct.regions import fragment_groups, regions_for
from usb_recovery.reconstruct.timeline import candidate_timeline
from usb_recovery.reconstruct.video import repair_mp4_copy
from tests.fixtures.builder import minimal_pdf, minimal_zip


def _cand(**kwargs) -> Candidate:
    base = dict(
        id="n",
        name="f.bin",
        size=10,
        file_type="bin",
        mime="application/octet-stream",
        method="carved",
        status="carved",
        source_offset=0,
        confidence=50,
    )
    base.update(kwargs)
    return Candidate(**base)  # type: ignore[arg-type]


def test_match_by_hash_and_overlap() -> None:
    a = _cand(id="a", name="A.JPG", method="metadata", sha256="abc", source_offset=100, size=50)
    b = _cand(id="b", name="carved.jpg", method="carved", sha256="abc", source_offset=100, size=50)
    groups = match_candidates([a, b])
    assert any(g["kind"] == "identical-hash" for g in groups)


def test_regions_and_fragments() -> None:
    c = _cand(size=100, extra={"content": b"x" * 40}, status="partial")
    regs = regions_for(c)
    assert regs[0].kind == "recovered"
    assert any(r.kind == "missing" for r in regs)
    frags = fragment_groups(
        [
            _cand(id="1", file_type="jpeg", source_offset=0, size=10),
            _cand(id="2", file_type="jpeg", source_offset=20, size=10),
        ]
    )
    assert frags and frags[0]["count"] == 2


def test_photos_timeline_preview() -> None:
    p1 = _cand(
        id="p1",
        name="a.jpg",
        file_type="jpeg",
        mime="image/jpeg",
        method="metadata",
        timestamps=TimestampSet(modified="2026-01-01T12:00:00Z"),
    )
    p2 = _cand(
        id="p2",
        name="b.jpg",
        file_type="jpeg",
        mime="image/jpeg",
        method="metadata",
        timestamps=TimestampSet(modified="2026-01-01T12:00:30Z"),
    )
    groups = group_photos([p1, p2])
    assert groups
    tl = candidate_timeline([p1, p2])
    assert tl[0]["trustworthy"] is True
    prev = preview_partial(_cand(extra={"content": b"hello"}, mime="text/plain", file_type="txt"))
    assert prev["executed"] is False
    assert "hello" in prev["text"]


def test_zip_salvage_embedded_and_pdf() -> None:
    z = minimal_zip("readme.txt", b"hello")
    salvaged = salvage_zip(z)
    assert salvaged["salvageable"]
    assert any(e["name"] == "readme.txt" for e in salvaged["entries"])
    pdf = minimal_pdf()
    wrapped = b"XXXX" + pdf
    hits = scan_embedded(wrapped)
    assert any(h["signature_id"] == "pdf" for h in hits)
    doc = validate_document(pdf, "pdf")
    assert doc["ok"] is True
    assert doc["detected"] == "pdf"
    ooxml = minimal_zip("[Content_Types].xml", b"<?xml") + b"word/document.xml"
    # still a zip
    v = validate_document(minimal_zip(), "zip")
    assert v["detected"] in {"zip", "docx", "xlsx", "pptx"}


def test_video_repair_refuses_to_invent_moov(tmp_path) -> None:
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 32)
    result = repair_mp4_copy(path)
    assert result["changed"] is False
    assert result["ok"] is False
    assert "moov" in result["reason"]
