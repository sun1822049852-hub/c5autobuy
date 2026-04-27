import time
import threading
import warnings

from httpx import ASGITransport, AsyncClient
from fastapi.testclient import TestClient

from app_backend.application.program_access import (
    PROGRAM_AUTH_REQUIRED_CODE,
    PROGRAM_AUTH_REQUIRED_MESSAGE,
    ProgramAccessSummary,
)
from app_backend.main import create_app


async def test_health_endpoint():
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["ready"] is True


def test_health_endpoint_stays_ready_after_runtime_full_state_is_detached(tmp_path):
    app = create_app(db_path=tmp_path / "health-runtime-detached.db")

    for attr in (
        "query_config_repository",
        "query_runtime_service",
        "purchase_runtime_service",
        "program_runtime_control_service",
        "purchase_ui_preferences_repository",
        "runtime_settings_repository",
        "stats_repository",
        "stats_pipeline",
        "task_manager",
    ):
        delattr(app.state, attr)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "ready": True}


def test_create_app_non_deferred_does_not_emit_deprecated_shutdown_warning(tmp_path):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        create_app(db_path=tmp_path / "warning-free.db")

    legacy_shutdown_warnings = [
        warning
        for warning in caught
        if issubclass(warning.category, DeprecationWarning)
        and "on_event is deprecated" in str(warning.message)
    ]

    assert legacy_shutdown_warnings == []


def test_non_deferred_shutdown_still_cleans_program_access_services(tmp_path):
    app = create_app(db_path=tmp_path / "cleanup.db")
    cleanup_calls: list[str] = []

    class _FakeRuntimeControlService:
        def stop(self) -> None:
            cleanup_calls.append("runtime-control-stop")

    class _FakeScheduler:
        def stop(self) -> None:
            cleanup_calls.append("stop")

    class _FakeGateway:
        def close(self) -> None:
            cleanup_calls.append("close")

    app.state.program_access_refresh_scheduler = _FakeScheduler()
    app.state.program_access_gateway = _FakeGateway()
    app.state.program_runtime_control_service = _FakeRuntimeControlService()

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert cleanup_calls == ["runtime-control-stop", "stop", "close"]


def test_deferred_health_eventually_becomes_ready_without_init_error(tmp_path):
    app = create_app(
        db_path=tmp_path / "deferred.db",
        deferred_init=True,
        program_access_start_refresh_scheduler=False,
    )

    with TestClient(app) as client:
        deadline = time.monotonic() + 5
        payload = None

        while time.monotonic() < deadline:
            response = client.get("/health")
            payload = response.json()
            assert payload["status"] != "error"
            if payload["ready"] is True:
                break
            time.sleep(0.05)

        assert payload is not None
        assert payload["status"] == "ok"
        assert payload["ready"] is True

        bootstrap_response = client.get("/app/bootstrap")
        assert bootstrap_response.status_code == 200


def test_deferred_packaged_release_health_ready_is_not_blocked_by_program_access_startup_refresh(
    monkeypatch,
    tmp_path,
):
    import app_backend.main as backend_main

    startup_refresh_entered = threading.Event()
    allow_startup_refresh_exit = threading.Event()
    lifecycle: list[str] = []

    class _BlockingScheduler:
        def start(self) -> None:
            lifecycle.append("start-enter")
            startup_refresh_entered.set()
            allow_startup_refresh_exit.wait(timeout=5)
            lifecycle.append("start-exit")

        def stop(self) -> None:
            lifecycle.append("stop")

    class _Gateway:
        def close(self) -> None:
            lifecycle.append("close")

    def _fake_build_program_access_services(**_kwargs):
        return _Gateway(), object(), object(), object(), _BlockingScheduler()

    monkeypatch.setattr(backend_main, "_build_program_access_services", _fake_build_program_access_services)

    app = backend_main.create_app(
        db_path=tmp_path / "deferred-packaged-release.db",
        deferred_init=True,
        program_access_stage="packaged_release",
        program_access_start_refresh_scheduler=True,
    )

    with TestClient(app) as client:
        assert startup_refresh_entered.wait(timeout=5) is True

        response = client.get("/health")
        payload = response.json()

        assert response.status_code == 200
        assert payload["status"] == "ok"
        assert payload["ready"] is True

        allow_startup_refresh_exit.set()

    assert "stop" in lifecycle
    assert "close" in lifecycle


def test_deferred_packaged_release_post_ready_warm_updates_registration_flow_version_without_blocking_ready(
    monkeypatch,
    tmp_path,
):
    import app_backend.main as backend_main

    warm_entered = threading.Event()
    allow_warm_exit = threading.Event()
    lifecycle: list[str] = []

    class _WarmableGateway:
        def __init__(self) -> None:
            self._registration_flow_version = 2

        def get_summary(self) -> ProgramAccessSummary:
            return ProgramAccessSummary(
                mode="remote_entitlement",
                stage="packaged_release",
                guard_enabled=True,
                message=PROGRAM_AUTH_REQUIRED_MESSAGE,
                registration_flow_version=self._registration_flow_version,
                username=None,
                auth_state=None,
                runtime_state="stopped",
                grace_expires_at=None,
                last_error_code=PROGRAM_AUTH_REQUIRED_CODE,
            )

        def warm_registration_readiness_cache(self) -> int:
            lifecycle.append("warm-enter")
            warm_entered.set()
            allow_warm_exit.wait(timeout=5)
            self._registration_flow_version = 3
            lifecycle.append("warm-exit")
            return self._registration_flow_version

        def close(self) -> None:
            lifecycle.append("close")

    gateway = _WarmableGateway()

    def _fake_build_program_access_services(**_kwargs):
        return gateway, object(), object(), object(), None

    monkeypatch.setattr(backend_main, "_build_program_access_services", _fake_build_program_access_services)

    app = backend_main.create_app(
        db_path=tmp_path / "deferred-packaged-release-warm.db",
        deferred_init=True,
        program_access_stage="packaged_release",
        program_access_start_refresh_scheduler=False,
    )

    with TestClient(app) as client:
        ready_deadline = time.monotonic() + 5
        while time.monotonic() < ready_deadline:
            response = client.get("/health")
            payload = response.json()
            if payload["ready"] is True:
                break
            time.sleep(0.05)

        assert payload["status"] == "ok"
        assert payload["ready"] is True
        assert warm_entered.wait(timeout=5) is True

        health_while_warm_running = client.get("/health")
        assert health_while_warm_running.json()["ready"] is True
        assert client.get("/app/bootstrap").json()["program_access"]["registration_flow_version"] == 2

        allow_warm_exit.set()

        warm_deadline = time.monotonic() + 5
        warmed_version = None
        while time.monotonic() < warm_deadline:
            warmed_version = client.get("/app/bootstrap").json()["program_access"]["registration_flow_version"]
            if warmed_version == 3:
                break
            time.sleep(0.05)

        assert warmed_version == 3

    assert "close" in lifecycle
