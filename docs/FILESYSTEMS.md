# Filesystem support and limitations

Detection of a filesystem signature is **not** full reconstruction. The table below is the source of truth for this release.

| Filesystem | Detect | Boot sector | Deleted names | Allocation chain | Directory tree | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| FAT12 | yes | yes | yes (first character lost) | yes, plus contiguous heuristic | yes | USB floppy-style volumes |
| FAT16 | yes | yes | yes (first character lost) | yes, plus contiguous heuristic | yes | Common on smaller pen drives |
| FAT32 | yes | yes, backup boot compared | yes | yes | yes | Backup boot is **not** copied over the primary |
| exFAT | yes | yes | yes (in-use bit) | FAT or no-FAT contiguous flag | yes | Bitmap / up-case table not rebuilt |
| NTFS | yes | yes | yes (`FILE` in-use flag) | runlist `$DATA` | original name from `$FILE_NAME` | `$LogFile` not replayed; attribute lists skipped |
| ext2/3/4 | detect only | superblock magic `0xEF53` | no | no | no | Reported, not reconstructed |
| HFS+/APFS | no | no | no | no | no | Unsupported |

## FAT

- VFAT long names are reconstructed when the LFN sequence and 8.3 checksum survive.
- Deleted 8.3 entries start with `0xE5`; the original first character is unknown and is replaced with `_`.
- After deletion most operating systems zero the FAT chain. When the chain is gone the engine reads `ceil(size / cluster)` clusters starting at the recorded cluster and **marks the result as a heuristic**.
- Cross-linked chains are not repaired.

## exFAT

- File / Stream / File-Name entry sets are parsed.
- Deleted sets have bit `0x80` cleared (`0x05` / `0x40` / `0x41`).
- `NoFatChain` files are read as a contiguous cluster run.

## NTFS

- `$MFT` FILE records are walked from record 0 using the boot-sector MFT cluster.
- Resident and non-resident unnamed `$DATA` are extracted. Alternate data stream **names** are recorded.
- Compression, encryption, sparse-tail reconstruction, and `$I30` orphan-name recovery are not implemented.
- The journal is not replayed. That is a deliberate read-only limitation.

## Super-floppy volumes

Some factory USB sticks have no MBR/GPT. If neither table is valid the engine treats LBA 0 as the start of a single volume.
