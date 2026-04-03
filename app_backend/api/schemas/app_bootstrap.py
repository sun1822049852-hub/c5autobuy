from __future__ import annotations

from pydantic import BaseModel

from app_backend.api.schemas.diagnostics import SidebarDiagnosticsSummaryResponse
from app_backend.api.schemas.purchase_runtime import (
    PurchaseRuntimeStatusResponse,
    PurchaseRuntimeUiPreferencesResponse,
)
from app_backend.api.schemas.query_configs import (
    QueryCapacitySummaryResponse,
    QueryConfigResponse,
)
from app_backend.api.schemas.query_runtime import QueryRuntimeStatusResponse
from app_backend.api.schemas.runtime_settings import PurchaseRuntimeSettingsResponse


class AppBootstrapQuerySystemResponse(BaseModel):
    configs: list[QueryConfigResponse]
    capacity_summary: QueryCapacitySummaryResponse
    runtime_status: QueryRuntimeStatusResponse


class AppBootstrapPurchaseSystemResponse(BaseModel):
    runtime_status: PurchaseRuntimeStatusResponse
    ui_preferences: PurchaseRuntimeUiPreferencesResponse
    runtime_settings: PurchaseRuntimeSettingsResponse


class AppBootstrapDiagnosticsResponse(BaseModel):
    summary: SidebarDiagnosticsSummaryResponse


class AppBootstrapResponse(BaseModel):
    version: int
    generated_at: str
    query_system: AppBootstrapQuerySystemResponse
    purchase_system: AppBootstrapPurchaseSystemResponse
    diagnostics: AppBootstrapDiagnosticsResponse
