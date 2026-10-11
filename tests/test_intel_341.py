from __future__ import annotations

from usb_recovery.intel.anomalies import detect_scan_anomalies
from usb_recovery.intel.classify import classify_candidate
from usb_recovery.intel.filter import filter_false_positives
from usb_recovery.intel.group import group_correlated
from usb_recovery.intel.plan import adaptive_plan, algorithm_profile, estimate_cost
from usb_recovery.intel.reports import strategy_report, uncertainty_report
from usb_recovery.intel.scorecard import quality_scorecard
from usb_recovery.models import Candidate
from usb_recovery.util import sha256_file
from tests.fixtures.builder import minimal_jpeg


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


def test_classifier_plan_cost_anomalies():
    jpeg = minimal_jpeg()
    labelled = classify_candidate(jpeg, "photo.jpg")
    assert labelled["label"] == "jpeg"
    text = classify_candidate(b"hello world\n" * 20, "notes.txt")
    assert text["label"] == "text"
    plan = adaptive_plan(goal="photos", filesystem="fat32", size_bytes=8_000_000)
    assert plan["enable_carving"] is True
    assert plan["signatures"] and "jpeg" in plan["signatures"]
    cost = estimate_cost(8_000_000, "standard")
    assert cost["estimated_scan_s"] > 0
    algo = algorithm_profile("fat32", "photos")
    assert "fat-directory" in algo["methods"]
    report = strategy_report(goal="photos", filesystem="ntfs", size_bytes=1000)
    assert report["why"]
    cands = [
        _c(id=str(i), name=f"{i}.jpg", source_offset=0, confidence=10, method="carved")
        for i in range(12)
    ]
    anomalies = detect_scan_anomalies(cands, read_errors=3, source_size=10_000_000)
    assert anomalies["anomalous"] is True


def test_filter_group_uncertainty_scorecard(tmp_path):
    jpeg = minimal_jpeg()
    good = _c(id="g", extra={"content": jpeg}, confidence=45, method="carved")
    bad = _c(id="b", extra={"content": b"nope"}, confidence=20, method="carved", name="b.jpg")
    filtered = filter_false_positives([good, bad], drop=True)
    ids = [c.id for c in filtered["kept"]]
    assert "g" in ids
    assert "b" not in ids
    groups = group_correlated(
        [
            _c(id="a", source_offset=0, size=50, sha256="aa"),
            _c(id="b", name="b.jpg", method="metadata", source_offset=10, size=50, sha256="aa"),
        ]
    )
    assert groups
    unc = uncertainty_report([_c(status="partial", confidence=20, method="carved")])
    assert unc["items"][0]["missing"]
    recovered = tmp_path / "out"
    recovered.mkdir()
    dest = recovered / "hello.bin"
    dest.write_bytes(b"hi")
    card = quality_scorecard(recovered, [{"name": "hello.bin", "sha256": sha256_file(dest)}])
    assert card["ok"] is True
    assert card["by_type"]["bin"]["found"] == 1
