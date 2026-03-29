from __future__ import annotations


def normalize_proxy_bucket_key(*, proxy_mode: str | None, proxy_url: str | None) -> str:
    mode = str(proxy_mode or "direct").strip().lower()
    normalized_url = str(proxy_url or "").strip()
    if mode == "direct" or not normalized_url:
        return "direct"
    return normalized_url


def build_bucket_display_name(*, proxy_mode: str | None, proxy_url: str | None) -> str:
    bucket_key = normalize_proxy_bucket_key(proxy_mode=proxy_mode, proxy_url=proxy_url)
    return "直连" if bucket_key == "direct" else bucket_key
