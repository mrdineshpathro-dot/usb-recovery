"""Dataclasses shared by the engine, CLI, GUI, and reports."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Literal


ScanProfile = Literal["quick", "standard", "deep"]
CandidateMethod = Literal["metadata", "carved", "orphan", "existing"]
CandidateStatus = Literal["deleted", "existing", "carved", "partial", "unreadable"]
RecoveryStatus = Literal["pending", "recovered", "partial", "failed", "skipped"]


@dataclass
class DeviceWarning:
    code: str
    message: str
    severity: Literal["info", "warning", "danger"] = "warning"


@dataclass
class DeviceInfo:
    path: str
    display_name: str
    size_bytes: int
    sector_size: int
    bus: str = "unknown"
    removable: bool = False
    vendor: str = ""
    model: str = ""
    serial: str = ""
    revision: str = ""
    filesystem_hint: str | None = None
    mountpoints: list[str] = field(default_factory=list)
    is_image: bool = False
    is_physical: bool = False
    read_only_open: bool = True
    warnings: list[DeviceWarning] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


@dataclass
class PartitionInfo:
    index: int
    start_lba: int
    sector_count: int
    scheme: str
    type_id: str
    type_name: str
    bootable: bool = False
    filesystem: str | None = None
    label: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def start_offset(self) -> int:
        return self.start_lba * 512

    @property
    def size_bytes(self) -> int:
        return self.sector_count * 512


@dataclass
class TimestampSet:
    created: str | None = None
    modified: str | None = None
    accessed: str | None = None


@dataclass
class Candidate:
    id: str
    name: str
    size: int
    file_type: str
    mime: str
    method: CandidateMethod
    status: CandidateStatus
    source_offset: int
    confidence: float
    confidence_reasons: list[str] = field(default_factory=list)
    original_path: str | None = None
    cluster_start: int | None = None
    partition_index: int | None = None
    extension: str = ""
    timestamps: TimestampSet = field(default_factory=TimestampSet)
    is_fragmented: bool = False
    is_duplicate: bool = False
    sha256: str | None = None
    notes: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


@dataclass
class ScanOptions:
    profile: ScanProfile = "standard"
    enable_metadata: bool = True
    enable_carving: bool = True
    enable_unallocated: bool = True
    full_image_carve: bool = False
    signatures: list[str] | None = None
    sector_range: tuple[int, int] | None = None
    partition_index: int | None = None
    max_carve_size: int = 64 * 1024 * 1024
    carve_window: int = 1024 * 1024
    carve_workers: int = 1
    deduplicate: bool = True
    image_offset: int = 0
    exclude_types: list[str] | None = None
    exclude_paths: list[str] | None = None

    @classmethod
    def from_profile(cls, profile: ScanProfile) -> "ScanOptions":
        options = cls(profile=profile)
        if profile == "quick":
            options.enable_carving = False
            options.enable_unallocated = False
            options.full_image_carve = False
        elif profile == "deep":
            options.enable_carving = True
            options.enable_unallocated = True
            options.full_image_carve = True
        return options


@dataclass
class ProgressEvent:
    phase: str
    current: int
    total: int
    message: str = ""
    bytes_done: int = 0
    bytes_total: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def ratio(self) -> float:
        if self.total <= 0:
            if self.bytes_total <= 0:
                return 0.0
            return min(1.0, self.bytes_done / self.bytes_total)
        return min(1.0, self.current / self.total)


ProgressCallback = Callable[[ProgressEvent], None]


@dataclass
class BadSector:
    lba: int
    offset: int
    size: int
    error: str
    retries: int


@dataclass
class ImagingResult:
    source_path: str
    dest_path: str
    bytes_requested: int
    bytes_written: int
    bad_sectors: list[BadSector]
    sha256: str | None
    resumed: bool
    cancelled: bool
    checkpoint_path: str | None


@dataclass
class RecoveryResult:
    candidate_id: str
    dest_path: str | None
    status: RecoveryStatus
    bytes_written: int
    sha256: str | None
    error: str | None = None
    size_match: bool | None = None


@dataclass
class ByteRange:
    """A recovered or missing span inside a candidate (feature 212)."""

    start: int
    end: int
    kind: Literal["recovered", "missing", "uncertain"] = "recovered"

    @property
    def length(self) -> int:
        return max(0, self.end - self.start)


@dataclass
class Advice:
    """A recommended action from the recovery assistant (features 201–207)."""

    title: str
    summary: str
    steps: list[str] = field(default_factory=list)
    profile: ScanProfile | None = None
    methods: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Assessment:
    """Pre-recovery assessment (feature 204) plus effort estimate (205)."""

    source_path: str
    accessible: bool
    is_image: bool
    is_physical: bool
    size_bytes: int
    sector_size: int
    filesystems: list[str] = field(default_factory=list)
    mounted: bool = False
    risks: list[str] = field(default_factory=list)
    recommended_profile: ScanProfile = "standard"
    estimated_scan_s: float | None = None
    estimated_image_s: float | None = None
    estimated_dest_bytes: int | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SessionSummary:
    session_id: str
    source_path: str
    profile: str
    created_at: str
    status: str
    candidates: int = 0
    recovered: int = 0
    partial: int = 0
    failed: int = 0
    notes: list[str] = field(default_factory=list)
