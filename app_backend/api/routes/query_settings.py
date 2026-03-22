from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app_backend.api.schemas.query_settings import (
    QuerySettingsResponse,
    QuerySettingsUpdateRequest,
)
from app_backend.application.use_cases.get_query_settings import GetQuerySettingsUseCase
from app_backend.application.use_cases.update_query_settings import UpdateQuerySettingsUseCase

router = APIRouter(prefix="/query-settings", tags=["query-settings"])


def _repository(request: Request):
    return request.app.state.query_settings_repository


def _query_runtime_service(request: Request):
    return request.app.state.query_runtime_service


def _serialize_response(settings, *, warnings: list[str] | None = None) -> QuerySettingsResponse:
    return QuerySettingsResponse.model_validate(
        {
            "modes": [
                {
                    "mode_type": mode.mode_type,
                    "enabled": mode.enabled,
                    "window_enabled": mode.window_enabled,
                    "start_hour": mode.start_hour,
                    "start_minute": mode.start_minute,
                    "end_hour": mode.end_hour,
                    "end_minute": mode.end_minute,
                    "base_cooldown_min": mode.base_cooldown_min,
                    "base_cooldown_max": mode.base_cooldown_max,
                    "item_min_cooldown_seconds": mode.item_min_cooldown_seconds,
                    "item_min_cooldown_strategy": mode.item_min_cooldown_strategy,
                    "random_delay_enabled": mode.random_delay_enabled,
                    "random_delay_min": mode.random_delay_min,
                    "random_delay_max": mode.random_delay_max,
                    "created_at": mode.created_at,
                    "updated_at": mode.updated_at,
                }
                for mode in settings.modes
            ],
            "warnings": list(warnings or []),
            "updated_at": settings.updated_at,
        }
    )


@router.get("", response_model=QuerySettingsResponse)
async def get_query_settings(request: Request) -> QuerySettingsResponse:
    settings = GetQuerySettingsUseCase(_repository(request)).execute()
    return _serialize_response(settings)


@router.put("", response_model=QuerySettingsResponse)
async def update_query_settings(
    payload: QuerySettingsUpdateRequest,
    request: Request,
) -> QuerySettingsResponse:
    try:
        settings, warnings = UpdateQuerySettingsUseCase(_repository(request)).execute(
            modes=[mode.model_dump() for mode in payload.modes]
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    apply_query_settings = getattr(_query_runtime_service(request), "apply_query_settings", None)
    if callable(apply_query_settings):
        apply_query_settings()
    return _serialize_response(settings, warnings=warnings)
