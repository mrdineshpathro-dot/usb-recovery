"""Adaptive scan planner, cost estimate, and algorithm profiles (342, 343, 348)."""

from __future__ import annotations

from usb_recovery.models import ScanOptions

GOAL_SIGNATURES = {
    "photos": ["jpeg", "png", "webp", "gif", "bmp", "cr2", "rw2", "dng"],
    "documents": ["pdf", "zip", "ole", "sqlite"],
    "video": ["mp4", "avi", "mkv"],
    "audio": ["mp3", "wav", "flac"],
    "general": None,
}

GOAL_PROFILE = {
    "photos": "standard",
    "documents": "standard",
    "video": "deep",
    "audio": "standard",
    "general": "standard",
    "forensic": "deep",
}


def adaptive_plan(
    *,
    goal: str = "general",
    filesystem: str | None = None,
    size_bytes: int = 0,
    previous: dict | None = None,
) -> dict:
    """Prioritize methods from the recovery goal and optional prior scan stats."""
    goal_key = (goal or "general").lower()
    profile = GOAL_PROFILE.get(goal_key, "standard")
    signatures = GOAL_SIGNATURES.get(goal_key)
    enable_carve = profile != "quick"
    enable_meta = True
    if previous:
        # If a prior metadata-only scan found nothing, escalate carving.
        if previous.get("candidates", 0) == 0:
            profile = "deep"
            enable_carve = True
        if previous.get("filesystem") == "unknown":
            enable_carve = True
    if filesystem in {"ext", "encrypted"}:
        enable_meta = filesystem != "encrypted"
        enable_carve = True
        profile = "deep"
    options = ScanOptions.from_profile(profile)  # type: ignore[arg-type]
    options.enable_carving = enable_carve
    options.enable_metadata = enable_meta
    if signatures:
        options.signatures = list(signatures)
    return {
        "goal": goal_key,
        "profile": profile,
        "filesystem": filesystem,
        "signatures": options.signatures,
        "enable_carving": options.enable_carving,
        "enable_metadata": options.enable_metadata,
        "options": options,
        "size_bytes": size_bytes,
        "note": "Plan selects among implemented methods. It does not invent unsupported filesystems.",
    }


def estimate_cost(size_bytes: int, profile: str = "standard") -> dict:
    """Rough time / RAM / coverage estimate (343). Not a promise."""
    mb = max(size_bytes, 1) / (1024 * 1024)
    rates = {"quick": 80.0, "standard": 25.0, "deep": 8.0}  # MiB/s heuristic
    rate = rates.get(profile, 25.0)
    seconds = mb / rate
    ram_mb = {"quick": 32, "standard": 96, "deep": 256}.get(profile, 96)
    coverage = {"quick": 0.4, "standard": 0.7, "deep": 0.85}.get(profile, 0.7)
    return {
        "profile": profile,
        "size_bytes": size_bytes,
        "estimated_scan_s": round(seconds, 2),
        "estimated_ram_mb": ram_mb,
        "expected_coverage": coverage,
        "note": "Estimates are order-of-magnitude only. Flash speed and fragmentation dominate.",
    }


def algorithm_profile(filesystem: str | None, goal: str = "general") -> dict:
    """Pick among tested algorithms for a filesystem + goal (348)."""
    fs = (filesystem or "unknown").lower()
    methods: list[str] = ["partition-map"]
    if fs.startswith("fat"):
        methods += ["fat-directory", "fat-allocation-history"]
    elif fs == "exfat":
        methods += ["exfat-directory", "exfat-bitmap"]
    elif fs == "ntfs":
        methods += ["ntfs-mft", "ntfs-record-graph"]
    else:
        methods += ["signature-carve"]
    if goal in {"photos", "general", "video", "documents"}:
        methods.append("signature-carve")
    if goal == "photos":
        methods += ["jpeg-fragment", "raw-fragment"]
    if goal == "documents":
        methods += ["zip-directory", "pdf-xref", "ooxml-rels"]
    return {
        "filesystem": fs,
        "goal": goal,
        "methods": methods,
        "note": "Only implemented, tested algorithms are listed.",
    }
