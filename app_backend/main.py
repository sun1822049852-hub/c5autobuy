from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app_backend.api.routes import account_center as account_center_routes
from app_backend.api.routes import accounts as account_routes
from app_backend.api.routes import purchase_runtime as purchase_runtime_routes
from app_backend.api.routes import query_configs as query_config_routes
from app_backend.api.routes import query_settings as query_settings_routes
from app_backend.api.routes import query_items as query_item_routes
from app_backend.api.routes import query_runtime as query_runtime_routes
from app_backend.api.routes import stats as stats_routes
from app_backend.api.routes import tasks as task_routes
from app_backend.api.websocket import tasks as task_websocket_routes
from app_backend.infrastructure.db.base import build_engine, build_session_factory, create_schema
from app_backend.infrastructure.purchase.runtime.inventory_refresh_gateway import (
    InventoryRefreshGateway,
)
from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService
from app_backend.infrastructure.repositories.account_inventory_snapshot_repository import (
    SqliteAccountInventorySnapshotRepository,
)
from app_backend.infrastructure.repositories.account_repository import SqliteAccountRepository
from app_backend.infrastructure.repositories.purchase_ui_preferences_repository import (
    SqlitePurchaseUiPreferencesRepository,
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
from app_backend.infrastructure.selenium.login_adapter import SeleniumLoginAdapter
from app_backend.workers.manager.task_manager import TaskManager


def create_app(db_path: Path | None = None) -> FastAPI:
    database_path = db_path or Path("data/app.db")
    database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = build_engine(database_path)
    create_schema(engine)
    session_factory = build_session_factory(engine)
    repository = SqliteAccountRepository(session_factory)
    query_config_repository = SqliteQueryConfigRepository(session_factory)
    query_settings_repository = SqliteQuerySettingsRepository(session_factory)
    inventory_snapshot_repository = SqliteAccountInventorySnapshotRepository(session_factory)
    purchase_ui_preferences_repository = SqlitePurchaseUiPreferencesRepository(session_factory)
    stats_repository = SqliteStatsRepository(session_factory)
    stats_pipeline = StatsPipeline(repository=stats_repository)
    stats_pipeline.start()
    purchase_runtime_service = PurchaseRuntimeService(
        account_repository=repository,
        inventory_snapshot_repository=inventory_snapshot_repository,
        inventory_refresh_gateway_factory=InventoryRefreshGateway,
        stats_sink=stats_pipeline.enqueue,
    )
    query_runtime_service = QueryRuntimeService(
        query_config_repository=query_config_repository,
        query_settings_repository=query_settings_repository,
        account_repository=repository,
        purchase_runtime_service=purchase_runtime_service,
        stats_sink=stats_pipeline.enqueue,
    )
    task_manager = TaskManager()
    login_adapter = SeleniumLoginAdapter()
    product_url_parser = ProductUrlParser()
    detail_account_selector = DetailAccountSelector(repository)
    product_detail_fetcher = ProductDetailFetcher(selector=detail_account_selector)
    product_detail_collector = ProductDetailCollector(fetcher=product_detail_fetcher.fetch)
    query_item_detail_refresh_service = QueryItemDetailRefreshService(
        repository=query_config_repository,
        collector=product_detail_collector,
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
    app.state.account_repository = repository
    app.state.query_config_repository = query_config_repository
    app.state.query_settings_repository = query_settings_repository
    app.state.purchase_ui_preferences_repository = purchase_ui_preferences_repository
    app.state.purchase_runtime_service = purchase_runtime_service
    app.state.query_runtime_service = query_runtime_service
    app.state.task_manager = task_manager
    app.state.login_adapter = login_adapter
    app.state.product_url_parser = product_url_parser
    app.state.product_detail_collector = product_detail_collector
    app.state.query_item_detail_refresh_service = query_item_detail_refresh_service
    app.state.stats_repository = stats_repository
    app.state.stats_pipeline = stats_pipeline

    app.include_router(account_center_routes.router)
    app.include_router(account_routes.router)
    app.include_router(purchase_runtime_routes.router)
    app.include_router(query_config_routes.router)
    app.include_router(query_settings_routes.router)
    app.include_router(query_item_routes.router)
    app.include_router(query_runtime_routes.router)
    app.include_router(stats_routes.router)
    app.include_router(task_routes.router)
    app.include_router(task_websocket_routes.router)

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
