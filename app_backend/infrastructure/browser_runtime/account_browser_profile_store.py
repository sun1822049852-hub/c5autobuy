from __future__ import annotations

import re
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app_backend.infrastructure.browser_runtime.managed_browser_runtime import ManagedBrowserRuntime


class AccountBrowserProfileStore:
    DEFAULT_PROFILE_DIRECTORY = "Default"
    OPEN_API_COOKIE_DB_RELATIVE_PATHS = (
        Path(DEFAULT_PROFILE_DIRECTORY) / "Network" / "Cookies",
        Path(DEFAULT_PROFILE_DIRECTORY) / "Cookies",
    )
    OPEN_API_COOKIE_EXPIRY_EXTENSION_DAYS = 30
    OPEN_API_COOKIE_HOST_FRAGMENT = "c5game.com"
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
        Path(DEFAULT_PROFILE_DIRECTORY) / "Cache",
        Path(DEFAULT_PROFILE_DIRECTORY) / "Code Cache",
        Path(DEFAULT_PROFILE_DIRECTORY) / "GPUCache",
        Path(DEFAULT_PROFILE_DIRECTORY) / "ShaderCache",
        Path(DEFAULT_PROFILE_DIRECTORY) / "GrShaderCache",
        Path(DEFAULT_PROFILE_DIRECTORY) / "DawnCache",
        Path(DEFAULT_PROFILE_DIRECTORY) / "Sessions",
        Path(DEFAULT_PROFILE_DIRECTORY) / "Service Worker" / "CacheStorage",
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
        self._copytree(source_root, session_root)
        self._remove_transient_paths(session_root)
        return session_root

    def persist_session(self, account_id: str, session_root: Path) -> Path:
        destination_root = self.profile_root_for(account_id)
        temp_root = destination_root.with_name(f"{destination_root.name}.tmp")
        if temp_root.exists():
            shutil.rmtree(temp_root, ignore_errors=True)
        self._copytree(session_root, temp_root)
        self._remove_transient_paths(temp_root)
        if destination_root.exists():
            shutil.rmtree(destination_root, ignore_errors=True)
        temp_root.replace(destination_root)
        return destination_root

    def prepare_open_api_binding_session(self, session_root: Path) -> dict[str, object]:
        normalized_session_root = Path(session_root)
        refreshed_cookie_rows = 0
        refreshed_cookie_dbs: list[str] = []
        for relative_path in self.OPEN_API_COOKIE_DB_RELATIVE_PATHS:
            cookie_db_path = normalized_session_root / relative_path
            updated_rows = self._refresh_open_api_cookie_expiry(cookie_db_path)
            if updated_rows <= 0:
                continue
            refreshed_cookie_rows += updated_rows
            refreshed_cookie_dbs.append(str(cookie_db_path))
        return {
            "refreshed_cookie_rows": refreshed_cookie_rows,
            "refreshed_cookie_dbs": refreshed_cookie_dbs,
        }

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

    @classmethod
    def _copytree(cls, source: Path, destination: Path) -> None:
        shutil.copytree(
            source,
            destination,
            dirs_exist_ok=True,
            ignore=cls._build_transient_copy_ignore(Path(source)),
        )

    @classmethod
    def _build_transient_copy_ignore(cls, source_root: Path):
        transient_relatives = {
            cls._normalize_relative_path(relative_path)
            for relative_path in cls.TRANSIENT_RELATIVE_PATHS
        }

        def _ignore(current_dir: str, names: list[str]) -> set[str]:
            current_path = Path(current_dir)
            current_relative = cls._normalize_relative_path(current_path.relative_to(source_root))
            ignored_names: set[str] = set()
            for name in names:
                candidate_relative = current_relative + (name,)
                if candidate_relative in transient_relatives:
                    ignored_names.add(name)
            return ignored_names

        return _ignore

    @staticmethod
    def _normalize_relative_path(relative_path: str | Path) -> tuple[str, ...]:
        parts = Path(relative_path).parts
        return tuple(part for part in parts if part not in {"", "."})

    @classmethod
    def _refresh_open_api_cookie_expiry(cls, cookie_db_path: Path) -> int:
        normalized_cookie_db_path = Path(cookie_db_path)
        if not normalized_cookie_db_path.exists():
            return 0

        connection = sqlite3.connect(str(normalized_cookie_db_path))
        try:
            if not cls._cookies_table_exists(connection):
                return 0
            refresh_expiry_utc = cls._build_future_cookie_expiry_utc()
            before_changes = connection.total_changes
            connection.execute(
                """
                UPDATE cookies
                SET expires_utc = ?, has_expires = 1, is_persistent = 1
                WHERE instr(lower(host_key), ?) > 0
                """,
                (refresh_expiry_utc, cls.OPEN_API_COOKIE_HOST_FRAGMENT),
            )
            connection.commit()
            return connection.total_changes - before_changes
        finally:
            connection.close()

    @staticmethod
    def _cookies_table_exists(connection: sqlite3.Connection) -> bool:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'cookies' LIMIT 1"
        ).fetchone()
        return row is not None

    @classmethod
    def _build_future_cookie_expiry_utc(cls) -> int:
        chrome_epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
        expires_at = datetime.now(timezone.utc) + timedelta(days=cls.OPEN_API_COOKIE_EXPIRY_EXTENSION_DAYS)
        return int((expires_at - chrome_epoch).total_seconds() * 1_000_000)

