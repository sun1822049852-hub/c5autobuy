from __future__ import annotations

import asyncio
import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

# ---------------------------------------------------------------------------
# Phase 1 only needs FastAPI + CORSMiddleware + BaseHTTPMiddleware (already
# imported above).  All other imports are deferred to _sync_heavy_init() so
# that `from app_backend.main import main` stays fast (~200ms).
# ---------------------------------------------------------------------------


PROGRAM_ACCESS_APP_NAME = "C5AutoBug"
DEFAULT_PROGRAM_CONTROL_PLANE_BASE_URL = "http://8.138.39.139:18787"

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Readiness gate middleware — returns 503 for business routes while Phase 2
# initialisation is still in progress.
# ---------------------------------------------------------------------------

class _ReadinessGateMiddleware(BaseHTTPMiddleware):
    """Return 503 for every non-health request until ``app.state._ready`` is True."""

    async def dispatch(self, request: Request, call_next):
        if not getattr(request.app.state, "_ready", False):
            if request.url.path != "/health":
                return Response(
                    content='{"detail":"service is starting"}',
                    status_code=503,
                    media_type="application/json",
                )
        return await call_next(request)


# ---------------------------------------------------------------------------
# Lifespan — shared by both modes. Deferred mode also starts Phase 2 init.
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _app_lifespan(app: FastAPI):
    """Run shared shutdown cleanup and optional deferred init."""
    init_task = None
    if getattr(app.state, "_deferred_init_enabled", False):
        init_task = asyncio.create_task(_deferred_init(app))
    _schedule_program_access_post_ready_init(app)
    try:
        yield
    finally:
        if init_task is not None:
            # Shutdown: cancel init if still running, then run cleanup.
            init_task.cancel()
            try:
                await init_task
            except asyncio.CancelledError:
                pass
        post_ready_task = getattr(app.state, "_program_access_post_ready_init_task", None)
        if post_ready_task is not None:
            try:
                await post_ready_task
            except asyncio.CancelledError:
                pass
        _shutdown_program_access(app)


async def _deferred_init(app: FastAPI) -> None:
    """Phase 2: execute all heavy initialisation off the critical startup path."""
    params = app.state._init_params
    try:
        await asyncio.to_thread(_sync_heavy_init, app, params)
        _schedule_program_access_post_ready_init(app)
    except Exception:
        _logger.exception("Deferred init failed")
        app.state._init_error = "deferred init failed — check logs"
        raise


def _schedule_program_access_post_ready_init(app: FastAPI) -> None:
    if not getattr(app.state, "_program_access_post_ready_init_pending", False):
        return

    task = getattr(app.state, "_program_access_post_ready_init_task", None)
    if task is not None and not task.done():
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    app.state._program_access_post_ready_init_pending = False
    app.state._program_access_post_ready_init_task = loop.create_task(
        _run_program_access_post_ready_init(app)
    )


async def _run_program_access_post_ready_init(app: FastAPI) -> None:
    scheduler = getattr(app.state, "program_access_refresh_scheduler", None)
    gateway = getattr(app.state, "program_access_gateway", None)

    lifecycle_lock = getattr(app.state, "_program_access_lifecycle_lock", None)
    warm_registration_readiness_cache = _resolve_program_access_post_ready_warm(gateway)

    def _post_ready_init() -> None:
        if lifecycle_lock is None:
            if getattr(app.state, "_program_access_shutdown_requested", False):
                return
            if callable(warm_registration_readiness_cache):
                warm_registration_readiness_cache()
            if getattr(app.state, "_program_access_shutdown_requested", False):
                return
            if scheduler is not None:
                scheduler.start()
            return

        with lifecycle_lock:
            if getattr(app.state, "_program_access_shutdown_requested", False):
                return
            if callable(warm_registration_readiness_cache):
                warm_registration_readiness_cache()
            if getattr(app.state, "_program_access_shutdown_requested", False):
                return
            if scheduler is not None:
                scheduler.start()

    try:
        await asyncio.to_thread(_post_ready_init)
    except Exception:
        _logger.exception("Program access post-ready init failed")


