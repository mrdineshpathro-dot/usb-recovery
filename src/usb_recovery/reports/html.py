"""HTML session report. Paths and hashes only — never file contents."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from usb_recovery.constants import APP_NAME, APP_VERSION
from usb_recovery.util import human_size, isoformat


def render_html_report(
    session: dict[str, Any],
    candidates: list[dict[str, Any]],
    events: list[dict[str, Any]],
    recoveries: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    extra = extra or {}
    rows = []
    for item in candidates:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(item.get('name') or ''))}</td>"
            f"<td>{html.escape(str(item.get('original_path') or ''))}</td>"
            f"<td>{human_size(int(item.get('size') or 0))}</td>"
            f"<td>{html.escape(str(item.get('file_type') or ''))}</td>"
            f"<td>{html.escape(str(item.get('method') or ''))}</td>"
            f"<td>{html.escape(str(item.get('status') or ''))}</td>"
            f"<td>{float(item.get('confidence') or 0):.0f}</td>"
            f"<td><code>{html.escape(str(item.get('sha256') or ''))}</code></td>"
            "</tr>"
        )
    event_rows = "".join(
        f"<li>[{html.escape(e.get('ts') or '')}] {html.escape(e.get('level') or '')} "
        f"{html.escape(e.get('category') or '')}: {html.escape(e.get('message') or '')}</li>"
        for e in events
    )
    recovered = sum(1 for r in (recoveries or []) if r.get("status") == "recovered")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>{html.escape(APP_NAME)} report</title>
<style>
body {{ font-family: ui-sans-serif, system-ui, sans-serif; background:#0f1419; color:#e6edf3; margin:2rem; }}
h1,h2 {{ color:#79c0ff; }}
table {{ border-collapse: collapse; width:100%; }}
th,td {{ border:1px solid #30363d; padding:6px 8px; font-size:14px; }}
th {{ background:#161b22; text-align:left; }}
code {{ font-size:12px; }}
.banner {{ background:#3d2a00; padding:12px; border:1px solid #d29922; margin-bottom:1.5rem; }}
</style></head><body>
<div class="banner">Recovery is not guaranteed. Confidence scores are heuristic explanations,
not probabilities. This report does not contain recovered file contents.</div>
<h1>{html.escape(APP_NAME)} session report</h1>
<p>Generated {html.escape(isoformat())} · version {html.escape(APP_VERSION)}</p>
<h2>Session</h2>
<ul>
<li>ID: <code>{html.escape(str(session.get('id') or ''))}</code></li>
<li>Source: <code>{html.escape(str(session.get('source_path') or ''))}</code></li>
<li>Profile: {html.escape(str(session.get('profile') or ''))}</li>
<li>Status: {html.escape(str(session.get('status') or ''))}</li>
<li>Candidates: {len(candidates)} · Recovered: {recovered}</li>
</ul>
<h2>Candidates</h2>
<table><thead><tr>
<th>Name</th><th>Original path</th><th>Size</th><th>Type</th><th>Method</th><th>Status</th><th>Score</th><th>SHA-256</th>
</tr></thead><tbody>
{''.join(rows) or '<tr><td colspan="8">None</td></tr>'}
</tbody></table>
<h2>Event log</h2>
<ul>{event_rows or '<li>No events</li>'}</ul>
<p style="margin-top:2rem;color:#8b949e">Offline report. USB Recovery Lab never uploads recovered data.</p>
</body></html>
"""


def write_html_report(path: Path, **kwargs: Any) -> Path:
    path.write_text(render_html_report(**kwargs), encoding="utf-8")
    return path
