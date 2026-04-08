from __future__ import annotations

from pathlib import Path

from app_backend.domain.models.account import Account


class _MemoryRepository:
    def __init__(self, account: Account) -> None:
        self._accounts = {account.account_id: account}
        self.updates: list[dict[str, object]] = []

    def get_account(self, account_id: str) -> Account | None:
        return self._accounts.get(account_id)

    def update_account(self, account_id: str, **changes):
        account = self._accounts.get(account_id)
        if account is None:
            raise KeyError(account_id)
        self.updates.append(dict(changes))
        for key, value in changes.items():
            if hasattr(account, key):
                setattr(account, key, value)
        return account

    def create_account(self, account: Account) -> Account:
        self._accounts[account.account_id] = account
        return account

    def delete_account(self, account_id: str) -> None:
        self._accounts.pop(account_id, None)


class _RecordingBalanceService:
    def __init__(self) -> None:
        self.scheduled_account_ids: list[str] = []

    def maybe_schedule_refresh(self, account_id: str) -> bool:
        self.scheduled_account_ids.append(account_id)
        return True


def _build_account() -> Account:
    return Account(
        account_id="a-1",
        default_name="默认账号",
        remark_name="测试账号",
        browser_proxy_mode="custom",
        browser_proxy_url="http://127.0.0.1:9000",
        api_proxy_mode="custom",
        api_proxy_url="http://127.0.0.1:9000",
        api_key=None,
        c5_user_id="10001",
        c5_nick_name="Nick",
        cookie_raw="NC5_accessToken=token-1",
        purchase_capability_state="bound",
        purchase_pool_state="not_connected",
        last_login_at="2026-03-27T12:00:00",
        last_error=None,
        created_at="2026-03-27T12:00:00",
        updated_at="2026-03-27T12:00:00",
    )


def _build_api_only_source_account(*, account_id: str = "source", api_key: str = "api-key-1") -> Account:
    return Account(
        account_id=account_id,
        default_name="API only",
        remark_name="API only",
        browser_proxy_mode="direct",
        browser_proxy_url=None,
        api_proxy_mode="direct",
        api_proxy_url=None,
        api_key=api_key,
        c5_user_id=None,
        c5_nick_name=None,
        cookie_raw=None,
        purchase_capability_state="unbound",
        purchase_pool_state="not_connected",
        last_login_at=None,
        last_error=None,
        created_at="2026-03-27T12:00:00",
        updated_at="2026-03-27T12:00:00",
    )


def test_open_api_binding_sync_service_marks_ip_invalid_when_allow_list_mismatches():
    from app_backend.infrastructure.browser_runtime.open_api_binding_sync_service import OpenApiBindingSyncService

    account = _build_account()
    account.api_key = "api-key-1"
    account.api_ip_allow_list = "36.138.220.178"
    repository = _MemoryRepository(account)
    service = OpenApiBindingSyncService(
        account_repository=repository,
        public_ip_fetcher=lambda proxy_url: "39.71.213.149",
    )

    outcome = service.sync_account_now("a-1", final=True)
    updated = repository.get_account("a-1")

    assert outcome["matched"] is False
    assert updated is not None
    assert updated.api_key == "api-key-1"
    assert updated.api_ip_allow_list == "36.138.220.178"
    assert updated.api_public_ip == "http://127.0.0.1:9000"
    assert updated.api_query_disabled_reason is None


def test_open_api_binding_sync_service_keeps_runtime_ip_invalid_until_runtime_clears_it():
    from app_backend.infrastructure.browser_runtime.open_api_binding_sync_service import OpenApiBindingSyncService

    account = _build_account()
    account.api_query_disabled_reason = "ip_invalid"
    account.new_api_enabled = False
    account.fast_api_enabled = False
    account.api_key = "api-key-1"
    account.api_ip_allow_list = "39.71.213.149, 36.138.220.178"
    repository = _MemoryRepository(account)
    service = OpenApiBindingSyncService(
        account_repository=repository,
        public_ip_fetcher=lambda proxy_url: "39.71.213.149",
    )

    outcome = service.sync_account_now("a-1", final=False)
    updated = repository.get_account("a-1")

    assert outcome["matched"] is False
    assert updated is not None
    assert updated.api_query_disabled_reason == "ip_invalid"
    assert updated.new_api_enabled is False
    assert updated.fast_api_enabled is False

    outcome = service.sync_account_now("a-1", final=True)
    updated = repository.get_account("a-1")

    assert outcome["matched"] is False
    assert updated is not None
    assert updated.api_query_disabled_reason == "ip_invalid"
    assert updated.new_api_enabled is False
    assert updated.fast_api_enabled is False


