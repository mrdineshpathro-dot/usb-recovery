"""Load TOML configuration with safe defaults."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from usb_recovery.exceptions import ConfigurationError

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


def _default_config_candidates() -> list[Path]:
    here = Path(__file__).resolve().parents[2]
    bundled = here / "config" / "default.toml"
    local = here / "config" / "local.toml"
    env = os.environ.get("USB_RECOVERY_CONFIG")
    paths = [bundled]
    if local.exists():
        paths.append(local)
    if env:
        paths.append(Path(env))
    return paths


def _get(mapping: dict[str, Any], *keys: str, default: Any) -> Any:
    cursor: Any = mapping
    for key in keys:
        if not isinstance(cursor, dict) or key not in cursor:
            return default
        cursor = cursor[key]
    return cursor


@dataclass
class AppConfig:
    prevent_same_device: bool = True
    require_device_confirmation: bool = True
    bad_sector_retries: int = 3
    bad_sector_retry_delay_s: float = 0.05
    unstable_device_bad_sector_threshold: int = 64
    imaging_block_size: int = 1_048_576
    checkpoint_every_bytes: int = 16_777_216
    hash_while_imaging: bool = True
    bad_sector_policy: str = "zero"
    default_profile: str = "standard"
    carve_window_bytes: int = 1_048_576
    max_carve_size_bytes: int = 67_108_864
    carve_workers: int = 1
    no_overwrite: bool = True
    recreate_directory_hierarchy: bool = True
    verify_size: bool = True
    hash_recovered: bool = True
    collision_template: str = "{stem} ({n}){suffix}"
    log_level: str = "INFO"
    rotate_bytes: int = 1_048_576
    rotate_backups: int = 5
    theme: str = "dark"
    allow_network: bool = False
    telemetry: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | None = None) -> "AppConfig":
        merged: dict[str, Any] = {}
        candidates = [path] if path else _default_config_candidates()
        for candidate in candidates:
            if candidate is None or not candidate.exists():
                continue
            try:
                with open(candidate, "rb") as handle:
                    data = tomllib.load(handle)
            except tomllib.TOMLDecodeError as exc:
                raise ConfigurationError(f"Invalid TOML in {candidate}: {exc}") from exc
            merged = _deep_merge(merged, data)
        cfg = cls()
        cfg.prevent_same_device = bool(
            _get(merged, "safety", "prevent_same_device", default=cfg.prevent_same_device)
        )
        cfg.require_device_confirmation = bool(
            _get(
                merged,
                "safety",
                "require_device_confirmation",
                default=cfg.require_device_confirmation,
            )
        )
        cfg.bad_sector_retries = int(
            _get(merged, "safety", "bad_sector_retries", default=cfg.bad_sector_retries)
        )
        cfg.bad_sector_retry_delay_s = float(
            _get(
                merged,
                "safety",
                "bad_sector_retry_delay_s",
                default=cfg.bad_sector_retry_delay_s,
            )
        )
        cfg.unstable_device_bad_sector_threshold = int(
            _get(
                merged,
                "safety",
                "unstable_device_bad_sector_threshold",
                default=cfg.unstable_device_bad_sector_threshold,
            )
        )
        cfg.imaging_block_size = int(
            _get(merged, "imaging", "block_size", default=cfg.imaging_block_size)
        )
        cfg.checkpoint_every_bytes = int(
            _get(
                merged,
                "imaging",
                "checkpoint_every_bytes",
                default=cfg.checkpoint_every_bytes,
            )
        )
        cfg.hash_while_imaging = bool(
            _get(merged, "imaging", "hash_while_imaging", default=cfg.hash_while_imaging)
        )
        cfg.bad_sector_policy = str(
            _get(merged, "imaging", "bad_sector_policy", default=cfg.bad_sector_policy)
        )
        cfg.default_profile = str(
            _get(merged, "scan", "default_profile", default=cfg.default_profile)
        )
        cfg.carve_window_bytes = int(
            _get(merged, "scan", "carve_window_bytes", default=cfg.carve_window_bytes)
        )
        cfg.max_carve_size_bytes = int(
            _get(merged, "scan", "max_carve_size_bytes", default=cfg.max_carve_size_bytes)
        )
        cfg.carve_workers = int(
            _get(merged, "scan", "carve_workers", default=cfg.carve_workers)
        )
        cfg.no_overwrite = bool(
            _get(merged, "recovery", "no_overwrite", default=cfg.no_overwrite)
        )
        cfg.recreate_directory_hierarchy = bool(
            _get(
                merged,
                "recovery",
                "recreate_directory_hierarchy",
                default=cfg.recreate_directory_hierarchy,
            )
        )
        cfg.verify_size = bool(
            _get(merged, "recovery", "verify_size", default=cfg.verify_size)
        )
        cfg.hash_recovered = bool(
            _get(merged, "recovery", "hash_recovered", default=cfg.hash_recovered)
        )
        cfg.collision_template = str(
            _get(merged, "recovery", "collision_template", default=cfg.collision_template)
        )
        cfg.log_level = str(_get(merged, "logging", "level", default=cfg.log_level))
        cfg.rotate_bytes = int(
            _get(merged, "logging", "rotate_bytes", default=cfg.rotate_bytes)
        )
        cfg.rotate_backups = int(
            _get(merged, "logging", "rotate_backups", default=cfg.rotate_backups)
        )
        cfg.theme = str(_get(merged, "gui", "theme", default=cfg.theme))
        cfg.allow_network = bool(
            _get(merged, "network", "allow_network", default=cfg.allow_network)
        )
        cfg.telemetry = bool(_get(merged, "network", "telemetry", default=cfg.telemetry))
        cfg.extra = merged
        if cfg.telemetry or cfg.allow_network:
            # Offline-first: ignore network flags even if a local config enables them.
            cfg.telemetry = False
            cfg.allow_network = False
        return cfg


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
