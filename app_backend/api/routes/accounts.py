from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from app_backend.api.schemas.account_center import (
    AccountCenterAccountResponse,
    AccountPurchaseConfigUpdateRequest,
)
from app_backend.api.schemas.accounts import (
    AccountCreateRequest,
    AccountQueryModeUpdateRequest,
    AccountResponse,
    AccountUpdateRequest,
    LoginConflictResolveRequest,
)
from app_backend.api.schemas.tasks import TaskResponse
from app_backend.application.use_cases.clear_purchase_capability import (
    ClearPurchaseCapabilityUseCase,
)
from app_backend.application.use_cases.create_account import CreateAccountUseCase
from app_backend.application.use_cases.delete_account import DeleteAccountUseCase
from app_backend.application.use_cases.start_login_task import StartLoginTaskUseCase
from app_backend.application.use_cases.update_account import UpdateAccountUseCase
from app_backend.application.use_cases.update_account_purchase_config import (
    UpdateAccountPurchaseConfigUseCase,
)
from app_backend.application.use_cases.update_account_query_modes import UpdateAccountQueryModesUseCase
from app_backend.application.use_cases.resolve_login_conflict import ResolveLoginConflictUseCase

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _repository(request: Request):
    return request.app.state.account_repository


def _task_manager(request: Request):
    return request.app.state.task_manager


def _bundle_repository(request: Request):
    return request.app.state.account_session_bundle_repository


def _login_adapter(request: Request):
    return request.app.state.login_adapter


@router.get("", response_model=list[AccountResponse])
async def list_accounts(request: Request) -> list[AccountResponse]:
    repository = _repository(request)
    return [AccountResponse.model_validate(account) for account in repository.list_accounts()]


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    payload: AccountCreateRequest,
    request: Request,
) -> AccountResponse:
    use_case = CreateAccountUseCase(_repository(request))
    account = use_case.execute(
        remark_name=payload.remark_name,
        browser_proxy_mode=payload.browser_proxy_mode,
        browser_proxy_url=payload.browser_proxy_url,
        api_proxy_mode=payload.api_proxy_mode,
        api_proxy_url=payload.api_proxy_url,
        api_key=payload.api_key,
    )
    return AccountResponse.model_validate(account)


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(account_id: str, request: Request) -> AccountResponse:
    repository = _repository(request)
    account = repository.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return AccountResponse.model_validate(account)


@router.patch("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: str,
    payload: AccountUpdateRequest,
    request: Request,
) -> AccountResponse:
    use_case = UpdateAccountUseCase(_repository(request))
    try:
        account = use_case.execute(
            account_id=account_id,
            remark_name=payload.remark_name,
            browser_proxy_mode=payload.browser_proxy_mode,
            browser_proxy_url=payload.browser_proxy_url,
            api_proxy_mode=payload.api_proxy_mode,
            api_proxy_url=payload.api_proxy_url,
            api_key=payload.api_key,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found") from exc

    return AccountResponse.model_validate(account)


@router.patch("/{account_id}/query-modes", response_model=AccountResponse)
async def update_account_query_modes(
    account_id: str,
    payload: AccountQueryModeUpdateRequest,
    request: Request,
) -> AccountResponse:
    use_case = UpdateAccountQueryModesUseCase(_repository(request))
    try:
        account = use_case.execute(
            account_id=account_id,
            api_query_enabled=payload.api_query_enabled,
            browser_query_enabled=payload.browser_query_enabled,
            api_query_disabled_reason=payload.api_query_disabled_reason,
            browser_query_disabled_reason=payload.browser_query_disabled_reason,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found") from exc
    return AccountResponse.model_validate(account)


@router.patch("/{account_id}/purchase-config", response_model=AccountCenterAccountResponse)
async def update_account_purchase_config(
    account_id: str,
    payload: AccountPurchaseConfigUpdateRequest,
    request: Request,
) -> AccountCenterAccountResponse:
    use_case = UpdateAccountPurchaseConfigUseCase(request.app.state.purchase_runtime_service)
    try:
        row = use_case.execute(
            account_id=account_id,
            purchase_disabled=payload.purchase_disabled,
            selected_steam_id=payload.selected_steam_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return AccountCenterAccountResponse.model_validate(row)


@router.post("/{account_id}/purchase-capability/clear", response_model=AccountResponse)
async def clear_purchase_capability(account_id: str, request: Request) -> AccountResponse:
    use_case = ClearPurchaseCapabilityUseCase(_repository(request))
    try:
        account = use_case.execute(account_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found") from exc
    return AccountResponse.model_validate(account)


@router.post(
    "/{account_id}/login",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_login_task(account_id: str, request: Request) -> TaskResponse:
    use_case = StartLoginTaskUseCase(
        _repository(request),
        _task_manager(request),
        _login_adapter(request),
        _bundle_repository(request),
        request.app.state.purchase_runtime_service,
        request.app.state.open_api_binding_sync_service,
    )
    try:
        task = use_case.execute(account_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found") from exc
    return TaskResponse.model_validate(task)


@router.post("/{account_id}/open-api/sync", response_model=AccountResponse)
async def sync_open_api_binding(account_id: str, request: Request) -> AccountResponse:
    repository = _repository(request)
    account = repository.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    service = request.app.state.open_api_binding_sync_service
    outcome = service.sync_account_now(account_id, final=True)
    account = repository.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    if not outcome.get("updated") and not outcome.get("matched") and not getattr(account, "cookie_raw", None):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="当前账号未登录，无法同步 API 白名单")
    return AccountResponse.model_validate(account)


@router.post("/{account_id}/open-api/open")
async def open_open_api_binding_page(account_id: str, request: Request) -> dict[str, object]:
    repository = _repository(request)
    bundle_repository = _bundle_repository(request)
    account = repository.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    active_bundle = bundle_repository.get_active_bundle(account_id)
    bundle_payload = active_bundle.payload if active_bundle is not None and isinstance(active_bundle.payload, dict) else {}
    profile_root = str(bundle_payload.get("profile_root") or "").strip()
    profile_directory = str(bundle_payload.get("profile_directory") or "").strip() or None
    if not profile_root:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前账号缺少可复用登录会话，请重新登录后再添加白名单",
        )
    launcher = request.app.state.open_api_binding_page_launcher
    result = launcher.launch(
        account_id=account_id,
        profile_root=profile_root or None,
        profile_directory=profile_directory,
        proxy_url=getattr(account, "browser_proxy_url", None),
        sync_service=request.app.state.open_api_binding_sync_service,
    )
    return {
        "launched": True,
        **result,
    }


@router.post("/{account_id}/login/resolve", response_model=TaskResponse)
async def resolve_login_conflict(
    account_id: str,
    payload: LoginConflictResolveRequest,
    request: Request,
) -> TaskResponse:
    use_case = ResolveLoginConflictUseCase(
        _repository(request),
        _task_manager(request),
        _bundle_repository(request),
        request.app.state.purchase_runtime_service,
    )
    try:
        task = use_case.execute(
            account_id=account_id,
            task_id=payload.task_id,
            action=payload.action,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return TaskResponse.model_validate(task)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(account_id: str, request: Request) -> Response:
    use_case = DeleteAccountUseCase(
        _repository(request),
        _bundle_repository(request),
        request.app.state.account_update_hub,
    )
    use_case.execute(account_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
