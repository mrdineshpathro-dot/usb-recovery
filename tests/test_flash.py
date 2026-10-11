from __future__ import annotations

import pytest

from usb_recovery.exceptions import IdentityMismatchError, StopThresholdError
from usb_recovery.flash.adaptive import AdaptivePolicy, StabilityMonitor
from usb_recovery.flash.connection import diagnose_connection, identities_match, identity_from_device
from usb_recovery.flash.heatmap import render_heatmap
from usb_recovery.flash.risk import acquisition_risk_summary
from usb_recovery.flash.usbids import lookup_usb
from usb_recovery.models import BadSector, DeviceInfo


def test_adaptive_stop_and_budget() -> None:
    policy = AdaptivePolicy(stop_after_bad=2, read_budget=100)
    policy.on_failure()
    policy.check_stop()
    policy.on_failure()
    with pytest.raises(StopThresholdError):
        policy.check_stop()
    policy2 = AdaptivePolicy(read_budget=10)
    policy2.bytes_read = 10
    with pytest.raises(StopThresholdError):
        policy2.check_budget()


def test_heatmap_and_usbids() -> None:
    bad = [BadSector(lba=1, offset=100, size=512, error="eio", retries=1)]
    heat = render_heatmap(bad, 4096, columns=16, rows=2)
    assert heat["bad"] == 1
    assert heat["ascii"]
    info = lookup_usb("0781")
    assert info["known"] is True
    assert "SanDisk" in info["name"]
    assert lookup_usb("ffff")["known"] is False


def test_identity_and_risk() -> None:
    info = DeviceInfo(
        path="/dev/sdb",
        display_name="x",
        size_bytes=1000,
        sector_size=512,
        vendor="SanDisk",
        serial="ABC",
        is_physical=True,
        mountpoints=["/mnt"],
    )
    ident = identity_from_device(info)
    ok, issues = identities_match(ident, {**ident, "serial": "XYZ", "size_bytes": 1000})
    assert ok is False
    assert issues
    with pytest.raises(IdentityMismatchError):
        from usb_recovery.flash.connection import assert_same_device

        assert_same_device(ident, {**ident, "serial": "nope"})
    diag = diagnose_connection(info, io_errors=3, stalls=1)
    assert diag["clues"]
    risk = acquisition_risk_summary(info, stalls=2)
    assert "cannot predict" in risk["disclaimer"]


def test_stability_monitor() -> None:
    mon = StabilityMonitor()
    mon.mark(0)
    mon.mark(1000)
    assert mon.throughput() >= 0
    assert "throughput_bps" in mon.summary()
