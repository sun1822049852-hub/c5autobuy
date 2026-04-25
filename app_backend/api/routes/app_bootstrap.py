from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request

from app_backend.api.schemas.app_bootstrap import AppBootstrapResponse, AppBootstrapShellResponse
from app_backend.application.use_cases.get_app_bootstrap import GetAppBootstrapUseCase

router = APIRouter(prefix="/app", tags=["app"])


def _state_attr(request: Request, name: str):
    return getattr(request.app.state, name, None)


def _ensure_runtime_full_ready(request: Request) -> None:
    ensure = getattr(request.app.state, "ensure_runtime_full_ready", None)
    if callable(ensure):
        ensure()


@router.get("/bootstrap", response_model=AppBootstrapResponse | AppBootstrapShellResponse)
def get_app_bootstrap(
    request: Request,
    scope: Literal["shell", "full"] = "full",
) -> AppBootstrapResponse | AppBootstrapShellResponse:
    if scope == "full":
        _ensure_runtime_full_ready(request)

    payload = GetAppBootstrapUseCase(
        query_config_repository=_state_attr(request, "query_config_repository"),
        account_repository=_state_attr(request, "account_repository"),
        query_runtime_service=_state_attr(request, "query_runtime_service"),
        purchase_runtime_service=_state_attr(request, "purchase_runtime_service"),
        purchase_ui_preferences_repository=_state_attr(request, "purchase_ui_preferences_repository"),
        stats_repository=_state_attr(request, "stats_repository"),
        stats_flush_callback=getattr(_state_attr(request, "stats_pipeline"), "flush_pending", None),
        runtime_settings_repository=_state_attr(request, "runtime_settings_repository"),
        task_manager=_state_attr(request, "task_manager"),
        runtime_update_hub=_state_attr(request, "runtime_update_hub"),
        program_access_gateway=_state_attr(request, "program_access_gateway"),
    ).execute(scope=scope)
    if scope == "shell":
        return AppBootstrapShellResponse.model_validate(payload)

    return AppBootstrapResponse.model_validate(payload)
