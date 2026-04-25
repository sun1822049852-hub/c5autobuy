from __future__ import annotations

from app_backend.domain.enums.account_states import PurchaseCapabilityState, PurchasePoolState
from app_backend.infrastructure.query.runtime.api_key_status import (
    build_api_query_status,
    build_browser_query_status,
)


class AccountCenterSnapshotService:
    def __init__(self, account_repository) -> None:
        self._account_repository = account_repository

    def list_account_center_accounts(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for account in self._account_repository.list_accounts():
            rows.append(self._build_account_center_row(account))
        return rows

    def get_account_center_account(self, account_id: str) -> dict[str, object] | None:
        get_account = getattr(self._account_repository, "get_account", None)
        if callable(get_account):
            account = get_account(account_id)
            if account is None:
                return None
            return self._build_account_center_row(account)
        for account in self._account_repository.list_accounts():
            if str(getattr(account, "account_id", "") or "") == str(account_id):
                return self._build_account_center_row(account)
        return None

    def _build_account_center_row(self, account) -> dict[str, object]:
        account_id = str(getattr(account, "account_id", "") or "")
        purchase_capability_state = str(getattr(account, "purchase_capability_state", "") or "")
        purchase_pool_state = str(getattr(account, "purchase_pool_state", "") or "")
        purchase_disabled = bool(getattr(account, "purchase_disabled", False))
        purchase_status_code, purchase_status_text = self._build_purchase_status(
            purchase_capability_state=purchase_capability_state,
            purchase_pool_state=purchase_pool_state,
            purchase_disabled=purchase_disabled,
        )

        browser_proxy_url = getattr(account, "browser_proxy_url", None) or None
        api_proxy_url = getattr(account, "api_proxy_url", None) or None
        browser_public_ip = getattr(account, "browser_public_ip", None)
        api_public_ip = getattr(account, "api_public_ip", None)
        api_key = getattr(account, "api_key", None) or None

        (
            api_query_enabled,
            api_query_status_code,
            api_query_status_text,
            api_query_disable_reason_code,
            api_query_disable_reason_text,
        ) = build_api_query_status(
            api_key=api_key,
            new_api_enabled=bool(getattr(account, "new_api_enabled", False)),
            fast_api_enabled=bool(getattr(account, "fast_api_enabled", False)),
            api_query_disabled_reason=getattr(account, "api_query_disabled_reason", None),
            proxy_public_ip=getattr(account, "api_public_ip", None),
        )
        (
            browser_query_enabled,
            browser_query_status_code,
            browser_query_status_text,
            browser_query_disable_reason_code,
            browser_query_disable_reason_text,
        ) = build_browser_query_status(
            token_enabled=bool(getattr(account, "token_enabled", False)),
            browser_query_disabled_reason=getattr(account, "browser_query_disabled_reason", None),
            cookie_raw=getattr(account, "cookie_raw", None),
            last_error=getattr(account, "last_error", None),
            purchase_capability_state=purchase_capability_state,
            purchase_pool_state=purchase_pool_state,
        )

        return {
            "account_id": account_id,
            "display_name": str(getattr(account, "display_name", "") or account_id),
            "remark_name": getattr(account, "remark_name", None),
            "c5_nick_name": getattr(account, "c5_nick_name", None),
            "default_name": str(getattr(account, "default_name", "") or ""),
            "api_key_present": bool(api_key),
            "api_query_enabled": api_query_enabled,
            "api_query_status_code": api_query_status_code,
            "api_query_status_text": api_query_status_text,
            "api_query_disable_reason_code": api_query_disable_reason_code,
            "api_query_disable_reason_text": api_query_disable_reason_text,
            "browser_query_enabled": browser_query_enabled,
            "browser_query_status_code": browser_query_status_code,
            "browser_query_status_text": browser_query_status_text,
            "browser_query_disable_reason_code": browser_query_disable_reason_code,
            "browser_query_disable_reason_text": browser_query_disable_reason_text,
            "api_key": api_key,
            "browser_proxy_mode": str(getattr(account, "browser_proxy_mode", "") or "direct"),
            "browser_proxy_url": browser_proxy_url,
            "browser_proxy_id": getattr(account, "browser_proxy_id", None),
            "browser_proxy_display": browser_proxy_url or browser_public_ip or "未获取IP",
            "api_proxy_mode": str(getattr(account, "api_proxy_mode", "") or "direct"),
            "api_proxy_url": api_proxy_url,
            "api_proxy_id": getattr(account, "api_proxy_id", None),
            "api_proxy_display": api_proxy_url or api_public_ip or "未获取IP",
            "proxy_mode": str(getattr(account, "api_proxy_mode", "") or "direct"),
            "proxy_url": api_proxy_url,
            "proxy_display": api_proxy_url or api_public_ip or "未获取IP",
            "api_ip_allow_list": getattr(account, "api_ip_allow_list", None),
            "browser_public_ip": browser_public_ip,
            "api_public_ip": api_public_ip,
            "balance_amount": getattr(account, "balance_amount", None),
            "balance_source": getattr(account, "balance_source", None),
            "balance_updated_at": getattr(account, "balance_updated_at", None),
            "balance_refresh_after_at": getattr(account, "balance_refresh_after_at", None),
            "balance_last_error": getattr(account, "balance_last_error", None),
            "purchase_capability_state": purchase_capability_state,
            "purchase_pool_state": purchase_pool_state,
            "purchase_disabled": purchase_disabled,
            "selected_steam_id": None,
            "selected_warehouse_text": None,
            "purchase_status_code": purchase_status_code,
            "purchase_status_text": purchase_status_text,
        }

    @staticmethod
    def _build_purchase_status(
        *,
        purchase_capability_state: str,
        purchase_pool_state: str,
        purchase_disabled: bool,
    ) -> tuple[str, str]:
        if (
            purchase_capability_state != PurchaseCapabilityState.BOUND
            or purchase_pool_state == PurchasePoolState.PAUSED_AUTH_INVALID
        ):
            return "not_logged_in", "未登录"
        if purchase_disabled:
            return "disabled", "禁用"
        return "runtime_unavailable", "运行时未就绪"
