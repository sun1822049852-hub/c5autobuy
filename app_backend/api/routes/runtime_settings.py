from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app_backend.api.schemas.runtime_settings import (
    PurchaseRuntimeSettingsResponse,
    PurchaseRuntimeSettingsUpdateRequest,
)
from app_backend.application.use_cases.get_runtime_settings import GetRuntimeSettingsUseCase
from app_backend.application.use_cases.update_purchase_runtime_settings import (
    UpdatePurchaseRuntimeSettingsUseCase,
)

router = APIRouter(prefix="/runtime-settings", tags=["runtime-settings"])


def _repository(request: Request):
    return request.app.state.runtime_settings_repository


def _runtime_update_hub(request: Request):
    return request.app.state.runtime_update_hub


def _serialize_purchase_settings(settings) -> PurchaseRuntimeSettingsResponse:
    purchase_settings = dict(getattr(settings, "purchase_settings_json", {}) or {})
    return PurchaseRuntimeSettingsResponse.model_validate(
        {
            "per_batch_ip_fanout_limit": int(purchase_settings.get("per_batch_ip_fanout_limit", 1) or 1),
            "updated_at": settings.updated_at,
        }
    )


@router.get("/purchase", response_model=PurchaseRuntimeSettingsResponse)
def get_purchase_runtime_settings(request: Request) -> PurchaseRuntimeSettingsResponse:
    settings = GetRuntimeSettingsUseCase(_repository(request)).execute()
    return _serialize_purchase_settings(settings)


@router.put("/purchase", response_model=PurchaseRuntimeSettingsResponse)
def update_purchase_runtime_settings(
    payload: PurchaseRuntimeSettingsUpdateRequest,
    request: Request,
) -> PurchaseRuntimeSettingsResponse:
    try:
        settings = UpdatePurchaseRuntimeSettingsUseCase(_repository(request)).execute(
            per_batch_ip_fanout_limit=payload.per_batch_ip_fanout_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    response = _serialize_purchase_settings(settings)
    _runtime_update_hub(request).publish(
        event="runtime_settings.updated",
        payload=response.model_dump(mode="json"),
    )
    return response
