from __future__ import annotations

import json
from typing import Any

QUERY_STATUS_ENABLED = "enabled"
QUERY_STATUS_DISABLED = "disabled"
API_QUERY_MODES = frozenset({"fast_api", "new_api"})
IP_WHITELIST_ERROR_CODE = 499103
DISABLE_REASON_IP_INVALID = "ip_invalid"
DISABLE_REASON_MANUAL_DISABLED = "manual_disabled"
DISABLE_REASON_MISSING_API_KEY = "missing_api_key"
DISABLE_REASON_NOT_LOGGED_IN = "not_logged_in"
BOUND_PURCHASE_STATE = "bound"
PAUSED_AUTH_INVALID_STATE = "paused_auth_invalid"
NOT_LOGGED_IN_ERROR = "Not login"
REASON_TEXTS = {
    DISABLE_REASON_IP_INVALID: "IP失效",
    DISABLE_REASON_MANUAL_DISABLED: "手动禁用",
    DISABLE_REASON_MISSING_API_KEY: "未配置",
    DISABLE_REASON_NOT_LOGGED_IN: "未登录",
}


def is_api_query_mode(mode_type: str | None) -> bool:
    return str(mode_type or "").strip() in API_QUERY_MODES


def build_api_query_status(
    *,
    api_key: str | None,
    new_api_enabled: bool,
    fast_api_enabled: bool,
    api_query_disabled_reason: str | None,
) -> tuple[bool, str, str, str | None, str | None]:
    if not str(api_key or "").strip():
        return _build_disabled_status(DISABLE_REASON_MISSING_API_KEY)
    if bool(new_api_enabled) and bool(fast_api_enabled):
        return _build_enabled_status()
    reason = _normalize_api_disabled_reason(api_query_disabled_reason) or DISABLE_REASON_MANUAL_DISABLED
    return _build_disabled_status(reason)


def build_browser_query_status(
    *,
    token_enabled: bool,
    browser_query_disabled_reason: str | None,
    cookie_raw: str | None,
    last_error: str | None,
    purchase_capability_state: str | None,
    purchase_pool_state: str | None,
) -> tuple[bool, str, str, str | None, str | None]:
    if not bool(token_enabled):
        reason = _normalize_browser_disabled_reason(browser_query_disabled_reason) or DISABLE_REASON_MANUAL_DISABLED
        return _build_disabled_status(reason)
    if _is_not_logged_in(
        cookie_raw=cookie_raw,
        last_error=last_error,
        purchase_capability_state=purchase_capability_state,
        purchase_pool_state=purchase_pool_state,
    ):
        return _build_disabled_status(DISABLE_REASON_NOT_LOGGED_IN)
    return _build_enabled_status()


def is_api_key_ip_invalid_marker(last_error: str | None) -> bool:
    return is_api_key_ip_invalid_error(error=last_error)


def is_api_key_ip_invalid_error(
    *,
    error: str | None = None,
    response_text: str | None = None,
    status_code: int | str | None = None,
) -> bool:
    error_text = str(error or "").strip()
    if _contains_ip_whitelist_marker(error_text):
        return True

    payload = _parse_response_payload(response_text)
    if isinstance(payload, dict):
        error_code = payload.get("errorCode")
        if _normalize_status_code(error_code) == IP_WHITELIST_ERROR_CODE:
            return True
        if _contains_ip_whitelist_marker(str(payload.get("errorMsg") or "").strip()):
            return True

    response_body = str(response_text or "").strip()
    if _contains_ip_whitelist_marker(response_body):
        return True

    normalized_status = _normalize_status_code(status_code)
    if normalized_status == 403 and _contains_ip_whitelist_marker(error_text):
        return True

    return False


def has_access_token(cookie_raw: str | None) -> bool:
    if not cookie_raw:
        return False
    for raw_part in cookie_raw.split(";"):
        key, _, value = raw_part.strip().partition("=")
        if key == "NC5_accessToken" and bool(value):
            return True
    return False


def _build_enabled_status() -> tuple[bool, str, str, str | None, str | None]:
    return True, QUERY_STATUS_ENABLED, "已启用", None, None


def _build_disabled_status(reason_code: str) -> tuple[bool, str, str, str | None, str | None]:
    return False, QUERY_STATUS_DISABLED, "已禁用", reason_code, REASON_TEXTS.get(reason_code, reason_code)


def _normalize_api_disabled_reason(value: str | None) -> str | None:
    text = str(value or "").strip()
    if text in {DISABLE_REASON_IP_INVALID, DISABLE_REASON_MANUAL_DISABLED}:
        return text
    return None


def _normalize_browser_disabled_reason(value: str | None) -> str | None:
    text = str(value or "").strip()
    if text == DISABLE_REASON_MANUAL_DISABLED:
        return text
    return None


def _is_not_logged_in(
    *,
    cookie_raw: str | None,
    last_error: str | None,
    purchase_capability_state: str | None,
    purchase_pool_state: str | None,
) -> bool:
    if str(last_error or "").strip() == NOT_LOGGED_IN_ERROR:
        return True
    capability_state = str(purchase_capability_state or "").strip()
    if capability_state and capability_state != BOUND_PURCHASE_STATE:
        return True
    if str(purchase_pool_state or "").strip() == PAUSED_AUTH_INVALID_STATE:
        return True
    return not has_access_token(cookie_raw)


def _contains_ip_whitelist_marker(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return "499103" in lowered or "白名单" in text or "ip whitelist" in lowered


def _parse_response_payload(response_text: str | None) -> dict[str, Any] | None:
    payload_text = str(response_text or "").strip()
    if not payload_text:
        return None
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _normalize_status_code(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
