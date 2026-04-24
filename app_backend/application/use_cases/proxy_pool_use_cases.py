from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app_backend.domain.models.proxy_pool_entry import ProxyPoolEntry
from app_backend.infrastructure.proxy.value_objects import render_proxy_url, parse_proxy_import_line

_UNSET = object()


class ProxyPoolUseCases:
    def __init__(self, proxy_pool_repository, account_repository) -> None:
        self._proxy_pool_repository = proxy_pool_repository
        self._account_repository = account_repository

    def list_all(self) -> list[ProxyPoolEntry]:
        return self._proxy_pool_repository.list_all()

    def create(
        self,
        *,
        name: str,
        scheme: str = "http",
        host: str,
        port: str,
        username: str | None = None,
        password: str | None = None,
    ) -> ProxyPoolEntry:
        now = datetime.now().isoformat(timespec="seconds")
        entry = ProxyPoolEntry(
            proxy_id=str(uuid4()),
            name=name,
            scheme=scheme,
            host=host,
            port=port,
            username=username or None,
            password=password or None,
            created_at=now,
            updated_at=now,
        )
        return self._proxy_pool_repository.create(entry)

    def update(
        self,
        proxy_id: str,
        *,
        name: str | None = None,
        scheme: str | None = None,
        host: str | None = None,
        port: str | None = None,
        username: str | None = _UNSET,
        password: str | None = _UNSET,
    ) -> ProxyPoolEntry:
        now = datetime.now().isoformat(timespec="seconds")
        changes: dict = {"updated_at": now}
        if name is not None:
            changes["name"] = name
        if scheme is not None:
            changes["scheme"] = scheme
        if host is not None:
            changes["host"] = host
        if port is not None:
            changes["port"] = port
        if username is not _UNSET:
            changes["username"] = username or None
        if password is not _UNSET:
            changes["password"] = password or None

        entry = self._proxy_pool_repository.update(proxy_id, **changes)

        # Cascade: update all accounts referencing this proxy
        self._cascade_update_accounts(proxy_id, entry)

        return entry

    def delete(self, proxy_id: str) -> None:
        # Cascade: clear references in accounts BEFORE deleting the proxy
        self._cascade_clear_accounts(proxy_id)
        self._proxy_pool_repository.delete(proxy_id)

    def batch_import(
        self,
        *,
        text: str,
        default_scheme: str = "http",
    ) -> list[ProxyPoolEntry]:
        results = []
        for i, line in enumerate(text.strip().splitlines()):
            parsed = parse_proxy_import_line(line, default_scheme=default_scheme)
            if parsed is None:
                continue
            entry = self.create(
                name=f"\u5bfc\u5165-{i + 1}",
                scheme=parsed["scheme"],
                host=parsed["host"],
                port=parsed["port"],
                username=parsed.get("username"),
                password=parsed.get("password"),
            )
            results.append(entry)
        return results

    def _cascade_update_accounts(self, proxy_id: str, entry: ProxyPoolEntry) -> None:
        """Update proxy_url for all accounts referencing this proxy_id."""
        resolved_url = render_proxy_url(
            scheme=entry.scheme,
            host=entry.host,
            port=entry.port,
            username=entry.username,
            password=entry.password,
        )
        now = datetime.now().isoformat(timespec="seconds")
        for account in self._account_repository.list_accounts():
            changes = {}
            if getattr(account, "browser_proxy_id", None) == proxy_id:
                changes["browser_proxy_mode"] = "pool"
                changes["browser_proxy_url"] = resolved_url
            if getattr(account, "api_proxy_id", None) == proxy_id:
                changes["api_proxy_mode"] = "pool"
                changes["api_proxy_url"] = resolved_url
            if changes:
                changes["updated_at"] = now
                self._account_repository.update_account(account.account_id, **changes)

    def _cascade_clear_accounts(self, proxy_id: str) -> None:
        """Clear proxy references for all accounts using this proxy_id."""
        now = datetime.now().isoformat(timespec="seconds")
        for account in self._account_repository.list_accounts():
            changes = {}
            if getattr(account, "browser_proxy_id", None) == proxy_id:
                changes["browser_proxy_id"] = None
                changes["browser_proxy_mode"] = "direct"
                changes["browser_proxy_url"] = None
            if getattr(account, "api_proxy_id", None) == proxy_id:
                changes["api_proxy_id"] = None
                changes["api_proxy_mode"] = "direct"
                changes["api_proxy_url"] = None
            if changes:
                changes["updated_at"] = now
                self._account_repository.update_account(account.account_id, **changes)
