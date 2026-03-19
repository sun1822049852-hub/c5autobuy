from __future__ import annotations


def normalize_proxy_input(*, proxy_mode: str, proxy_url: str | None) -> str | None:
    normalized = (proxy_url or "").strip()
    if proxy_mode == "direct" or not normalized or normalized.lower() == "direct":
        return None

    if "://" not in normalized:
        return f"http://{normalized}"

    return normalized


def render_proxy_url(
    *,
    scheme: str,
    host: str,
    port: str,
    username: str | None = None,
    password: str | None = None,
) -> str:
    auth = ""
    if username and password:
        auth = f"{username}:{password}@"
    return f"{scheme}://{auth}{host}:{port}"