def test_open_api_binding_sync_service_writes_debug_log(tmp_path: Path):
    from app_backend.infrastructure.browser_runtime.open_api_binding_sync_service import OpenApiBindingSyncService

    account = _build_account()
    account.api_key = "api-key-1"
    account.api_ip_allow_list = "39.71.213.149"
    repository = _MemoryRepository(account)
    log_path = tmp_path / "open_api_binding_debug.jsonl"
    service = OpenApiBindingSyncService(
        account_repository=repository,
        public_ip_fetcher=lambda proxy_url: "39.71.213.149",
        debug_log_path=log_path,
    )

    outcome = service.sync_account_now("a-1", final=False)

    assert outcome["matched"] is False
    content = log_path.read_text(encoding="utf-8")
    assert "sync_result" in content
    assert "write_account" in content


def test_open_api_binding_watch_keeps_refreshing_browser_allow_list_until_ip_matches(tmp_path: Path, monkeypatch):
    import app_backend.infrastructure.browser_runtime.open_api_binding_sync_service as module
    from app_backend.infrastructure.browser_runtime.open_api_binding_sync_service import OpenApiBindingSyncService

    account = _build_account()
    account.api_query_disabled_reason = "ip_invalid"
    account.new_api_enabled = False
    account.fast_api_enabled = False
    account.browser_proxy_mode = "direct"
    account.browser_proxy_url = None
    account.api_proxy_mode = "direct"
    account.api_proxy_url = None
    repository = _MemoryRepository(account)
    page_payloads = iter([
        {
            "success": True,
            "data": {
                "apiInfo": {
                    "key": "api-key-1",
                    "ipAllowList": "36.138.220.178",
                }
            },
        },
        {
            "success": True,
            "data": {
                "apiInfo": {
                    "key": "api-key-1",
                    "ipAllowList": "36.138.220.178, 162.128.182.254",
                }
            },
        },
    ])
    monkeypatch.setattr(
        module,
        "navigate_and_capture_open_api_partner_info",
        lambda debugger_address, url, timeout_seconds=20.0: next(page_payloads),
    )
    monkeypatch.setattr(module, "capture_open_api_partner_info", lambda debugger_address, timeout_seconds=20.0: None)
    monkeypatch.setattr(
        module,
        "poll_open_api_page_partner_info",
        lambda debugger_address, timeout_seconds=20.0, interval_seconds=1.0: next(page_payloads, None),
    )

    service = OpenApiBindingSyncService(
        account_repository=repository,
        public_ip_fetcher=lambda proxy_url: "162.128.182.254",
        poll_interval_seconds=0.01,
        max_wait_seconds=0.05,
        debug_log_path=tmp_path / "open_api_binding_debug.jsonl",
    )

    service._watch_account("a-1", "127.0.0.1:9222")

    updated = repository.get_account("a-1")
    assert updated is not None
    assert updated.api_key == "api-key-1"
    assert updated.api_ip_allow_list == "36.138.220.178, 162.128.182.254"
    assert updated.api_query_disabled_reason == "ip_invalid"
    assert updated.new_api_enabled is False
    assert updated.fast_api_enabled is False


