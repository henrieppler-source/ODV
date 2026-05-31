from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import os


class SecureStoreError(RuntimeError):
    pass


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def _blob_from_bytes(data: bytes) -> DATA_BLOB:
    buf = ctypes.create_string_buffer(data)
    blob = DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))
    blob._buffer = buf  # type: ignore[attr-defined]
    return blob


def _bytes_from_blob(blob: DATA_BLOB) -> bytes:
    if not blob.pbData or blob.cbData == 0:
        return b""
    return ctypes.string_at(blob.pbData, blob.cbData)


def protect_text(value: str) -> str:
    if os.name != "nt":
        raise SecureStoreError("DPAPI ist nur unter Windows verfügbar.")
    data = value.encode("utf-8")
    in_blob = _blob_from_bytes(data)
    out_blob = DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise SecureStoreError("Passwort konnte nicht verschlüsselt werden.")
    try:
        return base64.b64encode(_bytes_from_blob(out_blob)).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def unprotect_text(value: str) -> str:
    if not value:
        return ""
    if os.name != "nt":
        raise SecureStoreError("DPAPI ist nur unter Windows verfügbar.")
    try:
        data = base64.b64decode(value.encode("ascii"))
    except Exception as exc:
        raise SecureStoreError("Gespeichertes Passwort ist ungültig.") from exc
    in_blob = _blob_from_bytes(data)
    out_blob = DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise SecureStoreError("Gespeichertes Passwort konnte nicht entschlüsselt werden.")
    try:
        return _bytes_from_blob(out_blob).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)
