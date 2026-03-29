from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app_backend.api.schemas.account_center import AccountCenterAccountResponse
from app_backend.application.use_cases.get_account_center_account import GetAccountCenterAccountUseCase
from app_backend.application.use_cases.list_account_center_accounts import ListAccountCenterAccountsUseCase

router = APIRouter(prefix="/account-center", tags=["account-center"])


def _runtime_service(request: Request):
    return request.app.state.purchase_runtime_service


@router.get("/accounts", response_model=list[AccountCenterAccountResponse])
async def list_account_center_accounts(request: Request) -> list[AccountCenterAccountResponse]:
    use_case = ListAccountCenterAccountsUseCase(_runtime_service(request))
    return [AccountCenterAccountResponse.model_validate(row) for row in use_case.execute()]


@router.get("/accounts/{account_id}", response_model=AccountCenterAccountResponse)
async def get_account_center_account(account_id: str, request: Request) -> AccountCenterAccountResponse:
    use_case = GetAccountCenterAccountUseCase(_runtime_service(request))
    row = use_case.execute(account_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return AccountCenterAccountResponse.model_validate(row)