def _shutdown_program_access(app: FastAPI) -> None:
    app.state._program_access_shutdown_requested = True
    scheduler = getattr(app.state, "program_access_refresh_scheduler", None)
    gateway = getattr(app.state, "program_access_gateway", None)
    lifecycle_lock = getattr(app.state, "_program_access_lifecycle_lock", None)

    if lifecycle_lock is None:
        if scheduler is not None:
            scheduler.stop()
        close = getattr(gateway, "close", None)
        if callable(close):
            close()
        return

    with lifecycle_lock:
        if scheduler is not None:
            scheduler.stop()
        close = getattr(gateway, "close", None)
        if callable(close):
            close()


def _supports_program_access_post_ready_warm(gateway: object) -> bool:
    warm = _resolve_program_access_post_ready_warm(gateway)
    return callable(warm)


def _resolve_program_access_post_ready_warm(gateway: object):
    warm = getattr(gateway, "warm_registration_readiness_cache", None)
    if callable(warm):
        return warm
    warm = getattr(gateway, "warm_registration_flow_version_cache", None)
    if callable(warm):
        return warm
    return None


def _resolve_program_access_stage(explicit_stage: str | None) -> str:
    return str(explicit_stage or os.getenv("C5_PROGRAM_ACCESS_STAGE") or "prepackaging")


def _resolve_program_access_app_data_root(
    explicit_root: Path | None,
    *,
    managed_browser_runtime: ManagedBrowserRuntime,
) -> Path:
    if explicit_root is not None:
        return Path(explicit_root)

    env_root = os.getenv("C5_PROGRAM_ACCESS_APP_DATA_ROOT")
    if env_root:
        return Path(env_root)

    return managed_browser_runtime.app_private_dir


def _resolve_program_access_control_plane_base_url(explicit_base_url: str | None) -> str:
    return str(
        explicit_base_url
        or os.getenv("C5_PROGRAM_CONTROL_PLANE_BASE_URL")
        or DEFAULT_PROGRAM_CONTROL_PLANE_BASE_URL
    ).strip()


def _resolve_program_access_key_cache_path(
    explicit_key_cache_path: Path | None,
    *,
    app_data_root: Path,
) -> Path:
    if explicit_key_cache_path is not None:
        return Path(explicit_key_cache_path)

    env_path = os.getenv("C5_PROGRAM_CONTROL_PLANE_KEY_CACHE_PATH")
    if env_path:
        return Path(env_path)

    return Path(app_data_root) / PROGRAM_ACCESS_APP_NAME / "program_access" / "control_plane_public.pem"


def _resolve_program_access_refresh_interval_seconds(explicit_interval: float | None) -> float:
    if explicit_interval is not None:
        return float(explicit_interval)

    raw = os.getenv("C5_PROGRAM_ACCESS_REFRESH_INTERVAL_SECONDS")
    if raw is None:
        return 300.0
    try:
        return float(raw)
    except ValueError:
        return 300.0


def _resolve_program_access_probe_registration_readiness(explicit_flag: bool | None) -> bool:
    if explicit_flag is not None:
        return bool(explicit_flag)

    raw = os.getenv("C5_PROGRAM_ACCESS_PROBE_REGISTRATION_READINESS")
    if raw is None:
        return False

    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _build_program_access_bundle_path(app_data_root: Path) -> Path:
    return Path(app_data_root) / PROGRAM_ACCESS_APP_NAME / "program_access" / "bundle.json"


