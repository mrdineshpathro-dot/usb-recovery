"""Filesystem slack-space analysis (328)."""

from __future__ import annotations

from usb_recovery.carving.signatures import load_signatures
from usb_recovery.devices.base import ReadOnlySource
from usb_recovery.filesystems.fat import parse_fat_boot
from usb_recovery.models import Candidate


def analyze_slack(
    source: ReadOnlySource,
    candidates: list[Candidate] | None = None,
    *,
    cluster_size: int | None = None,
    volume_offset: int = 0,
) -> dict:
    """Search the unused tail of the last cluster of each candidate for signatures."""
    if cluster_size is None:
        boot = parse_fat_boot(source.read(volume_offset, 512))
        cluster_size = boot.cluster_size if boot else 512
    _, sigs = load_signatures()
    hits: list[dict] = []
    for item in candidates or []:
        if not item.size or item.source_offset < 0:
            continue
        used = item.size % cluster_size
        if used == 0:
            continue
        slack_len = cluster_size - used
        slack_off = item.source_offset + item.size
        if slack_off + slack_len > source.size:
            continue
        blob = source.read(slack_off, slack_len)
        if not blob or set(blob) <= {0}:
            continue
        found = []
        for sig in sigs:
            if sig.header and sig.header in blob:
                found.append(sig.id)
        hits.append(
            {
                "id": item.id,
                "name": item.name,
                "slack_offset": slack_off,
                "slack_len": slack_len,
                "signatures": found,
                "nonzero": True,
            }
        )
    return {
        "cluster_size": cluster_size,
        "hits": hits,
        "note": "Slack hits are leftover bytes in the last cluster, not complete files.",
    }
