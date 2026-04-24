from __future__ import annotations

import re


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
    elif username:
        auth = f"{username}@"
    return f"{scheme}://{auth}{host}:{port}"


def parse_proxy_import_line(line: str, *, default_scheme: str = "http") -> dict | None:
    """Parse a single proxy import line into structured fields, or None if blank."""
    line = line.strip()
    if not line:
        return None

    # Format: scheme://user:pass@host:port or scheme://host:port (supports IPv6 [::1])
    url_match = re.match(
        r"^(?P<scheme>https?|socks5)://(?:(?P<username>[^:@]+):(?P<password>[^@]+)@)?(?P<host>\[[^\]]+\]|[^:]+):(?P<port>\d+)$",
        line,
    )
    if url_match:
        return {
            "scheme": url_match.group("scheme"),
            "host": url_match.group("host"),
            "port": url_match.group("port"),
            "username": url_match.group("username"),
            "password": url_match.group("password"),
        }

    # Format: host:port:user:pass (password may contain colons)
    parts = line.split(":", 3)
    if len(parts) == 4 and parts[1].isdigit():
        return {
            "scheme": default_scheme,
            "host": parts[0],
            "port": parts[1],
            "username": parts[2],
            "password": parts[3],
        }

    # Format: host:port
    if len(parts) == 2:
        return {
            "scheme": default_scheme,
            "host": parts[0],
            "port": parts[1],
            "username": None,
            "password": None,
        }

    return None
