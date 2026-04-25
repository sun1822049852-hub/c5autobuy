from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app_backend.api.program_access_guard import guard_program_action
from app_backend.api.schemas.purchase_runtime import (
    PurchaseRuntimeInventoryDetailResponse,
    PurchaseRuntimeStartRequest,
    PurchaseRuntimeStatusResponse,
    PurchaseRuntimeUiPreferencesRequest,
    PurchaseRuntimeUiPreferencesResponse,
)
from app_backend.application.use_cases.get_purchase_ui_preferences import (
    GetPurchaseUiPreferencesUseCase,
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
from app_backend.application.use_cases.update_purchase_ui_preferences import (
    UpdatePurchaseUiPreferencesUseCase,
)

router = APIRouter(prefix="/purchase-runtime", tags=["purchase-runtime"])


def _ensure_runtime_full_ready(request: Request) -> None:
    ensure = getattr(request.app.state, "ensure_runtime_full_ready", None)
    if callable(ensure):
        ensure()


def _state_attr(request: Request, name: str):
    if not hasattr(request.app.state, name):
        _ensure_runtime_full_ready(request)
    return getattr(request.app.state, name)


def _runtime_service(request: Request):
    return _state_attr(request, "purchase_runtime_service")


def _query_runtime_service(request: Request):
    return _state_attr(request, "query_runtime_service")


def _query_config_repository(request: Request):
    return _state_attr(request, "query_config_repository")


def _purchase_ui_preferences_repository(request: Request):
    return _state_attr(request, "purchase_ui_preferences_repository")


def _runtime_update_hub(request: Request):
    return request.app.state.runtime_update_hub


def _stats_repository(request: Request):
    return _state_attr(request, "stats_repository")


def _stats_flush_callback(request: Request):
    stats_pipeline = _state_attr(request, "stats_pipeline")
    return getattr(stats_pipeline, "flush_pending", None)


@router.get("/status", response_model=PurchaseRuntimeStatusResponse)
def get_purchase_runtime_status(request: Request) -> PurchaseRuntimeStatusResponse:
    use_case = GetPurchaseRuntimeStatusUseCase(
        _runtime_service(request),
        _query_runtime_service(request),
        query_config_repository=_query_config_repository(request),
        purchase_ui_preferences_repository=_purchase_ui_preferences_repository(request),
        stats_repository=_stats_repository(request),
        stats_flush_callback=_stats_flush_callback(request),
        include_recent_events=False,
    )
    return PurchaseRuntimeStatusResponse.model_validate(use_case.execute())


@router.get("/ui-preferences", response_model=PurchaseRuntimeUiPreferencesResponse)
def get_purchase_runtime_ui_preferences(request: Request) -> PurchaseRuntimeUiPreferencesResponse:
    use_case = GetPurchaseUiPreferencesUseCase(
        _purchase_ui_preferences_repository(request),
        _query_config_repository(request),
    )
    return PurchaseRuntimeUiPreferencesResponse.model_validate(use_case.execute())


@router.put("/ui-preferences", response_model=PurchaseRuntimeUiPreferencesResponse)
def update_purchase_runtime_ui_preferences(
    payload: PurchaseRuntimeUiPreferencesRequest,
    request: Request,
) -> PurchaseRuntimeUiPreferencesResponse:
    guard_program_action(request, "runtime.switch_config")
    use_case = UpdatePurchaseUiPreferencesUseCase(
        _purchase_ui_preferences_repository(request),
        _query_config_repository(request),
    )
    try:
        preferences = use_case.execute(selected_config_id=payload.selected_config_id)
    except KeyError as exc:
        detail = exc.args[0] if exc.args else "查询配置不存在"
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
    response = PurchaseRuntimeUiPreferencesResponse.model_validate(preferences)
    _runtime_update_hub(request).publish(
        event="purchase_ui_preferences.updated",
        payload=response.model_dump(mode="json"),
    )
    return response


@router.get("/accounts/{account_id}/inventory", response_model=PurchaseRuntimeInventoryDetailResponse)
def get_purchase_runtime_inventory_detail(
    account_id: str,
    request: Request,
) -> PurchaseRuntimeInventoryDetailResponse:
    use_case = GetPurchaseRuntimeInventoryDetailUseCase(_runtime_service(request))
    detail = use_case.execute(account_id=account_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="购买账号不存在")
    return PurchaseRuntimeInventoryDetailResponse.model_validate(detail)


@router.post("/accounts/{account_id}/inventory/refresh", response_model=PurchaseRuntimeInventoryDetailResponse)
def refresh_purchase_runtime_inventory_detail(
    account_id: str,
    request: Request,
) -> PurchaseRuntimeInventoryDetailResponse:
    use_case = RefreshPurchaseRuntimeInventoryDetailUseCase(_runtime_service(request))
    detail = use_case.execute(account_id=account_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="购买账号不存在")
    return PurchaseRuntimeInventoryDetailResponse.model_validate(detail)


@router.post("/start", response_model=PurchaseRuntimeStatusResponse)
def start_purchase_runtime(
    payload: PurchaseRuntimeStartRequest,
    request: Request,
) -> PurchaseRuntimeStatusResponse:
    guard_program_action(request, "runtime.start")
    runtime_service = _runtime_service(request)
    query_runtime_service = _query_runtime_service(request)
    started, message = StartPurchaseRuntimeUseCase(query_runtime_service).execute(
        config_id=payload.config_id,
    )
    if not started:
        status_code = status.HTTP_404_NOT_FOUND if message == "查询配置不存在" else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=status_code, detail=message)
    snapshot = GetPurchaseRuntimeStatusUseCase(
        runtime_service,
        query_runtime_service,
        query_config_repository=_query_config_repository(request),
        purchase_ui_preferences_repository=_purchase_ui_preferences_repository(request),
        stats_repository=_stats_repository(request),
        stats_flush_callback=_stats_flush_callback(request),
        include_recent_events=False,
    ).execute()
    return PurchaseRuntimeStatusResponse.model_validate(snapshot)


@router.post("/stop", response_model=PurchaseRuntimeStatusResponse)
def stop_purchase_runtime(request: Request) -> PurchaseRuntimeStatusResponse:
    runtime_service = _runtime_service(request)
    query_runtime_service = _query_runtime_service(request)
    stopped, message = StopPurchaseRuntimeUseCase(query_runtime_service).execute()
    if not stopped:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)
    snapshot = GetPurchaseRuntimeStatusUseCase(
        runtime_service,
        query_runtime_service,
        query_config_repository=_query_config_repository(request),
        purchase_ui_preferences_repository=_purchase_ui_preferences_repository(request),
        stats_repository=_stats_repository(request),
        stats_flush_callback=_stats_flush_callback(request),
        include_recent_events=False,
    ).execute()
    return PurchaseRuntimeStatusResponse.model_validate(snapshot)
