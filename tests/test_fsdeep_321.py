from __future__ import annotations

import struct

from usb_recovery.constants import EXFAT_OEM, NTFS_FILE_RECORD_MAGIC
from usb_recovery.devices.image import ImageSource
from usb_recovery.fsdeep.exfat_map import reconstruct_exfat_bitmap
from usb_recovery.fsdeep.fat_hist import analyze_fat_history
from usb_recovery.fsdeep.layouts import competing_layouts, scan_alternate_offsets
from usb_recovery.fsdeep.meta import compare_metadata_copies, correlate_orphans, cross_validate_directory
from usb_recovery.fsdeep.ntfs_rel import ntfs_journal_timeline, ntfs_record_graph
from usb_recovery.fsdeep.slack import analyze_slack
from usb_recovery.models import Candidate


def _c(**kwargs) -> Candidate:
    base = dict(
        id="1",
        name="a.bin",
        size=10,
        file_type="bin",
        mime="application/octet-stream",
        method="orphan",
        status="partial",
        source_offset=0,
        confidence=20,
    )
    base.update(kwargs)
    return Candidate(**base)  # type: ignore[arg-type]


def test_fat_history_slack_layouts(fat_image, mbr_image):
    with ImageSource(str(fat_image["path"])) as src:
        hist = analyze_fat_history(src)
        assert hist["ok"] is True
        assert hist["kind"] == "fat16"
        assert hist["fat_mirrors_match"] is True
        assert hist["directory"]
        copies = compare_metadata_copies(src)
        assert copies["fat_mirrors_match"] is True
        slack = analyze_slack(
            src,
            [
                _c(
                    id="s",
                    size=10,
                    source_offset=fat_image["data_offset"],
                    extra={},
                )
            ],
            cluster_size=512,
        )
        assert slack["cluster_size"] == 512
        boots = scan_alternate_offsets(src, stride=512, limit=4)
        assert any(h["filesystem"].startswith("fat") for h in boots)
    with ImageSource(str(mbr_image["path"])) as src:
        layouts = competing_layouts(src)
        assert layouts["scheme"] in {"mbr", "superfloppy", "gpt"}
        assert "partitions" in layouts


def test_ntfs_graph_journal_orphans_exfat(tmp_path):
    rec = bytearray(1024)
    rec[0:4] = NTFS_FILE_RECORD_MAGIC
    struct.pack_into("<H", rec, 0x14, 0x38)
    struct.pack_into("<H", rec, 0x16, 0x01)
    struct.pack_into("<I", rec, 0x38, 0xFFFFFFFF)
    graph = ntfs_record_graph(bytes(rec))
    assert graph["count"] >= 1
    journal = ntfs_journal_timeline(b"xxxxRCRD" + struct.pack("<Q", 99) + b"RSTR")
    assert journal["records"]
    assert journal["restart_pages"]
    dirs = [_c(id="d", name="FOLDER", file_type="dir", original_path="/FOLDER/", method="metadata", source_offset=0)]
    orphans = [_c(id="o", name="lost.bin", method="orphan", source_offset=512)]
    corr = correlate_orphans(dirs + orphans, cluster_size=512)
    assert corr and corr[0]["candidates_parents"]
    issues = cross_validate_directory(
        [_c(id="x", size=4, extra={"content": b"12345678"}, method="metadata", status="carved")]
    )
    assert issues[0]["ok"] is False
    # Minimal exFAT boot + bitmap cluster.
    boot = bytearray(4096)
    boot[3:11] = EXFAT_OEM
    struct.pack_into("<QQ", boot, 64, 0, 128)
    struct.pack_into("<IIIII", boot, 80, 1, 1, 1, 16, 3)  # fat_off, fat_len, heap_off=1, clusters=16, root=3
    boot[108] = 9  # 512-byte sectors
    boot[109] = 0  # 1 sector/cluster
    boot[110] = 1
    # cluster 2 at heap_off * 512 + 0 = 512
    boot[512] = 0x0F  # first 4 clusters allocated
    img = tmp_path / "exfat.img"
    img.write_bytes(bytes(boot) + b"\x00" * 2048)
    with ImageSource(str(img)) as src:
        bitmap = reconstruct_exfat_bitmap(src)
    assert bitmap["ok"] is True
    assert bitmap["allocated"] >= 1
