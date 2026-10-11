"""Photo sequence grouping using timestamps and JPEG metadata (214)."""

from __future__ import annotations

from collections import defaultdict

from usb_recovery.models import Candidate

PHOTO_TYPES = {"jpeg", "jpg", "png", "gif", "bmp", "webp", "raw", "heic"}


def group_photos(candidates: list[Candidate], bucket_seconds: int = 120) -> list[dict]:
    photos = [
        c
        for c in candidates
        if c.file_type.lower() in PHOTO_TYPES
        or c.mime.startswith("image/")
        or c.extension.lower() in PHOTO_TYPES
    ]
    buckets: dict[str, list[Candidate]] = defaultdict(list)
    for item in photos:
        ts = item.timestamps.modified or item.timestamps.created or "unknown"
        key = ts[:16] if ts != "unknown" else f"offset:{item.source_offset // max(bucket_seconds * 512, 1)}"
        buckets[key].append(item)
    groups = []
    for key, items in sorted(buckets.items(), key=lambda kv: kv[0]):
        groups.append(
            {
                "bucket": key,
                "count": len(items),
                "ids": [c.id for c in items],
                "names": [c.name for c in items],
            }
        )
    return groups
