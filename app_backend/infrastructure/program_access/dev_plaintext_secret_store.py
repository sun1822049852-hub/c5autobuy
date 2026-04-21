from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from .secret_store import SecretNotFoundError, SecretStoreReadError

_REF_PREFIX = "devfile:"


class DevPlaintextSecretStore:
    def __init__(self, app_name: str, storage_root: Path):
        self._base_dir = Path(storage_root) / app_name / "secrets" / "dev_plaintext"
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def put(self, secret: str) -> str:
        secret_id = uuid4().hex
        path = self._path_for_secret_id(secret_id)
        path.write_text(secret, encoding="utf-8")
        return f"{_REF_PREFIX}{secret_id}"

    def get(self, ref: str) -> str:
        secret_id = self._parse_ref(ref)
        path = self._path_for_secret_id(secret_id)
        if not path.exists():
            raise SecretNotFoundError(ref)
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise SecretStoreReadError(ref) from exc

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

    def _path_for_secret_id(self, secret_id: str) -> Path:
        return self._base_dir / f"{secret_id}.secret"
