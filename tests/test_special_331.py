from __future__ import annotations

import io
import struct
import zipfile

from usb_recovery.special.archive import salvage_archive_members
from usb_recovery.special.jpeg import reconstruct_jpeg_fragments
from usb_recovery.special.media import analyze_audio_frames, analyze_codec_stream
from usb_recovery.special.mp4 import analyze_mp4_index
from usb_recovery.special.office import validate_ooxml_relationships
from usb_recovery.special.pdf import recover_pdf_xref
from usb_recovery.special.raw import analyze_raw_fragments
from usb_recovery.special.sqlite import analyze_sqlite_journal_copy
from usb_recovery.special.zip import reconstruct_zip_directory
from tests.fixtures.builder import minimal_jpeg, minimal_pdf, minimal_zip


def test_jpeg_mp4_zip_pdf_office():
    jpeg = minimal_jpeg()
    rec = reconstruct_jpeg_fragments([jpeg[:25], jpeg[25:]])
    assert rec["ok"] is True
    ftyp = struct.pack(">I", 16) + b"ftyp" + b"isom" + struct.pack(">I", 0)
    moov = struct.pack(">I", 8) + b"moov"
    mdat = struct.pack(">I", 16) + b"mdat" + b"\x00" * 8
    mp4 = analyze_mp4_index(ftyp + moov + mdat)
    assert mp4["ftyp"] and mp4["moov"] and mp4["mdat"]
    z = minimal_zip()
    # drop central directory + EOCD
    cut = z.find(b"PK\x01\x02")
    rebuilt = reconstruct_zip_directory(z[:cut])
    assert rebuilt["repaired"] is True
    assert b"PK\x05\x06" in rebuilt["copy"]
    pdf = recover_pdf_xref(minimal_pdf())
    assert pdf["objects"] >= 1
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("_rels/.rels", '<Relationships><Relationship Target="word/document.xml"/></Relationships>')
        zf.writestr("word/document.xml", "<w:document/>")
    office = validate_ooxml_relationships(buf.getvalue())
    assert office["kind"] == "docx"
    assert office["ok"] is True
    members = salvage_archive_members(z)
    assert members["kind"] == "zip"
    assert members["count"] >= 1


def test_sqlite_codec_audio_raw():
    wal = b"Wal\x00" + struct.pack(">II", 3007000, 4096) + b"\x00" * 20
    frame = struct.pack(">I", 3) + struct.pack(">I", 1) + b"\x00" * 16 + b"P" * 4096
    info = analyze_sqlite_journal_copy(wal[:32] + frame)
    assert info["kind"] == "wal"
    assert info["applied"] is False
    nals = b"\x00\x00\x00\x01\x67" + b"\x00" * 8 + b"\x00\x00\x00\x01\x65" + b"\x00" * 8
    codec = analyze_codec_stream(nals)
    assert codec["has_sps"] is True
    assert codec["has_idr"] is True
    mp3 = b"\xff\xfb" + b"\x00" * 200
    audio = analyze_audio_frames(mp3)
    assert audio["kind"] == "mp3"
    raw = b"II*\x00" + struct.pack("<I", 8) + struct.pack("<H", 1)
    raw += struct.pack("<HHII", 0x0111, 3, 1, 0)  # StripOffsets
    raw += b"CR\x02\x00"
    # classify_raw wants CR2 at offset 8; keep a dedicated CR2 buffer too
    cr2 = b"II*\x00xxxxCR\x02\x00" + raw
    info = analyze_raw_fragments(cr2)
    assert info["kind"] in {"cr2", "tiff-raw"}
