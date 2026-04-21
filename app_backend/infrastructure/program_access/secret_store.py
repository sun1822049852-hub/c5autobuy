from pathlib import Path
import sys
from typing import Protocol, runtime_checkable


class SecretNotFoundError(Exception):
    """Raised when a referenced secret does not exist."""


class SecretStoreReadError(Exception):
    """Raised when a stored secret cannot be read."""


class SecretDecryptError(Exception):
    """Raised when a stored secret cannot be decrypted."""


@runtime_checkable
class SecretStore(Protocol):
    def put(self, secret: str) -> str: ...

    def get(self, ref: str) -> str: ...

    def delete(self, ref: str) -> None: ...


def build_secret_store(
    stage: str,
    app_name: str,
    storage_root: Path,
    platform: str | None = None,
) -> SecretStore:
    runtime_platform = platform or sys.platform
    if stage == "local_dev":
        from .dev_plaintext_secret_store import DevPlaintextSecretStore

        return DevPlaintextSecretStore(app_name=app_name, storage_root=storage_root)

    if stage == "packaged_release":
        if runtime_platform == "win32":
            from .windows_dpapi_secret_store import WindowsDpapiSecretStore

            return WindowsDpapiSecretStore(app_name=app_name, storage_root=storage_root)
        raise NotImplementedError(
            "packaged_release secret store is only implemented for win32."
        )

    raise NotImplementedError(f"Unsupported stage: {stage}")
