# Feature implementation matrix (IDs 001–360)

Status key:

- **done** — implemented and covered by tests or a deterministic code path
- **partial** — present with documented limitations
- **stub** — interface only / not in this MVP
- **unsupported** — out of scope for this release

Dependencies listed are other catalog IDs that the feature needs.

## Category A — Device detection and safe acquisition

| ID | Feature | Status | Module | Deps |
| --- | --- | --- | --- | --- |
| 001 | Automatic USB pen drive detection | done | `devices/linux.py`, `devices/windows.py` | 002 |
| 002 | Device identity and capacity | done | `devices/*`, `models.DeviceInfo` | |
| 003 | Read-only device access layer | done | `devices/base.py`, `safety.py` | |
| 004 | Safe volume unmounting/locking | partial | warns if mounted; does not unmount automatically | 003 |
| 005 | Logical sector-size detection | done | sysfs `logical_block_size`; 512 fallback | 002 |
| 006 | USB bridge/controller info | partial | sysfs vendor/model/rev when exposed | 001 |
| 007 | Raw DD disk-image creation | done | `imaging/dd.py` | 003,016 |
| 008 | E01 forensic imaging | unsupported | needs an external EWF tool | 007 |
| 009 | Resumable disk imaging | done | `*.checkpoint.json` | 007 |
| 010 | Configurable retry policy | done | `safety.bad_sector_retries` | 007 |
| 011 | Bad-sector map | done | `*.bad-sectors.json` | 007,010 |
| 012 | Imaging progress / speed / ETA | done | `ProgressEvent.extra` | 007 |
| 013 | Source-reading hash | done | SHA-256 while imaging | 007 |
| 014 | Disk-image integrity hashing | done | same digest on destination | 013 |
| 015 | Image verification vs manifest | partial | hash compared at recover time; no separate E01 manifest | 014 |
| 016 | Source/destination same-device protection | done | `safety.assert_destination_safe` | |
| 017 | Destination capacity estimation | done | `statvfs` / `GetDiskFreeSpaceEx` | 016 |
| 018 | Safe cancellation and checkpoints | done | `CancelledError` + checkpoint | 009 |
| 019 | Acquisition event log | done | SQLite `events` + rotating log | |
| 020 | Warnings for unsupported/unsafe devices | done | `DeviceWarning` | 002 |

## Category B — Partition and volume analysis

| ID | Feature | Status | Module | Deps |
| --- | --- | --- | --- | --- |
| 021 | MBR analysis | done | `partitions/mbr.py` | |
| 022 | GPT analysis | done | `partitions/gpt.py` | |
| 023 | Backup GPT comparison | done | `compare_backup` — no repair | 022 |
| 024 | Lost-partition boundary search | partial | `search_lost_partitions` stride scan | 034 |
| 025 | Deleted partition-entry analysis | partial | empty MBR slots noted; no undelete write | 021 |
| 026 | Overlapping partition detection | done | `detect_overlaps` | 021,022 |
| 027 | Unallocated-space analysis | done | `unallocated_ranges` | 021,022 |
| 028 | FS boot-sector backup detection | partial | FAT32 backup boot compared | 029 |
| 029 | FAT boot-sector analysis | done | `filesystems/fat.py` | |
| 030 | NTFS boot-sector analysis | done | `filesystems/ntfs.py` | |
| 031 | exFAT boot-sector analysis | done | `filesystems/exfat.py` | |
| 032 | Partition-boundary estimation | partial | heuristic LBA from boot signatures | 024 |
| 033 | Multi-LUN USB inspection | stub | | 001 |
| 034 | Automatic filesystem identification | done | `filesystems/identifier.py` | |
| 035 | Custom partition-offset scanning | partial | volume offset is an argument | 034 |
| 036 | User-defined sector-range scanning | done | `ScanOptions.sector_range` / `--sector-range` | |
| 037 | Separate scans per partition | done | engine loops partitions | 021,022 |
| 038 | Full-image scanning | done | `--profile deep` | 061 |
| 039 | Partition-table report export | partial | included in JSON/HTML session report | 121 |
| 040 | Visual partition map | partial | GUI source page text; no canvas widget | |

## Category C — Filesystem metadata recovery

