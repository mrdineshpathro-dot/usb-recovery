"""Test-corpus manager (302)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from usb_recovery.lab.synthetic import list_scenarios, write_scenario
from usb_recovery.util import isoformat, sha256_file


class Corpus:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "corpus.json"
        self._index = self._load()

    def _load(self) -> dict[str, Any]:
        if self.index_path.exists():
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        return {"items": [], "updated_at": None}

    def _save(self) -> None:
        self._index["updated_at"] = isoformat()
        self.index_path.write_text(json.dumps(self._index, indent=2), encoding="utf-8")

    def add_file(self, path: Path, *, label: str, expected: dict | None = None) -> dict:
        dest = self.root / path.name
        if path.resolve() != dest.resolve():
            dest.write_bytes(path.read_bytes())
        item = {
            "label": label,
            "path": str(dest),
            "sha256": sha256_file(dest) if dest.stat().st_size <= 64 * 1024 * 1024 else None,
            "expected": expected or {},
        }
        self._index["items"] = [i for i in self._index["items"] if i["label"] != label]
        self._index["items"].append(item)
        self._save()
        return item

    def generate_builtin(self) -> list[dict]:
        added = []
        for name in list_scenarios():
            dest = self.root / f"{name}.img"
            write_scenario(name, dest)
            expected = {"names": ["HELLO.TXT"]} if "fat" in name else {}
            added.append(self.add_file(dest, label=name, expected=expected))
        return added

    def items(self) -> list[dict]:
        return list(self._index["items"])
