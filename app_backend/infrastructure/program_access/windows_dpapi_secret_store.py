from __future__ import annotations

import ctypes
from ctypes import byref
from ctypes import wintypes
from pathlib import Path
from uuid import uuid4

from .secret_store import SecretDecryptError, SecretNotFoundError, SecretStoreReadError

_CRYPTPROTECT_UI_FORBIDDEN = 0x01
_REF_PREFIX = "dpapi:"


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


class WindowsDpapiSecretStore:
    def __init__(self, app_name: str, storage_root: Path):
        self._base_dir = Path(storage_root) / app_name / "secrets" / "windows_dpapi"
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def put(self, secret: str) -> str:
        secret_id = uuid4().hex
        protected = self._protect_bytes(secret.encode("utf-8"))
        self._path_for_secret_id(secret_id).write_bytes(protected)
        return f"{_REF_PREFIX}{secret_id}"

    def get(self, ref: str) -> str:
        secret_id = self._parse_ref(ref)
        path = self._path_for_secret_id(secret_id)
        if not path.exists():
            raise SecretNotFoundError(ref)
        try:
            protected = path.read_bytes()
        except OSError as exc:
            raise SecretStoreReadError(ref) from exc
        try:
            plaintext = self._unprotect_bytes(protected)
            return plaintext.decode("utf-8")
        except Exception as exc:  # pragma: no cover - exercised via behavior tests
            raise SecretDecryptError(ref) from exc

    def delete(self, ref: str) -> None:
        try:
            secret_id = self._parse_ref(ref)
        except SecretStoreReadError:
            return
        self._path_for_secret_id(secret_id).unlink(missing_ok=True)

    def _parse_ref(self, ref: str) -> str:
        if not ref.startswith(_REF_PREFIX):
            raise SecretStoreReadError(ref)
        secret_id = ref[len(_REF_PREFIX) :]
        if not secret_id or any(char in secret_id for char in ("/", "\\", ":")):
            raise SecretStoreReadError(ref)
        return secret_id

    def _path_for_ref(self, ref: str) -> Path:
        return self._path_for_secret_id(self._parse_ref(ref))

    def _path_for_secret_id(self, secret_id: str) -> Path:
        return self._base_dir / f"{secret_id}.secret"

    def _protect_bytes(self, value: bytes) -> bytes:
        crypt32 = self._get_crypt32()
        if crypt32 is None:
            return value
        input_blob, _buffer = self._blob_from_bytes(value)
        output_blob = _DataBlob()
        success = crypt32.CryptProtectData(
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
            self._local_free(output_blob.pbData)

    def _unprotect_bytes(self, value: bytes) -> bytes:
        crypt32 = self._get_crypt32()
        if crypt32 is None:
            return value
        input_blob, _buffer = self._blob_from_bytes(value)
        output_blob = _DataBlob()
        success = crypt32.CryptUnprotectData(
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
            self._local_free(output_blob.pbData)

    def _blob_from_bytes(self, value: bytes) -> tuple[_DataBlob, ctypes.Array[ctypes.c_char]]:
        if value:
            buffer = ctypes.create_string_buffer(value, len(value))
            return _DataBlob(len(value), buffer), buffer
        buffer = ctypes.create_string_buffer(b"\x00", 1)
        return _DataBlob(0, buffer), buffer

    def _local_free(self, pointer: ctypes.POINTER(ctypes.c_char)) -> None:
        kernel32 = self._get_kernel32()
        if kernel32 is None:
            return
        kernel32.LocalFree(pointer)

    def _get_crypt32(self):
        windll = getattr(ctypes, "windll", None)
        if windll is None:
            return None
        return getattr(windll, "crypt32", None)

    def _get_kernel32(self):
        windll = getattr(ctypes, "windll", None)
        if windll is None:
            return None
        return getattr(windll, "kernel32", None)