| ID | Feature | Status | Module | Deps |
| --- | --- | --- | --- | --- |
| 041 | FAT12/FAT16 metadata | done | `filesystems/fat.py` | 029 |
| 042 | FAT32 deleted-entry recovery | done | same | 029 |
| 043 | exFAT deleted-entry recovery | done | `filesystems/exfat.py` | 031 |
| 044 | NTFS $MFT analysis | partial | FILE records, not attribute lists | 030 |
| 045 | NTFS journal analysis | unsupported | read-only limitation | 044 |
| 046 | NTFS ADS detection | partial | stream names recorded, data not always extracted | 044 |
| 047 | Long filename reconstruction | done | VFAT LFN | 041 |
| 048 | Directory-tree reconstruction | done | FAT/exFAT walk | 041 |
| 049 | Original path preservation | done | `Candidate.original_path` | 048 |
| 050 | Deleted-directory reconstruction | partial | deleted dirs walked when cluster known | 048 |
| 051 | Original filename recovery | done | when metadata survives | 047 |
| 052 | FAT cluster-chain reconstruction | done | plus contiguous heuristic | 041 |
| 053 | NTFS runlist reconstruction | done | `parse_runlist` | 044 |
| 054 | Orphan cluster identification | partial | leftover clusters found via carving | 061 |
| 055 | Lost cluster-chain analysis | partial | short chains padded, marked heuristic | 052 |
| 056 | Original timestamp preservation | done | DOS / exFAT / FILETIME when valid | |
| 057 | File allocation map analysis | partial | FAT table read; no GUI map | 052 |
| 058 | Fragmented FAT reconstruction | partial | follows chain when present | 052 |
| 059 | ext2/3/4 detection | partial | magic only | 034 |
| 060 | Metadata consistency checks | partial | FAT32 backup boot, GPT backup | |

## Category D — File carving and format recognition

| ID | Feature | Status | Module | Deps |
| --- | --- | --- | --- | --- |
| 061 | Generic signature carving | done | `carving/carver.py` | 188 |
| 062 | User-defined signature DB | partial | JSON load path supported | 188 |
| 063 | JPEG recovery | done | signature + validator | 061 |
| 064 | PNG/GIF/BMP/WebP | done | | 061 |
| 065 | PDF recovery | done | | 061 |
| 066 | DOCX/XLSX/PPTX | done | ZIP + `[Content_Types].xml` | 068 |
| 067 | Legacy Office (OLE) | partial | header detection, no OLE parse | 061 |
| 068 | ZIP/RAR/7z | partial | ZIP validated; RAR/7z header only | 061 |
| 069 | TXT/CSV/LOG | partial | metadata names; no generic text carve | |
| 070 | MP3/WAV/FLAC | partial | headers/validators | 061 |
| 071 | MP4/MOV/AVI/MKV | partial | ftyp / RIFF / EBML headers | 061 |
| 072 | SQLite recovery | done | magic + page size | 061 |
| 073 | PST/OST candidate | partial | `!BDN` header | 061 |
| 074 | EML candidate | partial | `From: ` header | 061 |
| 075 | Source-code file recovery | stub | | |
| 076 | Nested archive inspection | stub | | 068 |
| 077 | Footer-based bounds | done | JPEG/PNG/PDF/ZIP | 061 |
| 078 | Header/footer consistency | done | validators | 077 |
| 079 | Fragmented carving heuristics | stub | | 061 |
| 080 | Entropy-assisted unknown binary | stub | | |

## Category E — Advanced scan and file analysis

| ID | Feature | Status | Module | Deps |
| --- | --- | --- | --- | --- |
| 081 | Quick/standard/deep profiles | done | `ScanOptions.from_profile` | |
| 082 | Multi-pass strategy | partial | metadata then carve | 081 |
| 083 | Scan-region prioritization | partial | unallocated then volumes | 027 |
| 084 | Parallel CPU scanning | stub | `carve_workers` reserved | |
| 085 | GPU signature matching | unsupported | | |
| 086 | Duplicate-content detection | done | SHA-256 | |
| 087 | False-positive filtering | partial | validators drop/penalize | 078 |
| 088 | Fragment grouping | stub | | |
| 089 | Entropy classification | stub | | |
| 090 | Corrupted-file repair on copy | unsupported | never mutates source; no auto-repair | |
| 091 | JPEG structure validation | done | `validators.validate_jpeg` | 063 |
| 092 | PNG integrity validation | done | CRC | 064 |
| 093 | PDF structure validation | done | | 065 |
| 094 | ZIP CRC / EOCD validation | partial | EOCD required; per-file CRC not fully walked | 068 |
| 095 | SQLite integrity on a copy | partial | header check only | 072 |
| 096 | Archive metadata extraction | partial | OOXML subtype | 066 |
| 097 | MIME type detection | done | signature MIME | 061 |
| 098 | Extension mismatch detection | partial | OOXML subtype vs .zip | |
| 099 | Conflicting signature detection | partial | RIFF WAV/WEBP/AVI disambiguation | |
| 100 | Explainable confidence scoring | done | `recovery/confidence.py` | |

