from __future__ import annotations


def test_runtime_account_adapter_exposes_legacy_minimum_interface():
    from tests.backend.test_query_executor_router import build_account
    from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

    adapter = RuntimeAccountAdapter(build_account())

    assert adapter.current_user_id == "a1"
    assert adapter.get_api_key() == "api-1"
    assert adapter.has_api_key() is True
    assert adapter.get_x_access_token() == "token-1"
    assert adapter.get_x_device_id() == "device-1"
    assert adapter.get_cookie_header_exact() == "foo=bar; NC5_accessToken=token-1; NC5_deviceId=device-1; _csrf=abc%3D"
    assert adapter.get_cookie_header_with_decoded_csrf() == "foo=bar; NC5_accessToken=token-1; NC5_deviceId=device-1; _csrf=abc="


def test_legacy_scanner_adapter_is_query_executor_router_compat_alias():
    from app_backend.infrastructure.query.runtime.legacy_scanner_adapter import LegacyScannerAdapter
    from app_backend.infrastructure.query.runtime.query_executor_router import QueryExecutorRouter

    adapter = LegacyScannerAdapter()

    assert isinstance(adapter, QueryExecutorRouter)
