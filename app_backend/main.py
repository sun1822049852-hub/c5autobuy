from __future__ import annotations

import asyncio
import logging
import os
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
# Lifespan — used only when *deferred_init=True* (production / main()).
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _deferred_lifespan(app: FastAPI):
    """Run heavy init in a background task so uvicorn can accept /health immediately."""
    init_task = asyncio.create_task(_deferred_init(app))
    try:
        yield
    finally:
        # Shutdown: cancel init if still running, then run cleanup.
        init_task.cancel()
        try:
            await init_task
        except asyncio.CancelledError:
            pass
        _shutdown_program_access(app)


async def _deferred_init(app: FastAPI) -> None:
    """Phase 2: execute all heavy initialisation off the critical startup path."""
    params = app.state._init_params
    try:
        await asyncio.to_thread(_sync_heavy_init, app, params)
    except Exception:
        _logger.exception("Deferred init failed")
        app.state._init_error = "deferred init failed — check logs"
        raise


def _shutdown_program_access(app: FastAPI) -> None:
    scheduler = getattr(app.state, "program_access_refresh_scheduler", None)
    if scheduler is not None:
        scheduler.stop()
    gateway = getattr(app.state, "program_access_gateway", None)
    close = getattr(gateway, "close", None)
    if callable(close):
        close()


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

    # ------------------------------------------------------------------
    # Phase 1 — minimal app: /health reachable immediately
    # ------------------------------------------------------------------
    app = FastAPI(
        title="C5 Account Center Backend",
        lifespan=_deferred_lifespan if deferred_init else None,
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

    @app.get("/health")
    async def health() -> dict:
        error = getattr(app.state, "_init_error", None)
        if error:
            return {"status": "error", "ready": False, "error": str(error)}
        return {"status": "ok", "ready": getattr(app.state, "_ready", False)}

    if deferred_init:
        # Store params for _deferred_init to pick up later.
        app.add_middleware(_ReadinessGateMiddleware)
        app.state._init_params = {
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
        return app

    # ------------------------------------------------------------------
    # Phase 2 (synchronous) — full init, used by tests & non-deferred mode
    # ------------------------------------------------------------------
    _sync_heavy_init(app, {
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
    })

    # Legacy shutdown hook for non-deferred mode (lifespan handles deferred).
    @app.on_event("shutdown")
    async def _shutdown_program_access_services() -> None:
        _shutdown_program_access(app)

    return app


# ---------------------------------------------------------------------------
# _sync_heavy_init — all the expensive work, extracted from old create_app()
# ---------------------------------------------------------------------------

def _sync_heavy_init(app: FastAPI, params: dict) -> None:
    """Build every service / repository and wire routers onto *app*.

    Called synchronously in test mode, or via ``asyncio.to_thread`` in deferred
    mode.  Must be safe to run from any thread (no event-loop interaction).
    """
    # ------------------------------------------------------------------
    # Deferred imports — kept out of module-level so that
    # `from app_backend.main import main` only loads ~200ms of deps.
    # ------------------------------------------------------------------
    from app_backend.api.routes import account_center as account_center_routes
    from app_backend.api.routes import accounts as account_routes
    from app_backend.api.routes import app_bootstrap as app_bootstrap_routes
    from app_backend.api.routes import diagnostics as diagnostics_routes
    from app_backend.api.routes import purchase_runtime as purchase_runtime_routes
    from app_backend.api.routes import program_auth as program_auth_routes
    from app_backend.api.routes import proxy_pool as proxy_pool_routes
    from app_backend.api.routes import query_configs as query_config_routes
    from app_backend.api.routes import query_settings as query_settings_routes
    from app_backend.api.routes import runtime_settings as runtime_settings_routes
    from app_backend.api.routes import query_items as query_item_routes
    from app_backend.api.routes import query_runtime as query_runtime_routes
    from app_backend.api.routes import stats as stats_routes
    from app_backend.api.routes import tasks as task_routes
    from app_backend.api.websocket import tasks as task_websocket_routes
    from app_backend.api.websocket import accounts as account_websocket_routes
    from app_backend.api.websocket import runtime as runtime_websocket_routes
    from app_backend.infrastructure.db.base import build_engine, build_session_factory, create_schema
    from app_backend.infrastructure.events import AccountUpdateHub
    from app_backend.infrastructure.events.runtime_update_hub import RuntimeUpdateHub
    from app_backend.infrastructure.purchase.runtime.inventory_refresh_gateway import (
        InventoryRefreshGateway,
    )
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService
    from app_backend.infrastructure.repositories.account_inventory_snapshot_repository import (
        SqliteAccountInventorySnapshotRepository,
    )
    from app_backend.infrastructure.repositories.account_session_bundle_repository import (
        SqliteAccountSessionBundleRepository,
    )
    from app_backend.infrastructure.repositories.account_repository import SqliteAccountRepository
    from app_backend.infrastructure.repositories.proxy_pool_repository import SqliteProxyPoolRepository
    from app_backend.infrastructure.repositories.purchase_ui_preferences_repository import (
        SqlitePurchaseUiPreferencesRepository,
    )
    from app_backend.infrastructure.repositories.runtime_settings_repository import (
        SqliteRuntimeSettingsRepository,
    )
    from app_backend.infrastructure.repositories.stats_repository import SqliteStatsRepository
    from app_backend.infrastructure.repositories.query_config_repository import SqliteQueryConfigRepository
    from app_backend.infrastructure.repositories.query_settings_repository import SqliteQuerySettingsRepository
    from app_backend.infrastructure.stats.runtime.stats_pipeline import StatsPipeline
    from app_backend.infrastructure.query.collectors.detail_account_selector import DetailAccountSelector
    from app_backend.infrastructure.query.collectors.product_detail_collector import ProductDetailCollector
    from app_backend.infrastructure.query.collectors.product_detail_fetcher import ProductDetailFetcher
    from app_backend.infrastructure.query.refresh.query_item_detail_refresh_service import QueryItemDetailRefreshService
    from app_backend.infrastructure.query.collectors.product_url_parser import ProductUrlParser
    from app_backend.infrastructure.browser_runtime.login_adapter import (
        ManagedEdgeCdpLoginRunner,
        BrowserLoginAdapter,
    )
    from app_backend.infrastructure.browser_runtime.account_browser_profile_store import (
        AccountBrowserProfileStore,
    )
    from app_backend.infrastructure.browser_runtime.managed_browser_runtime import ManagedBrowserRuntime
    from app_backend.infrastructure.browser_runtime.open_api_binding_sync_service import (
        OpenApiBindingSyncService,
    )
    from app_backend.infrastructure.browser_runtime.open_api_binding_page_launcher import (
        OpenApiBindingPageLauncher,
    )
    from app_backend.application.use_cases.delete_account import DeleteAccountUseCase
    from app_backend.application.use_cases.proxy_pool_use_cases import ProxyPoolUseCases
    from app_backend.infrastructure.proxy.proxy_test_service import ProxyTestService
    from app_backend.application.services.account_balance_service import AccountBalanceService
    from app_backend.workers.manager.task_manager import TaskManager
    from app_backend.infrastructure.request_diagnostics import RequestDiagnosticsMiddleware
    database_path: Path = params["database_path"]
    program_access_stage = params["program_access_stage"]
    program_access_app_data_root = params["program_access_app_data_root"]
    program_access_secret_stage = params["program_access_secret_stage"]
    program_access_secret_platform = params["program_access_secret_platform"]
    program_access_control_plane_base_url = params["program_access_control_plane_base_url"]
    program_access_key_cache_path = params["program_access_key_cache_path"]
    program_access_refresh_interval_seconds = params["program_access_refresh_interval_seconds"]
    program_access_probe_registration_readiness = params["program_access_probe_registration_readiness"]
    program_access_start_refresh_scheduler = params["program_access_start_refresh_scheduler"]
    request_diagnostics_log_path = params["request_diagnostics_log_path"]
    request_diagnostics_slow_ms = params["request_diagnostics_slow_ms"]

    engine = build_engine(database_path)
    create_schema(engine)
    session_factory = build_session_factory(engine)
    repository = SqliteAccountRepository(session_factory)
    proxy_pool_repository = SqliteProxyPoolRepository(session_factory)
    proxy_pool_use_cases = ProxyPoolUseCases(proxy_pool_repository, repository)
    proxy_test_service = ProxyTestService()
    managed_browser_runtime = ManagedBrowserRuntime.from_environment(
        default_root=database_path.parent / "app-private",
    )
    bundle_repository = SqliteAccountSessionBundleRepository(
        session_factory,
        storage_root=managed_browser_runtime.bundle_root,
    )
    query_config_repository = SqliteQueryConfigRepository(session_factory)
    query_settings_repository = SqliteQuerySettingsRepository(session_factory)
    inventory_snapshot_repository = SqliteAccountInventorySnapshotRepository(session_factory)
    purchase_ui_preferences_repository = SqlitePurchaseUiPreferencesRepository(session_factory)
    runtime_settings_repository = SqliteRuntimeSettingsRepository(session_factory)
    stats_repository = SqliteStatsRepository(session_factory)
    resolved_program_access_stage = _resolve_program_access_stage(program_access_stage)
    (
        program_access_gateway,
        program_access_credential_store,
        program_access_secret_store,
        program_access_device_id_store,
        program_access_refresh_scheduler,
    ) = _build_program_access_services(
        stage=resolved_program_access_stage,
        managed_browser_runtime=managed_browser_runtime,
        explicit_app_data_root=program_access_app_data_root,
        explicit_secret_stage=program_access_secret_stage,
        explicit_secret_platform=program_access_secret_platform,
        explicit_control_plane_base_url=program_access_control_plane_base_url,
        explicit_key_cache_path=program_access_key_cache_path,
        explicit_refresh_interval_seconds=program_access_refresh_interval_seconds,
        explicit_probe_registration_readiness=program_access_probe_registration_readiness,
    )
    stats_pipeline = StatsPipeline(repository=stats_repository)
    stats_pipeline.start()
    account_update_hub = AccountUpdateHub()
    runtime_update_hub = RuntimeUpdateHub()
    account_balance_service = AccountBalanceService(
        account_repository=repository,
        account_update_hub=account_update_hub,
    )
    purchase_runtime_service = PurchaseRuntimeService(
        account_repository=repository,
        settings_repository=runtime_settings_repository,
        inventory_snapshot_repository=inventory_snapshot_repository,
        query_config_repository=query_config_repository,
        purchase_ui_preferences_repository=purchase_ui_preferences_repository,
        stats_repository=stats_repository,
        inventory_refresh_gateway_factory=InventoryRefreshGateway,
        stats_sink=stats_pipeline.enqueue,
        runtime_update_hub=runtime_update_hub,
    )
    open_api_binding_sync_service = OpenApiBindingSyncService(
        account_repository=repository,
        account_update_hub=account_update_hub,
        account_balance_service=account_balance_service,
        account_cleanup_callback=DeleteAccountUseCase(
            repository,
            bundle_repository,
            account_update_hub,
        ).execute,
        poll_interval_seconds=1.0,
        debug_log_path=database_path.parent / "runtime" / "open_api_binding_debug.runtime.jsonl",
    )
    query_runtime_service = QueryRuntimeService(
        query_config_repository=query_config_repository,
        query_settings_repository=query_settings_repository,
        account_repository=repository,
        purchase_runtime_service=purchase_runtime_service,
        open_api_binding_sync_service=open_api_binding_sync_service,
        stats_sink=stats_pipeline.enqueue,
        runtime_update_hub=runtime_update_hub,
    )
    purchase_runtime_service.set_query_runtime_service(query_runtime_service)
    task_manager = TaskManager()
    account_browser_profile_store = AccountBrowserProfileStore(runtime=managed_browser_runtime)
    login_adapter = BrowserLoginAdapter(
        login_runner=ManagedEdgeCdpLoginRunner(
            runtime=managed_browser_runtime,
            profile_store=account_browser_profile_store,
        ).run
    )
    product_url_parser = ProductUrlParser()
    detail_account_selector = DetailAccountSelector(repository)
    product_detail_fetcher = ProductDetailFetcher(selector=detail_account_selector)
    product_detail_collector = ProductDetailCollector(fetcher=product_detail_fetcher.fetch)
    query_item_detail_refresh_service = QueryItemDetailRefreshService(
        repository=query_config_repository,
        collector=product_detail_collector,
    )
    open_api_binding_page_launcher = OpenApiBindingPageLauncher(
        runtime=managed_browser_runtime,
        profile_store=account_browser_profile_store,
        debug_log_path=database_path.parent / "runtime" / "open_api_binding_page_launcher.runtime.jsonl",
    )

    # -- Bind state --------------------------------------------------------
    app.state.account_repository = repository
    app.state.proxy_pool_repository = proxy_pool_repository
    app.state.proxy_pool_use_cases = proxy_pool_use_cases
    app.state.proxy_test_service = proxy_test_service
    app.state.program_access_gateway = program_access_gateway
    app.state.program_access_stage = resolved_program_access_stage
    app.state.program_access_credential_store = program_access_credential_store
    app.state.program_access_secret_store = program_access_secret_store
    app.state.program_access_device_id_store = program_access_device_id_store
    app.state.program_access_refresh_scheduler = program_access_refresh_scheduler
    app.state.account_session_bundle_repository = bundle_repository
    app.state.managed_browser_runtime = managed_browser_runtime
    app.state.query_config_repository = query_config_repository
    app.state.query_settings_repository = query_settings_repository
    app.state.purchase_ui_preferences_repository = purchase_ui_preferences_repository
    app.state.runtime_settings_repository = runtime_settings_repository
    app.state.purchase_runtime_service = purchase_runtime_service
    app.state.query_runtime_service = query_runtime_service
    app.state.task_manager = task_manager
    app.state.account_update_hub = account_update_hub
    app.state.runtime_update_hub = runtime_update_hub
    app.state.login_adapter = login_adapter
    app.state.account_browser_profile_store = account_browser_profile_store
    app.state.product_url_parser = product_url_parser
    app.state.product_detail_collector = product_detail_collector
    app.state.query_item_detail_refresh_service = query_item_detail_refresh_service
    app.state.open_api_binding_sync_service = open_api_binding_sync_service
    app.state.open_api_binding_page_launcher = open_api_binding_page_launcher
    app.state.account_balance_service = account_balance_service
    app.state.stats_repository = stats_repository
    app.state.stats_pipeline = stats_pipeline
    app.state.request_diagnostics_log_path = request_diagnostics_log_path
    app.state.request_diagnostics_slow_ms = request_diagnostics_slow_ms

    if program_access_refresh_scheduler is not None and program_access_start_refresh_scheduler:
        program_access_refresh_scheduler.start()

    # -- Request diagnostics middleware (deferred from Phase 1) ----------------
    request_diagnostics_log_path = params["request_diagnostics_log_path"]
    request_diagnostics_slow_ms = params["request_diagnostics_slow_ms"]
    app.add_middleware(
        RequestDiagnosticsMiddleware,
        log_path=request_diagnostics_log_path,
        slow_ms=request_diagnostics_slow_ms,
    )

    # -- Register routers --------------------------------------------------
    app.include_router(account_center_routes.router)
    app.include_router(account_routes.router)
    app.include_router(app_bootstrap_routes.router)
    app.include_router(diagnostics_routes.router)
    app.include_router(program_auth_routes.router)
    app.include_router(proxy_pool_routes.router)
    app.include_router(purchase_runtime_routes.router)
    app.include_router(query_config_routes.router)
    app.include_router(query_settings_routes.router)
    app.include_router(runtime_settings_routes.router)
    app.include_router(query_item_routes.router)
    app.include_router(query_runtime_routes.router)
    app.include_router(stats_routes.router)
    app.include_router(task_routes.router)
    app.include_router(task_websocket_routes.router)
    app.include_router(account_websocket_routes.router)
    app.include_router(runtime_websocket_routes.router)

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

