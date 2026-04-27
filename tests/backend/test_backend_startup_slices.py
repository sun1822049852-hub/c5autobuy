from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from app_backend.domain.models.account import Account
from app_backend.main import create_app

_RUNTIME_FULL_STATE_ATTRS = (
    "query_config_repository",
    "query_runtime_service",
    "purchase_runtime_service",
    "program_runtime_control_service",
    "purchase_ui_preferences_repository",
    "runtime_settings_repository",
    "stats_repository",
    "stats_pipeline",
    "task_manager",
)


def _route_signatures(app) -> set[tuple[str, str, tuple[str, ...], str]]:
    return {
        (
            type(route).__name__,
            str(getattr(route, "path", "") or getattr(route, "path_format", "") or ""),
            tuple(sorted(str(method) for method in (getattr(route, "methods", None) or ()))),
            str(getattr(route, "name", "") or ""),
        )
        for route in app.routes
    }


def _build_account(
    account_id: str,
    *,
    remark_name: str | None = None,
    api_key: str | None = None,
) -> Account:
    return Account(
        account_id=account_id,
        default_name=f"默认-{account_id}",
        remark_name=remark_name,
        browser_proxy_mode="custom",
        browser_proxy_url="http://127.0.0.1:9001",
        api_proxy_mode="custom",
        api_proxy_url="http://127.0.0.1:9001",
        api_key=api_key,
        c5_user_id="10001",
        c5_nick_name="回退账号",
        cookie_raw="NC5_accessToken=token",
        purchase_capability_state="bound",
        purchase_pool_state="not_connected",
        last_login_at="2026-03-16T20:00:00",
        last_error=None,
        created_at="2026-03-16T20:00:00",
        updated_at="2026-03-16T20:00:00",
        purchase_disabled=False,
        purchase_recovery_due_at=None,
        balance_amount=None,
        balance_source=None,
        balance_updated_at=None,
        balance_refresh_after_at=None,
        balance_last_error=None,
    )


def _detach_runtime_full_slice(app) -> list[str]:
    saved_state = {}
    for attr in _RUNTIME_FULL_STATE_ATTRS:
        if hasattr(app.state, attr):
            saved_state[attr] = getattr(app.state, attr)
            delattr(app.state, attr)

    ensure_calls: list[str] = []

    def _ensure_runtime_full_ready() -> None:
        ensure_calls.append("runtime-full")
        for attr, value in saved_state.items():
            setattr(app.state, attr, value)

    app.state.ensure_runtime_full_ready = _ensure_runtime_full_ready
    return ensure_calls


def test_core_home_routes_do_not_require_runtime_full_slice(tmp_path: Path):
    app = create_app(db_path=tmp_path / "startup-slices.db")
    app.state.account_repository.create_account(
        _build_account(
            "home-ready",
            remark_name="首页回退账号",
            api_key="api-home-ready",
        )
    )
    ensure_calls = _detach_runtime_full_slice(app)

    with TestClient(app, raise_server_exceptions=False) as client:
        shell_response = client.get("/app/bootstrap?scope=shell")
        program_auth_response = client.get("/program-auth/status")
        account_center_response = client.get("/account-center/accounts")

    assert {
        "shell": shell_response.status_code,
        "program_auth": program_auth_response.status_code,
        "account_center": account_center_response.status_code,
    } == {
        "shell": 200,
        "program_auth": 200,
        "account_center": 200,
    }
    assert ensure_calls == []
    assert set(shell_response.json()) == {"version", "generated_at", "program_access"}
    assert program_auth_response.json()["guard_enabled"] is False
    assert [row["account_id"] for row in account_center_response.json()] == ["home-ready"]


def test_deferred_create_app_builds_core_home_without_runtime_or_browser_actions(tmp_path: Path):
    app = create_app(
        db_path=tmp_path / "startup-slices-deferred.db",
        deferred_init=True,
        program_access_start_refresh_scheduler=False,
    )

    assert callable(getattr(app.state, "ensure_runtime_full_ready", None))
    assert callable(getattr(app.state, "ensure_browser_actions_ready", None))
    assert getattr(app.state, "account_center_snapshot_service", None) is not None
    assert getattr(app.state, "account_repository", None) is not None
    assert getattr(app.state, "account_session_bundle_repository", None) is not None
    assert not hasattr(app.state, "query_runtime_service")
    assert not hasattr(app.state, "purchase_runtime_service")
    assert not hasattr(app.state, "program_runtime_control_service")
    assert not hasattr(app.state, "login_adapter")
    assert not hasattr(app.state, "open_api_binding_page_launcher")
    assert not hasattr(app.state, "open_api_binding_sync_service")


def test_deferred_create_app_registers_runtime_and_browser_routes_before_slice_ensure(tmp_path: Path):
    app = create_app(
        db_path=tmp_path / "startup-slices-routes.db",
        deferred_init=True,
        program_access_start_refresh_scheduler=False,
    )

    route_paths = {route.path for route in app.routes}

    assert {
        "/query-runtime/status",
        "/purchase-runtime/status",
        "/query-configs",
        "/runtime-settings/purchase",
        "/diagnostics/sidebar",
        "/stats/query-items",
        "/stats/account-capability",
        "/tasks/{task_id}",
        "/ws/runtime",
        "/ws/tasks/{task_id}",
        "/ws/accounts/updates",
    }.issubset(route_paths)


def test_deferred_create_app_lifespan_eventually_binds_runtime_full_services(tmp_path: Path):
    app = create_app(
        db_path=tmp_path / "startup-slices-lifespan.db",
        deferred_init=True,
        program_access_start_refresh_scheduler=False,
    )

    assert not hasattr(app.state, "purchase_runtime_service")

    with TestClient(app) as client:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not hasattr(app.state, "purchase_runtime_service"):
            response = client.get("/health")
            assert response.status_code == 200
            time.sleep(0.05)

    assert hasattr(app.state, "purchase_runtime_service")
    assert hasattr(app.state, "query_runtime_service")
    assert hasattr(app.state, "program_runtime_control_service")


def test_slice_ensure_only_binds_state_and_does_not_mutate_route_table(tmp_path: Path):
    app = create_app(
        db_path=tmp_path / "startup-slices-route-stability.db",
        deferred_init=True,
        program_access_start_refresh_scheduler=False,
    )

    route_signatures_before = _route_signatures(app)

    app.state.ensure_runtime_full_ready()
    app.state.ensure_browser_actions_ready()

    assert _route_signatures(app) == route_signatures_before


def test_full_bootstrap_scope_explicitly_ensures_runtime_full_slice(tmp_path: Path):
    app = create_app(db_path=tmp_path / "startup-slices-full.db")
    ensure_calls = _detach_runtime_full_slice(app)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/app/bootstrap?scope=full")

    assert response.status_code == 200
    assert ensure_calls == ["runtime-full"]
    payload = response.json()
    assert "query_system" in payload
    assert "purchase_system" in payload
    assert "diagnostics" in payload
