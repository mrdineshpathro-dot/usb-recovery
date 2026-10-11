# PyInstaller spec for USB Recovery Lab (Windows).
# Build from the project root:
#   pyinstaller scripts/usb-recovery.spec
# This spec is provided so you can reproduce an .exe. This repository does not
# ship a pre-built executable.

from pathlib import Path

block_cipher = None
project = Path(SPECPATH).resolve().parents[1]  # noqa: F821
src = project / "src"

a = Analysis(  # noqa: F821
    [str(src / "usb_recovery" / "gui" / "app.py")],
    pathex=[str(src)],
    binaries=[],
    datas=[
        (str(src / "usb_recovery" / "data" / "signatures.json"), "usb_recovery/data"),
        (str(project / "config" / "default.toml"), "config"),
    ],
    hiddenimports=["usb_recovery", "usb_recovery.gui.app"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="USBRecoveryLab",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
