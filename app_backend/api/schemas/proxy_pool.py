from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ProxyPoolCreateRequest(BaseModel):
    name: str
    scheme: str = "http"
    host: str
    port: str
    username: str | None = None
    password: str | None = None


class ProxyPoolUpdateRequest(BaseModel):
    name: str | None = None
    scheme: str | None = None
    host: str | None = None
    port: str | None = None
    username: str | None = None
    password: str | None = None


class ProxyPoolBatchImportRequest(BaseModel):
    text: str
    default_scheme: str = "http"


class ProxyPoolResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    proxy_id: str
    name: str
    scheme: str
    host: str
    port: str
    username: str | None
    password: str | None
    created_at: str
    updated_at: str


class ProxyTestResponse(BaseModel):
    reachable: bool
    latency_ms: int
    public_ip: str | None
    error: str | None
