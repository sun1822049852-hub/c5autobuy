from __future__ import annotations

from urllib.parse import urlsplit


_C5_PRODUCT_HOSTS = {
    "c5game.com",
    "www.c5game.com",
}


def normalize_c5_product_url(product_url: str | None) -> str:
    normalized = str(product_url or "").strip()
    if not normalized:
        return ""

    parsed = urlsplit(normalized)
    if parsed.scheme.lower() != "http":
        return normalized

    host = (parsed.hostname or "").lower()
    if host not in _C5_PRODUCT_HOSTS:
        return normalized

    return parsed._replace(scheme="https").geturl()
