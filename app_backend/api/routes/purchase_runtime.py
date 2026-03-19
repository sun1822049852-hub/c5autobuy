from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app_backend.api.schemas.purchase_runtime import (
    PurchaseRuntimeInventoryDetailResponse,
    PurchaseRuntimeSettingsResponse,
    PurchaseRuntimeSettingsUpdateRequest,
    PurchaseRuntimeStatusResponse,
)
from app_backend.application.use_cases.get_purchase_runtime_inventory_detail import (
    GetPurchaseRuntimeInventoryDetailUseCase,
)
from app_backend.application.use_cases.get_purchase_runtime_settings import GetPurchaseRuntimeSettingsUseCase
from app_backend.application.use_cases.get_purchase_runtime_status import GetPurchaseRuntimeStatusUseCase
from app_backend.application.use_cases.start_purchase_runtime import StartPurchaseRuntimeUseCase
from app_backend.application.use_cases.stop_purchase_runtime import StopPurchaseRuntimeUseCase
from app_backend.application.use_cases.update_purchase_runtime_settings import (
    UpdatePurchaseRuntimeSettingsUseCase,
)

router = APIRouter(prefix="/purchase-runtime", tags=["purchase-runtime"])


def _runtime_service(request: Request):
    return request.app.state.purchase_runtime_service


@router.get("/status", response_model=PurchaseRuntimeStatusResponse)
async def get_purchase_runtime_status(request: Request) -> PurchaseRuntimeStatusResponse:
    use_case = GetPurchaseRuntimeStatusUseCase(_runtime_service(request))
    return PurchaseRuntimeStatusResponse.model_validate(use_case.execute())


@router.get("/accounts/{account_id}/inventory", response_model=PurchaseRuntimeInventoryDetailResponse)
async def get_purchase_runtime_inventory_detail(
    account_id: str,
    request: Request,
) -> PurchaseRuntimeInventoryDetailResponse:
    use_case = GetPurchaseRuntimeInventoryDetailUseCase(_runtime_service(request))
    detail = use_case.execute(account_id=account_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="购买账号不存在")
    return PurchaseRuntimeInventoryDetailResponse.model_validate(detail)


@router.post("/start", response_model=PurchaseRuntimeStatusResponse)
async def start_purchase_runtime(request: Request) -> PurchaseRuntimeStatusResponse:
    runtime_service = _runtime_service(request)
    started, message = StartPurchaseRuntimeUseCase(runtime_service).execute()
    if not started:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)
    return PurchaseRuntimeStatusResponse.model_validate(runtime_service.get_status())


@router.post("/stop", response_model=PurchaseRuntimeStatusResponse)
async def stop_purchase_runtime(request: Request) -> PurchaseRuntimeStatusResponse:
    runtime_service = _runtime_service(request)
    stopped, message = StopPurchaseRuntimeUseCase(runtime_service).execute()
    if not stopped:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)
    return PurchaseRuntimeStatusResponse.model_validate(runtime_service.get_status())


@router.get("/settings", response_model=PurchaseRuntimeSettingsResponse)
async def get_purchase_runtime_settings(request: Request) -> PurchaseRuntimeSettingsResponse:
    use_case = GetPurchaseRuntimeSettingsUseCase(_runtime_service(request))
    return PurchaseRuntimeSettingsResponse.model_validate(use_case.execute())


@router.put("/settings", response_model=PurchaseRuntimeStatusResponse)
async def update_purchase_runtime_settings(
    payload: PurchaseRuntimeSettingsUpdateRequest,
    request: Request,
) -> PurchaseRuntimeStatusResponse:
    runtime_service = _runtime_service(request)
    snapshot = UpdatePurchaseRuntimeSettingsUseCase(runtime_service).execute(
        whitelist_account_ids=payload.whitelist_account_ids,
    )
    return PurchaseRuntimeStatusResponse.model_validate(snapshot)
