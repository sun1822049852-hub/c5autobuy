from app_backend.domain.enums.account_states import PurchaseCapabilityState, PurchasePoolState
from app_backend.domain.models.account import Account
from app_backend.infrastructure.db.base import build_engine, build_session_factory, create_schema
from app_backend.infrastructure.repositories.account_repository import SqliteAccountRepository


def build_account(account_id: str, default_name: str) -> Account:
    return Account(
        account_id=account_id,
        default_name=default_name,
        remark_name=None,
        proxy_mode="direct",
        proxy_url=None,
        api_key=None,
        c5_user_id=None,
        c5_nick_name=None,
        cookie_raw=None,
        purchase_capability_state=PurchaseCapabilityState.UNBOUND,
        purchase_pool_state=PurchasePoolState.NOT_CONNECTED,
        last_login_at=None,
        last_error=None,
        created_at="2026-03-16T10:00:00",
        updated_at="2026-03-16T10:00:00",
    )


def test_create_account_initializes_query_mode_flags(tmp_path):
    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)
    repository = SqliteAccountRepository(build_session_factory(engine))

    created = repository.create_account(build_account("a1", "账号1"))
    listed = repository.list_accounts()[0]

    assert created.new_api_enabled is True
    assert created.fast_api_enabled is True
    assert created.token_enabled is True
    assert listed.new_api_enabled is True
    assert listed.fast_api_enabled is True
    assert listed.token_enabled is True


async def test_query_mode_switches_are_saved_as_global_preferences(client):
    created = await client.post(
        "/accounts",
        json={
            "remark_name": "账号A",
            "proxy_mode": "direct",
            "proxy_url": None,
            "api_key": None,
        },
    )
    account_id = created.json()["account_id"]

    response = await client.patch(
        f"/accounts/{account_id}/query-modes",
        json={
            "new_api_enabled": True,
            "fast_api_enabled": False,
            "token_enabled": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["new_api_enabled"] is True
    assert payload["fast_api_enabled"] is False
    assert payload["token_enabled"] is True
