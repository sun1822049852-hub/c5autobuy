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
        account_proxy_mode: str | None = None,
        account_proxy_url: str | None = None,
        api_proxy_mode: str | None = None,
        api_proxy_url: str | None = None,
        proxy_mode: str | None = None,
        proxy_url: str | None = None,
        api_key: str | None,
    ):
        raw_account_proxy_mode = account_proxy_mode or proxy_mode or "direct"
        raw_account_proxy_url = account_proxy_url if account_proxy_url is not None else proxy_url
        normalized_account_proxy_url = normalize_proxy_input(
            proxy_mode=raw_account_proxy_mode,
            proxy_url=raw_account_proxy_url,
        )
        raw_api_proxy_mode = api_proxy_mode if api_proxy_mode is not None else raw_account_proxy_mode
        raw_api_proxy_url = api_proxy_url if api_proxy_url is not None else raw_account_proxy_url
        normalized_api_proxy_url = normalize_proxy_input(
            proxy_mode=raw_api_proxy_mode,
            proxy_url=raw_api_proxy_url,
        )
        return self._repository.update_account(
            account_id,
            remark_name=remark_name,
            proxy_mode="custom" if normalized_account_proxy_url else "direct",
            proxy_url=normalized_account_proxy_url,
            account_proxy_mode="custom" if normalized_account_proxy_url else "direct",
            account_proxy_url=normalized_account_proxy_url,
            api_proxy_mode="custom" if normalized_api_proxy_url else "direct",
            api_proxy_url=normalized_api_proxy_url,
            api_key=(api_key or None),
            updated_at=datetime.now().isoformat(timespec="seconds"),
        )