## Category F — Recovery and preview workflow

| ID | Feature | Status | Module | Deps |
| --- | --- | --- | --- | --- |
| 101 | Selectable file tree / table | done | GUI table + CLI `--ids` | 141 |
| 102 | File-type filters | done | GUI combo | 141 |
| 103 | File-size filters | stub | | |
| 104 | Deleted/existing/carved filters | done | GUI filter | |
| 105 | Timestamp filters | stub | timestamps stored | 056 |
| 106 | Filename/path search | done | GUI search box | |
| 107 | Image preview | done | QImage from buffered bytes | |
| 108 | Plain-text preview | done | | |
| 109 | Read-only hex viewer | done | 512-byte dump in preview | |
| 110 | Metadata preview | done | confidence reasons | |
| 111 | Thumbnail cache | stub | | 107 |
| 112 | Destination folder selector | done | GUI + CLI `--dest` | 016 |
| 113 | Recreate original hierarchy | done | `recreate_directory_hierarchy` | 049 |
| 114 | Filename-collision handling | done | `{stem} (n){suffix}` | 115 |
| 115 | No-overwrite-by-default | done | | |
| 116 | Persistent recovery queue | partial | SQLite `recovery_queue` | 176 |
| 117 | Batch file recovery | done | | |
| 118 | Partial-recovery status | done | `RecoveryResult.status` | |
| 119 | Source vs recovered comparison | partial | size + hash | 120 |
| 120 | Size and hash verification | done | `recovery/verify.py` | |

## Category G — Reporting and digital forensics

| ID | Feature | Status | Module | Deps |
| --- | --- | --- | --- | --- |
| 121 | HTML session reports | done | `reports/html.py` | |
| 122 | PDF report export | stub | | 121 |
| 123 | CSV report export | done | | |
| 124 | JSON report export | done | | |
| 125 | Per-file recovery status | done | report rows + queue | |
| 126 | SHA-256 recovery manifest | partial | hashes in JSON/CSV | 120 |
| 127 | Event timeline | partial | event list in reports | 129 |
| 128 | Device-information snapshot | done | `devices_snapshot` | 002 |
| 129 | Scan event logging | done | SQLite `events` | |
| 130 | Structured error logs | done | rotating log + events | |
| 131 | Failed-sector map export | done | `*.bad-sectors.json` | 011 |
| 132 | Partition-analysis export | partial | JSON session | 039 |
| 133 | Audit trail for source access | partial | events on open/scan | 129 |
| 134 | Chain-of-custody fields | stub | | |
| 135 | Case profiles | stub | | |
| 136 | Investigator notes | stub | session notes column | |
| 137 | File bookmarking | stub | | |
| 138 | Timeline filtering | stub | | |
| 139 | Sensitive redaction in reports | partial | contents never included | |
| 140 | Compare two scan sessions | stub | | |

## Category H — Desktop GUI and UX

| ID | Feature | Status | Module | Deps |
| --- | --- | --- | --- | --- |
| 141 | Modern PySide6 interface | done | `gui/app.py` | |
| 142 | Connected-device selector | done | | 001 |
| 143 | Visual source-device risk | partial | warning colors / text | 020 |
| 144 | Step-by-step wizard | done | stacked pages | |
| 145 | Recovery dashboard | done | home + summary | |
| 146 | Live scan progress | done | QProgressBar + log | |
| 147 | Sortable results table | done | QTableWidget | |
| 148 | Live filename search | done | | 106 |
| 149 | Multi-file selection | done | | |
| 150 | Preview panel | done | | 107-110 |
| 151 | Paginated hex viewer | partial | first 512 bytes | 109 |
| 152 | Dark and light themes | done | `gui/theme.py` | |
| 153 | Interface language selection | stub | English only | |
| 154 | Keyboard shortcuts | done | Ctrl+O/R/F, F5, Esc | |
| 155 | Accessibility / contrast | partial | theme contrast; no screen-reader audit | 152 |
| 156 | High-DPI layout | partial | Qt default + min sizes | |
| 157 | Pause and resume | partial | cancel; imaging resume | 018 |
| 158 | Live log viewer | done | | |
| 159 | Destination safety dialog | done | QMessageBox confirm | 016 |
| 160 | Recovery-completion summary | done | summary page | |

