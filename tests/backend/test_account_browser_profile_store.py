from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from app_backend.infrastructure.browser_runtime.account_browser_profile_store import (
    AccountBrowserProfileStore,
)
from app_backend.infrastructure.browser_runtime.managed_browser_runtime import ManagedBrowserRuntime


def _build_store(tmp_path: Path) -> AccountBrowserProfileStore:
    runtime = ManagedBrowserRuntime.from_app_private_dir(tmp_path / "app-private")
    return AccountBrowserProfileStore(runtime=runtime)


def _create_cookie_store(cookie_db_path: Path) -> None:
    cookie_db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(cookie_db_path))
    try:
        connection.execute(
            """
            CREATE TABLE cookies (
                creation_utc INTEGER NOT NULL,
                host_key TEXT NOT NULL,
                top_frame_site_key TEXT NOT NULL,
                name TEXT NOT NULL,
                value TEXT NOT NULL,
                encrypted_value BLOB NOT NULL,
                path TEXT NOT NULL,
                expires_utc INTEGER NOT NULL,
                is_secure INTEGER NOT NULL,
                is_httponly INTEGER NOT NULL,
                last_access_utc INTEGER NOT NULL,
                has_expires INTEGER NOT NULL,
                is_persistent INTEGER NOT NULL,
                priority INTEGER NOT NULL,
                samesite INTEGER NOT NULL,
                source_scheme INTEGER NOT NULL,
                source_port INTEGER NOT NULL,
                last_update_utc INTEGER NOT NULL,
                source_type INTEGER NOT NULL,
                has_cross_site_ancestor INTEGER NOT NULL
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO cookies (
                creation_utc,
                host_key,
                top_frame_site_key,
                name,
                value,
                encrypted_value,
                path,
                expires_utc,
                is_secure,
                is_httponly,
                last_access_utc,
                has_expires,
                is_persistent,
                priority,
                samesite,
                source_scheme,
                source_port,
                last_update_utc,
                source_type,
                has_cross_site_ancestor
            ) VALUES (?, ?, '', ?, '', X'', '/', ?, 0, 0, 0, 1, ?, 1, 0, 0, 0, 0, 0, 0)
            """,
            [
                (1, "www.c5game.com", "NC5_accessToken", 100, 1),
                (1, ".c5game.com", "NC5_crossAccessToken", 200, 1),
                (1, ".example.com", "other_cookie", 300, 0),
            ],
        )
        connection.commit()
    finally:
        connection.close()


def test_account_browser_profile_store_clones_and_persists_account_session(tmp_path: Path):
    store = _build_store(tmp_path)
    account_root = store.ensure_account_profile("a-1")
    account_root.joinpath("Local State").write_text("{}", encoding="utf-8")
    default_root = account_root / "Default"
    default_root.mkdir(parents=True, exist_ok=True)
    default_root.joinpath("Preferences").write_text('{"ok":1}', encoding="utf-8")
    default_root.joinpath("Cookies").write_text("seed-cookie", encoding="utf-8")

    cloned_session = store.clone_session("a-1")
    assert cloned_session.joinpath("Default", "Preferences").read_text(encoding="utf-8") == '{"ok":1}'
    assert cloned_session.joinpath("Default", "Cookies").read_text(encoding="utf-8") == "seed-cookie"

    cloned_session.joinpath("Default", "Cookies").write_text("session-cookie", encoding="utf-8")
    persisted_root = store.persist_session("a-1", cloned_session)

    assert persisted_root == account_root
    assert persisted_root.joinpath("Default", "Preferences").read_text(encoding="utf-8") == '{"ok":1}'
    assert persisted_root.joinpath("Default", "Cookies").read_text(encoding="utf-8") == "session-cookie"


def test_account_browser_profile_store_prepares_open_api_binding_session_by_refreshing_c5_cookie_expiry(tmp_path: Path):
    store = _build_store(tmp_path)
    session_root = tmp_path / "session"
    cookie_db_path = session_root / "Default" / "Network" / "Cookies"
    _create_cookie_store(cookie_db_path)

    summary = store.prepare_open_api_binding_session(session_root)

    assert summary["refreshed_cookie_rows"] == 2
    connection = sqlite3.connect(str(cookie_db_path))
    try:
        rows = list(
            connection.execute(
                "SELECT host_key, name, expires_utc, is_persistent, has_expires FROM cookies ORDER BY host_key, name"
            )
        )
    finally:
        connection.close()

    refreshed = {
        (host_key, name): (expires_utc, is_persistent, has_expires)
        for host_key, name, expires_utc, is_persistent, has_expires in rows
    }
    assert refreshed[(".c5game.com", "NC5_crossAccessToken")][0] > 200
    assert refreshed[(".c5game.com", "NC5_crossAccessToken")][1:] == (1, 1)
    assert refreshed[("www.c5game.com", "NC5_accessToken")][0] > 100
    assert refreshed[("www.c5game.com", "NC5_accessToken")][1:] == (1, 1)
    assert refreshed[(".example.com", "other_cookie")] == (300, 0, 1)


def test_account_browser_profile_store_persists_live_session_even_when_cache_file_is_locked(
    monkeypatch,
    tmp_path: Path,
):
    store = _build_store(tmp_path)
    session_root = tmp_path / "session"
    default_root = session_root / "Default"
    preferences_path = default_root / "Preferences"
    cache_file_path = default_root / "Cache" / "Cache_Data" / "data_0"
    preferences_path.parent.mkdir(parents=True, exist_ok=True)
    preferences_path.write_text('{"ok":1}', encoding="utf-8")
    cache_file_path.parent.mkdir(parents=True, exist_ok=True)
    cache_file_path.write_text("locked-cache", encoding="utf-8")

    original_copytree = shutil.copytree

    def _copytree(src, dst, *args, **kwargs):
        src_path = Path(src)
        if src_path != session_root:
            return original_copytree(src, dst, *args, **kwargs)

        ignore = kwargs.get("ignore")
        ignored_names = set(ignore(str(default_root), ["Preferences", "Cache"])) if callable(ignore) else set()
        if "Cache" not in ignored_names:
            raise shutil.Error(
                [
                    (
                        str(cache_file_path),
                        str(Path(dst) / "Default" / "Cache" / "Cache_Data" / "data_0"),
                        f"[Errno 13] Permission denied: '{cache_file_path}'",
                    )
                ]
            )
        return original_copytree(src, dst, *args, **kwargs)

    monkeypatch.setattr(
        "app_backend.infrastructure.browser_runtime.account_browser_profile_store.shutil.copytree",
        _copytree,
    )

    persisted_root = store.persist_session("a-live", session_root)

    assert persisted_root.joinpath("Default", "Preferences").read_text(encoding="utf-8") == '{"ok":1}'
    assert not persisted_root.joinpath("Default", "Cache").exists()