def test_open_api_binding_watch_keeps_syncing_after_initial_match_to_capture_allow_list_removal(tmp_path: Path, monkeypatch):
    import app_backend.infrastructure.browser_runtime.open_api_binding_sync_service as module
    from app_backend.infrastructure.browser_runtime.open_api_binding_sync_service import OpenApiBindingSyncService

    account = _build_account()
    account.browser_proxy_mode = "direct"
    account.browser_proxy_url = None
    account.api_proxy_mode = "direct"
    account.api_proxy_url = None
    repository = _MemoryRepository(account)
    page_payloads = iter([
        {
            "success": True,
            "data": {
                "apiInfo": {
                    "key": "api-key-1",
                    "ipAllowList": "36.138.220.178, 39.71.213.149",
                }
            },
        },
        {
            "success": True,
            "data": {
                "apiInfo": {
                    "key": "api-key-1",
                    "ipAllowList": "39.71.213.149",
                }
            },
        },
    ])
    monkeypatch.setattr(
        module,
        "navigate_and_capture_open_api_partner_info",
        lambda debugger_address, url, timeout_seconds=20.0: next(page_payloads),
    )
    monkeypatch.setattr(module, "capture_open_api_partner_info", lambda debugger_address, timeout_seconds=20.0: None)
    monkeypatch.setattr(
        module,
        "poll_open_api_page_partner_info",
        lambda debugger_address, timeout_seconds=20.0, interval_seconds=1.0: next(page_payloads, None),
    )

    service = OpenApiBindingSyncService(
        account_repository=repository,
        public_ip_fetcher=lambda proxy_url: "39.71.213.149",
        poll_interval_seconds=0.01,
        max_wait_seconds=0.05,
        debug_log_path=tmp_path / "open_api_binding_debug.jsonl",
    )

    service._watch_account("a-1", "127.0.0.1:9222")

    updated = repository.get_account("a-1")
    assert updated is not None
    assert updated.api_key == "api-key-1"
    assert updated.api_ip_allow_list == "39.71.213.149"


def test_open_api_binding_sync_service_writes_api_key_before_public_ip_fetch():
    from app_backend.infrastructure.browser_runtime.open_api_binding_sync_service import OpenApiBindingSyncService

    account = _build_account()
    account.api_key = None
    account.api_ip_allow_list = None
    repository = _MemoryRepository(account)

    def slow_public_ip_fetcher(proxy_url: str | None) -> str | None:
        return "162.128.182.254"

    service = OpenApiBindingSyncService(
        account_repository=repository,
        public_ip_fetcher=slow_public_ip_fetcher,
    )

    outcome = service.sync_account_now(
        "a-1",
        final=False,
        partner_payload_override={
            "success": True,
            "data": {
                "apiInfo": {
                    "key": "api-key-1",
                    "ipAllowList": "36.138.220.178",
                },
            },
        },
    )

    assert outcome["updated"] is True
    assert len(repository.updates) >= 2
    first_update = repository.updates[0]
    assert first_update["api_key"] == "api-key-1"
    assert first_update["api_ip_allow_list"] == "36.138.220.178"
    assert "api_public_ip" not in first_update
    final_update = repository.updates[-1]
    assert final_update["api_public_ip"] == "http://127.0.0.1:9000"


def test_open_api_binding_sync_service_triggers_balance_refresh_when_api_key_is_newly_written():
    from app_backend.infrastructure.browser_runtime.open_api_binding_sync_service import OpenApiBindingSyncService

    account = _build_account()
    account.api_key = None
    account.balance_refresh_after_at = "2099-01-01T00:00:00"
    repository = _MemoryRepository(account)
    balance_service = _RecordingBalanceService()
    service = OpenApiBindingSyncService(
        account_repository=repository,
        account_balance_service=balance_service,
        public_ip_fetcher=lambda proxy_url: "162.128.182.254",
    )

    outcome = service.sync_account_now(
        "a-1",
        final=False,
        partner_payload_override={
            "success": True,
            "data": {
                "apiInfo": {
                    "key": "api-key-1",
                    "ipAllowList": "36.138.220.178",
                },
            },
        },
    )
    updated = repository.get_account("a-1")

    assert outcome["updated"] is True
    assert updated is not None
    assert updated.api_key == "api-key-1"
    assert updated.balance_refresh_after_at is None
    assert balance_service.scheduled_account_ids == ["a-1"]


def test_open_api_binding_sync_service_mismatch_is_display_only():
    from app_backend.infrastructure.browser_runtime.open_api_binding_sync_service import OpenApiBindingSyncService

    account = _build_account()
    account.api_key = "api-key-1"
    account.api_ip_allow_list = "36.138.220.178"
    account.new_api_enabled = True
    account.fast_api_enabled = True
    repository = _MemoryRepository(account)
    service = OpenApiBindingSyncService(
        account_repository=repository,
        public_ip_fetcher=lambda proxy_url: "162.128.182.254",
    )

    outcome = service.sync_account_now("a-1", final=True)
    updated = repository.get_account("a-1")

    assert outcome["matched"] is False
    assert updated is not None
    assert updated.api_public_ip == "http://127.0.0.1:9000"
    assert updated.api_query_disabled_reason is None
    assert updated.new_api_enabled is True
    assert updated.fast_api_enabled is True


