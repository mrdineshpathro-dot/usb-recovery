# Safety model

USB Recovery Lab is a **read-only recovery application**. It is not a disk repair utility and it is not a guarantee of success.

## Mandatory controls (always on)

1. The original source is opened with `O_RDONLY` (`GENERIC_READ` on Windows). The code path never adds `O_RDWR` / `O_WRONLY`.
2. Recovered files, logs, reports, and disk images are written only to a caller-supplied destination.
3. The source path cannot be used as the destination.
4. By default the destination must live on a different physical device (`st_dev` / `st_rdev` comparison). Override with `--allow-same-device` only if you accept the risk.
5. Destructive commands (`mkfs`, `format`, `diskpart clean`, `wipefs`, `dd of=`, …) are refused if they are ever passed through the safety helper.
6. Physical devices require an explicit confirmation token: `I_UNDERSTAND_READ_ONLY`.
7. Unreadable sectors are recorded; they are never “repaired” on the source.
8. Recovered files are never executed and never uploaded.
9. Logs record paths, offsets, hashes, and status — not file contents.
10. Recovery is reported honestly: partial, carved, heuristic, and failed states are first-class.

## What read-only does *not* guarantee

A read-only file descriptor does **not** mean the operating system, USB bridge, or NAND controller will perform zero writes.

| Layer | Residual write risk |
| --- | --- |
| Mounted volume | Journal, access timestamps, Windows Recycle Bin, thumbnail caches |
| USB mass-storage bridge | Some bridges remap, wear-level, or cache writes independently of the host |
| Failing flash | Read disturb and controller retries can destroy remaining pages |
| Host OS | Automount, indexer, antivirus scanning of the live volume |

**Recommendation:** unmount / eject the volume, create a raw image on a healthy disk, and run all further analysis against the image. For high-value forensic work use a hardware write blocker and a controlled acquisition environment. This application does not replace that process.

## Privileges

- **Disk images:** no administrator/root rights.
- **Linux `/dev/sdX`:** typically root or membership in the `disk` group.
- **Windows `\\.\PhysicalDriveN` / `\\.\X:`:** typically Administrator.

The application never attempts to escalate privileges on its own.

## Unstable devices

If more than `safety.unstable_device_bad_sector_threshold` (default 64) sectors fail, a warning is logged recommending that you stop. Continued reads of dying flash can make remaining data unrecoverable.
