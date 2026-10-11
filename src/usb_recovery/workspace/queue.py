"""Priority queue and file-type batches (245, 246)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from usb_recovery.models import Candidate

BATCHES = {
    "photos": {"jpeg", "jpg", "png", "gif", "bmp", "webp"},
    "documents": {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "rtf"},
    "archives": {"zip", "rar", "7z"},
    "videos": {"mp4", "mov", "avi", "mkv"},
    "audio": {"mp3", "wav", "flac"},
    "other": set(),
}


@dataclass
class PriorityItem:
    candidate: Candidate
    priority: int = 100
    note: str = ""


@dataclass
class PriorityQueue:
    items: list[PriorityItem] = field(default_factory=list)

    def add(self, candidate: Candidate, priority: int = 100, note: str = "") -> None:
        self.items.append(PriorityItem(candidate, priority, note))
        self.items.sort(key=lambda x: (x.priority, -x.candidate.confidence, x.candidate.name))

    def ordered(self) -> list[Candidate]:
        return [i.candidate for i in self.items]


class FileTypeBatches:
    def __init__(self, candidates: list[Candidate]) -> None:
        self.groups: dict[str, list[Candidate]] = defaultdict(list)
        for item in candidates:
            placed = False
            for name, types in BATCHES.items():
                if name == "other":
                    continue
                if item.file_type.lower() in types or item.extension.lower() in types:
                    self.groups[name].append(item)
                    placed = True
                    break
            if not placed:
                self.groups["other"].append(item)

    def as_dict(self) -> dict[str, list[str]]:
        return {k: [c.id for c in v] for k, v in self.groups.items()}