## Category I — CLI, automation, batch

| ID | Feature | Status | Module | Deps |
| --- | --- | --- | --- | --- |
| 161 | CLI scan and recovery | done | `cli/main.py` | |
| 162 | JSON command output | done | `--json` | 161 |
| 163 | Batch jobs via config files | stub | | 164 |
| 164 | YAML/TOML scan profiles | partial | TOML app config, not per-job YAML | |
| 165 | Headless operation | done | CLI, no display | 161 |
| 166 | Documented exit codes | done | `constants.py` / README | |
| 167 | Dry-run mode | done | `--dry-run` on image/scan/recover | |
| 168 | Named scan profiles | done | quick/standard/deep | 081 |
| 169 | Include/exclude rules | partial | `--signatures` | |
| 170 | Scheduled scan jobs | unsupported | must be opt-in; not built | |
| 171 | USB insertion event detection | stub | refresh in GUI (F5) | 001 |
| 172 | User-approved auto imaging | stub | | 007 |
| 173 | Reusable Python API | done | `usb_recovery.api.RecoveryLab` | |
| 174 | Plugin interface | stub | | |
| 175 | Batch analysis of disk images | partial | invoke CLI per image | 161 |
| 176 | SQLite checkpoints / scan state | done | `db/store.py` | |
| 177 | CPU/memory/disk I/O limits | stub | | |
| 178 | Configurable timeouts | stub | | |
| 179 | Rotating log files | done | `logging_config.py` | |
| 180 | Configuration export/import | partial | TOML load; no dedicated export cmd | |

## Category J — Engineering, security, integrations

| ID | Feature | Status | Module | Deps |
| --- | --- | --- | --- | --- |
| 181 | Modular architecture | done | `src/usb_recovery/*` | |
| 182 | Type hints | done | `py.typed` | |
| 183 | Unit-test suite | done | `tests/` | |
| 184 | Mocked device-access tests | done | `tests/test_devices_mock.py` | 183 |
| 185 | Synthetic disk-image fixtures | done | `tests/fixtures/builder.py` | 183 |
| 186 | Fuzz testing parsers | done | `lab/fuzz.py` | 258 |
| 187 | Dependency/vulnerability audit | stub | stdlib-first core | |
| 188 | Versioned signature database | done | `data/signatures.json` | 061 |
| 189 | Verified update signatures | unsupported | no auto-updater | |
| 190 | Offline-first | done | network flags forced off | |
| 191 | Telemetry disabled | done | | 190 |
| 192 | Safe exception handling | done | typed errors, CLI mapping | |
| 193 | Isolated worker processes | partial | GUI QThread + `security/preview_isolate.py` | 254 |
| 194 | Shell-injection protection | done | no shell; `os.open` / Python I/O | |
| 195 | Platform raw-device adapters | done | Linux + Windows | 003 |
| 196 | Read-only SMART info | stub | | |
| 197 | GNU ddrescue integration | stub | | 007 |
| 198 | TestDisk/PhotoRec/TSK adapters | stub | | |
| 199 | Config backup/restore | stub | | 180 |
| 200 | Diagnostics / support bundle | done | `diagnostics.py` | |

### Counts (this MVP)

- **done:** 001–003, 005, 007, 009–014, 016–023, 026–027, 029–031, 034, 036–038, 041–043, 047–049, 051–053, 056, 061, 063–066, 072, 077–078, 081, 086, 091–093, 097, 100–102, 104, 106–110, 112–115, 117–118, 120–121, 123–125, 128–131, 141–142, 144–150, 152, 154, 158–162, 165–168, 173, 176, 179, 181–185, 188, 190–192, 194–195, 200
- **partial / stub / unsupported:** remaining IDs as tabulated

