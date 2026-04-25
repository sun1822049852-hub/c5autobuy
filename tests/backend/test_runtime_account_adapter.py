from __future__ import annotations

import asyncio


class _FakeLoop:
    def __init__(self, *, closed: bool) -> None:
        self._closed = bool(closed)

    def is_closed(self) -> bool:
        return self._closed

    def is_running(self) -> bool:
        return False


class _FakeSession:
    def __init__(self, *, loop, close_error: Exception | None = None, closed: bool = False) -> None:
        self._loop = loop
        self._close_error = close_error
        self.closed = bool(closed)
        self.close_calls = 0

    async def close(self) -> None:
        self.close_calls += 1
        if self._close_error is not None:
            raise self._close_error
        self.closed = True


def _build_account(
    *,
    browser_proxy_url: str = "http://browser.proxy:9001",
    api_proxy_url: str = "http://api.proxy:9002",
):
    from app_backend.domain.models.account import Account

    return Account(
        account_id="a1",
        default_name="账号-a1",
        remark_name=None,
        browser_proxy_mode="custom",
        browser_proxy_url=browser_proxy_url,
        api_proxy_mode="custom",
        api_proxy_url=api_proxy_url,
        api_key="api-1",
        c5_user_id=None,
        c5_nick_name=None,
        cookie_raw="foo=bar; NC5_accessToken=token-1; NC5_deviceId=device-1; _csrf=abc%3D",
        purchase_capability_state="unbound",
        purchase_pool_state="not_connected",
        last_login_at=None,
        last_error=None,
        created_at="2026-03-16T10:00:00",
        updated_at="2026-03-16T10:00:00",
    )


def test_runtime_account_adapter_exposes_cookie_and_token_helpers():
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    adapter = RuntimeAccountAdapter(_build_account())

    assert adapter.current_user_id == "a1"
    assert adapter.get_api_key() == "api-1"
    assert adapter.has_api_key() is True
    assert adapter.get_x_access_token() == "token-1"
    assert adapter.get_x_device_id() == "device-1"
    assert adapter.get_cookie_header_exact() == "foo=bar; NC5_accessToken=token-1; NC5_deviceId=device-1; _csrf=abc%3D"
    assert adapter.get_cookie_header_with_decoded_csrf() == "foo=bar; NC5_accessToken=token-1; NC5_deviceId=device-1; _csrf=abc="


async def test_runtime_account_adapter_recreates_api_session_when_bound_loop_is_closed(monkeypatch):
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    adapter = RuntimeAccountAdapter(_build_account())
    adapter._api_session = _FakeSession(
        loop=_FakeLoop(closed=True),
        close_error=RuntimeError("Event loop is closed"),
    )
    created_sessions: list[_FakeSession] = []

    def fake_create_session(**_kwargs):
        session = _FakeSession(loop=asyncio.get_running_loop())
        created_sessions.append(session)
        return session

    monkeypatch.setattr(adapter, "_create_session", fake_create_session)

    session = await adapter.get_api_session()

    assert len(created_sessions) == 1
    assert session is created_sessions[0]
    assert adapter._api_session is created_sessions[0]


async def test_runtime_account_adapter_recreates_global_session_when_bound_loop_is_closed(monkeypatch):
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    adapter = RuntimeAccountAdapter(_build_account())
    adapter._global_session = _FakeSession(
        loop=_FakeLoop(closed=True),
        close_error=RuntimeError("Event loop is closed"),
    )
    created_sessions: list[_FakeSession] = []

    def fake_create_session(**_kwargs):
        session = _FakeSession(loop=asyncio.get_running_loop())
        created_sessions.append(session)
        return session

    monkeypatch.setattr(adapter, "_create_session", fake_create_session)

    session = await adapter.get_global_session()

    assert len(created_sessions) == 1
    assert session is created_sessions[0]
    assert adapter._global_session is created_sessions[0]


async def test_runtime_account_adapter_uses_browser_proxy_for_global_session(monkeypatch):
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    adapter = RuntimeAccountAdapter(
        _build_account(
            browser_proxy_url="http://browser.proxy:9001",
            api_proxy_url="http://api.proxy:9002",
        )
    )
    created_calls: list[dict[str, object]] = []

    def fake_create_session(**kwargs):
        created_calls.append(dict(kwargs))
        return _FakeSession(loop=asyncio.get_running_loop())

    monkeypatch.setattr(adapter, "_create_session", fake_create_session)

    await adapter.get_global_session(force_new=True)

    assert created_calls[0]["proxy_url"] == "http://browser.proxy:9001"


async def test_runtime_account_adapter_rebuilds_session_when_proxy_changes_on_bind(monkeypatch):
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    adapter = RuntimeAccountAdapter(
        _build_account(
            browser_proxy_url="http://browser.proxy:9001",
            api_proxy_url="http://api.proxy:9002",
        )
    )
    old_api_session = _FakeSession(loop=asyncio.get_running_loop())
    adapter._api_session = old_api_session
    created_sessions: list[_FakeSession] = []

    def fake_create_session(**_kwargs):
        session = _FakeSession(loop=asyncio.get_running_loop())
        created_sessions.append(session)
        return session

    monkeypatch.setattr(adapter, "_create_session", fake_create_session)
    adapter.bind_account(
        _build_account(
            browser_proxy_url="http://browser.proxy:9001",
            api_proxy_url="http://api.proxy:9010",
        )
    )

    session = await adapter.get_api_session()

    assert old_api_session.close_calls == 1
    assert len(created_sessions) == 1
    assert session is created_sessions[0]
    assert adapter._api_session is created_sessions[0]
