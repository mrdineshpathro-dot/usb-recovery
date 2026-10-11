from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tests.fixtures.builder import (  # noqa: E402
    build_carve_image,
    build_fat16_image,
    build_gpt_empty_image,
    build_mbr_fat_image,
)


@pytest.fixture
def fat_image(tmp_path: Path) -> dict:
    return build_fat16_image(tmp_path / "fat16.img")


@pytest.fixture
def mbr_image(tmp_path: Path) -> dict:
    return build_mbr_fat_image(tmp_path / "mbr-fat.img")


@pytest.fixture
def gpt_image(tmp_path: Path) -> dict:
    return build_gpt_empty_image(tmp_path / "gpt.img")


@pytest.fixture
def carve_image(tmp_path: Path) -> dict:
    return build_carve_image(tmp_path / "carve.img")
