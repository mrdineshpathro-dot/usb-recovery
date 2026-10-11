"""Command-line interface (features 161–167)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from usb_recovery.constants import (
    APP_NAME,
    APP_VERSION,
    DEVICE_CONFIRM_TOKEN,
    EXIT_CANCELLED,
    EXIT_DESTINATION,
    EXIT_ERROR,
    EXIT_OK,
    EXIT_PARTIAL,
    EXIT_SAFETY,
    EXIT_SOURCE_ACCESS,
    EXIT_USAGE,
)
from usb_recovery.exceptions import (
    CancelledError,
    ConfirmationRequired,
    DestinationError,
    SafetyError,
    SourceAccessError,
)
from usb_recovery.logging_config import setup_logging
from usb_recovery.models import ScanOptions
from usb_recovery.util import human_size


def _print(payload: object, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        if isinstance(payload, list):
            for item in payload:
                print(item if isinstance(item, str) else json.dumps(item, default=str))
        else:
            print(payload if isinstance(payload, str) else json.dumps(payload, indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="usb-recovery",
        description=f"{APP_NAME} — read-only USB and disk-image recovery. Recovery is not guaranteed.",
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {APP_VERSION}")
    parser.add_argument("--json", action="store_true", help="JSON output (feature 162)")
    parser.add_argument("--db", help="SQLite session database path")
    parser.add_argument("--log-level", default="INFO")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list-devices", help="List removable USB devices")
    p.add_argument("--all", action="store_true", help="Include non-USB block devices")

    p = sub.add_parser("info", help="Show source identity, size, and warnings")
    p.add_argument("source")
    p.add_argument("--confirm", help=f"Required for physical devices: {DEVICE_CONFIRM_TOKEN}")

    p = sub.add_parser("image", help="Create a raw DD image of the source")
    p.add_argument("source")
    p.add_argument("dest")
    p.add_argument("--confirm", help=f"Required for physical devices: {DEVICE_CONFIRM_TOKEN}")
    p.add_argument("--no-resume", action="store_true")
    p.add_argument("--allow-same-device", action="store_true")
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("scan", help="Scan a device or image for recoverable files")
    p.add_argument("source")
    p.add_argument("--confirm", help=f"Required for physical devices: {DEVICE_CONFIRM_TOKEN}")
    p.add_argument("--profile", choices=["quick", "standard", "deep"], default="standard")
    p.add_argument("--no-carve", action="store_true")
    p.add_argument("--no-metadata", action="store_true")
    p.add_argument("--signatures", help="Comma-separated signature IDs")
    p.add_argument("--sector-range", help="start:end LBAs")
    p.add_argument("--image-offset", type=int, default=0, help="Byte offset of the filesystem in the image (266)")
    p.add_argument("--exclude-types", help="Comma-separated types to skip (285)")
    p.add_argument("--dry-run", action="store_true", help="Analyze but do not persist extra artifacts")

    p = sub.add_parser("recover", help="Recover selected candidate IDs from a session")
    p.add_argument("source")
    p.add_argument("--session", required=True)
    p.add_argument("--dest", required=True)
    p.add_argument("--ids", help="Comma-separated candidate IDs (default: all)")
    p.add_argument("--confirm")
    p.add_argument("--allow-same-device", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--sidecar", action="store_true", help="Write .recovery.json sidecars")
    p.add_argument("--name-template", help="Filename template, e.g. {stem}-{offset}{suffix}")

    p = sub.add_parser("report", help="Export a session report")
    p.add_argument("session")
    p.add_argument("--dest", required=True)
    p.add_argument("--format", choices=["json", "html", "csv"], default="json")

    p = sub.add_parser("gui", help="Launch the desktop interface")

    p = sub.add_parser("diagnostics", help="Write a sanitized support bundle")
    p.add_argument("--dest", default="usb-recovery-support.json")

    p = sub.add_parser("advise", help="Recovery assistant / decision tree (201, 207)")
    p.add_argument("--symptom", default="unknown", help="deleted, formatted, inaccessible, corrupted, unknown")
    p.add_argument("--filesystem", default="")

    p = sub.add_parser("assess", help="Pre-recovery assessment and effort estimate (204, 205)")
    p.add_argument("source")
    p.add_argument("--confirm")
    p.add_argument("--dest", help="Optional destination for space estimate")

    p = sub.add_parser("explain", help="Why some data cannot be recovered (203)")
    p.add_argument("--topic", default="", help="overwritten, trimmed, controller, formatted, encrypted, fragmented")

    p = sub.add_parser("diagnose", help="Plain-language error diagnosis (206)")
    p.add_argument("message")

    p = sub.add_parser("search", help="Natural-language / fuzzy search of a session (241, 242)")
    p.add_argument("session")
    p.add_argument("--query", required=True)
    p.add_argument("--fuzzy", action="store_true")

    p = sub.add_parser("lab", help="Write a synthetic practice image (255)")
    p.add_argument("--scenario", default="deleted_fat", choices=["deleted_fat", "mbr_fat", "carve_only", "gpt_empty"])
    p.add_argument("--dest", required=True)

    p = sub.add_parser("benchmark", help="Time a scan against a known image (256)")
    p.add_argument("image")
    p.add_argument("--expect", help="Comma-separated names that must be found")

    p = sub.add_parser("fuzz", help="Fuzz filesystem parsers (258)")
    p.add_argument("--iterations", type=int, default=64)

    p = sub.add_parser("cleanup-partials", help="Remove interrupted .ur-partial files (232)")
    p.add_argument("dest")

    p = sub.add_parser("inspect-image", help="Inspect image containers (267)")
    p.add_argument("source")

    p = sub.add_parser("convert-image", help="Convert split/gzip/raw images (268)")
    p.add_argument("source")
    p.add_argument("dest")
    p.add_argument("--format", dest="fmt", default="raw", choices=["raw", "split", "gzip"])

    p = sub.add_parser("compare-images", help="Compare two acquisitions (269)")
    p.add_argument("a")
    p.add_argument("b")

    p = sub.add_parser("provenance", help="Write an image provenance manifest (270)")
    p.add_argument("image")
    p.add_argument("--dest")

    p = sub.add_parser("setup", help="First-run setup checks (292)")
    p.add_argument("--dest")

    p = sub.add_parser("help-search", help="Search offline help (299)")
    p.add_argument("query", nargs="?", default="")

    p = sub.add_parser("readiness", help="Feature readiness dashboard (310)")

    p = sub.add_parser("identity-check", help="Compare two device identity snapshots (298)")
    p.add_argument("expected_json")
    p.add_argument("actual_json")

    p = sub.add_parser("evidence", help="Explain recovery evidence for a session (320)")
    p.add_argument("session")

    p = sub.add_parser("match-known", help="Search for known hashes or byte sequences (318)")
    p.add_argument("source")
    p.add_argument("--hash", dest="hashes", action="append", default=[])
    p.add_argument("--needle-hex", dest="needles", action="append", default=[])
    p.add_argument("--confirm")

    p = sub.add_parser("plan-scan", help="Adaptive scan plan and cost estimate (342, 343)")
    p.add_argument("--goal", default="general", help="photos, documents, video, audio, general")
    p.add_argument("--filesystem", default="")
    p.add_argument("--size", type=int, default=0)

    p = sub.add_parser("scorecard", help="Recovery quality scorecard vs expected files (350)")
    p.add_argument("recovered")
    p.add_argument("--expect-json", required=True)

    p = sub.add_parser("sign-manifest", help="Write a signed/checksummed evidence manifest (351)")
    p.add_argument("image")
    p.add_argument("--dest", required=True)
    p.add_argument("--key", help="HMAC key (or @path)")

    p = sub.add_parser("isolate-parse", help="Validate a file in an isolated worker (358)")
    p.add_argument("file")
    p.add_argument("--type", dest="kind", required=True)

    p = sub.add_parser("evidence-dashboard", help="Readiness and evidence dashboard (360)")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        return int(code) if isinstance(code, int) else EXIT_USAGE

    setup_logging(level=args.log_level, console=not args.json)
    from usb_recovery.api import RecoveryLab

    lab = RecoveryLab(db_path=args.db)
    as_json = bool(args.json)
    try:
        if args.cmd == "list-devices":
            devices = lab.list_devices(include_non_usb=args.all)
            if as_json:
                _print([d.to_dict() for d in devices], True)
            else:
                if not devices:
                    print("No removable devices found. You can still scan a disk image with `scan`.")
                for dev in devices:
                    warns = ", ".join(w.code for w in dev.warnings) or "none"
                    print(
                        f"{dev.path}\t{human_size(dev.size_bytes)}\t{dev.display_name}\t"
                        f"sector={dev.sector_size}\twarnings={warns}"
                    )
            return EXIT_OK

        if args.cmd == "info":
            info = lab.describe(args.source, confirm=args.confirm)
            _print(info.to_dict() if as_json else _format_info(info), as_json)
            return EXIT_OK

        if args.cmd == "image":
            if args.dry_run:
                info = lab.describe(args.source, confirm=args.confirm)
                _print(
                    {
                        "dry_run": True,
                        "source": info.path,
                        "size": info.size_bytes,
                        "dest": args.dest,
                    },
                    as_json,
                )
                return EXIT_OK
            result = lab.image(
                args.source,
                args.dest,
                confirm=args.confirm,
                resume=not args.no_resume,
                allow_same_device=args.allow_same_device,
            )
            payload = {
                "dest": result.dest_path,
                "bytes_written": result.bytes_written,
                "sha256": result.sha256,
                "bad_sectors": len(result.bad_sectors),
                "resumed": result.resumed,
            }
            _print(payload if as_json else f"Wrote {result.dest_path} sha256={result.sha256}", as_json)
            return EXIT_PARTIAL if result.bad_sectors else EXIT_OK

        if args.cmd == "scan":
            options = ScanOptions.from_profile(args.profile)
            if args.no_carve:
                options.enable_carving = False
            if args.no_metadata:
                options.enable_metadata = False
            if args.signatures:
                options.signatures = [s.strip() for s in args.signatures.split(",") if s.strip()]
            if args.sector_range:
                a, b = args.sector_range.split(":", 1)
                options.sector_range = (int(a), int(b))
            if getattr(args, "image_offset", 0):
                options.image_offset = args.image_offset
            if getattr(args, "exclude_types", None):
                options.exclude_types = [s.strip() for s in args.exclude_types.split(",") if s.strip()]
            session_id, found = lab.scan(args.source, confirm=args.confirm, options=options)
            payload = {
                "session_id": session_id,
                "count": len(found),
                "candidates": [c.to_dict() | {"extra": {k: v for k, v in c.extra.items() if k != "content"}} for c in found],
            }
            if as_json:
                _print(payload, True)
            else:
                print(f"Session {session_id}: {len(found)} candidates")
                for cand in found:
                    print(
                        f"  {cand.id}\t{cand.status:9}\t{cand.confidence:5.0f}\t"
                        f"{human_size(cand.size):>10}\t{cand.method:9}\t{cand.name}"
                    )
            return EXIT_OK

        if args.cmd == "recover":
            session = lab.store.get_session(args.session)
            if not session:
                print("Unknown session", file=sys.stderr)
                return EXIT_USAGE
            rows = lab.store.list_candidates(args.session)
            wanted = {s.strip() for s in args.ids.split(",")} if args.ids else None
            from usb_recovery.models import Candidate, TimestampSet

            cands: list[Candidate] = []
            for row in rows:
                if wanted and row["id"] not in wanted:
                    continue
                cands.append(
                    Candidate(
                        id=row["id"],
                        name=row["name"],
                        size=row["size"] or 0,
                        file_type=row["file_type"] or "",
                        mime=row["mime"] or "",
                        method=row["method"] or "carved",
                        status=row["status"] or "carved",
                        source_offset=row["source_offset"] or 0,
                        confidence=row["confidence"] or 0,
                        original_path=row["original_path"],
                        sha256=row["sha256"],
                        timestamps=TimestampSet(),
                    )
                )
            if args.dry_run:
                _print({"dry_run": True, "count": len(cands), "dest": args.dest}, as_json)
                return EXIT_OK
            results = lab.recover(
                args.source,
                cands,
                args.dest,
                confirm=args.confirm,
                session_id=args.session,
                allow_same_device=args.allow_same_device,
                write_sidecars=bool(args.sidecar),
                filename_template=args.name_template,
            )
            recovered = sum(1 for r in results if r.status == "recovered")
            payload = {"recovered": recovered, "total": len(results), "results": [r.__dict__ for r in results]}
            _print(payload if as_json else f"Recovered {recovered}/{len(results)} files into {args.dest}", as_json)
            return EXIT_OK if recovered == len(results) else EXIT_PARTIAL

        if args.cmd == "report":
            path = lab.export_report(args.session, args.dest, fmt=args.format)
            _print({"path": str(path)} if as_json else f"Wrote {path}", as_json)
            return EXIT_OK

        if args.cmd == "gui":
            from usb_recovery.gui.app import main as gui_main

            return gui_main()

        if args.cmd == "diagnostics":
            from usb_recovery.diagnostics import write_support_bundle

            path = write_support_bundle(Path(args.dest))
            _print({"path": str(path)} if as_json else f"Wrote {path}", as_json)
            return EXIT_OK

        if args.cmd == "advise":
            from usb_recovery.advisor.assistant import advise, format_advice

            advice = advise(symptom=args.symptom, filesystem=args.filesystem or None)
            _print(advice.to_dict() if as_json else format_advice(advice), as_json)
            return EXIT_OK

        if args.cmd == "assess":
            assessment = lab.assess(args.source, confirm=args.confirm, dest=args.dest)
            _print(assessment.to_dict() if as_json else json.dumps(assessment.to_dict(), indent=2), as_json)
            return EXIT_OK

        if args.cmd == "explain":
            from usb_recovery.advisor.explain import explain_limitations

            items = explain_limitations(args.topic or None)
            _print(items if as_json else "\n\n".join(f"{i['title']}\n{i['summary']}\n{i['advice']}" for i in items), as_json)
            return EXIT_OK

        if args.cmd == "diagnose":
            from usb_recovery.advisor.explain import diagnose_error

            result = diagnose_error(args.message)
            _print(result if as_json else result["explanation"] + "\n" + "\n".join(result["steps"]), as_json)
            return EXIT_OK

        if args.cmd == "search":
            from usb_recovery.models import Candidate, TimestampSet
            from usb_recovery.workspace.search import fuzzy_search, natural_search

            rows = lab.store.list_candidates(args.session)
            cands = [
                Candidate(
                    id=r["id"],
                    name=r["name"] or "",
                    size=r["size"] or 0,
                    file_type=r["file_type"] or "",
                    mime=r["mime"] or "",
                    method=r["method"] or "carved",
                    status=r["status"] or "carved",
                    source_offset=r["source_offset"] or 0,
                    confidence=r["confidence"] or 0,
                    original_path=r["original_path"],
                    sha256=r["sha256"],
                    timestamps=TimestampSet(),
                    extension=(r["name"] or "").rsplit(".", 1)[-1].lower() if r["name"] and "." in r["name"] else "",
                )
                for r in rows
            ]
            found = fuzzy_search(cands, args.query) if args.fuzzy else natural_search(cands, args.query)
            payload = [{"id": c.id, "name": c.name, "status": c.status, "size": c.size} for c in found]
            _print(payload if as_json else "\n".join(f"{c.id}\t{c.name}" for c in found) or "(none)", as_json)
            return EXIT_OK

        if args.cmd == "lab":
            from usb_recovery.lab.synthetic import write_scenario

            meta = write_scenario(args.scenario, Path(args.dest))
            _print({"path": str(meta["path"]), "scenario": args.scenario} if as_json else f"Wrote {meta['path']}", as_json)
            return EXIT_OK

        if args.cmd == "benchmark":
            from usb_recovery.lab.benchmark import run_benchmark

            expect = [s.strip() for s in args.expect.split(",")] if args.expect else None
            result = run_benchmark(Path(args.image), expect_names=expect)
            _print(result, as_json)
            return EXIT_OK if result["regression_ok"] else EXIT_PARTIAL

        if args.cmd == "fuzz":
            from usb_recovery.lab.fuzz import fuzz_parsers

            result = fuzz_parsers(iterations=args.iterations)
            _print(result, as_json)
            return EXIT_OK if result["ok"] else EXIT_ERROR

        if args.cmd == "cleanup-partials":
            from usb_recovery.output.transaction import cleanup_partials

            removed = cleanup_partials(args.dest)
            _print({"removed": removed} if as_json else f"Removed {len(removed)} partial files", as_json)
            return EXIT_OK

        if args.cmd == "inspect-image":
            from usb_recovery.images.inspect import inspect_container

            _print(inspect_container(args.source), as_json)
            return EXIT_OK

        if args.cmd == "convert-image":
            from usb_recovery.images.convert import convert_image

            result = convert_image(args.source, args.dest, fmt=args.fmt)
            _print(result, as_json)
            return EXIT_OK

        if args.cmd == "compare-images":
            from usb_recovery.images.compare import compare_images

            _print(compare_images(args.a, args.b), as_json)
            return EXIT_OK

        if args.cmd == "provenance":
            from usb_recovery.images.provenance import write_provenance

            path = write_provenance(args.image, args.dest)
            _print({"path": str(path)} if as_json else f"Wrote {path}", as_json)
            return EXIT_OK

        if args.cmd == "setup":
            from usb_recovery.platform.wizard import first_run_checks

            _print(first_run_checks(args.dest), as_json)
            return EXIT_OK

        if args.cmd == "help-search":
            from usb_recovery.platform.help import search_help

            hits = search_help(args.query)
            _print(hits if as_json else "\n\n".join(f"{h['title']}\n{h['text']}" for h in hits), as_json)
            return EXIT_OK

        if args.cmd == "readiness":
            from usb_recovery.devtools.readiness import feature_readiness

            _print(feature_readiness(), as_json)
            return EXIT_OK

        if args.cmd == "identity-check":
            from usb_recovery.flash.connection import identities_match

            expected = json.loads(Path(args.expected_json).read_text(encoding="utf-8"))
            actual = json.loads(Path(args.actual_json).read_text(encoding="utf-8"))
            ok, issues = identities_match(expected, actual)
            _print({"ok": ok, "issues": issues}, as_json)
            return EXIT_OK if ok else EXIT_SAFETY

        if args.cmd == "evidence":
            from usb_recovery.advanced.evidence import explain_evidence
            from usb_recovery.models import Candidate, TimestampSet

            rows = lab.store.list_candidates(args.session)
            cands = [
                Candidate(
                    id=r["id"],
                    name=r["name"] or "",
                    size=r["size"] or 0,
                    file_type=r["file_type"] or "",
                    mime=r["mime"] or "",
                    method=r["method"] or "carved",
                    status=r["status"] or "carved",
                    source_offset=r["source_offset"] or 0,
                    confidence=r["confidence"] or 0,
                    original_path=r["original_path"],
                    sha256=r["sha256"],
                    timestamps=TimestampSet(),
                )
                for r in rows
            ]
            _print(explain_evidence(cands), as_json)
            return EXIT_OK

        if args.cmd == "match-known":
            from usb_recovery.advanced.known import match_known_content
            from usb_recovery.devices.detector import open_source

            needles = [bytes.fromhex(n) for n in args.needles if n]
            with open_source(args.source, confirm=args.confirm) as src:
                result = match_known_content(source=src, hashes=args.hashes, needles=needles)
            _print(result, as_json)
            return EXIT_OK if result["hashes"] or result["sequences"] else EXIT_PARTIAL

        if args.cmd == "plan-scan":
            from usb_recovery.intel.reports import strategy_report

            report = strategy_report(
                goal=args.goal,
                filesystem=args.filesystem or None,
                size_bytes=args.size,
            )
            _print(report, as_json)
            return EXIT_OK

        if args.cmd == "scorecard":
            from usb_recovery.intel.scorecard import quality_scorecard

            expected = json.loads(Path(args.expect_json).read_text(encoding="utf-8"))
            if isinstance(expected, dict):
                expected = expected.get("files") or expected.get("expected") or []
            _print(quality_scorecard(args.recovered, expected), as_json)
            return EXIT_OK

        if args.cmd == "sign-manifest":
            from usb_recovery.forensics.manifest import sign_manifest
            from usb_recovery.util import sha256_file

            key = None
            if args.key:
                key = Path(args.key[1:]).read_bytes() if args.key.startswith("@") else args.key.encode()
            payload = {
                "image": args.image,
                "sha256_image": sha256_file(args.image) if Path(args.image).is_file() else None,
            }
            path = sign_manifest(payload, args.dest, key=key)
            _print({"path": str(path)} if as_json else f"Wrote {path}", as_json)
            return EXIT_OK

        if args.cmd == "isolate-parse":
            from usb_recovery.forensics.isolate import isolate_validate

            data = Path(args.file).read_bytes()
            result = isolate_validate(args.kind, data)
            _print(result, as_json)
            return EXIT_OK if result.get("ok") else EXIT_PARTIAL

        if args.cmd == "evidence-dashboard":
            from usb_recovery.forensics.dashboard import evidence_dashboard

            _print(evidence_dashboard(), as_json)
            return EXIT_OK

        return EXIT_USAGE
    except ConfirmationRequired as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_SAFETY
    except SafetyError as exc:
        print(f"Safety: {exc}", file=sys.stderr)
        return EXIT_SAFETY
    except SourceAccessError as exc:
        print(f"Source: {exc}", file=sys.stderr)
        return EXIT_SOURCE_ACCESS
    except DestinationError as exc:
        print(f"Destination: {exc}", file=sys.stderr)
        return EXIT_DESTINATION
    except CancelledError:
        return EXIT_CANCELLED
    except KeyboardInterrupt:
        return EXIT_CANCELLED
    except Exception as exc:  # pragma: no cover - last resort
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_ERROR


def _format_info(info) -> str:
    lines = [
        f"Path:        {info.path}",
        f"Name:        {info.display_name}",
        f"Size:        {human_size(info.size_bytes)} ({info.size_bytes} bytes)",
        f"Sector:      {info.sector_size}",
        f"Bus:         {info.bus}",
        f"Removable:   {info.removable}",
        f"Physical:    {info.is_physical}",
        f"Image:       {info.is_image}",
        f"Mounts:      {', '.join(info.mountpoints) or '-'}",
    ]
    for warn in info.warnings:
        lines.append(f"Warning ({warn.severity}/{warn.code}): {warn.message}")
    lines.append(
        "Note: opening a device read-only does not guarantee the OS or USB bridge will not write."
    )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
