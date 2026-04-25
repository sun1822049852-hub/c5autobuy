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


def _affected_account_ids(request: Request, *, proxy_id: str) -> list[str]:
    repository = getattr(request.app.state, "account_repository", None)
    list_accounts = getattr(repository, "list_accounts", None)
    if not callable(list_accounts):
        return []
    affected: list[str] = []
    for account in list_accounts():
        if getattr(account, "browser_proxy_id", None) == proxy_id or getattr(account, "api_proxy_id", None) == proxy_id:
            affected.append(str(getattr(account, "account_id", "") or ""))
    return [account_id for account_id in affected if account_id]


def _refresh_runtime_accounts(request: Request) -> None:
    for service_name in ("query_runtime_service", "purchase_runtime_service"):
        runtime_service = getattr(request.app.state, service_name, None)
        refresh_runtime_accounts = getattr(runtime_service, "refresh_runtime_accounts", None)
        if callable(refresh_runtime_accounts):
            try:
                refresh_runtime_accounts()
            except Exception:
                pass


def _publish_account_updates(request: Request, *, account_ids: list[str], proxy_id: str) -> None:
    hub = getattr(request.app.state, "account_update_hub", None)
    publish = getattr(hub, "publish", None)
    if not callable(publish):
        return
    for account_id in account_ids:
        try:
            publish(account_id=account_id, event="update_account", payload={"proxy_id": proxy_id})
        except Exception:
            continue


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

    affected_account_ids = _affected_account_ids(request, proxy_id=proxy_id)
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
    if affected_account_ids:
        _refresh_runtime_accounts(request)
        _publish_account_updates(request, account_ids=affected_account_ids, proxy_id=proxy_id)
    return ProxyPoolResponse.model_validate(entry)


@router.delete("/{proxy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_proxy(proxy_id: str, request: Request):
    affected_account_ids = _affected_account_ids(request, proxy_id=proxy_id)
    _use_cases(request).delete(proxy_id)
    if affected_account_ids:
        _refresh_runtime_accounts(request)
        _publish_account_updates(request, account_ids=affected_account_ids, proxy_id=proxy_id)


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
