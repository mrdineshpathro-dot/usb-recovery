# Build USB Recovery Lab for Windows with PyInstaller.
# Run from an elevated-optional, but not required, developer prompt:
#   python -m venv .venv
#   .\.venv\Scripts\Activate.ps1
#   pip install -e ".[gui]" pyinstaller
#   powershell -File scripts\build_windows.ps1
#
# The resulting dist\USBRecoveryLab.exe is NOT committed. Rebuild it yourself.

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
python -m PyInstaller --noconfirm scripts\usb-recovery.spec
Write-Host "Build output: dist\USBRecoveryLab.exe"
