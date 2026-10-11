# Troubleshooting

## Access denied / permission error

**Linux:** the account cannot open `/dev/sdX`. Unmount the volume (`udisksctl unmount -b /dev/sdX1`), then rerun with `sudo` or add the user to group `disk` and re-login.

**Windows:** open an elevated terminal. Use `\\.\PhysicalDriveN` or `\\.\E:`. Consumer “quick format” recovery still needs that handle.

The application will not try to bypass OS access controls.

## Device not listed

Only removable / USB-looking block devices are shown by default. Use:

```bash
usb-recovery list-devices --all
```

or open a disk image with `usb-recovery scan path/to/image.dd`.

## Unreadable sectors / failing stick

Stop a deep scan. Image with retries:

```bash
usb-recovery image /dev/sdb ~/safe-disk/stick.dd --confirm I_UNDERSTAND_READ_ONLY
```

Inspect `stick.dd.bad-sectors.json`. If the count is high, further reads may destroy remaining data.

Imaging can be resumed; checkpoint files are `*.checkpoint.json`.

## Corrupted or truncated image

If the image size is not a multiple of 512 bytes a warning is attached and trailing bytes are ignored. GPT/MBR parse errors are reported in the session log; the engine falls back to super-floppy mode rather than aborting.

## “No candidates”

- Try `--profile deep` (full-image carving).
- Confirm the image actually contains the filesystem you expect (`usb-recovery info`).
- Carving only finds formats in `signatures.json`. Add a user JSON and point to it in a future session, or recover by metadata if the directory is intact.

## Insufficient destination space

The engine estimates bytes needed from candidate sizes and refuses to start if `statvfs` / `GetDiskFreeSpaceEx` reports less free space. Free space or choose another disk. Never target the source pen drive.

## Same-device protection tripped

Recovered files would have been written onto the source disk. Choose a destination on another drive, or (at your own risk) `--allow-same-device`.

## GUI will not start

PySide6 is missing or there is no display:

```bash
pip install 'usb-recovery-lab[gui]'
# or
pip install PySide6
```

The CLI does not need PySide6.

## False-positive carved files

Signature carving produces candidates, not proven files. Check the confidence reasons, run the HTML/JSON report, and open recovered copies with a viewer — never execute them.