Do not treat a **partial** or **stub** row as a completed forensic capability.

## Category K — Smart recovery and diagnostics (201–210)

| ID | Feature | Status | Module | Deps |
| --- | --- | --- | --- | --- |
| 201 | AI Recovery Assistant | done | `advisor/assistant.py` (rule-based, offline) | 207 |
| 202 | Recovery Strategy Advisor | done | `advise()` + filesystem/device context | 201, 204 |
| 203 | Recovery Limitation Explainer | done | `advisor/explain.py` | |
| 204 | Pre-Recovery Assessment | done | `advisor/assessment.py` | 002, 034 |
| 205 | Recovery Effort Estimator | done | `estimate_effort()` | 204 |
| 206 | Interactive Error Diagnosis | done | `diagnose_error()` / `usb-recovery diagnose` | |
| 207 | Recovery Decision Tree | done | `decision_tree()` | 201 |
| 208 | Recovery Failure Analyzer | done | `summarize_failures()` | 118 |
| 209 | Recovery Method Comparison | done | `compare_methods()` | |
| 210 | Explainable Recovery Scores | done | `explain_score()` + existing reasons | 100 |

## Category L — Advanced file reconstruction (211–220)

| ID | Feature | Status | Module | Deps |
| --- | --- | --- | --- | --- |
| 211 | Cross-Scan Candidate Matching | done | `reconstruct/matching.py` | 086 |
| 212 | Partial-File Region Viewer | done | `reconstruct/regions.py` | |
| 213 | File Fragment Explorer | done | `fragment_groups()` | 212 |
| 214 | Photo Sequence Grouping | done | `reconstruct/photos.py` | 056 |
| 215 | Video Repair Assistant | done | `reconstruct/video.py` (copy only; no invented moov) | |
| 216 | Archive Salvage Mode | done | `reconstruct/archive.py` | 068 |
| 217 | Document Structure Validator | done | `reconstruct/documents.py` | 091–094 |
| 218 | Recoverable Content Preview | done | `reconstruct/preview.py` | 107–109 |
| 219 | Embedded Content Detection | done | `scan_embedded()` | 061 |
| 220 | Recovery Candidate Timeline | done | `reconstruct/timeline.py` | 056 |

## Category M — Flash diagnostics and resilience (221–230)

| ID | Feature | Status | Module | Deps |
| --- | --- | --- | --- | --- |
| 221 | Read Error Heatmap | done | `flash/heatmap.py` | 011 |
| 222 | Adaptive Read Policy | done | `flash/adaptive.py` | 010 |
| 223 | Recovery Stop Thresholds | done | `StopThresholdError` | 222 |
| 224 | USB Connection Diagnostics | done | `flash/connection.py` | 001 |
| 225 | Safe Reconnection Workflow | done | identity check on checkpoint resume | 230 |
| 226 | Transfer Stability Monitor | done | `StabilityMonitor` | 012 |
| 227 | Device Identification Database | done | `data/usb_ids.json` | |
| 228 | Acquisition Risk Summary | done | `flash/risk.py` | 020 |
| 229 | Source Read Budget | done | `AdaptivePolicy.read_budget` | 223 |
| 230 | Interrupted Acquisition Recovery | done | checkpoint + identity (009 enhanced) | 009, 225 |

## Category N — Safer output management (231–240)

| ID | Feature | Status | Module | Deps |
| --- | --- | --- | --- | --- |
| 231 | Transactional File Recovery | done | `output/transaction.py` | 115 |
| 232 | Failed Output Cleanup | done | `cleanup_partials` / CLI | 231 |
| 233 | Recovery Vault | done | ChaCha20-HMAC local vault | |
| 234 | Recovery Manifest Sidecars | done | `output/sidecars.py` | 126 |
| 235 | Safe Filename Templates | done | `output/naming.py` | 114 |
| 236 | Advanced Collision Resolver | done | increment / hash / skip / fail | 114 |
| 237 | Destination Compatibility Check | done | FAT32 4 GiB, free space | 017 |
| 238 | Destination Verification Test | done | probe file write/delete | 237 |
| 239 | Recoverable vs Unrecoverable Summary | done | `output/summary.py` | 208 |
| 240 | Optional Verified Second Copy | done | explicit `confirm=True` | 016 |

