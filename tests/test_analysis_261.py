from __future__ import annotations

from usb_recovery.analysis.alignment import analyze_alignment
from usb_recovery.analysis.bytemap import byte_range_map, render_byte_map
from usb_recovery.analysis.consistency import verify_read_consistency
from usb_recovery.analysis.diff import diff_candidates
from usb_recovery.analysis.raw import classify_raw
from usb_recovery.analysis.tempfiles import find_temp_candidates, is_temp_name
from usb_recovery.analysis.thumbnails import extract_jpeg_thumbnail
from usb_recovery.analysis.unicode_names import reconstruct_filename
from usb_recovery.analysis.video_frag import analyze_video_buffer
from usb_recovery.analysis.wal import inspect_sqlite_journal
from usb_recovery.devices.image import ImageSource
from usb_recovery.models import Candidate
from tests.fixtures.builder import minimal_jpeg


def test_alignment_and_consistency(mbr_image: dict) -> None:
    src = ImageSource(str(mbr_image["path"]))
    with src:
        align = analyze_alignment(src)
        assert align["scheme"] == "mbr"
        check = verify_read_consistency(src, 0, 512, passes=2)
        assert check["consistent"] is True


def test_unicode_temp_raw_wal() -> None:
    rec = reconstruct_filename("Cafe\u0301.txt")
    assert rec["preferred"]
    assert is_temp_name("~$report.docx")
    assert is_temp_name("Thumbs.db")
    assert not is_temp_name("HELLO.TXT")
    assert classify_raw(b"II*\x00xxxxCR\x02\x00") == "cr2"
    assert inspect_sqlite_journal(b"Wal\x00" + b"\x00" * 16)["kind"] == "wal"
    vid = analyze_video_buffer(b"\x00\x00\x00\x18ftypisom" + b"mdat" + b"\x00" * 20)
    assert vid["ftyp"] is True
    assert vid["mdat"] is True


def test_thumbnail_and_bytemap() -> None:
    jpeg = minimal_jpeg()
    planted = b"xxxx" + jpeg
    thumb = extract_jpeg_thumbnail(planted)
    assert thumb and thumb.startswith(b"\xff\xd8")
    cand = Candidate(
        id="1",
        name="a.jpg",
        size=100,
        file_type="jpeg",
        mime="image/jpeg",
        method="carved",
        status="partial",
        source_offset=4096,
        confidence=40,
        extra={"content": b"x" * 40},
    )
    mapped = byte_range_map(cand)
    assert mapped["ranges"]
    assert "#" in render_byte_map(cand) or "." in render_byte_map(cand)
    other = Candidate(**{**cand.__dict__, "id": "2", "method": "metadata", "name": "A.JPG"})
    diff = diff_candidates(cand, other)
    assert "method" in diff["changes"]
    temps = find_temp_candidates(
        [
            cand,
            Candidate(
                id="t",
                name="~$x.docx",
                size=1,
                file_type="docx",
                mime="x",
                method="carved",
                status="carved",
                source_offset=0,
                confidence=10,
            ),
        ]
    )
    assert temps
