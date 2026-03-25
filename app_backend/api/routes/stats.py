from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status

from app_backend.api.schemas.stats import (
    AccountCapabilityStatsResponse,
    QueryItemStatsResponse,
)
from app_backend.application.use_cases.get_account_capability_stats import (
    GetAccountCapabilityStatsUseCase,
)
from app_backend.application.use_cases.get_query_item_stats import GetQueryItemStatsUseCase

router = APIRouter(prefix="/stats", tags=["stats"])


def _stats_repository(request: Request):
    return request.app.state.stats_repository


@router.get("/query-items", response_model=QueryItemStatsResponse)
async def get_query_item_stats(
    request: Request,
    range_mode: str = Query(...),
    date: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
) -> QueryItemStatsResponse:
    use_case = GetQueryItemStatsUseCase(_stats_repository(request))
    try:
        payload = use_case.execute(
            range_mode=range_mode,
            date=date,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return QueryItemStatsResponse.model_validate(payload)


@router.get("/account-capability", response_model=AccountCapabilityStatsResponse)
async def get_account_capability_stats(
    request: Request,
    range_mode: str = Query(...),
    date: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
) -> AccountCapabilityStatsResponse:
    use_case = GetAccountCapabilityStatsUseCase(_stats_repository(request))
    try:
        payload = use_case.execute(
            range_mode=range_mode,
            date=date,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return AccountCapabilityStatsResponse.model_validate(payload)
