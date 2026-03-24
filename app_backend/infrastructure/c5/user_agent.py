from __future__ import annotations

from collections.abc import Iterable

DEFAULT_ACCOUNT_USER_AGENTS: tuple[str, ...] = (
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) "
        "Gecko/20100101 Firefox/123.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) "
        "Gecko/20100101 Firefox/124.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0"
    ),
)


def normalize_user_agent(user_agent: str | None) -> str | None:
    if user_agent is None:
        return None
    normalized = str(user_agent).strip()
    return normalized or None


def get_default_user_agent() -> str:
    return DEFAULT_ACCOUNT_USER_AGENTS[0]


def get_effective_user_agent(user_agent: str | None) -> str:
    return normalize_user_agent(user_agent) or get_default_user_agent()


def pick_rotating_user_agent(existing_user_agents: Iterable[str | None]) -> str:
    normalized_existing = [normalize_user_agent(user_agent) for user_agent in existing_user_agents]
    assigned_user_agents = {user_agent for user_agent in normalized_existing if user_agent}
    for candidate in DEFAULT_ACCOUNT_USER_AGENTS:
        if candidate not in assigned_user_agents:
            return candidate
    assigned_count = sum(1 for user_agent in normalized_existing if user_agent)
    return DEFAULT_ACCOUNT_USER_AGENTS[assigned_count % len(DEFAULT_ACCOUNT_USER_AGENTS)]