def test_open_api_binding_sync_service_skips_rewriting_identical_account_state():
    from app_backend.infrastructure.browser_runtime.open_api_binding_sync_service import OpenApiBindingSyncService

    account = _build_account()
    account.api_key = "api-key-1"
    account.api_ip_allow_list = "36.138.220.178"
    repository = _MemoryRepository(account)
    service = OpenApiBindingSyncService(
        account_repository=repository,
        public_ip_fetcher=lambda proxy_url: "162.128.182.254",
    )

    first_outcome = service.sync_account_now("a-1", final=False)
    first_update_count = len(repository.updates)

    second_outcome = service.sync_account_now("a-1", final=False)

    assert first_outcome["updated"] is True
    assert first_update_count >= 1
    assert second_outcome == {"matched": False, "updated": False}
    assert len(repository.updates) == first_update_count


def test_open_api_binding_sync_service_writes_browser_public_ip_for_direct_connection():
    from app_backend.infrastructure.browser_runtime.open_api_binding_sync_service import OpenApiBindingSyncService

    account = _build_account()
    account.api_key = "api-key-1"
    account.api_ip_allow_list = "36.138.220.178"
    account.browser_proxy_mode = "direct"
    account.browser_proxy_url = None
    account.api_proxy_mode = "direct"
    account.api_proxy_url = None
    repository = _MemoryRepository(account)
    service = OpenApiBindingSyncService(
        account_repository=repository,
        public_ip_fetcher=lambda proxy_url: "39.71.213.149",
    )

    outcome = service.sync_account_now("a-1", final=False)
    updated = repository.get_account("a-1")

    assert outcome["updated"] is True
    assert updated is not None
    assert updated.api_public_ip == "39.71.213.149"
    assert updated.browser_public_ip == "39.71.213.149"


def test_open_api_binding_sync_service_uses_proxy_values_without_fetching():
    from app_backend.infrastructure.browser_runtime.open_api_binding_sync_service import OpenApiBindingSyncService

    account = _build_account()
    account.api_key = "api-key-1"
    account.api_ip_allow_list = "36.138.220.178"
    seen_proxy_urls: list[str | None] = []

    def unexpected_fetcher(proxy_url: str | None) -> str | None:
        seen_proxy_urls.append(proxy_url)
        return "39.71.213.149"

    repository = _MemoryRepository(account)
    service = OpenApiBindingSyncService(
        account_repository=repository,
        public_ip_fetcher=unexpected_fetcher,
    )

    outcome = service.sync_account_now("a-1", final=False)
    updated = repository.get_account("a-1")

    assert outcome["updated"] is True
    assert updated is not None
    assert updated.api_public_ip == "http://127.0.0.1:9000"
    assert updated.browser_public_ip == "http://127.0.0.1:9000"
    assert seen_proxy_urls == []


def test_open_api_binding_sync_service_direct_fetcher_tries_multiple_sources():
    from app_backend.infrastructure.browser_runtime.open_api_binding_sync_service import OpenApiBindingSyncService

    account = _build_account()
    account.api_key = "api-key-1"
    account.api_ip_allow_list = "39.71.213.149"
    account.browser_proxy_mode = "direct"
    account.browser_proxy_url = None
    account.api_proxy_mode = "direct"
    account.api_proxy_url = None
    calls: list[str | None] = []

    def fallback_fetcher(proxy_url: str | None) -> str | None:
        calls.append(proxy_url)
        return "39.71.213.149"

    repository = _MemoryRepository(account)
    service = OpenApiBindingSyncService(
        account_repository=repository,
        public_ip_fetcher=fallback_fetcher,
    )

    outcome = service.sync_account_now("a-1", final=False)
    updated = repository.get_account("a-1")

    assert outcome["matched"] is True
    assert updated is not None
    assert updated.api_public_ip == "39.71.213.149"
    assert updated.browser_public_ip == "39.71.213.149"
    assert calls == [None]


