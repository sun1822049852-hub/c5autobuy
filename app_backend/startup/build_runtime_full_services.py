from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from app_backend.startup.build_core_home_services import CoreHomeServices, require_core_home_services


@dataclass(frozen=True)
class RuntimeFullBuildParams:
    database_path: Path
    request_diagnostics_log_path: Path | None = None
    request_diagnostics_slow_ms: float = 2_000
    program_access_start_refresh_scheduler: bool = True


@dataclass(frozen=True)
class RuntimeFullServices:
    proxy_pool_repository: object
    proxy_pool_use_cases: object
    proxy_test_service: object
    query_config_repository: object
    query_settings_repository: object
    inventory_snapshot_repository: object
    purchase_ui_preferences_repository: object
    runtime_settings_repository: object
    stats_repository: object
    stats_pipeline: object
    purchase_runtime_service: object
    open_api_binding_sync_service: object
    query_runtime_service: object
    program_runtime_control_service: object | None
    task_manager: object
    product_url_parser: object
    product_detail_collector: object
    query_item_detail_refresh_service: object
    request_diagnostics_log_path: Path
    request_diagnostics_slow_ms: float
    program_access_post_ready_init_pending: bool


def require_runtime_full_services(services: Mapping[str, object]) -> RuntimeFullServices:
    return RuntimeFullServices(
        proxy_pool_repository=services["proxy_pool_repository"],
        proxy_pool_use_cases=services["proxy_pool_use_cases"],
        proxy_test_service=services["proxy_test_service"],
        query_config_repository=services["query_config_repository"],
        query_settings_repository=services["query_settings_repository"],
        inventory_snapshot_repository=services["inventory_snapshot_repository"],
        purchase_ui_preferences_repository=services["purchase_ui_preferences_repository"],
        runtime_settings_repository=services["runtime_settings_repository"],
        stats_repository=services["stats_repository"],
        stats_pipeline=services["stats_pipeline"],
        purchase_runtime_service=services["purchase_runtime_service"],
        open_api_binding_sync_service=services["open_api_binding_sync_service"],
        query_runtime_service=services["query_runtime_service"],
        program_runtime_control_service=services.get("program_runtime_control_service"),
        task_manager=services["task_manager"],
        product_url_parser=services["product_url_parser"],
        product_detail_collector=services["product_detail_collector"],
        query_item_detail_refresh_service=services["query_item_detail_refresh_service"],
        request_diagnostics_log_path=Path(services["request_diagnostics_log_path"]),
        request_diagnostics_slow_ms=float(services["request_diagnostics_slow_ms"]),
        program_access_post_ready_init_pending=bool(services["program_access_post_ready_init_pending"]),
    )


