#!/usr/bin/env python3
"""Generate synthetic disk images for manual experiments (never real devices)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from tests.fixtures.builder import (  # noqa: E402
    build_carve_image,
    build_fat16_image,
    build_gpt_empty_image,
    build_mbr_fat_image,
)


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "tests" / "images"
    out.mkdir(parents=True, exist_ok=True)
    build_fat16_image(out / "fat16.img")
    build_mbr_fat_image(out / "mbr-fat16.img")
    build_gpt_empty_image(out / "gpt.img")
    build_carve_image(out / "carve.img")
    print(f"Wrote synthetic images in {out}")


if __name__ == "__main__":
    main()
