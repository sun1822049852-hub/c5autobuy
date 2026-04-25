from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app_backend.api.schemas.account_center import AccountCenterAccountResponse
from app_backend.application.services.account_center_snapshot_service import AccountCenterSnapshotService
from app_backend.application.use_cases.get_account_center_account import GetAccountCenterAccountUseCase
from app_backend.application.use_cases.list_account_center_accounts import ListAccountCenterAccountsUseCase
from app_backend.infrastructure.request_diagnostics import get_request_trace_recorder

router = APIRouter(prefix="/account-center", tags=["account-center"])


def _runtime_service(request: Request):
    return getattr(request.app.state, "purchase_runtime_service", None)


def _snapshot_service(request: Request) -> AccountCenterSnapshotService:
    return AccountCenterSnapshotService(request.app.state.account_repository)


def _balance_service(request: Request):
    return getattr(request.app.state, "account_balance_service", None)


def _maybe_schedule_balance_refresh(balance_service, account_id: str, *, trace=None) -> bool:
    maybe_schedule_refresh = getattr(balance_service, "maybe_schedule_refresh", None)
    if not callable(maybe_schedule_refresh):
        return False
    if trace is None:
        return bool(maybe_schedule_refresh(account_id))
    try:
        return bool(maybe_schedule_refresh(account_id, trace=trace))
    except TypeError as exc:
        if "trace" not in str(exc):
            raise
        return bool(maybe_schedule_refresh(account_id))


@router.get("/accounts", response_model=list[AccountCenterAccountResponse])
def list_account_center_accounts(request: Request) -> list[AccountCenterAccountResponse]:
    trace = get_request_trace_recorder(request, name="account_center.accounts")
    use_case = ListAccountCenterAccountsUseCase(
        _runtime_service(request),
        _snapshot_service(request),
    )
    if trace is not None:
        with trace.measure("route.use_case.execute"):
            raw_rows = use_case.execute(trace=trace)
    else:
        raw_rows = use_case.execute()
    rows: list[AccountCenterAccountResponse] = []
    for raw_row in raw_rows:
        if trace is not None:
            with trace.measure("route.model_validate.row"):
                rows.append(AccountCenterAccountResponse.model_validate(raw_row))
        else:
            rows.append(AccountCenterAccountResponse.model_validate(raw_row))
    if trace is not None:
        trace.set_detail("row_count", len(rows))
    balance_service = _balance_service(request)
    balance_refresh_attempted = 0
    balance_refresh_scheduled = 0
    if balance_service is not None:
        for row in rows:
            balance_refresh_attempted += 1
            try:
                if trace is not None:
                    with trace.measure("route.balance_refresh.schedule.row"):
                        scheduled = _maybe_schedule_balance_refresh(balance_service, row.account_id, trace=trace)
                else:
                    scheduled = _maybe_schedule_balance_refresh(balance_service, row.account_id)
                if scheduled:
                    balance_refresh_scheduled += 1
            except RuntimeError:
                continue
    if trace is not None:
        trace.set_detail("balance_refresh_attempted_count", balance_refresh_attempted)
        trace.set_detail("balance_refresh_scheduled_count", balance_refresh_scheduled)
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
