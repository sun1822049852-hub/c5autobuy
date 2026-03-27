from __future__ import annotations

import ctypes
from ctypes import byref
from ctypes import wintypes
import json
from typing import Any


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


_CRYPTPROTECT_UI_FORBIDDEN = 0x01
_IS_WINDOWS = hasattr(ctypes, "windll") and hasattr(ctypes.windll, "crypt32")


def dump_payload(payload: dict[str, Any]) -> bytes:
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
    if not _IS_WINDOWS:
        return serialized
    return _protect_bytes(serialized)


def load_payload(blob: bytes) -> dict[str, Any]:
    raw = _unprotect_bytes(blob) if _IS_WINDOWS else blob
    decoded = json.loads(raw.decode("utf-8"))
    return decoded if isinstance(decoded, dict) else {}


def _protect_bytes(value: bytes) -> bytes:
    input_blob, _buffer = _blob_from_bytes(value)
    output_blob = _DataBlob()
    success = ctypes.windll.crypt32.CryptProtectData(
        byref(input_blob),
        None,
        None,
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        byref(output_blob),
    )
    if not success:
        raise OSError(ctypes.GetLastError())
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output_blob.pbData)


def _unprotect_bytes(value: bytes) -> bytes:
    input_blob, _buffer = _blob_from_bytes(value)
    output_blob = _DataBlob()
    success = ctypes.windll.crypt32.CryptUnprotectData(
        byref(input_blob),
        None,
        None,
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        byref(output_blob),
    )
    if not success:
        raise OSError(ctypes.GetLastError())
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output_blob.pbData)


def _blob_from_bytes(value: bytes) -> tuple[_DataBlob, ctypes.Array[ctypes.c_char]]:
    if value:
        buffer = ctypes.create_string_buffer(value, len(value))
        return _DataBlob(len(value), buffer), buffer
    buffer = ctypes.create_string_buffer(b"\x00", 1)
    return _DataBlob(0, buffer), buffer