def test_open_api_binding_watch_uses_short_natural_capture_timeout(tmp_path: Path, monkeypatch):
    import app_backend.infrastructure.browser_runtime.open_api_binding_sync_service as module
    from app_backend.infrastructure.browser_runtime.open_api_binding_sync_service import OpenApiBindingSyncService

    account = _build_account()
    repository = _MemoryRepository(account)
    captured_timeouts: list[float] = []

    def fake_navigate(debugger_address, url, timeout_seconds=20.0):
        captured_timeouts.append(float(timeout_seconds))
        return None

    monkeypatch.setattr(module, "navigate_and_capture_open_api_partner_info", fake_navigate)
    monkeypatch.setattr(module, "capture_open_api_partner_info", lambda debugger_address, timeout_seconds=20.0: None)
    monkeypatch.setattr(module, "poll_open_api_page_partner_info", lambda debugger_address, timeout_seconds=20.0, interval_seconds=1.0: None)

    service = OpenApiBindingSyncService(
        account_repository=repository,
        public_ip_fetcher=lambda proxy_url: "39.71.213.149",
        poll_interval_seconds=0.01,
        max_wait_seconds=0.05,
        debug_log_path=tmp_path / "open_api_binding_debug.jsonl",
    )

    service._watch_account("a-1", "127.0.0.1:9222")

    assert captured_timeouts
    assert captured_timeouts[0] <= 2.0


def test_open_api_binding_watch_skips_initial_navigation_when_browser_already_on_open_api(tmp_path: Path, monkeypatch):
    import app_backend.infrastructure.browser_runtime.open_api_binding_sync_service as module
    from app_backend.infrastructure.browser_runtime.open_api_binding_sync_service import OpenApiBindingSyncService

    account = _build_account()
    repository = _MemoryRepository(account)
    navigate_calls: list[tuple[str, str, float]] = []
    poll_calls: list[tuple[str, float, float]] = []

    monkeypatch.setattr(
        module,
        "select_target",
        lambda debugger_address: {
            "type": "page",
            "url": "https://www.c5game.com/user/user/open-api",
            "webSocketDebuggerUrl": "ws://example.test/devtools/page/1",
        },
    )

    def fake_navigate(debugger_address, url, timeout_seconds=20.0):
        navigate_calls.append((debugger_address, url, float(timeout_seconds)))
        return None

    def fake_poll(debugger_address, timeout_seconds=20.0, interval_seconds=1.0):
        poll_calls.append((debugger_address, float(timeout_seconds), float(interval_seconds)))
        return None

    monkeypatch.setattr(module, "navigate_and_capture_open_api_partner_info", fake_navigate)
    monkeypatch.setattr(module, "capture_open_api_partner_info", lambda debugger_address, timeout_seconds=20.0: None)
    monkeypatch.setattr(module, "poll_open_api_page_partner_info", fake_poll)

    service = OpenApiBindingSyncService(
        account_repository=repository,
        public_ip_fetcher=lambda proxy_url: "39.71.213.149",
        poll_interval_seconds=0.01,
        max_wait_seconds=0.05,
        debug_log_path=tmp_path / "open_api_binding_debug.jsonl",
    )

    service._watch_account("a-1", "127.0.0.1:9222")

    assert navigate_calls == []
    assert poll_calls


def test_open_api_binding_watch_skips_initial_navigation_when_browser_is_on_login_returning_to_open_api(
    tmp_path: Path,
    monkeypatch,
):
    import app_backend.infrastructure.browser_runtime.open_api_binding_sync_service as module
    from app_backend.infrastructure.browser_runtime.open_api_binding_sync_service import OpenApiBindingSyncService

    account = _build_account()
    repository = _MemoryRepository(account)
    navigate_calls: list[tuple[str, str, float]] = []

    monkeypatch.setattr(
        module,
        "select_target",
        lambda debugger_address: {
            "type": "page",
            "url": "https://www.c5game.com/login?return_url=%2Fuser%2Fuser%2Fopen-api",
            "webSocketDebuggerUrl": "ws://example.test/devtools/page/1",
        },
    )
    monkeypatch.setattr(
        module,
        "navigate_and_capture_open_api_partner_info",
        lambda debugger_address, url, timeout_seconds=20.0: navigate_calls.append(
            (debugger_address, url, float(timeout_seconds))
        ) or None,
    )
    monkeypatch.setattr(module, "capture_open_api_partner_info", lambda debugger_address, timeout_seconds=20.0: None)
    monkeypatch.setattr(module, "poll_open_api_page_partner_info", lambda debugger_address, timeout_seconds=20.0, interval_seconds=1.0: None)

    service = OpenApiBindingSyncService(
        account_repository=repository,
        public_ip_fetcher=lambda proxy_url: "39.71.213.149",
        poll_interval_seconds=0.01,
        max_wait_seconds=0.05,
        debug_log_path=tmp_path / "open_api_binding_debug.jsonl",
    )

    service._watch_account("a-1", "127.0.0.1:9222")

    assert navigate_calls == []


