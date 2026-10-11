from __future__ import annotations

from pathlib import Path

from usb_recovery.config import AppConfig


def test_default_config_offline() -> None:
    cfg = AppConfig.load()
    assert cfg.prevent_same_device is True
    assert cfg.telemetry is False
    assert cfg.allow_network is False
    assert cfg.no_overwrite is True


def test_local_override(tmp_path: Path) -> None:
    path = tmp_path / "c.toml"
    path.write_text(
        """
[safety]
bad_sector_retries = 9
[scan]
default_profile = "deep"
[network]
telemetry = true
allow_network = true
""",
        encoding="utf-8",
    )
    cfg = AppConfig.load(path)
    assert cfg.bad_sector_retries == 9
    assert cfg.default_profile == "deep"
    # Offline-first: telemetry cannot be enabled via config.
    assert cfg.telemetry is False
    assert cfg.allow_network is False
