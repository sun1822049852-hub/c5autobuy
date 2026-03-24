from app_backend.infrastructure.c5.user_agent import DEFAULT_ACCOUNT_USER_AGENTS


def test_default_account_user_agent_pool_has_broader_rotation_coverage():
    assert len(DEFAULT_ACCOUNT_USER_AGENTS) == 20


def test_default_account_user_agent_pool_excludes_pure_chrome_variants():
    pure_chrome_agents = [
        user_agent
        for user_agent in DEFAULT_ACCOUNT_USER_AGENTS
        if "Chrome/" in user_agent and "Edg/" not in user_agent and "Firefox/" not in user_agent
    ]

    assert pure_chrome_agents == []