## Category O — Search, filtering, productivity (241–250)

| ID | Feature | Status | Module | Deps |
| --- | --- | --- | --- | --- |
| 241 | Natural-Language File Search | done | `workspace/search.py` | 106 |
| 242 | Fuzzy Filename Search | done | Levenshtein | 241 |
| 243 | Saved Search Workspaces | done | SQLite `saved_searches` | 176 |
| 244 | Custom Result Columns | done | `workspace/columns.py` | 147 |
| 245 | Recovery Priority Queue | done | `workspace/queue.py` | |
| 246 | File-Type Recovery Batches | done | photos/docs/archives/videos | |
| 247 | Smart Selection Rules | done | `select_by_rules()` | 241 |
| 248 | Recovery Progress Notifications | done | in-process `NotificationLog` | |
| 249 | Session Bookmarking | done | SQLite `bookmarks` | 137 |
| 250 | Recovery Workspace Profiles | done | settings without secrets | |

## Category P — Security and advanced testing (251–260)

| ID | Feature | Status | Module | Deps |
| --- | --- | --- | --- | --- |
| 251 | Offline File Safety Scanner | done | heuristic + optional `clamscan` | 194 |
| 252 | Suspicious File Warning | done | exe/MZ/ELF flags | 251 |
| 253 | Metadata Privacy Review | done | `security/privacy.py` | 139 |
| 254 | Safe Preview Isolation | done | spawn worker + fallback | 193 |
| 255 | Synthetic Recovery Lab | done | `lab/synthetic.py` | 185 |
| 256 | Recovery Benchmark Suite | done | `lab/benchmark.py` | 255 |
| 257 | Algorithm Regression Tests | done | expected names in benchmark + pytest | 183, 256 |
| 258 | Parser Fuzzing Toolkit | done | `lab/fuzz.py` / `usb-recovery fuzz` | 186 |
| 259 | Signed Plugin Verification | done | SHA-256 allow-list + HMAC | |
| 260 | Redacted Diagnostic Bundle | done | `diagnostics.redact_text` | 200 |

## Category Q — Advanced disk-image management (261–270)

| ID | Feature | Status | Module | Deps |
| --- | --- | --- | --- | --- |
| 261 | Split Image Import | done | `images/split.py` | |
| 262 | Virtual Disk Image Support | partial | fixed VHD read; VHDX inspect | |
| 263 | AFF4 Image Import | partial | ZIP/RDF inspect, not full map replay | |
| 264 | Compressed Image Reader | done | gzip in-memory (`images/compressed.py`) | |
| 265 | Sparse Image Support | done | SEEK_HOLE map | |
| 266 | Image Offset Explorer | done | `OffsetSource` / `--image-offset` | 036 |
| 267 | Image Container Inspector | done | `inspect_container` | 261–265 |
| 268 | Image Format Converter | done | raw/split/gzip | 016 |
| 269 | Imaging Attempt Comparison | done | `compare_images` | |
| 270 | Image Provenance Manifest | done | `*.provenance.json` | 014 |

## Category R — Deeper filesystem and data analysis (271–280)

| ID | Feature | Status | Module | Deps |
| --- | --- | --- | --- | --- |
| 271 | Sector Alignment Analyzer | done | `analysis/alignment.py` | 021 |
| 272 | Read-Consistency Verification | done | `verify_read_consistency` | 003 |
| 273 | Byte-Range Recovery Mapping | done | `analysis/bytemap.py` | 212 |
| 274 | Multi-Method Candidate Comparison | done | `analysis/diff.py` | 211 |
| 275 | Unicode Filename Reconstruction | done | NFC/NFD + encodings | 047 |
| 276 | Temporary File Discovery | done | `~$`, `.tmp`, Thumbs.db | |
| 277 | Thumbnail Artifact Recovery | done | embedded JPEG in EXIF/buffers | 063 |
| 278 | Camera RAW Recovery | partial | CR2/RW2/DNG/NEF signatures | 061 |
| 279 | Fragmented Video Analysis | done | ftyp/moov/mdat/NAL | 215 |
| 280 | Database Journal Recovery | done | SQLite WAL / rollback journal | 072 |

## Category S — Recovery workspace (281–290)

