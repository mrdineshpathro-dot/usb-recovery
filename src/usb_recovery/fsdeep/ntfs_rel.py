"""NTFS record relationship graph and journal timeline (322, 323)."""

from __future__ import annotations

import struct

from usb_recovery.constants import NTFS_ATTR_END, NTFS_ATTR_FILE_NAME, NTFS_FILE_RECORD_MAGIC


def _walk_attrs(record: bytes) -> list[dict]:
    if len(record) < 0x18 or record[:4] != NTFS_FILE_RECORD_MAGIC:
        return []
    first = struct.unpack_from("<H", record, 0x14)[0]
    offset = first
    attrs: list[dict] = []
    while offset + 8 <= len(record):
        atype = struct.unpack_from("<I", record, offset)[0]
        if atype == NTFS_ATTR_END:
            break
        length = struct.unpack_from("<I", record, offset + 4)[0]
        if length < 16 or offset + length > len(record):
            break
        non_res = record[offset + 8]
        if atype == NTFS_ATTR_FILE_NAME and non_res == 0:
            voff = struct.unpack_from("<H", record, offset + 0x14)[0]
            vlen = struct.unpack_from("<I", record, offset + 0x10)[0]
            value = record[offset + voff : offset + voff + vlen]
            if len(value) >= 0x42:
                parent = struct.unpack_from("<Q", value, 0)[0] & 0x0000FFFFFFFFFFFF
                nlen = value[0x40]
                name = value[0x42 : 0x42 + nlen * 2].decode("utf-16le", errors="replace")
                attrs.append({"type": atype, "parent": parent, "name": name})
        else:
            attrs.append({"type": atype})
        offset += length
    return attrs


def ntfs_record_graph(data: bytes, record_size: int = 1024) -> dict:
    """Map surviving FILE records and parent FILE_NAME references (322)."""
    nodes: list[dict] = []
    edges: list[dict] = []
    offset = 0
    index = 0
    while offset + 4 <= len(data):
        idx = data.find(NTFS_FILE_RECORD_MAGIC, offset)
        if idx < 0:
            break
        rec = data[idx : idx + record_size]
        flags = struct.unpack_from("<H", rec, 0x16)[0] if len(rec) >= 0x18 else 0
        attrs = _walk_attrs(rec)
        names = [a["name"] for a in attrs if a.get("name")]
        parents = [a["parent"] for a in attrs if "parent" in a]
        node = {
            "index": index,
            "offset": idx,
            "in_use": bool(flags & 0x01),
            "directory": bool(flags & 0x02),
            "names": names,
            "parents": parents,
        }
        nodes.append(node)
        for parent in parents:
            edges.append({"child": index, "parent_mft": parent, "name": names[-1] if names else None})
        index += 1
        offset = idx + 4
        if index > 4096:
            break
    return {
        "nodes": nodes,
        "edges": edges,
        "count": len(nodes),
        "note": "Parent links come from surviving $FILE_NAME attributes. Attribute lists are not followed.",
    }


def ntfs_journal_timeline(data: bytes) -> dict:
    """Parse $LogFile-style RSTR/RCRD pages for historical context (323). Not replayed."""
    restart = []
    records = []
    off = 0
    while True:
        i = data.find(b"RSTR", off)
        if i < 0:
            break
        restart.append({"offset": i})
        off = i + 4
        if len(restart) > 32:
            break
    off = 0
    while True:
        i = data.find(b"RCRD", off)
        if i < 0:
            break
        lsn = struct.unpack_from("<Q", data, i + 8)[0] if i + 16 <= len(data) else None
        records.append({"offset": i, "lsn": lsn})
        off = i + 4
        if len(records) > 256:
            break
    records.sort(key=lambda r: (r["lsn"] is None, r["lsn"] or 0, r["offset"]))
    return {
        "restart_pages": restart,
        "records": records,
        "count": len(records),
        "note": (
            "LSNs are listed for timeline context only. This tool never replays $LogFile "
            "onto the volume."
        ),
    }
