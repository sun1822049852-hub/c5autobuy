from __future__ import annotations

from app_backend.domain.enums.query_modes import QueryMode


class QueryModeCapacityService:
    def __init__(self, account_repository) -> None:
        self._account_repository = account_repository

    def get_summary(self) -> dict[str, object]:
        counts = {
            QueryMode.NEW_API: 0,
            QueryMode.FAST_API: 0,
            QueryMode.TOKEN: 0,
        }
        for account in self._account_repository.list_accounts():
            if bool(getattr(account, "api_key", None)) and bool(getattr(account, "new_api_enabled", False)):
                counts[QueryMode.NEW_API] += 1
            if bool(getattr(account, "api_key", None)) and bool(getattr(account, "fast_api_enabled", False)):
                counts[QueryMode.FAST_API] += 1
            if self._is_token_account_available(account):
                counts[QueryMode.TOKEN] += 1

        return {
            "modes": {
                mode_type: {
                    "mode_type": mode_type,
                    "available_account_count": count,
                }
                for mode_type, count in counts.items()
            }
        }

    @staticmethod
    def _is_token_account_available(account: object) -> bool:
        if not bool(getattr(account, "token_enabled", False)):
            return False
        if str(getattr(account, "last_error", "") or "").strip() == "Not login":
            return False
        cookie_raw = str(getattr(account, "cookie_raw", "") or "")
        return "NC5_accessToken=" in cookie_raw
