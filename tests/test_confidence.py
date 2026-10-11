from __future__ import annotations

from usb_recovery.models import Candidate
from usb_recovery.recovery.confidence import annotate, band_for, deduplicate


def test_bands() -> None:
    assert band_for(90)[0] == "high"
    assert band_for(20)[0] == "uncertain"


def test_annotate_and_dedup() -> None:
    a = Candidate(
        id="1",
        name="a",
        size=1,
        file_type="bin",
        mime="x",
        method="carved",
        status="carved",
        source_offset=0,
        confidence=50,
        sha256="deadbeef",
    )
    b = Candidate(
        id="2",
        name="b",
        size=1,
        file_type="bin",
        mime="x",
        method="carved",
        status="carved",
        source_offset=10,
        confidence=50,
        sha256="deadbeef",
    )
    annotate(a)
    assert any("not a probability" in r for r in a.confidence_reasons)
    deduplicate([a, b])
    assert b.is_duplicate
    assert not a.is_duplicate