def _build_program_access_services(
    *,
    stage: str,
    managed_browser_runtime: ManagedBrowserRuntime,
    explicit_app_data_root: Path | None,
    explicit_secret_stage: str | None,
    explicit_secret_platform: str | None,
    explicit_control_plane_base_url: str | None,
    explicit_key_cache_path: Path | None,
    explicit_refresh_interval_seconds: float | None,
    explicit_probe_registration_readiness: bool | None,
):
    from app_backend.infrastructure.program_access import (
        EntitlementVerifier,
        FileProgramCredentialStore,
        LocalPassThroughGateway,
        RefreshScheduler,
        RemoteControlPlaneClient,
        RemoteEntitlementGateway,
        build_device_id_store,
        build_secret_store,
    )
    if stage != "packaged_release":
        return LocalPassThroughGateway(), None, None, None, None

    control_plane_base_url = _resolve_program_access_control_plane_base_url(explicit_control_plane_base_url)
    app_data_root = _resolve_program_access_app_data_root(
        explicit_app_data_root,
        managed_browser_runtime=managed_browser_runtime,
    )
    secret_stage = str(explicit_secret_stage or os.getenv("C5_PROGRAM_ACCESS_SECRET_STAGE") or "packaged_release")
    secret_platform = explicit_secret_platform or os.getenv("C5_PROGRAM_ACCESS_SECRET_PLATFORM")
    device_id_store = build_device_id_store(
        app_name=PROGRAM_ACCESS_APP_NAME,
        app_data_root=app_data_root,
    )
    secret_store = build_secret_store(
        stage=secret_stage,
        app_name=PROGRAM_ACCESS_APP_NAME,
        storage_root=app_data_root,
        platform=secret_platform,
    )
    credential_store = FileProgramCredentialStore(
        _build_program_access_bundle_path(app_data_root),
        secret_store=secret_store,
        device_id_store=device_id_store,
    )
    key_cache_path = _resolve_program_access_key_cache_path(
        explicit_key_cache_path,
        app_data_root=app_data_root,
    )
    verifier = EntitlementVerifier(key_cache_path=key_cache_path)
    remote_client = RemoteControlPlaneClient(base_url=control_plane_base_url)
    gateway = RemoteEntitlementGateway(
        remote_client=remote_client,
        verifier=verifier,
        credential_store=credential_store,
        secret_store=secret_store,
        device_id_store=device_id_store,
        stage=stage,
        probe_registration_readiness=_resolve_program_access_probe_registration_readiness(
            explicit_probe_registration_readiness
        ),
    )
    scheduler = RefreshScheduler(
        gateway=gateway,
        interval_seconds=_resolve_program_access_refresh_interval_seconds(explicit_refresh_interval_seconds),
    )
    return gateway, credential_store, secret_store, device_id_store, scheduler


def _router_registration_key(router) -> tuple[str, tuple[str, ...], tuple[tuple[str, str, tuple[str, ...], str], ...]]:
    route_keys = tuple(
        (
            type(route).__name__,
            str(getattr(route, "path", "") or getattr(route, "path_format", "") or ""),
            tuple(sorted(str(method) for method in (getattr(route, "methods", None) or ()))),
            str(getattr(route, "name", "") or ""),
        )
        for route in (getattr(router, "routes", ()) or ())
    )
    return (
        str(getattr(router, "prefix", "") or ""),
        tuple(str(tag) for tag in getattr(router, "tags", ()) or ()),
        route_keys,
    )


def _include_router_once(app: FastAPI, router) -> None:
    registered_keys = getattr(app.state, "_registered_router_keys", None)
    if registered_keys is None:
        registered_keys = set()
        app.state._registered_router_keys = registered_keys

    key = _router_registration_key(router)
    if key in registered_keys:
        return

    app.include_router(router)
    registered_keys.add(key)


def _register_core_home_routes(app: FastAPI) -> None:
    from app_backend.api.routes import account_center as account_center_routes
    from app_backend.api.routes import app_bootstrap as app_bootstrap_routes
    from app_backend.api.routes import program_auth as program_auth_routes

    _include_router_once(app, account_center_routes.router)
    _include_router_once(app, app_bootstrap_routes.router)
    _include_router_once(app, program_auth_routes.router)


