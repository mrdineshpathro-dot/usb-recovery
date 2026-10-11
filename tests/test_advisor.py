from __future__ import annotations

from usb_recovery.advisor.assistant import advise, compare_methods, decision_tree
from usb_recovery.advisor.assessment import assess_source, estimate_effort
from usb_recovery.advisor.explain import diagnose_error, explain_limitations, explain_score, summarize_failures
from usb_recovery.models import Candidate, DeviceInfo, DeviceWarning, RecoveryResult


def test_decision_tree_deleted() -> None:
    advice = decision_tree("deleted")
    assert advice.profile == "quick"
    assert "metadata" in advice.methods
    assert advice.steps


def test_advise_ntfs_and_mounted() -> None:
    dev = DeviceInfo(
        path="/dev/sdb",
        display_name="stick",
        size_bytes=8,
        sector_size=512,
        mountpoints=["/media/usb"],
        warnings=[DeviceWarning("mounted", "mounted", "danger")],
        is_physical=True,
    )
    advice = advise(symptom="formatted", filesystem="ntfs", device=dev)
    assert any("mounted" in w.lower() or "Unmount" in w or "mounted" in w for w in advice.warnings)
    assert any("LogFile" in s or "MFT" in s for s in advice.steps + advice.limitations)


def test_limitations_and_errors() -> None:
    items = explain_limitations("trimmed")
    assert items and "TRIM" in items[0]["summary"]
    diag = diagnose_error("Permission denied errno 13")
    assert diag["matched"] is True
    unknown = diagnose_error("weird-xyz")
    assert unknown["matched"] is False


def test_failure_summary_and_score() -> None:
    results = [
        RecoveryResult("a", "/t/a", "recovered", 1, "aa"),
        RecoveryResult("b", None, "failed", 0, None, error="disk full"),
        RecoveryResult("c", "/t/c", "partial", 2, "cc"),
    ]
    summary = summarize_failures(results)
    assert summary["failed"] == 1
    assert summary["partial"] == 1
    cand = Candidate(
        id="1",
        name="x.jpg",
        size=10,
        file_type="jpeg",
        mime="image/jpeg",
        method="carved",
        status="carved",
        source_offset=0,
        confidence=40,
        confidence_reasons=["header match"],
    )
    explained = explain_score(cand)
    assert explained["not_a_probability"] is True
    assert explained["band"]


def test_compare_methods() -> None:
    assert {m["id"] for m in compare_methods()} >= {"metadata", "carving", "imaging"}


def test_assess_image(fat_image: dict) -> None:
    assessment = assess_source(str(fat_image["path"]))
    assert assessment.accessible
    assert assessment.is_image
    assert "fat16" in assessment.filesystems or assessment.filesystems
    estimate_effort(assessment, bytes_per_sec=10_000_000)
    assert assessment.estimated_scan_s is not None
    assert assessment.estimated_dest_bytes
