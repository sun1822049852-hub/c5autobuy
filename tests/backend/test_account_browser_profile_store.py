from __future__ import annotations

from pathlib import Path

from app_backend.infrastructure.browser_runtime.account_browser_profile_store import (
    AccountBrowserProfileStore,
)
from app_backend.infrastructure.browser_runtime.managed_browser_runtime import ManagedBrowserRuntime


def _build_store(tmp_path: Path) -> AccountBrowserProfileStore:
    runtime = ManagedBrowserRuntime.from_app_private_dir(tmp_path / "app-private")
    return AccountBrowserProfileStore(runtime=runtime)


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

