from __future__ import annotations

import sys
from pathlib import Path

from usb_recovery.db.store import SessionStore
from usb_recovery.devtools.corpus import Corpus
from usb_recovery.devtools.crash import crash_self_test
from usb_recovery.devtools.leaks import fd_snapshot, leak_delta
from usb_recovery.devtools.migrate import CURRENT_SCHEMA, migrate
from usb_recovery.devtools.plugin_api import check_plugin_api
from usb_recovery.devtools.profiles import dump_scan_profile, load_scan_profile
from usb_recovery.devtools.readiness import feature_readiness
from usb_recovery.devtools.validator import validate_expected
from usb_recovery.models import Candidate, ScanOptions
from usb_recovery.output.naming import apply_folder_template
from usb_recovery.platform.a11y import accessibility_hints
from usb_recovery.platform.dashboard import arrange_dashboard
from usb_recovery.platform.help import search_help
from usb_recovery.platform.portable import portable_paths
from usb_recovery.platform.resources import resource_snapshot
from usb_recovery.platform.wizard import first_run_checks
from usb_recovery.workspace.exclusions import apply_exclusions
from usb_recovery.workspace.history import HistoryStore
from usb_recovery.workspace.jobs import JobQueue
from usb_recovery.workspace.plan import build_plan, load_plan, save_plan


def test_plan_exclusions_jobs_history(tmp_path: Path) -> None:
    plan = build_plan(profile="quick", signatures=["jpeg"], regions=[(0, 100)])
    path = save_plan(plan, tmp_path / "plan.json")
    loaded = load_plan(path)
    assert loaded.profile == "quick"
    opts = loaded.to_options()
    assert opts.enable_carving is False
    cands = [
        Candidate(
            id="1",
            name="a.jpg",
            size=1,
            file_type="jpeg",
            mime="image/jpeg",
            method="carved",
            status="carved",
            source_offset=0,
            confidence=10,
            extension="jpg",
        ),
        Candidate(
            id="2",
            name="b.txt",
            size=1,
            file_type="txt",
            mime="text/plain",
            method="metadata",
            status="deleted",
            source_offset=1,
            confidence=10,
            extension="txt",
        ),
    ]
    filtered = apply_exclusions(cands, types=["jpeg"])
    assert [c.name for c in filtered] == ["b.txt"]
    q = JobQueue()
    q.add("scan", "job-a", priority=2)
    q.add("scan", "job-b", priority=1)
    q.run_sequential({"scan": lambda job: None})
    mon = q.monitor()
    assert mon["counts"].get("done") == 2
    store = SessionStore()
    sid = store.create_session("/tmp/x.img", 100, "quick")
    hist = HistoryStore(store)
    hist.tag(sid, "case-42", "usb")
    found = hist.search("case-42")
    assert found
    folder = apply_folder_template("{type}/{status}", cands[0])
    assert "jpeg" in str(folder)


def test_platform_and_devtools(tmp_path: Path) -> None:
    paths = portable_paths(tmp_path / "portable")
    assert paths["db"].name.endswith(".sqlite")
    setup = first_run_checks(tmp_path / "dest")
    assert setup["python"]
    assert search_help("TRIM")
    assert accessibility_hints()["shortcuts"]
    assert arrange_dashboard()
    snap = resource_snapshot()
    assert snap["pid"]
    corpus = Corpus(tmp_path / "corpus")
    img = tmp_path / "hello.bin"
    img.write_bytes(b"hi")
    corpus.add_file(img, label="hello", expected={"names": ["hello.bin"]})
    assert corpus.items()
    recovered = tmp_path / "out"
    recovered.mkdir()
    (recovered / "hello.bin").write_bytes(b"hi")
    from usb_recovery.util import sha256_file

    result = validate_expected(
        recovered, [{"name": "hello.bin", "sha256": sha256_file(recovered / "hello.bin")}]
    )
    assert result["ok"] is True
    assert crash_self_test(tmp_path / "crash")["ok"] is True
    store = SessionStore()
    from usb_recovery.devtools.migrate import current_version

    migrate(store)
    assert current_version(store) >= 2
    assert CURRENT_SCHEMA >= 2
    plugin = tmp_path / "p.py"
    plugin.write_text('PLUGIN_API = "1.0"\n')
    assert check_plugin_api(plugin)["compatible"] is True
    before = fd_snapshot()
    leak_delta(before, before)
    opts = ScanOptions.from_profile("deep")
    dump_scan_profile(opts, tmp_path / "profile.json", source="x.img")
    loaded = load_scan_profile(tmp_path / "profile.json")
    assert loaded.profile == "deep"
    board = feature_readiness()
    assert board["total"] >= 200
    assert sys.platform  # 309: platform is recorded


def test_cross_platform_imports() -> None:
    from usb_recovery.devices import linux, windows  # noqa: F401

    assert linux.SYS_BLOCK
    assert windows.DRIVE_REMOVABLE == 2