| ID | Feature | Status | Module | Deps |
| --- | --- | --- | --- | --- |
| 281 | Selective Region Rescan | done | `--sector-range` / scan plan regions | 036 |
| 282 | Scan Plan Builder | done | `workspace/plan.py` | 081 |
| 283 | Recovery Candidate Diff Viewer | done | `diff_candidates` | 274 |
| 284 | Recovered-File Byte Map | done | `render_byte_map` | 273 |
| 285 | Recovery Exclusion Rules | done | `--exclude-types` / path globs | |
| 286 | Recovery Naming Templates | done | folder `{type}/{status}` + file templates | 235 |
| 287 | Session Labels and Tags | done | `session_tags` | 176 |
| 288 | Searchable Recovery History | done | `HistoryStore.search` | 287 |
| 289 | Saved Scan Checkpoints | done | `save_scan_checkpoint` | 176 |
| 290 | Recovery Queue Scheduling | done | `JobQueue` sequential priorities | 245 |

## Category T — Usability and platform (291–300)

| ID | Feature | Status | Module | Deps |
| --- | --- | --- | --- | --- |
| 291 | Portable Application Mode | done | `USB_RECOVERY_HOME` / `usb-recovery-data` | |
| 292 | First-Run Setup Wizard | done | `usb-recovery setup` | |
| 293 | Built-In Sample Recovery Cases | done | `usb-recovery lab` scenarios | 255 |
| 294 | Recovery Method Tutorials | done | offline help topics | 299 |
| 295 | Customizable Dashboard | done | `platform/dashboard.py` | 250 |
| 296 | System Resource Dashboard | done | `/proc/self` snapshot | |
| 297 | Multi-Job Monitor | done | `JobQueue.monitor` | 290 |
| 298 | Device Reconnection Identity Check | done | `identity-check` CLI | 225 |
| 299 | Local Help and Search | done | `usb-recovery help-search` | |
| 300 | Accessibility Navigation Mode | done | focus ring + shortcut list | 154 |

## Category U — Developer tools (301–310)

| ID | Feature | Status | Module | Deps |
| --- | --- | --- | --- | --- |
| 301 | Recovery Algorithm Benchmarking | done | `usb-recovery benchmark` | 256 |
| 302 | Test-Corpus Manager | done | `devtools/corpus.py` | 255 |
| 303 | Expected-Result Validator | done | hash/name checks | 257 |
| 304 | Crash-Recovery Self-Test | done | checkpoint restore | 230 |
| 305 | Database Migration Tests | done | `schema_migrations` | 176 |
| 306 | Plugin Compatibility Checker | done | `PLUGIN_API = "1.0"` | 259 |
| 307 | Resource-Leak Detection | done | `/proc/self/fd` delta | |
| 308 | Reproducible Scan Profiles | done | dump/load `ScanOptions` JSON | 168 |
| 309 | Automated Cross-Platform Tests | done | Linux+Windows adapter imports | 183 |
| 310 | Feature Readiness Dashboard | done | parses `docs/FEATURES.md` | |

## Category V — Advanced recovery algorithms (311–320)

| ID | Feature | Status | Module | Deps |
| --- | --- | --- | --- | --- |
| 311 | Multi-Evidence Recovery Engine | done | `advanced/engine.py` | 211, 088 |
| 312 | Fragment Relationship Graph | done | `advanced/fragments.py` | 213 |
| 313 | Constraint-Based File Reconstruction | done | `reconstruct_with_constraints` | 066 |
| 314 | Iterative Recovery Refinement | done | `refine_candidates` | 311 |
| 315 | Cross-Method Recovery Fusion | done | `fuse_methods` | 211 |
| 316 | File Boundary Confidence Analyzer | done | `boundary_confidence` | 066 |
| 317 | Recovery Hypothesis Comparison | done | `compare_hypotheses` | 313 |
| 318 | Known-Content Matching | done | `advanced/known.py` | |
| 319 | Partial File Dependency Analyzer | done | `advanced/dependencies.py` | 066 |
| 320 | Recovery Evidence Explorer | done | `advanced/evidence.py` / `usb-recovery evidence` | 311–319 |

## Category W — Deep filesystem reconstruction (321–330)

