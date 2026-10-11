"""Rule-based recovery assistant, strategy advisor, and decision tree (201, 202, 207, 209).

This is a deterministic advisor, not a networked model. It never claims certainty.
"""

from __future__ import annotations

from typing import Any, Iterable

from usb_recovery.models import Advice, Assessment, DeviceInfo, ScanProfile

SYMPTOMS = ("deleted", "formatted", "inaccessible", "corrupted", "unknown")

METHODS = [
    {
        "id": "metadata",
        "name": "Filesystem metadata recovery",
        "best_for": "Deleted files on FAT/exFAT/NTFS while directory or $MFT still exists",
        "limit": "Fails after format or TRIM; first FAT character is lost (0xE5)",
        "profile": "quick",
    },
    {
        "id": "carving",
        "name": "Signature-based file carving",
        "best_for": "Known formats (JPEG, PNG, PDF, ZIP) after a quick format",
        "limit": "Misses fragmented files; produces false positives; original names usually lost",
        "profile": "standard",
    },
    {
        "id": "imaging",
        "name": "Sector image then analyze",
        "best_for": "Unstable or failing flash; any high-value case",
        "limit": "Needs as much free space as the source; does not by itself recover files",
        "profile": "standard",
    },
    {
        "id": "deep-carve",
        "name": "Full-image deep carving",
        "best_for": "No usable metadata, still-readable media",
        "limit": "Slow; extra false positives; read-disturb risk on dying flash",
        "profile": "deep",
    },
]


def compare_methods() -> list[dict[str, str]]:
    return list(METHODS)


def decision_tree(symptom: str) -> Advice:
    key = (symptom or "unknown").lower().strip()
    if key in {"deleted", "accidentally deleted", "recycle"}:
        return Advice(
            title="Accidentally deleted files",
            summary="Do not save new files onto the pen drive. Metadata recovery is the first pass.",
            steps=[
                "Unmount / eject the volume.",
                "If the stick is unstable, image it onto another disk first.",
                "Run a quick metadata scan (FAT/exFAT/NTFS deleted entries).",
                "If names are missing, follow with a standard carve of unallocated space.",
                "Recover selected copies onto a different physical disk.",
            ],
            profile="quick",
            methods=["metadata", "carving"],
            warnings=["Continued use can overwrite the deleted clusters."],
            limitations=["TRIM may already have zeroed the pages on some flash controllers."],
        )
    if key in {"formatted", "quick format", "format"}:
        return Advice(
            title="Formatted volume",
            summary="A quick format often destroys names but may leave payloads. Do not format again.",
            steps=[
                "Image the device if possible.",
                "Identify the previous filesystem from leftover boot sectors.",
                "Run a standard scan (metadata remnants + carving).",
                "Use deep carving only if the first pass is empty and the device is healthy.",
            ],
            profile="standard",
            methods=["metadata", "carving", "imaging"],
            warnings=["Never run mkfs/format/repair against the source."],
            limitations=["Full overwrite formats are generally unrecoverable in software."],
        )
    if key in {"inaccessible", "unrecognized", "raw", "not recognized"}:
        return Advice(
            title="OS does not recognize the volume",
            summary="Treat this as a partition or boot-sector problem, not a reason to initialize the disk.",
            steps=[
                "Do not accept the OS offer to format.",
                "Open the device or image read-only and inspect MBR/GPT.",
                "If a FAT/NTFS/exFAT boot sector is found, scan that volume offset.",
                "Fall back to super-floppy (LBA 0) and carving.",
            ],
            profile="standard",
            methods=["imaging", "metadata", "carving"],
            warnings=["Windows 'initialize disk' is destructive."],
        )
    if key in {"corrupted", "i/o", "bad sectors", "failing"}:
        return Advice(
            title="Corrupted or failing media",
            summary="Prioritize imaging with retries and a stop threshold over a deep live scan.",
            steps=[
                "Try another cable and USB port.",
                "Image with checkpoints and a bad-sector map.",
                "Pause if errors climb; remaining data can get worse with more reads.",
                "Analyze the image, not the live stick.",
            ],
            profile="quick",
            methods=["imaging"],
            warnings=["Read disturb on NAND is real. This tool cannot predict remaining life."],
        )
    return Advice(
        title="Unknown loss scenario",
        summary="Start with a non-destructive assessment, then a quick scan of a disk image.",
        steps=[
            "Run pre-recovery assessment.",
            "Prefer working from a sector image.",
            "Quick metadata scan, then standard carving if needed.",
        ],
        profile="quick",
        methods=["imaging", "metadata", "carving"],
        limitations=["Recovery is not guaranteed in any scenario."],
    )


def advise(
    *,
    symptom: str = "unknown",
    filesystem: str | None = None,
    device: DeviceInfo | None = None,
    assessment: Assessment | None = None,
    mounted: bool | None = None,
) -> Advice:
    advice = decision_tree(symptom)
    fs = (filesystem or (assessment.filesystems[0] if assessment and assessment.filesystems else "")).lower()
    if fs in {"fat12", "fat16", "fat32"}:
        advice.steps.append("FAT deleted names lose the first character; expect _ILENAME.EXT.")
        advice.methods = ["metadata", "carving"]
    elif fs == "exfat":
        advice.steps.append("exFAT deleted entry sets clear the in-use bit; names often survive.")
    elif fs == "ntfs":
        advice.steps.append("NTFS $LogFile is not replayed. Deleted $MFT records are still scanned.")
        advice.limitations.append("Encrypted/compressed NTFS attributes are not reconstructed.")
    elif fs.startswith("ext"):
        advice.warnings.append("ext4 is detected only; inode recovery is not implemented.")
        advice.profile = "deep"
        advice.methods = ["carving"]

    is_mounted = mounted
    if is_mounted is None and device is not None:
        is_mounted = bool(device.mountpoints)
    if is_mounted:
        advice.warnings.insert(0, "Volume is mounted. Unmount before acquisition; the OS may write.")

    if device and device.warnings:
        for warn in device.warnings:
            if warn.severity == "danger":
                advice.warnings.append(warn.message)
                advice.profile = "quick"
                if "imaging" not in advice.methods:
                    advice.methods.insert(0, "imaging")

    if assessment and not assessment.accessible:
        advice.warnings.append("Source was not readable during assessment.")
        advice.profile = None
        advice.steps = ["Fix access permissions or cabling before any scan."]

    advice.extra["symptom"] = symptom
    advice.extra["filesystem"] = fs or None
    return advice


def recommend_profile(assessment: Assessment, symptom: str = "unknown") -> ScanProfile:
    advice = advise(symptom=symptom, assessment=assessment)
    return advice.profile or "standard"


def format_advice(advice: Advice) -> str:
    lines = [advice.title, advice.summary, "", "Steps:"]
    lines.extend(f"  {i}. {s}" for i, s in enumerate(advice.steps, 1))
    if advice.methods:
        lines += ["", "Methods: " + ", ".join(advice.methods)]
    if advice.profile:
        lines.append(f"Suggested scan profile: {advice.profile}")
    if advice.warnings:
        lines += ["", "Warnings:"]
        lines.extend(f"  - {w}" for w in advice.warnings)
    if advice.limitations:
        lines += ["", "Limitations:"]
        lines.extend(f"  - {x}" for x in advice.limitations)
    lines.append("Recovery is not guaranteed.")
    return "\n".join(lines)
