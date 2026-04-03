from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app_backend.api.routes import account_center as account_center_routes
from app_backend.api.routes import accounts as account_routes
from app_backend.api.routes import app_bootstrap as app_bootstrap_routes
from app_backend.api.routes import diagnostics as diagnostics_routes
from app_backend.api.routes import purchase_runtime as purchase_runtime_routes
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
from app_backend.application.services.account_balance_service import AccountBalanceService
from app_backend.workers.manager.task_manager import TaskManager
from app_backend.infrastructure.request_diagnostics import RequestDiagnosticsMiddleware


def create_app(
    db_path: Path | None = None,
    *,
    request_diagnostics_log_path: Path | None = None,
    request_diagnostics_slow_ms: float = 2_000,
) -> FastAPI:
    database_path = db_path or Path("data/app.db")
    database_path.parent.mkdir(parents=True, exist_ok=True)
    request_diagnostics_log_path = request_diagnostics_log_path or (
        database_path.parent / "runtime" / "request_diagnostics.runtime.jsonl"
    )
    engine = build_engine(database_path)
    create_schema(engine)
    session_factory = build_session_factory(engine)
    repository = SqliteAccountRepository(session_factory)
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
    stats_pipeline = StatsPipeline(repository=stats_repository)
    stats_pipeline.start()
    account_update_hub = AccountUpdateHub()
    runtime_update_hub = RuntimeUpdateHub()
    purchase_runtime_service = PurchaseRuntimeService(
        account_repository=repository,
        settings_repository=runtime_settings_repository,
        inventory_snapshot_repository=inventory_snapshot_repository,
        inventory_refresh_gateway_factory=InventoryRefreshGateway,
        stats_sink=stats_pipeline.enqueue,
        runtime_update_hub=runtime_update_hub,
    )
    open_api_binding_sync_service = OpenApiBindingSyncService(
        account_repository=repository,
        account_update_hub=account_update_hub,
        account_cleanup_callback=DeleteAccountUseCase(
            repository,
            bundle_repository,
            account_update_hub,
        ).execute,
        poll_interval_seconds=1.0,
        debug_log_path=database_path.parent / "runtime" / "open_api_binding_debug.runtime.jsonl",
    )
    account_balance_service = AccountBalanceService(
        account_repository=repository,
        account_update_hub=account_update_hub,
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

    app = FastAPI(title="C5 Account Center Backend")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["null"],
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(
        RequestDiagnosticsMiddleware,
        log_path=request_diagnostics_log_path,
        slow_ms=request_diagnostics_slow_ms,
    )
    app.state.account_repository = repository
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

    app.include_router(account_center_routes.router)
    app.include_router(account_routes.router)
    app.include_router(app_bootstrap_routes.router)
    app.include_router(diagnostics_routes.router)
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

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


def main(*, db_path: Path | None = None, host: str = "127.0.0.1", port: int = 8000) -> None:
    uvicorn.run(
        create_app(db_path=db_path),
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()

