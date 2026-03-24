from __future__ import annotations


def test_runtime_account_adapter_exposes_cookie_and_token_helpers():
    from tests.backend.test_query_executor_router import build_account
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    adapter = RuntimeAccountAdapter(build_account())

    assert adapter.current_user_id == "a1"
    assert adapter.get_api_key() == "api-1"
    assert adapter.has_api_key() is True
    assert adapter.get_x_access_token() == "token-1"
    assert adapter.get_x_device_id() == "device-1"
    assert adapter.get_user_agent() == "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0"
    assert adapter.get_cookie_header_exact() == "foo=bar; NC5_accessToken=token-1; NC5_deviceId=device-1; _csrf=abc%3D"
    assert adapter.get_cookie_header_with_decoded_csrf() == "foo=bar; NC5_accessToken=token-1; NC5_deviceId=device-1; _csrf=abc="


def test_runtime_account_adapter_prefers_persisted_user_agent():
    from tests.backend.test_query_executor_router import build_account
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    account = build_account()
    account.user_agent = "ua-1"

    adapter = RuntimeAccountAdapter(account)

    assert adapter.get_user_agent() == "ua-1"


async def test_runtime_account_adapter_routes_global_and_api_sessions_through_split_proxies():
    from tests.backend.test_query_executor_router import build_account
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    class FakeSession:
        def __init__(self) -> None:
            self.closed = False

        async def close(self) -> None:
            self.closed = True

    account = build_account()
    account.account_proxy_mode = "custom"
    account.account_proxy_url = "http://127.0.0.1:8001"
    account.api_proxy_mode = "custom"
    account.api_proxy_url = "http://127.0.0.1:8002"
    adapter = RuntimeAccountAdapter(account)
    captured_proxies: list[str | None] = []

    def fake_create_session(self, *, limit, limit_per_host, timeout_total, force_close, proxy_url):
        captured_proxies.append(proxy_url)
        return FakeSession()

    adapter._create_session = fake_create_session.__get__(adapter, RuntimeAccountAdapter)

    global_session = await adapter.get_global_session()
    api_session = await adapter.get_api_session()

    assert global_session is not None
    assert api_session is not None
    assert adapter.get_account_proxy_url() == "http://127.0.0.1:8001"
    assert adapter.get_api_proxy_url() == "http://127.0.0.1:8002"
    assert captured_proxies == ["http://127.0.0.1:8001", "http://127.0.0.1:8002"]
