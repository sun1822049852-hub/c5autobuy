from __future__ import annotations

from datetime import datetime


class UpdateAccountQueryModesUseCase:
    def __init__(self, repository) -> None:
        self._repository = repository

    def execute(
        self,
        *,
        account_id: str,
        api_query_enabled: bool | None = None,
        browser_query_enabled: bool | None = None,
        api_query_disabled_reason: str | None = None,
        browser_query_disabled_reason: str | None = None,
    ):
        changes = {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        if api_query_enabled is not None:
            enabled = bool(api_query_enabled)
            changes["new_api_enabled"] = enabled
            changes["fast_api_enabled"] = enabled
            changes["api_query_disabled_reason"] = None if enabled else _normalize_reason(
                api_query_disabled_reason,
                default="manual_disabled",
            )
        elif api_query_disabled_reason is not None:
            changes["api_query_disabled_reason"] = _normalize_reason(api_query_disabled_reason)

        if browser_query_enabled is not None:
            enabled = bool(browser_query_enabled)
            changes["token_enabled"] = enabled
            changes["browser_query_disabled_reason"] = None if enabled else _normalize_reason(
                browser_query_disabled_reason,
                default="manual_disabled",
            )
        elif browser_query_disabled_reason is not None:
            changes["browser_query_disabled_reason"] = _normalize_reason(browser_query_disabled_reason)

        return self._repository.update_account(
            account_id,
            **changes,
        )


def _normalize_reason(value: str | None, *, default: str | None = None) -> str | None:
    text = str(value or "").strip()
    if text:
        return text
    return default
