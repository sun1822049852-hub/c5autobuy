from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app_backend.api.schemas.query_runtime import (
    QueryRuntimePrepareRequest,
    QueryRuntimePrepareResponse,
    QueryRuntimeStartRequest,
    QueryRuntimeStatusResponse,
)
from app_backend.application.use_cases.get_query_runtime_status import GetQueryRuntimeStatusUseCase
from app_backend.application.use_cases.prepare_query_runtime import PrepareQueryRuntimeUseCase
from app_backend.application.use_cases.start_query_runtime import StartQueryRuntimeUseCase
from app_backend.application.use_cases.stop_query_runtime import StopQueryRuntimeUseCase

router = APIRouter(prefix="/query-runtime", tags=["query-runtime"])


def _runtime_service(request: Request):
    return request.app.state.query_runtime_service


def _refresh_service(request: Request):
    return request.app.state.query_item_detail_refresh_service


@router.get("/status", response_model=QueryRuntimeStatusResponse)
async def get_query_runtime_status(request: Request) -> QueryRuntimeStatusResponse:
    use_case = GetQueryRuntimeStatusUseCase(_runtime_service(request))
    return QueryRuntimeStatusResponse.model_validate(use_case.execute())


@router.post("/start", response_model=QueryRuntimeStatusResponse)
async def start_query_runtime(
    payload: QueryRuntimeStartRequest,
    request: Request,
) -> QueryRuntimeStatusResponse:
    runtime_service = _runtime_service(request)
    started, message = StartQueryRuntimeUseCase(runtime_service).execute(config_id=payload.config_id)
    if not started:
        status_code = status.HTTP_404_NOT_FOUND if message == "查询配置不存在" else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=status_code, detail=message)
    return QueryRuntimeStatusResponse.model_validate(runtime_service.get_status())


@router.post("/prepare", response_model=QueryRuntimePrepareResponse)
async def prepare_query_runtime(
    payload: QueryRuntimePrepareRequest,
    request: Request,
) -> QueryRuntimePrepareResponse:
    try:
        summary = await PrepareQueryRuntimeUseCase(_refresh_service(request)).execute(
            config_id=payload.config_id,
            force_refresh=payload.force_refresh,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="查询配置不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return QueryRuntimePrepareResponse.model_validate(summary)


@router.post("/stop", response_model=QueryRuntimeStatusResponse)
async def stop_query_runtime(request: Request) -> QueryRuntimeStatusResponse:
    runtime_service = _runtime_service(request)
    stopped, message = StopQueryRuntimeUseCase(runtime_service).execute()
    if not stopped:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)
    return QueryRuntimeStatusResponse.model_validate(runtime_service.get_status())
