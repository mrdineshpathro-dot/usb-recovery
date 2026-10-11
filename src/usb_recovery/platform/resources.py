"""Process resource snapshot (296). Stdlib only; /proc on Linux."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def resource_snapshot() -> dict:
    rss = None
    cpu = None
    io: dict | None = None
    if sys.platform.startswith("linux"):
        try:
            status = Path("/proc/self/status").read_text(encoding="utf-8", errors="replace")
            for line in status.splitlines():
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    rss = int(parts[1]) * 1024  # kB
        except OSError:
            pass
        try:
            io_text = Path("/proc/self/io").read_text(encoding="utf-8", errors="replace")
            io = {}
            for line in io_text.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    io[k.strip()] = int(v.strip())
        except OSError:
            io = None
    return {
        "pid": os.getpid(),
        "rss_bytes": rss,
        "cpu_time_s": os.times().user + os.times().system if hasattr(os, "times") else cpu,
        "io": io,
        "note": "Self-reported process stats. Not a system-wide performance warranty.",
    }
