from __future__ import annotations

from datetime import datetime

from app_backend.infrastructure.proxy.value_objects import normalize_proxy_input


class UpdateAccountUseCase:
    def __init__(self, repository) -> None:
        self._repository = repository

    def execute(
        self,
        *,
        account_id: str,
        remark_name: str | None,
        proxy_mode: str,
        proxy_url: str | None,
        api_key: str | None,
    ):
        return self._repository.update_account(
            account_id,
            remark_name=remark_name,
            proxy_mode=proxy_mode,
            proxy_url=normalize_proxy_input(proxy_mode=proxy_mode, proxy_url=proxy_url),
            api_key=(api_key or None),
            updated_at=datetime.now().isoformat(timespec="seconds"),
        )
