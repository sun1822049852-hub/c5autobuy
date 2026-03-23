from __future__ import annotations


def classify_c5_response_error(*, status: int, text: str) -> str | None:
    normalized = str(text or "").strip().lower()

    if "not login" in normalized:
        return "Not login"
    if status == 403:
        return "HTTP 403 Forbidden"
    if status == 429:
        return "HTTP 429 Too Many Requests"
    if status != 200:
        return f"HTTP {status} 请求失败"
    return None


def is_auth_invalid_c5_error(error: str | None) -> bool:
    normalized = str(error or "").strip().lower()
    return "not login" in normalized or "403" in normalized
