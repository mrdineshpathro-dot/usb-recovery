# Packaging

No `.exe` is shipped with this source tree. The commands below reproduce a Windows build.

## Windows executable (PyInstaller)

On a Windows machine with Python 3.11+:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[gui]" pyinstaller
powershell -File scripts\build_windows.ps1
```

Output: `dist\USBRecoveryLab.exe`.

Alternative one-liner:

```powershell
pyinstaller --noconfirm scripts\usb-recovery.spec
```

The GUI entry point is `usb_recovery.gui.app:main`. The CLI remains available as `usb-recovery.exe` if you add a second spec targeting `usb_recovery/cli/main.py`.

## Linux installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[gui]"          # omit [gui] on headless systems
usb-recovery list-devices
usb-recovery-gui                 # requires PySide6 and a display
```

Debian/Fedora packaging is not provided as a `.deb`/`.rpm` in this release. For a system package, wrap the same `pip install` (or install from a wheel) and ship a `.desktop` file pointing at `usb-recovery-gui`.

## Wheel

```bash
pip install build
python -m build
```

## Permissions

- Scanning a `.img` / `.dd` file: no extra rights.
- Scanning `/dev/sdX`: root or `disk` group, plus `--confirm I_UNDERSTAND_READ_ONLY`.
- Windows physical drives: run as Administrator and pass the same confirm token.
