from __future__ import annotations

from usb_recovery.db.store import SessionStore
from usb_recovery.models import Candidate
from usb_recovery.workspace.columns import project_rows
from usb_recovery.workspace.notify import NotificationLog
from usb_recovery.workspace.queue import FileTypeBatches, PriorityQueue
from usb_recovery.workspace.saved import WorkspaceStore
from usb_recovery.workspace.search import fuzzy_search, levenshtein, natural_search, select_by_rules


def _c(name: str, **kw) -> Candidate:
    data = dict(
        id=name,
        name=name,
        size=100,
        file_type="bin",
        mime="application/octet-stream",
        method="metadata",
        status="deleted",
        source_offset=0,
        confidence=60,
        extension=name.rsplit(".", 1)[-1].lower() if "." in name else "",
    )
    data.update(kw)
    if "file_type" not in kw and "." in name:
        data["file_type"] = name.rsplit(".", 1)[-1].lower()
    return Candidate(**data)  # type: ignore[arg-type]


def test_natural_and_fuzzy() -> None:
    items = [
        _c("HELLO.TXT", file_type="txt", size=50, status="deleted"),
        _c("photo.jpg", file_type="jpeg", size=2_000_000, status="carved", method="carved"),
        _c("notes.pdf", file_type="pdf", size=10, status="existing", method="existing"),
    ]
    deleted_txt = natural_search(items, "deleted txt named hello")
    assert [c.name for c in deleted_txt] == ["HELLO.TXT"]
    big = natural_search(items, "jpegs larger than 1mb")
    assert any(c.name == "photo.jpg" for c in big)
    fuzzy = fuzzy_search(items, "helo", max_distance=2)
    assert any(c.name == "HELLO.TXT" for c in fuzzy)
    assert levenshtein("kitten", "sitting") == 3
    selected = select_by_rules(items, {"types": ["pdf"], "status": ["existing"]})
    assert selected[0].name == "notes.pdf"


def test_workspace_store_queue_notify() -> None:
    store = SessionStore()
    ws = WorkspaceStore(store)
    sid = ws.save_search("photos", query="photos larger than 1mb")
    assert ws.list_searches()[0]["id"] == sid
    ws.bookmark(session_id="sess-1", candidate_id="c1", offset=512, note="look here")
    assert ws.list_bookmarks("sess-1")
    ws.save_profile("dark-work", {"theme": "dark", "columns": ["name", "size"], "passphrase": "nope"})
    profile = ws.load_profile("dark-work")
    assert profile and "passphrase" not in profile["settings"]
    q = PriorityQueue()
    q.add(_c("b.jpg", file_type="jpeg"), priority=10)
    q.add(_c("a.jpg", file_type="jpeg"), priority=1)
    assert q.ordered()[0].name == "a.jpg"
    batches = FileTypeBatches([_c("x.jpg", file_type="jpeg"), _c("y.pdf", file_type="pdf")])
    assert "photos" in batches.as_dict()
    notes = NotificationLog()
    notes.scan_finished("sess", 3)
    assert notes.items[-1].kind == "scan-finished"
    rows = project_rows([_c("z.jpg", file_type="jpeg")], ["name", "status"])
    assert rows[0]["name"] == "z.jpg"
