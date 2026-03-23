from __future__ import annotations

from fastapi import APIRouter, Request

from app_backend.api.schemas.runtime_settings import (
    RuntimePurchaseSettingsPayload,
    RuntimeQuerySettingsPayload,
    RuntimeSettingsResponse,
)
from app_backend.application.use_cases.get_runtime_settings import GetRuntimeSettingsUseCase
from app_backend.application.use_cases.update_purchase_runtime_settings import (
    UpdatePurchaseRuntimeSettingsUseCase,
)
from app_backend.application.use_cases.update_query_runtime_settings import (
    UpdateQueryRuntimeSettingsUseCase,
)

router = APIRouter(prefix="/runtime-settings", tags=["runtime-settings"])


def _repository(request: Request):
    return request.app.state.runtime_settings_repository


def _query_runtime_service(request: Request):
    return request.app.state.query_runtime_service


def _to_response_payload(settings) -> dict[str, object]:
    return {
        "settings_id": settings.settings_id,
        "query_settings": settings.query_settings_json,
        "purchase_settings": settings.purchase_settings_json,
        "updated_at": settings.updated_at,
    }


@router.get("", response_model=RuntimeSettingsResponse)
async def get_runtime_settings(request: Request) -> RuntimeSettingsResponse:
    settings = GetRuntimeSettingsUseCase(_repository(request)).execute()
    return RuntimeSettingsResponse.model_validate(_to_response_payload(settings))


@router.put("/query", response_model=RuntimeSettingsResponse)
async def update_query_runtime_settings(
    payload: RuntimeQuerySettingsPayload,
    request: Request,
) -> RuntimeSettingsResponse:
    settings = UpdateQueryRuntimeSettingsUseCase(_repository(request)).execute(
        query_settings=payload.model_dump(),
    )
    apply_query_settings = getattr(_query_runtime_service(request), "apply_query_settings", None)
    if callable(apply_query_settings):
        apply_query_settings(query_settings=settings.query_settings_json)
    return RuntimeSettingsResponse.model_validate(_to_response_payload(settings))


@router.put("/purchase", response_model=RuntimeSettingsResponse)
async def update_purchase_runtime_settings(
    payload: RuntimePurchaseSettingsPayload,
    request: Request,
) -> RuntimeSettingsResponse:
    settings = UpdatePurchaseRuntimeSettingsUseCase(_repository(request)).execute(
        purchase_settings=payload.model_dump(),
    )
    return RuntimeSettingsResponse.model_validate(_to_response_payload(settings))
