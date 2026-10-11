"""Deep filesystem reconstruction helpers (features 321–330)."""

from usb_recovery.fsdeep.exfat_map import reconstruct_exfat_bitmap
from usb_recovery.fsdeep.fat_hist import analyze_fat_history
from usb_recovery.fsdeep.layouts import competing_layouts, scan_alternate_offsets
from usb_recovery.fsdeep.meta import (
    compare_metadata_copies,
    correlate_orphans,
    cross_validate_directory,
)
from usb_recovery.fsdeep.ntfs_rel import ntfs_journal_timeline, ntfs_record_graph
from usb_recovery.fsdeep.slack import analyze_slack

__all__ = [
    "analyze_fat_history",
    "analyze_slack",
    "compare_metadata_copies",
    "competing_layouts",
    "correlate_orphans",
    "cross_validate_directory",
    "ntfs_journal_timeline",
    "ntfs_record_graph",
    "reconstruct_exfat_bitmap",
    "scan_alternate_offsets",
]
