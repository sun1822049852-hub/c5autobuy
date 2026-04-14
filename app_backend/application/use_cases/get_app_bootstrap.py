from __future__ import annotations

from datetime import datetime

from app_backend.application.services.query_mode_capacity_service import QueryModeCapacityService
from app_backend.application.use_cases.get_purchase_ui_preferences import GetPurchaseUiPreferencesUseCase
from app_backend.application.use_cases.get_purchase_runtime_status import GetPurchaseRuntimeStatusUseCase
from app_backend.application.use_cases.get_query_capacity_summary import GetQueryCapacitySummaryUseCase
from app_backend.application.use_cases.get_query_runtime_status import GetQueryRuntimeStatusUseCase
from app_backend.application.use_cases.get_sidebar_diagnostics import GetSidebarDiagnosticsUseCase
from app_backend.application.use_cases.list_query_configs import ListQueryConfigsUseCase


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class GetAppBootstrapUseCase:
    def __init__(
        self,
        *,
        query_config_repository,
        account_repository,
        query_runtime_service,
        purchase_runtime_service,
        purchase_ui_preferences_repository,
        runtime_settings_repository,
        task_manager,
        runtime_update_hub,
    ) -> None:
        self._query_config_repository = query_config_repository
        self._account_repository = account_repository
        self._query_runtime_service = query_runtime_service
        self._purchase_runtime_service = purchase_runtime_service
        self._purchase_ui_preferences_repository = purchase_ui_preferences_repository
        self._runtime_settings_repository = runtime_settings_repository
        self._task_manager = task_manager
        self._runtime_update_hub = runtime_update_hub

    def execute(self) -> dict[str, object]:
        query_configs = ListQueryConfigsUseCase(self._query_config_repository).execute()
        capacity_summary = GetQueryCapacitySummaryUseCase(
            QueryModeCapacityService(self._account_repository)
        ).execute()
        query_runtime_status = GetQueryRuntimeStatusUseCase(self._query_runtime_service).execute()
        purchase_runtime_status = GetPurchaseRuntimeStatusUseCase(
            self._purchase_runtime_service,
            self._query_runtime_service,
            include_recent_events=False,
        ).execute()
        ui_preferences = GetPurchaseUiPreferencesUseCase(
            self._purchase_ui_preferences_repository,
            self._query_config_repository,
        ).execute()
        runtime_settings = self._runtime_settings_repository.get()
        diagnostics_summary = GetSidebarDiagnosticsUseCase(
            self._query_runtime_service,
            self._purchase_runtime_service,
            self._task_manager,
        ).execute()["summary"]

        return {
            "version": self._runtime_update_hub.current_version(),
            "generated_at": _now(),
            "query_system": {
                "configs": list(query_configs),
                "capacity_summary": capacity_summary,
                "runtime_status": query_runtime_status,
            },
            "purchase_system": {
                "runtime_status": purchase_runtime_status,
                "ui_preferences": ui_preferences,
                "runtime_settings": {
                    "per_batch_ip_fanout_limit": self._read_per_batch_ip_fanout_limit(runtime_settings),
                    "max_inflight_per_account": self._read_max_inflight_per_account(runtime_settings),
                    "updated_at": getattr(runtime_settings, "updated_at", None),
                },
            },
            "diagnostics": {
                "summary": diagnostics_summary,
            },
        }

    @staticmethod
    def _read_per_batch_ip_fanout_limit(runtime_settings) -> int:
        purchase_settings = dict(getattr(runtime_settings, "purchase_settings_json", {}) or {})
        return int(purchase_settings.get("per_batch_ip_fanout_limit", 1) or 1)

    @staticmethod
    def _read_max_inflight_per_account(runtime_settings) -> int:
        purchase_settings = dict(getattr(runtime_settings, "purchase_settings_json", {}) or {})
        return int(purchase_settings.get("max_inflight_per_account", 3) or 3)
