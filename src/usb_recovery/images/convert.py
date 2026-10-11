"""Convert compatible image formats, recording details (268). Writes only to dest."""

from __future__ import annotations

import gzip
from pathlib import Path

from usb_recovery.exceptions import DestinationError, SafetyError
from usb_recovery.images.inspect import inspect_container
from usb_recovery.images.split import discover_parts
from usb_recovery.safety import assert_destination_safe
from usb_recovery.util import isoformat, sha256_file


def convert_image(
    source: str | Path,
    dest: str | Path,
    *,
    fmt: str = "raw",
    part_size: int = 100 * 1024 * 1024,
    allow_same_device: bool = False,
) -> dict:
    src = Path(source)
    dest_path = Path(dest)
    assert_destination_safe(src, dest_path, allow_same_device=allow_same_device)
    if dest_path.resolve() == src.resolve():
        raise SafetyError("Refusing to convert an image onto itself")
    info = inspect_container(src)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    parts_out: list[str] = []
    if fmt == "raw":
        if info["kind"] == "split":
            with open(dest_path, "wb") as out:
                for part in discover_parts(src):
                    with open(part, "rb") as handle:
                        while True:
                            chunk = handle.read(1024 * 1024)
                            if not chunk:
                                break
                            out.write(chunk)
                            written += len(chunk)
        elif info["kind"] == "gzip":
            with gzip.open(src, "rb") as handle, open(dest_path, "wb") as out:
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    written += len(chunk)
        else:
            # raw/vhd-as-file copy (does not strip VHD footer — caller may use VhdSource)
            with open(src, "rb") as handle, open(dest_path, "wb") as out:
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    written += len(chunk)
    elif fmt == "split":
        idx = 1
        with open(src, "rb") as handle:
            while True:
                chunk = handle.read(part_size)
                if not chunk:
                    break
                part = dest_path.parent / f"{dest_path.name}.{idx:03d}"
                part.write_bytes(chunk)
                parts_out.append(str(part))
                written += len(chunk)
                idx += 1
        dest_path = Path(parts_out[0]) if parts_out else dest_path
    elif fmt == "gzip":
        with open(src, "rb") as handle, gzip.open(dest_path, "wb") as out:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                written += len(chunk)
    else:
        raise DestinationError(f"Unsupported conversion format {fmt!r}")
    digest = None
    if dest_path.is_file() and dest_path.stat().st_size <= 64 * 1024 * 1024:
        digest = sha256_file(dest_path)
    return {
        "source": str(src),
        "dest": str(dest_path),
        "format": fmt,
        "source_kind": info.get("kind"),
        "bytes_written": written,
        "parts": parts_out,
        "sha256": digest,
        "converted_at": isoformat(),
    }
