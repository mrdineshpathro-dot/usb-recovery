"""Specialized recovery for difficult files (features 331–340)."""

from usb_recovery.special.archive import salvage_archive_members
from usb_recovery.special.jpeg import reconstruct_jpeg_fragments
from usb_recovery.special.media import analyze_audio_frames, analyze_codec_stream
from usb_recovery.special.mp4 import analyze_mp4_index
from usb_recovery.special.office import validate_ooxml_relationships
from usb_recovery.special.pdf import recover_pdf_xref
from usb_recovery.special.raw import analyze_raw_fragments
from usb_recovery.special.sqlite import analyze_sqlite_journal_copy
from usb_recovery.special.zip import reconstruct_zip_directory

__all__ = [
    "analyze_audio_frames",
    "analyze_codec_stream",
    "analyze_mp4_index",
    "analyze_raw_fragments",
    "analyze_sqlite_journal_copy",
    "reconstruct_jpeg_fragments",
    "reconstruct_zip_directory",
    "recover_pdf_xref",
    "salvage_archive_members",
    "validate_ooxml_relationships",
]
