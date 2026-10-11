"""Natural-language, fuzzy, and rule-based candidate search (241, 242, 247)."""

from __future__ import annotations

import re
from typing import Any, Iterable

from usb_recovery.models import Candidate
from usb_recovery.util import human_size

TYPE_ALIASES = {
    "photo": {"jpeg", "jpg", "png", "gif", "bmp", "webp"},
    "photos": {"jpeg", "jpg", "png", "gif", "bmp", "webp"},
    "image": {"jpeg", "jpg", "png", "gif", "bmp", "webp"},
    "images": {"jpeg", "jpg", "png", "gif", "bmp", "webp"},
    "document": {"pdf", "doc", "docx", "txt", "rtf", "odt"},
    "documents": {"pdf", "doc", "docx", "txt", "rtf", "odt"},
    "archive": {"zip", "rar", "7z", "tar"},
    "archives": {"zip", "rar", "7z", "tar"},
    "video": {"mp4", "mov", "avi", "mkv"},
    "videos": {"mp4", "mov", "avi", "mkv"},
    "audio": {"mp3", "wav", "flac"},
}


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            ins, delete, sub = curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + (ca != cb)
            curr.append(min(ins, delete, sub))
        prev = curr
    return prev[-1]


def _parse_size(token: str) -> int | None:
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(b|kb|kib|mb|mib|gb|gib)?", token.lower())
    if not m:
        return None
    n = float(m.group(1))
    unit = m.group(2) or "b"
    mul = {
        "b": 1,
        "kb": 1000,
        "kib": 1024,
        "mb": 1000**2,
        "mib": 1024**2,
        "gb": 1000**3,
        "gib": 1024**3,
    }[unit]
    return int(n * mul)


def natural_search(candidates: Iterable[Candidate], phrase: str) -> list[Candidate]:
    """Interpret everyday phrases such as 'deleted jpegs larger than 1mb named hello'."""
    text = (phrase or "").strip().lower()
    if not text:
        return list(candidates)
    status = None
    methods = None
    types: set[str] | None = None
    min_size = None
    max_size = None
    name_part = None

    if "deleted" in text:
        status = "deleted"
    if "carved" in text:
        methods = {"carved"}
    if "existing" in text or "not deleted" in text:
        status = "existing"

    for alias, group in TYPE_ALIASES.items():
        if re.search(rf"\b{alias}\b", text):
            types = group if types is None else types | group
    for ext in ("jpeg", "jpg", "png", "pdf", "zip", "docx", "mp3", "mp4", "txt"):
        if re.search(rf"\b{ext}s?\b", text):
            types = {ext, "jpeg"} if ext == "jpg" else ({ext} if types is None else types | {ext})

    m = re.search(r"larger than ([0-9.]+\s*[a-z]*)", text)
    if m:
        min_size = _parse_size(m.group(1).replace(" ", ""))
        if min_size is None:
            min_size = _parse_size(m.group(1))
    m = re.search(r"smaller than ([0-9.]+\s*[a-z]*)", text)
    if m:
        max_size = _parse_size(m.group(1).replace(" ", "")) or _parse_size(m.group(1))

    m = re.search(r"named ([a-z0-9._-]+)", text)
    if m:
        name_part = m.group(1)
    elif "named" not in text and types is None and status is None and methods is None:
        # leftover words as a filename hint if they are not keywords
        type_words = set(TYPE_ALIASES) | {
            "jpeg",
            "jpegs",
            "jpg",
            "jpgs",
            "png",
            "pngs",
            "pdf",
            "pdfs",
            "zip",
            "zips",
        }
        leftovers = [
            w
            for w in re.findall(r"[a-z0-9._-]+", text)
            if w
            not in {
                "deleted",
                "carved",
                "existing",
                "files",
                "file",
                "larger",
                "smaller",
                "than",
                "named",
                "the",
                "and",
                "with",
                "from",
                *type_words,
            }
            and not re.match(r"\d", w)
        ]
        if len(leftovers) == 1:
            name_part = leftovers[0]

    out: list[Candidate] = []
    for item in candidates:
        if status and item.status != status:
            continue
        if methods and item.method not in methods:
            continue
        if types and item.file_type.lower() not in types and item.extension.lower() not in types:
            continue
        if min_size is not None and item.size < min_size:
            continue
        if max_size is not None and item.size > max_size:
            continue
        if name_part and name_part not in item.name.lower() and name_part not in (item.original_path or "").lower():
            continue
        out.append(item)
    return out


def fuzzy_search(candidates: Iterable[Candidate], query: str, *, max_distance: int = 3) -> list[Candidate]:
    q = (query or "").lower().strip()
    if not q:
        return list(candidates)
    scored: list[tuple[int, Candidate]] = []
    for item in candidates:
        names = [item.name.lower(), Path_stem(item.name)]
        if item.original_path:
            names.append(item.original_path.lower())
        dist = min(levenshtein(q, n) for n in names)
        if q in item.name.lower() or (item.original_path and q in item.original_path.lower()):
            dist = 0
        if dist <= max_distance:
            scored.append((dist, item))
    scored.sort(key=lambda t: (t[0], t[1].name.lower()))
    return [c for _, c in scored]


def Path_stem(name: str) -> str:
    if "." in name:
        return name.rsplit(".", 1)[0].lower()
    return name.lower()


def select_by_rules(candidates: Iterable[Candidate], rules: dict[str, Any]) -> list[Candidate]:
    """rules: types, min_size, max_size, status, method, path_contains, min_confidence."""
    types = {t.lower() for t in rules.get("types") or []}
    statuses = {s.lower() for s in rules.get("status") or []}
    methods = {m.lower() for m in rules.get("method") or []}
    min_size = rules.get("min_size")
    max_size = rules.get("max_size")
    path_contains = (rules.get("path_contains") or "").lower()
    min_conf = rules.get("min_confidence")
    out = []
    for item in candidates:
        if types and item.file_type.lower() not in types and item.extension.lower() not in types:
            continue
        if statuses and item.status not in statuses:
            continue
        if methods and item.method not in methods:
            continue
        if min_size is not None and item.size < int(min_size):
            continue
        if max_size is not None and item.size > int(max_size):
            continue
        if path_contains and path_contains not in (item.original_path or item.name).lower():
            continue
        if min_conf is not None and item.confidence < float(min_conf):
            continue
        out.append(item)
    return out
