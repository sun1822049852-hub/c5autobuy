from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ProxyPoolEntry:
    proxy_id: str
    name: str
    scheme: str
    host: str
    port: str
    username: str | None
    password: str | None
    created_at: str
    updated_at: str