| ID | Feature | Status | Module | Deps |
| --- | --- | --- | --- | --- |
| 321 | FAT Allocation History Analysis | done | `fsdeep/fat_hist.py` | 041 |
| 322 | NTFS Record Relationship Graph | done | `fsdeep/ntfs_rel.py` | 051 |
| 323 | NTFS Journal Timeline Parser | partial | RSTR/RCRD listed, never replayed | 052 |
| 324 | exFAT Allocation Bitmap Reconstruction | done | `fsdeep/exfat_map.py` | 046 |
| 325 | Directory Metadata Cross-Validation | done | `cross_validate_directory` | 041, 046, 051 |
| 326 | Filesystem Metadata Version Comparison | done | FAT mirrors / NTFS backup boot | 321 |
| 327 | Lost Directory Entry Correlation | done | `correlate_orphans` | 044 |
| 328 | Filesystem Slack-Space Analysis | done | `fsdeep/slack.py` | 062 |
| 329 | Alternate Filesystem Offset Detection | done | `scan_alternate_offsets` | 036 |
| 330 | Competing Filesystem Layout Analysis | done | `competing_layouts` | 021, 329 |

## Category X — Specialized recovery for difficult files (331–340)

| ID | Feature | Status | Module | Deps |
| --- | --- | --- | --- | --- |
| 331 | Fragmented JPEG Reconstruction | done | `special/jpeg.py` | 063 |
| 332 | MP4 Fragment and Index Analysis | done | `special/mp4.py` | 215 |
| 333 | ZIP Directory Reconstruction | done | isolated CD/EOCD rebuild | 216 |
| 334 | PDF Cross-Reference Recovery | done | isolated xref rebuild | 217 |
| 335 | Office Document Relationship Validator | done | `special/office.py` | 067 |
| 336 | SQLite Journal Analysis | done | isolated WAL frame list | 280 |
| 337 | Video Codec Stream Analyzer | done | Annex-B NAL / MPEG start codes | 279 |
| 338 | Audio Frame Reconstruction | done | MP3/AAC-ADTS/WAV frames | 069 |
| 339 | RAW Photo Fragment Analyzer | done | TIFF IFD + CR2/NEF/DNG | 278 |
| 340 | Archive Member Salvage | partial | ZIP members; RAR/7z detect-only | 216 |

## Category Y — Intelligent analysis and automation (341–350)

| ID | Feature | Status | Module | Deps |
| --- | --- | --- | --- | --- |
| 341 | Local ML Candidate Classifier | done | local linear model; optional JSON weights | |
| 342 | Adaptive Scan Planner | done | `intel/plan.py` | 081, 168 |
| 343 | Recovery Cost Optimizer | done | `estimate_cost` | 205 |
| 344 | Scan Result Anomaly Detector | done | `intel/anomalies.py` | |
| 345 | Format-Aware False Positive Filter | done | `intel/filter.py` | 066 |
| 346 | Automatic Recovery Strategy Reports | done | `strategy_report` / `plan-scan` | 342 |
| 347 | Correlation-Based Candidate Grouping | done | `intel/group.py` | 211, 312 |
| 348 | Recovery Algorithm Selection Profiles | done | `algorithm_profile` | 342 |
| 349 | Uncertainty-Aware Recovery Assistant | done | `uncertainty_report` | 088, 203 |
| 350 | Automated Recovery Quality Scorecard | done | `intel/scorecard.py` | 257, 303 |

## Category Z — Forensic-grade integrity and engineering (351–360)

| ID | Feature | Status | Module | Deps |
| --- | --- | --- | --- | --- |
| 351 | Signed Evidence Manifest | done | HMAC-SHA256 or checksum | 270 |
| 352 | Source-to-Output Provenance Chain | done | `provenance_chain` | 351 |
| 353 | Repeatable Analysis Pipeline | done | versioned steps `pipeline.json` | 308 |
| 354 | Independent Validation Engine | done | `forensics/validate.py` | 066 |
| 355 | Differential Recovery Testing | done | `differential_results` | |
| 356 | Golden Dataset Regression Suite | done | corpus + expected names | 302, 303 |
| 357 | Failure Injection Framework | done | `FailureInjector` / malformed images | 258 |
| 358 | Isolated Binary Parser Workers | done | subprocess + rlimits | 253 |
| 359 | Recovery Plugin Capability Controls | done | AST allow-list | 259, 306 |
| 360 | Recovery Readiness and Evidence Dashboard | done | `usb-recovery evidence-dashboard` | 310 |
