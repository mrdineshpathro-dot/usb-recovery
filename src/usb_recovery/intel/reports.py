"""Strategy reports and uncertainty-aware assistant (346, 349)."""

from __future__ import annotations

from usb_recovery.intel.plan import adaptive_plan, algorithm_profile, estimate_cost
from usb_recovery.models import Candidate


OVERCLAIM = ("guaranteed", "definitely recovered", "100%", "will recover", "bit-perfect")


def strategy_report(
    *,
    goal: str = "general",
    filesystem: str | None = None,
    size_bytes: int = 0,
) -> dict:
    """Evidence-based explanation of why methods were selected (346)."""
    plan = adaptive_plan(goal=goal, filesystem=filesystem, size_bytes=size_bytes)
    algo = algorithm_profile(filesystem, goal)
    cost = estimate_cost(size_bytes, plan["profile"])
    why = []
    why.append(f"Goal '{goal}' maps to profile '{plan['profile']}'.")
    if filesystem:
        why.append(f"Filesystem hint '{filesystem}' selects {', '.join(algo['methods'][:4])}.")
    else:
        why.append("No filesystem hint; partition mapping plus carving remain available.")
    if plan["enable_carving"]:
        why.append("Carving is enabled because metadata alone often misses orphaned payloads.")
    else:
        why.append("Carving is off (quick profile) to limit time; names and chains only.")
    why.append("Recovery is not guaranteed. Scores are heuristic explanations.")
    return {
        "plan": {k: v for k, v in plan.items() if k != "options"},
        "methods": algo["methods"],
        "cost": cost,
        "why": why,
    }


def uncertainty_report(candidates: list[Candidate]) -> dict:
    """Highlight missing evidence and refuse overconfident language (349)."""
    items = []
    for item in candidates:
        missing = []
        if not item.sha256:
            missing.append("content hash")
        if item.status in {"partial", "unreadable"}:
            missing.append("complete payload")
        if item.method == "carved" and not item.original_path:
            missing.append("original path/name")
        if item.is_fragmented:
            missing.append("contiguous allocation")
        if item.confidence < 60:
            missing.append("strong metadata corroboration")
        content = item.extra.get("content")
        if isinstance(content, (bytes, bytearray)) and item.size and len(content) < item.size:
            missing.append("bytes beyond recovered prefix")
        items.append(
            {
                "id": item.id,
                "name": item.name,
                "confidence": item.confidence,
                "missing": missing,
                "language": "heuristic candidate — recovery is not guaranteed",
            }
        )
    return {
        "items": items,
        "banned_phrases": list(OVERCLAIM),
        "note": "This assistant will not claim a file is recovered unless it was written and hashed.",
    }