def test_open_api_binding_sync_service_never_issues_backend_partner_fetch(tmp_path: Path):
    from app_backend.infrastructure.browser_runtime.open_api_binding_sync_service import OpenApiBindingSyncService

    account = _build_account()
    account.api_key = "api-key-1"
    account.api_ip_allow_list = "36.138.220.178"
    repository = _MemoryRepository(account)
    service = OpenApiBindingSyncService(
        account_repository=repository,
        public_ip_fetcher=lambda proxy_url: "36.138.220.178",
        debug_log_path=tmp_path / "open_api_binding_debug.jsonl",
    )

    outcome = service.sync_account_now("a-1", final=False)

    assert outcome["matched"] is False
    content = (tmp_path / "open_api_binding_debug.jsonl").read_text(encoding="utf-8")
    assert "stored_account_snapshot" in content
    assert "backend_fetch" not in content


def test_open_api_binding_watch_deletes_source_api_only_account_when_browser_api_key_matches(
    tmp_path: Path,
    monkeypatch,
):
    import app_backend.infrastructure.browser_runtime.open_api_binding_sync_service as module
    from app_backend.infrastructure.browser_runtime.open_api_binding_sync_service import OpenApiBindingSyncService

    final_account = _build_account()
    repository = _MemoryRepository(final_account)
    repository.create_account(_build_api_only_source_account(api_key="api-key-1"))

    monkeypatch.setattr(
        module,
        "navigate_and_capture_open_api_partner_info",
        lambda debugger_address, url, timeout_seconds=20.0: {
            "success": True,
            "data": {"apiInfo": {"key": "api-key-1", "ipAllowList": "39.71.213.149"}},
        },
    )
    monkeypatch.setattr(module, "capture_open_api_partner_info", lambda debugger_address, timeout_seconds=20.0: None)
    monkeypatch.setattr(module, "poll_open_api_page_partner_info", lambda debugger_address, timeout_seconds=20.0, interval_seconds=1.0: None)

    service = OpenApiBindingSyncService(
        account_repository=repository,
        public_ip_fetcher=lambda proxy_url: "39.71.213.149",
        poll_interval_seconds=0.01,
        max_wait_seconds=0.05,
        debug_log_path=tmp_path / "open_api_binding_debug.jsonl",
    )

    service._watch_account("a-1", "127.0.0.1:9222", "source", "api-key-1")

    updated = repository.get_account("a-1")
    assert updated is not None
    assert updated.api_key == "api-key-1"
    assert repository.get_account("source") is None


def test_open_api_binding_watch_keeps_source_api_only_account_when_browser_api_key_differs(
    tmp_path: Path,
    monkeypatch,
):
    import app_backend.infrastructure.browser_runtime.open_api_binding_sync_service as module
    from app_backend.infrastructure.browser_runtime.open_api_binding_sync_service import OpenApiBindingSyncService

    final_account = _build_account()
    repository = _MemoryRepository(final_account)
    repository.create_account(_build_api_only_source_account(api_key="api-key-1"))

    monkeypatch.setattr(
        module,
        "navigate_and_capture_open_api_partner_info",
        lambda debugger_address, url, timeout_seconds=20.0: {
            "success": True,
            "data": {"apiInfo": {"key": "api-key-2", "ipAllowList": "39.71.213.149"}},
        },
    )
    monkeypatch.setattr(module, "capture_open_api_partner_info", lambda debugger_address, timeout_seconds=20.0: None)
    monkeypatch.setattr(module, "poll_open_api_page_partner_info", lambda debugger_address, timeout_seconds=20.0, interval_seconds=1.0: None)

    service = OpenApiBindingSyncService(
        account_repository=repository,
        public_ip_fetcher=lambda proxy_url: "39.71.213.149",
        poll_interval_seconds=0.01,
        max_wait_seconds=0.05,
        debug_log_path=tmp_path / "open_api_binding_debug.jsonl",
    )

    service._watch_account("a-1", "127.0.0.1:9222", "source", "api-key-1")

    updated = repository.get_account("a-1")
    source = repository.get_account("source")
    assert updated is not None
    assert updated.api_key == "api-key-2"
    assert source is not None
    assert source.api_key == "api-key-1"

