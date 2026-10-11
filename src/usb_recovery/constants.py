"""Shared constants. Keep magic numbers and safety tokens in one place."""

from __future__ import annotations

APP_NAME = "USB Recovery Lab"
APP_ID = "usb-recovery-lab"
APP_VERSION = "0.1.0"

# Logical sector fallback when the OS does not expose a size.
DEFAULT_SECTOR_SIZE = 512

# MBR / GPT
MBR_SIGNATURE = b"\x55\xAA"
MBR_PARTITION_OFFSET = 446
MBR_PARTITION_ENTRY_SIZE = 16
MBR_PARTITION_COUNT = 4
GPT_SIGNATURE = b"EFI PART"
GPT_HEADER_LBA = 1
GPT_PARTITION_ENTRY_SIZE_DEFAULT = 128

# Filesystem OEM / magic
FAT32_FS_TYPE = b"FAT32   "
FAT16_FS_TYPE = b"FAT16   "
FAT12_FS_TYPE = b"FAT12   "
NTFS_OEM = b"NTFS    "
EXFAT_OEM = b"EXFAT   "
EXT_MAGIC = 0xEF53

# FAT
FAT_DIR_ENTRY_SIZE = 32
FAT_DELETED_MARK = 0xE5
FAT_ATTR_READONLY = 0x01
FAT_ATTR_HIDDEN = 0x02
FAT_ATTR_SYSTEM = 0x04
FAT_ATTR_VOLUME = 0x08
FAT_ATTR_DIRECTORY = 0x10
FAT_ATTR_ARCHIVE = 0x20
FAT_ATTR_LFN = 0x0F

FAT12_EOC = 0xFF8
FAT16_EOC = 0xFFF8
FAT32_EOC = 0x0FFFFFF8
FAT12_BAD = 0xFF7
FAT16_BAD = 0xFFF7
FAT32_BAD = 0x0FFFFFF7

# NTFS
NTFS_FILE_RECORD_MAGIC = b"FILE"
NTFS_ATTR_STANDARD_INFORMATION = 0x10
NTFS_ATTR_FILE_NAME = 0x30
NTFS_ATTR_DATA = 0x80
NTFS_ATTR_END = 0xFFFFFFFF
NTFS_FILE_IN_USE = 0x01
NTFS_FILE_DIRECTORY = 0x02

# Scan profiles (feature 081)
SCAN_PROFILES = {
    "quick": {
        "description": "Boot sectors, partition tables, and allocated metadata only.",
        "metadata": True,
        "carving": False,
        "unallocated": False,
    },
    "standard": {
        "description": "Metadata recovery plus carving of unallocated regions with common signatures.",
        "metadata": True,
        "carving": True,
        "unallocated": True,
    },
    "deep": {
        "description": "Full-image carving, metadata, and extra validators. Slow on large devices.",
        "metadata": True,
        "carving": True,
        "unallocated": True,
        "full_image": True,
    },
}

# CLI exit codes (feature 166)
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_SAFETY = 3
EXIT_SOURCE_ACCESS = 4
EXIT_DESTINATION = 5
EXIT_CANCELLED = 6
EXIT_PARTIAL = 7

# Explicit confirmation token required before opening a physical device.
DEVICE_CONFIRM_TOKEN = "I_UNDERSTAND_READ_ONLY"

# Confidence score bands. These are heuristic explanations, not probabilities.
CONFIDENCE_BANDS = (
    (85, "high", "Metadata and allocation chain are internally consistent."),
    (60, "medium", "Recognizable structure with some missing or reconstructed fields."),
    (30, "low", "Signature or heuristic match only; contents may be truncated or false-positive."),
    (0, "uncertain", "Insufficient evidence; treat as a candidate, not a recovered file."),
)