def _register_runtime_full_routes(app: FastAPI) -> None:
    from app_backend.api.routes import diagnostics as diagnostics_routes
    from app_backend.api.routes import proxy_pool as proxy_pool_routes
    from app_backend.api.routes import purchase_runtime as purchase_runtime_routes
    from app_backend.api.routes import query_configs as query_config_routes
    from app_backend.api.routes import query_settings as query_settings_routes
    from app_backend.api.routes import runtime_settings as runtime_settings_routes
    from app_backend.api.routes import query_items as query_item_routes
    from app_backend.api.routes import query_runtime as query_runtime_routes
    from app_backend.api.routes import stats as stats_routes
    from app_backend.api.routes import tasks as task_routes
    from app_backend.api.websocket import tasks as task_websocket_routes
    from app_backend.api.websocket import runtime as runtime_websocket_routes

    _include_router_once(app, diagnostics_routes.router)
    _include_router_once(app, proxy_pool_routes.router)
    _include_router_once(app, purchase_runtime_routes.router)
    _include_router_once(app, query_config_routes.router)
    _include_router_once(app, query_settings_routes.router)
    _include_router_once(app, runtime_settings_routes.router)
    _include_router_once(app, query_item_routes.router)
    _include_router_once(app, query_runtime_routes.router)
    _include_router_once(app, stats_routes.router)
    _include_router_once(app, task_routes.router)
    _include_router_once(app, task_websocket_routes.router)
    _include_router_once(app, runtime_websocket_routes.router)


def _register_browser_action_routes(app: FastAPI) -> None:
    from app_backend.api.routes import accounts as account_routes
    from app_backend.api.websocket import accounts as account_websocket_routes

    _include_router_once(app, account_routes.router)
    _include_router_once(app, account_websocket_routes.router)


def _bind_state_mapping(app: FastAPI, services: dict[str, object] | MappingProxyType) -> None:
    for name, value in dict(services).items():
        setattr(app.state, name, value)


def _build_startup_slice_registry(
    *,
    database_path: Path,
    request_diagnostics_log_path: Path,
    request_diagnostics_slow_ms: float,
    program_access_stage: str | None,
    program_access_app_data_root: Path | None,
    program_access_secret_stage: str | None,
    program_access_secret_platform: str | None,
    program_access_control_plane_base_url: str | None,
    program_access_key_cache_path: Path | None,
    program_access_refresh_interval_seconds: float | None,
    program_access_probe_registration_readiness: bool | None,
    program_access_start_refresh_scheduler: bool,
):
    from app_backend.startup import (
        STARTUP_SLICE_BROWSER_ACTIONS,
        STARTUP_SLICE_CORE_HOME,
        STARTUP_SLICE_RUNTIME_FULL,
        BrowserActionBuildParams,
        CoreHomeBuildParams,
        ProgramAccessBuildOptions,
        RuntimeFullBuildParams,
        StartupSliceRegistry,
        build_browser_action_services,
        build_core_home_services,
        build_runtime_full_services,
    )

    registry = StartupSliceRegistry()
    core_services = build_core_home_services(
        CoreHomeBuildParams(
            database_path=database_path,
            program_access=ProgramAccessBuildOptions(
                stage=program_access_stage,
                app_data_root=program_access_app_data_root,
                secret_stage=program_access_secret_stage,
                secret_platform=program_access_secret_platform,
                control_plane_base_url=program_access_control_plane_base_url,
                key_cache_path=program_access_key_cache_path,
                refresh_interval_seconds=program_access_refresh_interval_seconds,
                probe_registration_readiness=program_access_probe_registration_readiness,
                start_refresh_scheduler=program_access_start_refresh_scheduler,
            ),
        ),
        program_access_services_factory=lambda *, stage, managed_browser_runtime, options: _build_program_access_services(
            stage=stage,
            managed_browser_runtime=managed_browser_runtime,
            explicit_app_data_root=options.app_data_root,
            explicit_secret_stage=options.secret_stage,
            explicit_secret_platform=options.secret_platform,
            explicit_control_plane_base_url=options.control_plane_base_url,
            explicit_key_cache_path=options.key_cache_path,
            explicit_refresh_interval_seconds=options.refresh_interval_seconds,
            explicit_probe_registration_readiness=options.probe_registration_readiness,
        ),
    )
    registry.register_slice(
        STARTUP_SLICE_CORE_HOME,
        lambda: core_services,
    )
    registry.ensure_slice(STARTUP_SLICE_CORE_HOME)
    registry.register_slice(
        STARTUP_SLICE_RUNTIME_FULL,
        lambda: build_runtime_full_services(
            core_services=registry.slice_services(STARTUP_SLICE_CORE_HOME),
            params=RuntimeFullBuildParams(
                database_path=database_path,
                request_diagnostics_log_path=request_diagnostics_log_path,
                request_diagnostics_slow_ms=request_diagnostics_slow_ms,
                program_access_start_refresh_scheduler=program_access_start_refresh_scheduler,
            ),
        ),
        depends_on=(STARTUP_SLICE_CORE_HOME,),
    )
    registry.register_slice(
        STARTUP_SLICE_BROWSER_ACTIONS,
        lambda: build_browser_action_services(
            core_services=registry.slice_services(STARTUP_SLICE_CORE_HOME),
            runtime_services=registry.slice_services(STARTUP_SLICE_RUNTIME_FULL),
            params=BrowserActionBuildParams(database_path=database_path),
        ),
        depends_on=(STARTUP_SLICE_RUNTIME_FULL,),
    )
    return registry, dict(registry.slice_services(STARTUP_SLICE_CORE_HOME))


