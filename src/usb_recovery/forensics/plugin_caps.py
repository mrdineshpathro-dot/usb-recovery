"""Recovery plugin capability controls (359)."""

from __future__ import annotations

import ast
from pathlib import Path

from usb_recovery.devtools.plugin_api import PLUGIN_API, check_plugin_api

ALLOWED_IMPORT_PREFIXES = (
    "__future__",
    "usb_recovery.carving",
    "usb_recovery.models",
    "usb_recovery.intel",
    "usb_recovery.advanced",
    "usb_recovery.special",
    "usb_recovery.util",
    "json",
    "math",
    "re",
    "struct",
    "hashlib",
    "pathlib",
    "typing",
    "dataclasses",
    "collections",
)

FORBIDDEN_CALLS = {
    "os.remove",
    "os.unlink",
    "os.rmdir",
    "shutil.rmtree",
    "subprocess.Popen",
    "subprocess.call",
    "socket.socket",
    "ctypes.CDLL",
}

ALLOWED_CAPABILITIES = frozenset({"validate", "classify", "score", "report"})


def check_plugin_capabilities(path: str | Path, *, requested: list[str] | None = None) -> dict:
    """Restrict plugins to explicitly approved operations and import surfaces."""
    api = check_plugin_api(path)
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    issues: list[str] = []
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return {**api, "allowed": False, "issues": [f"syntax error: {exc}"]}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if not _import_ok(alias.name):
                    issues.append(f"import not allowed: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if not _import_ok(mod):
                issues.append(f"import not allowed: {mod}")
        elif isinstance(node, ast.Call):
            name = _call_name(node)
            if name in FORBIDDEN_CALLS:
                issues.append(f"forbidden call: {name}")
    req = list(requested or [])
    extra = [c for c in req if c not in ALLOWED_CAPABILITIES]
    if extra:
        issues.append(f"capabilities not granted: {extra}")
    return {
        **api,
        "allowed": api.get("compatible") and not issues,
        "issues": issues,
        "requested": req,
        "granted": [c for c in req if c in ALLOWED_CAPABILITIES] if req else sorted(ALLOWED_CAPABILITIES),
        "plugin_api": PLUGIN_API,
        "note": "Plugins cannot open the source for write and cannot use subprocess/socket/ctypes.",
    }


def _import_ok(name: str) -> bool:
    if not name:
        return True
    return any(name == p or name.startswith(p + ".") for p in ALLOWED_IMPORT_PREFIXES)


def _call_name(node: ast.Call) -> str:
    func = node.func
    parts: list[str] = []
    while isinstance(func, ast.Attribute):
        parts.append(func.attr)
        func = func.value
    if isinstance(func, ast.Name):
        parts.append(func.id)
    return ".".join(reversed(parts))
