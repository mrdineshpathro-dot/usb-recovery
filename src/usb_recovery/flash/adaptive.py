"""Adaptive retries, stop thresholds, stability monitor, read budget (222, 223, 226, 229)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from usb_recovery.exceptions import StopThresholdError
from usb_recovery.models import BadSector


@dataclass
class AdaptivePolicy:
    base_retries: int = 3
    max_retries: int = 8
    base_delay_s: float = 0.05
    max_delay_s: float = 1.0
    stop_after_bad: int = 0  # 0 = disabled
    read_budget: int = 0  # 0 = unlimited
    min_block: int = 512
    max_block: int = 1_048_576
    consecutive_fail_slowdown: int = 3

    consecutive_failures: int = 0
    bad_count: int = 0
    bytes_read: int = 0
    block_size: int = 1_048_576

    def on_success(self, nbytes: int) -> None:
        self.consecutive_failures = 0
        self.bytes_read += nbytes
        self.block_size = min(self.max_block, max(self.block_size * 2, self.min_block * 8))

    def on_failure(self) -> None:
        self.consecutive_failures += 1
        self.bad_count += 1
        self.block_size = max(self.min_block, self.block_size // 2)

    def retries_now(self) -> int:
        if self.consecutive_failures >= self.consecutive_fail_slowdown:
            return min(self.max_retries, self.base_retries + self.consecutive_failures)
        return self.base_retries

    def delay_now(self) -> float:
        if self.consecutive_failures <= 1:
            return self.base_delay_s
        return min(self.max_delay_s, self.base_delay_s * (2 ** min(4, self.consecutive_failures)))

    def check_budget(self) -> None:
        if self.read_budget and self.bytes_read >= self.read_budget:
            raise StopThresholdError(
                f"Source read budget of {self.read_budget} bytes reached (initial assessment cap)"
            )

    def check_stop(self) -> None:
        if self.stop_after_bad and self.bad_count >= self.stop_after_bad:
            raise StopThresholdError(
                f"Stop threshold: {self.bad_count} unreadable regions (limit {self.stop_after_bad})"
            )


@dataclass
class StabilityMonitor:
    samples: list[tuple[float, float]] = field(default_factory=list)  # (t, bytes)
    stalls: int = 0
    timeouts: int = 0

    def mark(self, bytes_done: int) -> None:
        now = time.monotonic()
        if self.samples:
            prev_t, prev_b = self.samples[-1]
            dt = now - prev_t
            db = bytes_done - prev_b
            if dt > 5 and db == 0:
                self.stalls += 1
        self.samples.append((now, float(bytes_done)))
        if len(self.samples) > 64:
            self.samples = self.samples[-64:]

    def throughput(self) -> float:
        if len(self.samples) < 2:
            return 0.0
        t0, b0 = self.samples[0]
        t1, b1 = self.samples[-1]
        dt = max(1e-6, t1 - t0)
        return max(0.0, (b1 - b0) / dt)

    def summary(self) -> dict:
        speeds: list[float] = []
        for (t0, b0), (t1, b1) in zip(self.samples, self.samples[1:]):
            dt = t1 - t0
            if dt > 0:
                speeds.append((b1 - b0) / dt)
        return {
            "throughput_bps": self.throughput(),
            "min_bps": min(speeds) if speeds else 0.0,
            "max_bps": max(speeds) if speeds else 0.0,
            "stalls": self.stalls,
            "timeouts": self.timeouts,
            "samples": len(self.samples),
        }


def heatmap_cells(bad: list[BadSector], total_bytes: int, columns: int = 64) -> list[int]:
    if total_bytes <= 0 or columns <= 0:
        return []
    cells = [0] * columns
    span = total_bytes / columns
    for item in bad:
        idx = min(columns - 1, int(item.offset / span))
        cells[idx] += 1
    return cells
