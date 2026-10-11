"""Offline searchable help (294, 299)."""

from __future__ import annotations

from pathlib import Path

TOPICS = [
    {
        "id": "safety",
        "title": "Safety rules",
        "text": (
            "The source is opened read-only. Recovered files never go back to the pen drive. "
            "A read-only handle does not stop USB bridges or NAND controllers from writing. "
            "Unmount live volumes. Prefer imaging failing flash."
        ),
    },
    {
        "id": "metadata",
        "title": "Filesystem metadata recovery",
        "text": (
            "Walks FAT/exFAT directories and NTFS $MFT records. Deleted FAT names lose the "
            "first character. Zeroed FAT chains use a contiguous heuristic marked uncertain."
        ),
    },
    {
        "id": "carving",
        "title": "Signature carving",
        "text": (
            "Finds JPEG/PNG/PDF/ZIP and other headers. Fragmented files are often incomplete. "
            "Original names are usually lost. Confidence scores are not probabilities."
        ),
    },
    {
        "id": "imaging",
        "title": "Disk imaging",
        "text": (
            "Creates a raw .dd with checkpoints and a bad-sector map. Resume after unplug only "
            "if the device identity (serial/size) still matches."
        ),
    },
    {
        "id": "trim",
        "title": "TRIM and unrecoverable data",
        "text": (
            "If the controller discarded pages, reads return zeros. Software cannot undo TRIM."
        ),
    },
    {
        "id": "evidence",
        "title": "Multi-evidence recovery",
        "text": (
            "Metadata, signatures, and structural validators are combined to rank candidates. "
            "Scores remain heuristic. Fragment graphs and hypotheses are guesses, not proof."
        ),
    },
    {
        "id": "samples",
        "title": "Sample recovery cases",
        "text": (
            "usb-recovery lab --scenario deleted_fat|mbr_fat|carve_only|gpt_empty writes a "
            "synthetic image with known files. Never practice on a real victim stick."
        ),
    },
]


def search_help(query: str) -> list[dict]:
    q = (query or "").lower().strip()
    if not q:
        return list(TOPICS)
    hits = []
    for topic in TOPICS:
        blob = f"{topic['id']} {topic['title']} {topic['text']}".lower()
        if q in blob:
            hits.append(topic)
    return hits


def load_markdown_help() -> list[Path]:
    root = Path(__file__).resolve().parents[3] / "docs"
    if not root.is_dir():
        return []
    return sorted(root.glob("*.md"))
