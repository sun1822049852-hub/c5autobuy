from __future__ import annotations

import re
import shutil
from pathlib import Path

from app_backend.infrastructure.browser_runtime.managed_browser_runtime import ManagedBrowserRuntime


class AccountBrowserProfileStore:
    DEFAULT_PROFILE_DIRECTORY = "Default"
    TRANSIENT_RELATIVE_PATHS = (
        "SingletonCookie",
        "SingletonLock",
        "SingletonSocket",
        "DevToolsActivePort",
        "BrowserMetrics",
        "Crashpad",
        "ShaderCache",
        "GrShaderCache",
        "DawnCache",
        "Code Cache",
        "GPUCache",
        "Sessions",
    )

    def __init__(
        self,
        *,
        runtime: ManagedBrowserRuntime,
        profiles_root: Path | None = None,
    ) -> None:
        self._runtime = runtime
        self._profiles_root = Path(profiles_root) if profiles_root is not None else runtime.app_private_dir / "browser-profiles"
        self._profiles_root.mkdir(parents=True, exist_ok=True)

    def profile_root_for(self, account_id: str) -> Path:
        normalized_account_id = str(account_id or "").strip()
        if not normalized_account_id:
            raise ValueError("account_id is required")
        safe_name = re.sub(r"[^0-9A-Za-z._-]", "_", normalized_account_id)
        return self._profiles_root / safe_name

    def ensure_account_profile(self, account_id: str) -> Path:
        profile_root = self.profile_root_for(account_id)
        profile_root.mkdir(parents=True, exist_ok=True)
        profile_root.joinpath("Local State").parent.mkdir(parents=True, exist_ok=True)
        profile_root.joinpath(self.DEFAULT_PROFILE_DIRECTORY).mkdir(parents=True, exist_ok=True)
        return profile_root

    def clone_session(self, account_id: str, *, session_name: str | None = None) -> Path:
        source_root = self.ensure_account_profile(account_id)
        normalized_session_name = str(session_name or "").strip()
        if normalized_session_name:
            session_root = self._runtime.session_root / self._safe_name(normalized_session_name)
        else:
            session_root = self._runtime.session_root / f"account-{self._safe_name(account_id)}"
        if session_root.exists():
            shutil.rmtree(session_root, ignore_errors=True)
        shutil.copytree(source_root, session_root, dirs_exist_ok=True)
        self._remove_transient_paths(session_root)
        return session_root

    def persist_session(self, account_id: str, session_root: Path) -> Path:
        destination_root = self.profile_root_for(account_id)
        temp_root = destination_root.with_name(f"{destination_root.name}.tmp")
        if temp_root.exists():
            shutil.rmtree(temp_root, ignore_errors=True)
        shutil.copytree(session_root, temp_root, dirs_exist_ok=True)
        self._remove_transient_paths(temp_root)
        if destination_root.exists():
            shutil.rmtree(destination_root, ignore_errors=True)
        temp_root.replace(destination_root)
        return destination_root

    @classmethod
    def build_profile_payload(cls, profile_root: Path) -> dict[str, str]:
        return {
            "profile_root": str(profile_root),
            "profile_directory": cls.DEFAULT_PROFILE_DIRECTORY,
            "profile_kind": "account",
        }

    @classmethod
    def _safe_name(cls, account_id: str) -> str:
        return re.sub(r"[^0-9A-Za-z._-]", "_", str(account_id or "").strip())

    @classmethod
    def _remove_transient_paths(cls, root: Path) -> None:
        for relative_path in cls.TRANSIENT_RELATIVE_PATHS:
            target = root / relative_path
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
            else:
                target.unlink(missing_ok=True)

