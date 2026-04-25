from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app_backend.api.schemas.account_center import AccountCenterAccountResponse
from app_backend.application.services.account_center_snapshot_service import AccountCenterSnapshotService
from app_backend.application.use_cases.get_account_center_account import GetAccountCenterAccountUseCase
from app_backend.application.use_cases.list_account_center_accounts import ListAccountCenterAccountsUseCase

router = APIRouter(prefix="/account-center", tags=["account-center"])


def _runtime_service(request: Request):
    return getattr(request.app.state, "purchase_runtime_service", None)


def _snapshot_service(request: Request) -> AccountCenterSnapshotService:
    return AccountCenterSnapshotService(request.app.state.account_repository)


def _balance_service(request: Request):
    return getattr(request.app.state, "account_balance_service", None)


@router.get("/accounts", response_model=list[AccountCenterAccountResponse])
def list_account_center_accounts(request: Request) -> list[AccountCenterAccountResponse]:
    use_case = ListAccountCenterAccountsUseCase(
        _runtime_service(request),
        _snapshot_service(request),
    )
    rows = [AccountCenterAccountResponse.model_validate(row) for row in use_case.execute()]
    balance_service = _balance_service(request)
    if balance_service is not None:
        for row in rows:
            try:
                balance_service.maybe_schedule_refresh(row.account_id)
            except RuntimeError:
                continue
    return rows


@router.get("/accounts/{account_id}", response_model=AccountCenterAccountResponse)
def get_account_center_account(account_id: str, request: Request) -> AccountCenterAccountResponse:
    use_case = GetAccountCenterAccountUseCase(
        _runtime_service(request),
        _snapshot_service(request),
    )
    row = use_case.execute(account_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    balance_service = _balance_service(request)
    if balance_service is not None:
        try:
            balance_service.maybe_schedule_refresh(account_id)
        except RuntimeError:
            pass
    return AccountCenterAccountResponse.model_validate(row)
