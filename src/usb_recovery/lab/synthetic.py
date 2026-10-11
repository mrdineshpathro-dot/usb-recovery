"""Synthetic Recovery Lab — practice images with known deletions (255)."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

# Import test fixtures builder — available when running from the repo.
# Fallback: minimal inline FAT builder is not duplicated; we reuse tests.fixtures.

SCENARIOS = ("deleted_fat", "mbr_fat", "carve_only", "gpt_empty")


def list_scenarios() -> list[str]:
    return list(SCENARIOS)


def write_scenario(name: str, dest: Path) -> dict:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        from tests.fixtures.builder import (
            build_carve_image,
            build_fat16_image,
            build_gpt_empty_image,
            build_mbr_fat_image,
        )
    except ImportError:
        import sys

        root = Path(__file__).resolve().parents[3]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        try:
            from tests.fixtures.builder import (
                build_carve_image,
                build_fat16_image,
                build_gpt_empty_image,
                build_mbr_fat_image,
            )
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Synthetic lab requires the repository test fixtures (tests/fixtures/builder.py)"
            ) from exc
    builders: dict[str, Callable[[Path], dict]] = {
        "deleted_fat": build_fat16_image,
        "mbr_fat": build_mbr_fat_image,
        "carve_only": build_carve_image,
        "gpt_empty": build_gpt_empty_image,
    }
    if name not in builders:
        raise ValueError(f"Unknown scenario {name}. Choose from {SCENARIOS}")
    meta = builders[name](dest)
    meta["scenario"] = name
    meta["path"] = dest
    return meta
