from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app_backend.api.schemas.query_configs import QueryItemUrlParseRequest, QueryItemUrlParseResponse
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
