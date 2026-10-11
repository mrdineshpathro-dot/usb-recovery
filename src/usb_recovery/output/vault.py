"""Local encrypted recovery vault (feature 233). Offline ChaCha20-HMAC, no network.

This is a local passphrase vault for recovered *copies*. It is not a substitute
for a hardware encrypted drive and it never encrypts the source device.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import struct
from pathlib import Path

from usb_recovery.exceptions import VaultError
from usb_recovery.util import isoformat, new_id, safe_filename

MAGIC = b"URVL1"
ITERATIONS = 200_000


def _rotl32(v: int, n: int) -> int:
    v &= 0xFFFFFFFF
    return ((v << n) | (v >> (32 - n))) & 0xFFFFFFFF


def _qr(s: list[int], a: int, b: int, c: int, d: int) -> None:
    s[a] = (s[a] + s[b]) & 0xFFFFFFFF
    s[d] ^= s[a]
    s[d] = _rotl32(s[d], 16)
    s[c] = (s[c] + s[d]) & 0xFFFFFFFF
    s[b] ^= s[c]
    s[b] = _rotl32(s[b], 12)
    s[a] = (s[a] + s[b]) & 0xFFFFFFFF
    s[d] ^= s[a]
    s[d] = _rotl32(s[d], 8)
    s[c] = (s[c] + s[d]) & 0xFFFFFFFF
    s[b] ^= s[c]
    s[b] = _rotl32(s[b], 7)


def chacha20_block(key: bytes, counter: int, nonce: bytes) -> bytes:
    const = b"expand 32-byte k"
    packed = const + key + struct.pack("<I", counter) + nonce
    state = list(struct.unpack("<16I", packed))
    working = state[:]
    for _ in range(10):
        _qr(working, 0, 4, 8, 12)
        _qr(working, 1, 5, 9, 13)
        _qr(working, 2, 6, 10, 14)
        _qr(working, 3, 7, 11, 15)
        _qr(working, 0, 5, 10, 15)
        _qr(working, 1, 6, 11, 12)
        _qr(working, 2, 7, 8, 13)
        _qr(working, 3, 4, 9, 14)
    out = [(working[i] + state[i]) & 0xFFFFFFFF for i in range(16)]
    return struct.pack("<16I", *out)


def chacha20_xor(key: bytes, nonce: bytes, data: bytes) -> bytes:
    out = bytearray()
    counter = 1
    for i in range(0, len(data), 64):
        block = chacha20_block(key, counter, nonce)
        chunk = data[i : i + 64]
        out.extend(a ^ b for a, b in zip(chunk, block))
        counter += 1
    return bytes(out)


def _derive(passphrase: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, ITERATIONS, dklen=32)


class RecoveryVault:
    def __init__(self, root: str | Path, passphrase: str) -> None:
        if not passphrase:
            raise VaultError("Vault passphrase must not be empty")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.root, 0o700)
        except OSError:
            pass
        self._passphrase = passphrase
        self._meta = self.root / "vault.json"
        if not self._meta.exists():
            salt = os.urandom(16)
            self._meta.write_text(
                json.dumps({"version": 1, "salt_hex": salt.hex(), "created": isoformat(), "files": []}),
                encoding="utf-8",
            )

    def _key(self) -> tuple[bytes, bytes]:
        payload = json.loads(self._meta.read_text(encoding="utf-8"))
        salt = bytes.fromhex(payload["salt_hex"])
        return _derive(self._passphrase, salt), salt

    def store(self, filename: str, data: bytes, *, meta: dict | None = None) -> Path:
        key, _salt = self._key()
        nonce = os.urandom(12)
        cipher = chacha20_xor(key, nonce, data)
        tag = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
        blob = MAGIC + nonce + tag + cipher
        name = safe_filename(filename) + ".urv"
        path = self.root / name
        if path.exists():
            path = self.root / f"{safe_filename(Path(filename).stem)}-{new_id()[:8]}.urv"
        path.write_bytes(blob)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        catalog = json.loads(self._meta.read_text(encoding="utf-8"))
        catalog.setdefault("files", []).append(
            {"name": path.name, "original": filename, "size": len(data), "meta": meta or {}, "stored": isoformat()}
        )
        self._meta.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
        return path

    def unlock(self, path: str | Path) -> bytes:
        raw = Path(path).read_bytes()
        if not raw.startswith(MAGIC):
            raise VaultError("Not a USB Recovery Lab vault object")
        nonce = raw[5:17]
        tag = raw[17:49]
        cipher = raw[49:]
        key, _salt = self._key()
        expect = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expect):
            raise VaultError("Vault authentication failed (wrong passphrase or corrupt file)")
        return chacha20_xor(key, nonce, cipher)
