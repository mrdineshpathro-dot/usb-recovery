from __future__ import annotations

import gzip
import struct
from pathlib import Path

from usb_recovery.devices.detector import open_source
from usb_recovery.images.compare import compare_images
from usb_recovery.images.compressed import GzipImageSource, is_gzip
from usb_recovery.images.convert import convert_image
from usb_recovery.images.inspect import inspect_container
from usb_recovery.images.offset import OffsetSource
from usb_recovery.images.provenance import write_provenance
from usb_recovery.images.sparse import sparse_map
from usb_recovery.images.split import SplitImageSource, discover_parts
from usb_recovery.images.vhd import VhdSource, is_vhd, parse_vhd_footer
from usb_recovery.devices.image import ImageSource


def _fixed_vhd(payload: bytes) -> bytes:
    footer = bytearray(512)
    footer[0:8] = b"conectix"
    footer[16:24] = b"\xff" * 8
    struct.pack_into(">Q", footer, 40, len(payload))
    struct.pack_into(">Q", footer, 48, len(payload))
    struct.pack_into(">I", footer, 60, 2)
    checksum = 0
    for byte in footer:
        checksum += byte
    struct.pack_into(">I", footer, 64, (~checksum) & 0xFFFFFFFF)
    return payload + bytes(footer)


def test_split_image(tmp_path: Path) -> None:
    a = tmp_path / "disk.001"
    b = tmp_path / "disk.002"
    a.write_bytes(b"AAAA" * 128)
    b.write_bytes(b"BBBB" * 128)
    parts = discover_parts(a)
    assert len(parts) == 2
    src = SplitImageSource(str(a))
    with src:
        assert src.size == 1024
        assert src.read(0, 4) == b"AAAA"
        assert src.read(512, 4) == b"BBBB"


def test_gzip_and_convert(tmp_path: Path) -> None:
    raw = tmp_path / "x.img"
    raw.write_bytes(b"Z" * 2048)
    gz = tmp_path / "x.img.gz"
    with gzip.open(gz, "wb") as handle:
        handle.write(raw.read_bytes())
    assert is_gzip(gz)
    src = GzipImageSource(str(gz))
    with src:
        assert src.read(0, 3) == b"ZZZ"
        assert src.size == 2048
    dest = tmp_path / "out.img"
    result = convert_image(gz, dest, fmt="raw")
    assert dest.read_bytes() == raw.read_bytes()
    assert result["bytes_written"] == 2048


def test_vhd_fixed(tmp_path: Path) -> None:
    payload = b"V" * 1024
    vhd = tmp_path / "disk.vhd"
    vhd.write_bytes(_fixed_vhd(payload))
    assert is_vhd(vhd)
    meta = parse_vhd_footer(vhd.read_bytes()[-512:])
    assert meta["disk_type"] == "fixed"
    src = VhdSource(str(vhd))
    with src:
        assert src.size == 1024
        assert src.read(0, 4) == b"VVVV"


def test_offset_source(fat_image: dict) -> None:
    inner = ImageSource(str(fat_image["path"]))
    wrap = OffsetSource(inner, 512)
    with wrap:
        assert wrap.size == fat_image["size"] - 512
        assert wrap.read(0, 2) == inner.read(512, 2)


def test_compare_provenance_inspect(tmp_path: Path) -> None:
    a = tmp_path / "a.img"
    b = tmp_path / "b.img"
    a.write_bytes(b"\x00" * 1024)
    b.write_bytes(b"\x00" * 512 + b"\xff" * 512)
    diff = compare_images(a, b, block=256)
    assert diff["identical"] is False
    assert diff["diff_blocks"]
    man = write_provenance(a)
    assert man.exists()
    info = inspect_container(a)
    assert info["kind"] in {"raw", "sparse"}
    sparse_map(a)


def test_open_source_gzip(tmp_path: Path) -> None:
    raw = tmp_path / "s.img"
    raw.write_bytes(b"\x00" * 512)
    gz = tmp_path / "s.img.gz"
    with gzip.open(gz, "wb") as handle:
        handle.write(raw.read_bytes())
    src = open_source(str(gz))
    try:
        assert src.size == 512
    finally:
        src.close()
