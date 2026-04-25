from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request

from app_backend.api.schemas.app_bootstrap import AppBootstrapResponse, AppBootstrapShellResponse
from app_backend.application.use_cases.get_app_bootstrap import GetAppBootstrapUseCase

router = APIRouter(prefix="/app", tags=["app"])


@router.get("/bootstrap", response_model=AppBootstrapResponse | AppBootstrapShellResponse)
def get_app_bootstrap(
    request: Request,
    scope: Literal["shell", "full"] = "full",
) -> AppBootstrapResponse | AppBootstrapShellResponse:
    payload = GetAppBootstrapUseCase(
        query_config_repository=request.app.state.query_config_repository,
        account_repository=request.app.state.account_repository,
        query_runtime_service=request.app.state.query_runtime_service,
        purchase_runtime_service=request.app.state.purchase_runtime_service,
        purchase_ui_preferences_repository=request.app.state.purchase_ui_preferences_repository,
        stats_repository=request.app.state.stats_repository,
        runtime_settings_repository=request.app.state.runtime_settings_repository,
        task_manager=request.app.state.task_manager,
        runtime_update_hub=request.app.state.runtime_update_hub,
        program_access_gateway=request.app.state.program_access_gateway,
    ).execute(scope=scope)
    if scope == "shell":
        return AppBootstrapShellResponse.model_validate(payload)

    return AppBootstrapResponse.model_validate(payload)
