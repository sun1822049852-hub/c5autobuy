from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app_backend.api.schemas.purchase_runtime import (
    PurchaseRuntimeInventoryDetailResponse,
    PurchaseRuntimeStatusResponse,
)
from app_backend.application.use_cases.get_purchase_runtime_inventory_detail import (
    GetPurchaseRuntimeInventoryDetailUseCase,
)
from app_backend.application.use_cases.refresh_purchase_runtime_inventory_detail import (
    RefreshPurchaseRuntimeInventoryDetailUseCase,
)
from app_backend.application.use_cases.get_purchase_runtime_status import GetPurchaseRuntimeStatusUseCase
from app_backend.application.use_cases.start_purchase_runtime import StartPurchaseRuntimeUseCase
from app_backend.application.use_cases.stop_purchase_runtime import StopPurchaseRuntimeUseCase

router = APIRouter(prefix="/purchase-runtime", tags=["purchase-runtime"])


def _runtime_service(request: Request):
    return request.app.state.purchase_runtime_service


def _query_runtime_service(request: Request):
    return request.app.state.query_runtime_service


@router.get("/status", response_model=PurchaseRuntimeStatusResponse)
async def get_purchase_runtime_status(request: Request) -> PurchaseRuntimeStatusResponse:
    use_case = GetPurchaseRuntimeStatusUseCase(
        _runtime_service(request),
        _query_runtime_service(request),
    )
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


@router.post("/accounts/{account_id}/inventory/refresh", response_model=PurchaseRuntimeInventoryDetailResponse)
async def refresh_purchase_runtime_inventory_detail(
    account_id: str,
    request: Request,
) -> PurchaseRuntimeInventoryDetailResponse:
    use_case = RefreshPurchaseRuntimeInventoryDetailUseCase(_runtime_service(request))
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
