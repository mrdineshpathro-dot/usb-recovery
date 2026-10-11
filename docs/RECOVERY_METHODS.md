# Recovery methods

## 1. Read-only acquisition

The source is opened with `O_RDONLY`. Optional raw imaging (`image` command / GUI) copies logical sectors to a destination `.dd` file, writing zeros for unreadable sectors and recording them in `*.bad-sectors.json`. Checkpoints (`*.checkpoint.json`) allow resume. SHA-256 is computed while imaging when enabled.

## 2. Partition analysis

1. Parse the MBR at LBA 0, including extended/EBR chains.
2. If type `0xEE` or an `EFI PART` header is present, parse GPT and compare the backup header. Differences are reported; nothing is written back.
3. If both tables are absent, fall back to a super-floppy volume.
4. Overlaps are flagged. Lost-partition search looks for FAT/NTFS/exFAT boot signatures on a stride (default 2048 sectors) without repairing the table.

## 3. Filesystem metadata recovery

For each detected volume the matching parser walks directory entries or `$MFT` records:

- **Live entries** (optional) — still referenced by the filesystem.
- **Deleted entries** — marked deleted / in-use flag clear.
- **Orphan heuristic** — allocation metadata missing; contiguous clusters are read and scored lower.

Original paths are preserved when parent directories are still readable.

## 4. Signature-based carving

A versioned JSON database (`usb_recovery/data/signatures.json`) stores headers, optional footers, max sizes, and validator names. The carver slides an overlapping window so signatures that straddle a block boundary are still seen.

Supported in this release: JPEG, PNG, GIF, BMP, WebP, PDF, ZIP/OOXML (DOCX/XLSX/PPTX), RAR, 7z, OLE (legacy Office), SQLite, MP3/ID3, WAV, FLAC, MP4/MOV, AVI, MKV, PST candidate, EML candidate.

Footer-based bounds are used when present (`FFD9`, PNG `IEND`, `%%EOF`, ZIP EOCD). RIFF sizes are honoured for WAV/WEBP/AVI.

## 5. Validation vs recognition

A file can be *recognized* (header match) without being *structurally valid*. Validators:

- JPEG — SOI / SOS / EOI walk
- PNG — IHDR, IEND, per-chunk CRC32
- PDF — `%PDF-` and `%%EOF`
- ZIP — local header + EOCD; OOXML detected via `[Content_Types].xml`
- SQLite — magic and page size
- BMP / WAV / AVI / WebP / MP4 / MP3 — container headers

Validator failure sets status `partial` and lowers the heuristic score.

## 6. Confidence scoring

Scores are **explanations**, not probabilities. Bands:

| Score | Band | Meaning |
| --- | --- | --- |
| ≥ 85 | high | Metadata and allocation chain agree |
| ≥ 60 | medium | Recognizable structure, some reconstruction |
| ≥ 30 | low | Signature / heuristic only |
| < 30 | uncertain | Insufficient evidence |

Every candidate includes a `confidence_reasons` list stating *why*.

## 7. Deduplication

SHA-256 of reconstructed bytes is used to mark identical payloads. Distinct filenames are kept; duplicates are flagged, not discarded.

## 8. Advisor, reconstruction, and safer output (201–260)

- **Assistant (201–210):** offline rule engine maps symptoms (deleted / formatted / inaccessible / failing) to a scan profile and explains why TRIM, overwrite, or a dead controller cannot be undone in software.
- **Reconstruction (211–220):** hash/offset matching, recovered-vs-missing byte ranges, photo grouping, ZIP local-header salvage, document validators, and a timeline of trustworthy timestamps.
- **Flash resilience (221–230):** ASCII error heatmap, adaptive retries, stop thresholds, USB vendor lookup, reconnection identity, and a read budget for first-look assessments.
- **Output (231–240):** write `.ur-partial` then rename, ChaCha20-HMAC vault, `.recovery.json` sidecars, destination FAT32/space checks, optional second copy with explicit approval.
- **Workspace (241–250):** phrases such as `deleted jpegs larger than 1mb`, fuzzy names, bookmarks, type batches.
- **Security (251–260):** never execute recovered files; flag MZ/ELF; optional local `clamscan`; isolated preview workers; parser fuzz; HMAC/SHA-256 plugins; redacted support bundles.

## 9. Recovery and verification

Selected candidates are written to the destination with:

- no overwrite (name `(1)`, `(2)`, …)
- optional original directory hierarchy
- size check and SHA-256 of the recovered copy

The source is never opened for write during this step.

## 10. Disk-image containers

`open_source` can wrap gzip (in-memory, size-capped), fixed VHD (footer stripped), multi-part split images, and an `--image-offset` window. Dynamic/differencing VHD and full AFF4 map replay are not implemented — inspect only. `convert-image` writes **destination** copies (raw / split / gzip) and never overwrites the source. Provenance JSON sits beside the image.

## 11. Deeper analysis (optional)

Post-scan helpers: sector-alignment vs cluster size, double-read consistency, recovered-file byte maps, NFC/NFD name repair, `~$` / `.tmp` / Thumbs.db discovery, embedded JPEG thumbnails, CR2/RW2 signatures, MP4 ftyp/moov/mdat and H.264 NAL fragments, SQLite WAL / rollback journals. These explain candidates; they do not mutate the source.

## 12. Multi-evidence ranking and specialized salvage

Metadata hits, carved signatures, and structural validators are combined into an explainable rank (not a probability). Fragment graphs and reconstruction hypotheses are compared against format rules (JPEG markers, ZIP EOCD, PDF xref, OOXML relationships). ZIP/PDF repairs, if any, are applied only to an isolated copy. `$LogFile` RCRD pages are listed for timeline context and never replayed.

## 13. Repeatable analysis and evidence integrity

A versioned pipeline (`identify → partitions → metadata/carve → independent validate`) records parameters. Manifests carry SHA-256 and optional HMAC-SHA256. Format parsers can run in a resource-limited subprocess. Plugins are confined to an import/call allow-list. None of this is a chain-of-custody certificate.
