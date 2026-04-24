from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app_backend.api.schemas.proxy_pool import (
    ProxyPoolBatchImportRequest,
    ProxyPoolCreateRequest,
    ProxyPoolResponse,
    ProxyPoolUpdateRequest,
    ProxyTestResponse,
)

router = APIRouter(prefix="/proxy-pool", tags=["proxy-pool"])


def _use_cases(request: Request):
    return request.app.state.proxy_pool_use_cases


def _test_service(request: Request):
    return request.app.state.proxy_test_service


@router.get("", response_model=list[ProxyPoolResponse])
async def list_proxies(request: Request) -> list[ProxyPoolResponse]:
    entries = _use_cases(request).list_all()
    return [ProxyPoolResponse.model_validate(entry) for entry in entries]


@router.post("", response_model=ProxyPoolResponse, status_code=status.HTTP_201_CREATED)
async def create_proxy(payload: ProxyPoolCreateRequest, request: Request) -> ProxyPoolResponse:
    entry = _use_cases(request).create(
        name=payload.name,
        scheme=payload.scheme,
        host=payload.host,
        port=payload.port,
        username=payload.username,
        password=payload.password,
    )
    return ProxyPoolResponse.model_validate(entry)


@router.post("/batch-import", response_model=list[ProxyPoolResponse])
async def batch_import(payload: ProxyPoolBatchImportRequest, request: Request) -> list[ProxyPoolResponse]:
    entries = _use_cases(request).batch_import(
        text=payload.text,
        default_scheme=payload.default_scheme,
    )
    return [ProxyPoolResponse.model_validate(entry) for entry in entries]


@router.patch("/{proxy_id}", response_model=ProxyPoolResponse)
async def update_proxy(proxy_id: str, payload: ProxyPoolUpdateRequest, request: Request) -> ProxyPoolResponse:
    from app_backend.application.use_cases.proxy_pool_use_cases import _UNSET

    fields = payload.model_fields_set
    kwargs: dict = {}
    if "name" in fields:
        kwargs["name"] = payload.name
    if "scheme" in fields:
        kwargs["scheme"] = payload.scheme
    if "host" in fields:
        kwargs["host"] = payload.host
    if "port" in fields:
        kwargs["port"] = payload.port
    kwargs["username"] = payload.username if "username" in fields else _UNSET
    kwargs["password"] = payload.password if "password" in fields else _UNSET

    try:
        entry = _use_cases(request).update(proxy_id, **kwargs)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proxy not found")
    return ProxyPoolResponse.model_validate(entry)


@router.delete("/{proxy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_proxy(proxy_id: str, request: Request):
    _use_cases(request).delete(proxy_id)


@router.post("/{proxy_id}/test", response_model=ProxyTestResponse)
async def test_proxy(proxy_id: str, request: Request) -> ProxyTestResponse:
    entry = request.app.state.proxy_pool_repository.get(proxy_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proxy not found")
    result = await _test_service(request).test(
        scheme=entry.scheme,
        host=entry.host,
        port=entry.port,
        username=entry.username,
        password=entry.password,
    )
    return ProxyTestResponse(**result)