def build_runtime_full_services(
    *,
    core_services: CoreHomeServices | Mapping[str, object],
    params: RuntimeFullBuildParams,
) -> dict[str, object]:
    from app_backend.application.use_cases.delete_account import DeleteAccountUseCase
    from app_backend.application.use_cases.proxy_pool_use_cases import ProxyPoolUseCases
    from app_backend.infrastructure.proxy.proxy_test_service import ProxyTestService
    from app_backend.infrastructure.purchase.runtime.inventory_refresh_gateway import (
        InventoryRefreshGateway,
    )
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService
    from app_backend.infrastructure.query.runtime.query_runtime_service import QueryRuntimeService
    from app_backend.infrastructure.query.collectors.detail_account_selector import DetailAccountSelector
    from app_backend.infrastructure.query.collectors.product_detail_collector import ProductDetailCollector
    from app_backend.infrastructure.query.collectors.product_detail_fetcher import ProductDetailFetcher
    from app_backend.infrastructure.query.collectors.product_url_parser import ProductUrlParser
    from app_backend.infrastructure.query.refresh.query_item_detail_refresh_service import QueryItemDetailRefreshService
    from app_backend.infrastructure.browser_runtime.open_api_binding_sync_service import OpenApiBindingSyncService
    from app_backend.infrastructure.program_access.runtime_control_service import RuntimeControlService
    from app_backend.infrastructure.repositories.account_inventory_snapshot_repository import (
        SqliteAccountInventorySnapshotRepository,
    )
    from app_backend.infrastructure.repositories.proxy_pool_repository import SqliteProxyPoolRepository
    from app_backend.infrastructure.repositories.purchase_ui_preferences_repository import (
        SqlitePurchaseUiPreferencesRepository,
    )
    from app_backend.infrastructure.repositories.query_config_repository import SqliteQueryConfigRepository
    from app_backend.infrastructure.repositories.query_settings_repository import SqliteQuerySettingsRepository
    from app_backend.infrastructure.repositories.runtime_settings_repository import (
        SqliteRuntimeSettingsRepository,
    )
    from app_backend.infrastructure.repositories.stats_repository import SqliteStatsRepository
    from app_backend.infrastructure.stats.runtime.stats_pipeline import StatsPipeline
    from app_backend.workers.manager.task_manager import TaskManager

    shared = (
        core_services
        if isinstance(core_services, CoreHomeServices)
        else require_core_home_services(core_services)
    )
    database_path = Path(params.database_path)
    request_diagnostics_log_path = params.request_diagnostics_log_path or (
        database_path.parent / "runtime" / "request_diagnostics.runtime.jsonl"
    )

    proxy_pool_repository = SqliteProxyPoolRepository(shared.session_factory)
    proxy_pool_use_cases = ProxyPoolUseCases(proxy_pool_repository, shared.account_repository)
    proxy_test_service = ProxyTestService()
    query_config_repository = SqliteQueryConfigRepository(shared.session_factory)
    query_settings_repository = SqliteQuerySettingsRepository(shared.session_factory)
    inventory_snapshot_repository = SqliteAccountInventorySnapshotRepository(shared.session_factory)
    purchase_ui_preferences_repository = SqlitePurchaseUiPreferencesRepository(shared.session_factory)
    runtime_settings_repository = SqliteRuntimeSettingsRepository(shared.session_factory)
    stats_repository = SqliteStatsRepository(shared.session_factory)
    stats_pipeline = StatsPipeline(repository=stats_repository)
    stats_pipeline.start()

    purchase_runtime_service = PurchaseRuntimeService(
        account_repository=shared.account_repository,
        settings_repository=runtime_settings_repository,
        inventory_snapshot_repository=inventory_snapshot_repository,
        query_config_repository=query_config_repository,
        purchase_ui_preferences_repository=purchase_ui_preferences_repository,
        stats_repository=stats_repository,
        inventory_refresh_gateway_factory=InventoryRefreshGateway,
        stats_sink=stats_pipeline.enqueue,
        stats_flush_callback=stats_pipeline.flush_pending,
        runtime_update_hub=shared.runtime_update_hub,
    )
    open_api_binding_sync_service = OpenApiBindingSyncService(
        account_repository=shared.account_repository,
        account_update_hub=shared.account_update_hub,
        account_balance_service=shared.account_balance_service,
        account_cleanup_callback=DeleteAccountUseCase(
            shared.account_repository,
            shared.account_session_bundle_repository,
            shared.account_update_hub,
        ).execute,
        poll_interval_seconds=1.0,
        debug_log_path=database_path.parent / "runtime" / "open_api_binding_debug.runtime.jsonl",
    )
    remote_client = getattr(shared.program_access_gateway, "_remote_client", None)
    if (
        remote_client is not None
        and shared.program_access_credential_store is not None
        and shared.program_access_secret_store is not None
    ):
        program_runtime_control_service = RuntimeControlService(
            remote_client=remote_client,
            credential_store=shared.program_access_credential_store,
            secret_store=shared.program_access_secret_store,
            device_id_store=shared.program_access_device_id_store,
        )
    else:
        program_runtime_control_service = None
    query_runtime_service = QueryRuntimeService(
        query_config_repository=query_config_repository,
        query_settings_repository=query_settings_repository,
        account_repository=shared.account_repository,
        purchase_runtime_service=purchase_runtime_service,
        open_api_binding_sync_service=open_api_binding_sync_service,
        stats_sink=stats_pipeline.enqueue,
        runtime_update_hub=shared.runtime_update_hub,
        program_runtime_control_service=program_runtime_control_service,
    )
    purchase_runtime_service.set_query_runtime_service(query_runtime_service)
    task_manager = TaskManager()

    product_url_parser = ProductUrlParser()
    detail_account_selector = DetailAccountSelector(shared.account_repository)
    product_detail_fetcher = ProductDetailFetcher(selector=detail_account_selector)
    product_detail_collector = ProductDetailCollector(fetcher=product_detail_fetcher.fetch)
    query_item_detail_refresh_service = QueryItemDetailRefreshService(
        repository=query_config_repository,
        collector=product_detail_collector,
    )
    program_access_post_ready_init_pending = bool(
        _supports_program_access_post_ready_warm(shared.program_access_gateway)
        or (shared.program_access_refresh_scheduler is not None and params.program_access_start_refresh_scheduler)
    )

    return {
        "proxy_pool_repository": proxy_pool_repository,
        "proxy_pool_use_cases": proxy_pool_use_cases,
        "proxy_test_service": proxy_test_service,
        "query_config_repository": query_config_repository,
        "query_settings_repository": query_settings_repository,
        "inventory_snapshot_repository": inventory_snapshot_repository,
        "purchase_ui_preferences_repository": purchase_ui_preferences_repository,
        "runtime_settings_repository": runtime_settings_repository,
        "stats_repository": stats_repository,
        "stats_pipeline": stats_pipeline,
        "purchase_runtime_service": purchase_runtime_service,
        "open_api_binding_sync_service": open_api_binding_sync_service,
        "query_runtime_service": query_runtime_service,
        "program_runtime_control_service": program_runtime_control_service,
        "task_manager": task_manager,
        "product_url_parser": product_url_parser,
        "product_detail_collector": product_detail_collector,
        "query_item_detail_refresh_service": query_item_detail_refresh_service,
        "request_diagnostics_log_path": request_diagnostics_log_path,
        "request_diagnostics_slow_ms": float(params.request_diagnostics_slow_ms),
        "program_access_post_ready_init_pending": program_access_post_ready_init_pending,
    }


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
