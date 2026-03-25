from __future__ import annotations

import json
from typing import Any

API_KEY_STATUS_ACTIVE = "active"
API_KEY_STATUS_IP_INVALID = "ip_invalid"
API_KEY_STATUS_MISSING = "missing"
API_QUERY_MODES = frozenset({"fast_api", "new_api"})
IP_WHITELIST_ERROR_CODE = 499103


def is_api_query_mode(mode_type: str | None) -> bool:
    return str(mode_type or "").strip() in API_QUERY_MODES


def build_api_key_status(*, api_key: str | None, last_error: str | None) -> tuple[str, str]:
    if not str(api_key or "").strip():
        return API_KEY_STATUS_MISSING, "无"
    if is_api_key_ip_invalid_marker(last_error):
        return API_KEY_STATUS_IP_INVALID, "IP失效"
    return API_KEY_STATUS_ACTIVE, "有"


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
