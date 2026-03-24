from __future__ import annotations

from collections.abc import Iterable

DEFAULT_ACCOUNT_USER_AGENTS: tuple[str, ...] = (
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) "
        "Gecko/20100101 Firefox/126.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 11.0; Win64; x64; rv:127.0) "
        "Gecko/20100101 Firefox/127.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) "
        "Gecko/20100101 Firefox/128.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 11.0; Win64; x64; rv:129.0) "
        "Gecko/20100101 Firefox/129.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) "
        "Gecko/20100101 Firefox/130.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 11.0; Win64; x64; rv:131.0) "
        "Gecko/20100101 Firefox/131.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 Edg/133.0.0.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) "
        "Gecko/20100101 Firefox/132.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 11.0; Win64; x64; rv:133.0) "
        "Gecko/20100101 Firefox/133.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) "
        "Gecko/20100101 Firefox/134.0"
    ),
    (
        "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0"
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
