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
        browser_proxy_mode: str,
        browser_proxy_url: str | None,
        api_proxy_mode: str,
        api_proxy_url: str | None,
        api_key: str | None,
    ):
        normalized_browser_proxy_url = normalize_proxy_input(
            proxy_mode=browser_proxy_mode,
            proxy_url=browser_proxy_url,
        )
        normalized_api_proxy_url = normalize_proxy_input(
            proxy_mode=api_proxy_mode,
            proxy_url=api_proxy_url,
        )
        return self._repository.update_account(
            account_id,
            remark_name=remark_name,
            browser_proxy_mode="custom" if normalized_browser_proxy_url else "direct",
            browser_proxy_url=normalized_browser_proxy_url,
            api_proxy_mode="custom" if normalized_api_proxy_url else "direct",
            api_proxy_url=normalized_api_proxy_url,
            api_key=(api_key or None),
            updated_at=datetime.now().isoformat(timespec="seconds"),
        )
