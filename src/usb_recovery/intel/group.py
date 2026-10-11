"""Correlation-based candidate grouping (347)."""

from __future__ import annotations

from usb_recovery.advanced.fragments import fragment_graph
from usb_recovery.models import Candidate
from usb_recovery.reconstruct.matching import match_candidates


def group_correlated(candidates: list[Candidate]) -> list[dict]:
    """Group candidates that share source regions, metadata, or content."""
    groups: list[dict] = []
    seen: set[str] = set()
    for match in match_candidates(candidates):
        ids = tuple(match.get("ids") or [])
        groups.append({"kind": match.get("kind"), "ids": list(ids), "via": "match"})
        seen.update(ids)
    graph = fragment_graph(candidates)
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for edge in graph.get("edges") or []:
        union(edge["a"], edge["b"])
    buckets: dict[str, list[str]] = {}
    for node in graph.get("nodes") or []:
        buckets.setdefault(find(node["id"]), []).append(node["id"])
    for ids in buckets.values():
        if len(ids) < 2:
            continue
        key = tuple(sorted(ids))
        if any(set(g["ids"]) == set(key) for g in groups):
            continue
        groups.append({"kind": "graph-component", "ids": list(key), "via": "proximity"})
    return groups
