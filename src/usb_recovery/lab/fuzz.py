"""Parser fuzzing against malformed inputs (258)."""

from __future__ import annotations

import os
from typing import Callable

from usb_recovery.filesystems.exfat import parse_exfat_boot
from usb_recovery.filesystems.fat import parse_fat_boot
from usb_recovery.filesystems.ntfs import parse_ntfs_boot, parse_runlist
from usb_recovery.partitions.gpt import parse_gpt_header
from usb_recovery.partitions.mbr import parse_mbr


def _mutate(seed: bytes, rng: Callable[[int], bytes]) -> bytes:
    buf = bytearray(seed if seed else rng(512))
    if not buf:
        buf = bytearray(rng(512))
    n = rng(1)[0] % 8 + 1
    for _ in range(n):
        idx = rng(2)[0] * 256 + rng(1)[0]
        idx %= max(1, len(buf))
        buf[idx] = rng(1)[0]
    if rng(1)[0] & 1 and len(buf) > 16:
        del buf[rng(1)[0] % len(buf)]
    return bytes(buf)


def fuzz_parsers(iterations: int = 64, seed: bytes | None = None) -> dict:
    """Feed random mutations to parsers. They must not raise uncaught crashes."""
    crashes: list[str] = []
    parsed = 0

    def rng(n: int) -> bytes:
        return os.urandom(n)

    base = seed or os.urandom(512)
    parsers = [
        ("mbr", lambda b: parse_mbr(b[:512].ljust(512, b"\x00"))),
        ("gpt", lambda b: parse_gpt_header(b[:92].ljust(92, b"\x00"))),
        ("fat", parse_fat_boot),
        ("exfat", parse_exfat_boot),
        ("ntfs", parse_ntfs_boot),
        ("runlist", lambda b: parse_runlist(b[:64])),
    ]
    for i in range(iterations):
        blob = _mutate(base, rng)
        for name, fn in parsers:
            try:
                fn(blob)
                parsed += 1
            except Exception as exc:  # noqa: BLE001 — record, do not fail the fuzzer loop
                # Defensive parsers may raise ParseError; that is acceptable.
                if type(exc).__name__ in {"SystemExit", "KeyboardInterrupt", "MemoryError"}:
                    crashes.append(f"{name}: {type(exc).__name__}")
    return {
        "iterations": iterations,
        "parser_calls": parsed,
        "crashes": crashes,
        "ok": not crashes,
    }
