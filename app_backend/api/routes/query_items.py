from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app_backend.api.schemas.query_configs import (
    QueryItemDetailFetchRequest,
    QueryItemDetailFetchResponse,
    QueryItemUrlParseRequest,
    QueryItemUrlParseResponse,
)
from app_backend.application.use_cases.fetch_query_item_detail import FetchQueryItemDetailUseCase
from app_backend.application.use_cases.parse_query_item_url import ParseQueryItemUrlUseCase

router = APIRouter(prefix="/query-items", tags=["query-items"])


@router.post("/parse-url", response_model=QueryItemUrlParseResponse)
async def parse_query_item_url(
    payload: QueryItemUrlParseRequest,
    request: Request,
) -> QueryItemUrlParseResponse:
    use_case = ParseQueryItemUrlUseCase(request.app.state.product_url_parser)
    try:
        parsed = use_case.execute(product_url=payload.product_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return QueryItemUrlParseResponse(
        product_url=parsed.product_url,
        external_item_id=parsed.external_item_id,
    )


@router.post("/fetch-detail", response_model=QueryItemDetailFetchResponse)
async def fetch_query_item_detail(
    payload: QueryItemDetailFetchRequest,
    request: Request,
) -> QueryItemDetailFetchResponse:
    use_case = FetchQueryItemDetailUseCase(request.app.state.product_detail_collector)
    try:
        detail = await use_case.execute(
            external_item_id=payload.external_item_id,
            product_url=payload.product_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return QueryItemDetailFetchResponse(
        product_url=detail.product_url,
        external_item_id=detail.external_item_id,
        item_name=detail.item_name,
        market_hash_name=detail.market_hash_name,
        min_wear=detail.min_wear,
        detail_max_wear=detail.max_wear,
        last_market_price=detail.last_market_price,
    )
