from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app_backend.api.schemas.query_configs import (
    QueryConfigCreateRequest,
    QueryConfigResponse,
    QueryConfigUpdateRequest,
    QueryItemCreateRequest,
    QueryItemResponse,
    QueryItemUpdateRequest,
    QueryModeSettingResponse,
    QueryModeSettingUpdateRequest,
)
from app_backend.application.use_cases.add_query_item import AddQueryItemUseCase
from app_backend.application.use_cases.create_query_config import CreateQueryConfigUseCase
from app_backend.application.use_cases.delete_query_config import DeleteQueryConfigUseCase
from app_backend.application.use_cases.delete_query_item import DeleteQueryItemUseCase
from app_backend.application.use_cases.get_query_config import GetQueryConfigUseCase
from app_backend.application.use_cases.list_query_configs import ListQueryConfigsUseCase
from app_backend.application.use_cases.refresh_query_item_detail import RefreshQueryItemDetailUseCase
from app_backend.application.use_cases.update_query_config import UpdateQueryConfigUseCase
from app_backend.application.use_cases.update_query_item import UpdateQueryItemUseCase
from app_backend.application.use_cases.update_query_mode_setting import UpdateQueryModeSettingUseCase

router = APIRouter(prefix="/query-configs", tags=["query-configs"])


def _repository(request: Request):
    return request.app.state.query_config_repository


def _detail_collector(request: Request):
    return request.app.state.product_detail_collector


def _detail_refresh_service(request: Request):
    return request.app.state.query_item_detail_refresh_service


@router.get("", response_model=list[QueryConfigResponse])
async def list_query_configs(request: Request) -> list[QueryConfigResponse]:
    use_case = ListQueryConfigsUseCase(_repository(request))
    return [QueryConfigResponse.model_validate(config) for config in use_case.execute()]


@router.post("", response_model=QueryConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_query_config(
    payload: QueryConfigCreateRequest,
    request: Request,
) -> QueryConfigResponse:
    use_case = CreateQueryConfigUseCase(_repository(request))
    config = use_case.execute(name=payload.name, description=payload.description)
    return QueryConfigResponse.model_validate(config)


@router.get("/{config_id}", response_model=QueryConfigResponse)
async def get_query_config(config_id: str, request: Request) -> QueryConfigResponse:
    config = GetQueryConfigUseCase(_repository(request)).execute(config_id)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Query config not found")
    return QueryConfigResponse.model_validate(config)


@router.patch("/{config_id}", response_model=QueryConfigResponse)
async def update_query_config(
    config_id: str,
    payload: QueryConfigUpdateRequest,
    request: Request,
) -> QueryConfigResponse:
    use_case = UpdateQueryConfigUseCase(_repository(request))
    try:
        config = use_case.execute(
            config_id=config_id,
            name=payload.name,
            description=payload.description,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Query config not found") from exc
    return QueryConfigResponse.model_validate(config)


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_query_config(config_id: str, request: Request) -> None:
    use_case = DeleteQueryConfigUseCase(_repository(request))
    try:
        use_case.execute(config_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Query config not found") from exc


@router.post("/{config_id}/items", response_model=QueryItemResponse, status_code=status.HTTP_201_CREATED)
async def add_query_item(
    config_id: str,
    payload: QueryItemCreateRequest,
    request: Request,
) -> QueryItemResponse:
    use_case = AddQueryItemUseCase(
        _repository(request),
        request.app.state.product_url_parser,
        _detail_collector(request),
    )
    try:
        item = await use_case.execute(
            config_id=config_id,
            product_url=payload.product_url,
            max_wear=payload.max_wear,
            max_price=payload.max_price,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Query config not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return QueryItemResponse.model_validate(item)


@router.patch("/{config_id}/items/{query_item_id}", response_model=QueryItemResponse)
async def update_query_item(
    config_id: str,
    query_item_id: str,
    payload: QueryItemUpdateRequest,
    request: Request,
) -> QueryItemResponse:
    use_case = UpdateQueryItemUseCase(_repository(request))
    try:
        item = use_case.execute(
            query_item_id=query_item_id,
            max_wear=payload.max_wear,
            max_price=payload.max_price,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Query item not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if item.config_id != config_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Query item not found")
    return QueryItemResponse.model_validate(item)


@router.delete("/{config_id}/items/{query_item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_query_item(
    config_id: str,
    query_item_id: str,
    request: Request,
) -> None:
    config = _repository(request).get_config(config_id)
    if config is None or all(item.query_item_id != query_item_id for item in config.items):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Query item not found")
    DeleteQueryItemUseCase(_repository(request)).execute(query_item_id=query_item_id)


@router.post("/{config_id}/items/{query_item_id}/refresh-detail", response_model=QueryItemResponse)
async def refresh_query_item_detail(
    config_id: str,
    query_item_id: str,
    request: Request,
) -> QueryItemResponse:
    use_case = RefreshQueryItemDetailUseCase(_detail_refresh_service(request))
    try:
        item = await use_case.execute(
            config_id=config_id,
            query_item_id=query_item_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Query item not found") from exc
    except ValueError as exc:
        status_code = status.HTTP_409_CONFLICT if "没有可用于商品信息补全的已登录账号" in str(exc) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return QueryItemResponse.model_validate(item)


@router.patch("/{config_id}/modes/{mode_type}", response_model=QueryModeSettingResponse)
async def update_query_mode_setting(
    config_id: str,
    mode_type: str,
    payload: QueryModeSettingUpdateRequest,
    request: Request,
) -> QueryModeSettingResponse:
    use_case = UpdateQueryModeSettingUseCase(_repository(request))
    try:
        setting = use_case.execute(
            config_id=config_id,
            mode_type=mode_type,
            enabled=payload.enabled,
            window_enabled=payload.window_enabled,
            start_hour=payload.start_hour,
            start_minute=payload.start_minute,
            end_hour=payload.end_hour,
            end_minute=payload.end_minute,
            base_cooldown_min=payload.base_cooldown_min,
            base_cooldown_max=payload.base_cooldown_max,
            random_delay_enabled=payload.random_delay_enabled,
            random_delay_min=payload.random_delay_min,
            random_delay_max=payload.random_delay_max,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Query mode not found") from exc
    return QueryModeSettingResponse.model_validate(setting)