def create_app(
    db_path: Path | None = None,
    *,
    request_diagnostics_log_path: Path | None = None,
    request_diagnostics_slow_ms: float = 2_000,
    program_access_stage: str | None = None,
    program_access_app_data_root: Path | None = None,
    program_access_secret_stage: str | None = None,
    program_access_secret_platform: str | None = None,
    program_access_control_plane_base_url: str | None = None,
    program_access_key_cache_path: Path | None = None,
    program_access_refresh_interval_seconds: float | None = None,
    program_access_probe_registration_readiness: bool | None = None,
    program_access_start_refresh_scheduler: bool = True,
    deferred_init: bool = False,
) -> FastAPI:
    # ------------------------------------------------------------------
    # Resolve lightweight params that don't touch DB / filesystem heavily
    # ------------------------------------------------------------------
    database_path = db_path or Path("data/app.db")
    database_path.parent.mkdir(parents=True, exist_ok=True)
    request_diagnostics_log_path = request_diagnostics_log_path or (
        database_path.parent / "runtime" / "request_diagnostics.runtime.jsonl"
    )
    from app_backend.infrastructure.request_diagnostics import RequestDiagnosticsMiddleware

    # ------------------------------------------------------------------
    # Phase 1 — minimal app: /health reachable immediately
    # ------------------------------------------------------------------
    app = FastAPI(
        title="C5 Account Center Backend",
        lifespan=_app_lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["null"],
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state._ready = False
    app.state._init_error = None
    app.state._deferred_init_enabled = deferred_init
    app.state._program_access_post_ready_init_pending = False
    app.state._program_access_post_ready_init_task = None
    app.state._program_access_shutdown_requested = False
    app.state._program_access_lifecycle_lock = threading.Lock()
    app.state._registered_router_keys = set()

    @app.get("/health")
    async def health() -> dict:
        error = getattr(app.state, "_init_error", None)
        if error:
            return {"status": "error", "ready": False, "error": str(error)}
        return {"status": "ok", "ready": getattr(app.state, "_ready", False)}

    # Register request diagnostics before startup begins. In deferred mode this
    # preserves the existing middleware order while avoiding Starlette's
    # "cannot add middleware after startup" restriction inside lifespan.
    app.add_middleware(
        RequestDiagnosticsMiddleware,
        log_path=request_diagnostics_log_path,
        slow_ms=request_diagnostics_slow_ms,
    )

    _register_core_home_routes(app)
    _register_runtime_full_routes(app)
    _register_browser_action_routes(app)

    init_params = {
        "database_path": database_path,
        "request_diagnostics_log_path": request_diagnostics_log_path,
        "request_diagnostics_slow_ms": request_diagnostics_slow_ms,
        "program_access_stage": program_access_stage,
        "program_access_app_data_root": program_access_app_data_root,
        "program_access_secret_stage": program_access_secret_stage,
        "program_access_secret_platform": program_access_secret_platform,
        "program_access_control_plane_base_url": program_access_control_plane_base_url,
        "program_access_key_cache_path": program_access_key_cache_path,
        "program_access_refresh_interval_seconds": program_access_refresh_interval_seconds,
        "program_access_probe_registration_readiness": program_access_probe_registration_readiness,
        "program_access_start_refresh_scheduler": program_access_start_refresh_scheduler,
    }
    app.state._init_params = init_params
    startup_slice_registry, core_home_services = _build_startup_slice_registry(
        database_path=database_path,
        request_diagnostics_log_path=request_diagnostics_log_path,
        request_diagnostics_slow_ms=request_diagnostics_slow_ms,
        program_access_stage=program_access_stage,
        program_access_app_data_root=program_access_app_data_root,
        program_access_secret_stage=program_access_secret_stage,
        program_access_secret_platform=program_access_secret_platform,
        program_access_control_plane_base_url=program_access_control_plane_base_url,
        program_access_key_cache_path=program_access_key_cache_path,
        program_access_refresh_interval_seconds=program_access_refresh_interval_seconds,
        program_access_probe_registration_readiness=program_access_probe_registration_readiness,
        program_access_start_refresh_scheduler=program_access_start_refresh_scheduler,
    )
    _bind_state_mapping(app, core_home_services)
    app.state.request_diagnostics_log_path = request_diagnostics_log_path
    app.state.request_diagnostics_slow_ms = request_diagnostics_slow_ms
    app.state.startup_slice_registry = startup_slice_registry

    def _ensure_runtime_full_ready() -> dict[str, object]:
        from app_backend.startup import STARTUP_SLICE_RUNTIME_FULL

        services = dict(startup_slice_registry.ensure_slice(STARTUP_SLICE_RUNTIME_FULL))
        _bind_state_mapping(app, services)
        return services

    def _ensure_browser_actions_ready() -> dict[str, object]:
        from app_backend.startup import STARTUP_SLICE_BROWSER_ACTIONS

        _ensure_runtime_full_ready()
        services = dict(startup_slice_registry.ensure_slice(STARTUP_SLICE_BROWSER_ACTIONS))
        _bind_state_mapping(app, services)
        return services

    app.state.ensure_runtime_full_ready = _ensure_runtime_full_ready
    app.state.ensure_browser_actions_ready = _ensure_browser_actions_ready
    app.state._program_access_post_ready_init_pending = bool(
        _supports_program_access_post_ready_warm(app.state.program_access_gateway)
        or (app.state.program_access_refresh_scheduler is not None and program_access_start_refresh_scheduler)
    )
    app.state._deferred_init_enabled = False
    app.state._ready = True

    if deferred_init:
        return app

    # ------------------------------------------------------------------
    # Phase 2 (synchronous) — full init, used by tests & non-deferred mode
    # ------------------------------------------------------------------
    _sync_heavy_init(app, init_params)

    return app


# ---------------------------------------------------------------------------
# _sync_heavy_init — legacy eager ensure wrapper for non-deferred mode
# ---------------------------------------------------------------------------

def _sync_heavy_init(app: FastAPI, params: dict) -> None:
    """Eagerly ensure non-core slices for legacy non-deferred callers."""
    ensure_runtime_full_ready = getattr(app.state, "ensure_runtime_full_ready", None)
    if callable(ensure_runtime_full_ready):
        ensure_runtime_full_ready()

    ensure_browser_actions_ready = getattr(app.state, "ensure_browser_actions_ready", None)
    if callable(ensure_browser_actions_ready):
        ensure_browser_actions_ready()

    app.state._ready = True


_default_app: FastAPI | None = None


def get_default_app() -> FastAPI:
    global _default_app
    if _default_app is None:
        _default_app = create_app()
    return _default_app


def __getattr__(name: str):
    if name == "app":
        return get_default_app()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def main(*, db_path: Path | None = None, host: str = "127.0.0.1", port: int = 8000) -> None:
    uvicorn.run(
        create_app(db_path=db_path, deferred_init=True),
        host=host,
        port=port,
        log_level="info",
    )

