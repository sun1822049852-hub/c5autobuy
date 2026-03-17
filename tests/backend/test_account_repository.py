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
        disabled=False,
    )


def test_repository_can_create_and_list_accounts(tmp_path):
    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)
    repository = SqliteAccountRepository(build_session_factory(engine))

    repository.create_account(build_account("a1", "账号1"))

    accounts = repository.list_accounts()

    assert [account.account_id for account in accounts] == ["a1"]


def test_repository_can_update_account(tmp_path):
    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)
    repository = SqliteAccountRepository(build_session_factory(engine))
    repository.create_account(build_account("a1", "账号1"))

    updated = repository.update_account(
        "a1",
        remark_name="新备注",
        proxy_mode="custom",
        proxy_url="http://127.0.0.1:8080",
        api_key="abc123",
    )

    assert updated.remark_name == "新备注"
    assert updated.proxy_url == "http://127.0.0.1:8080"
    assert updated.api_key == "abc123"


def test_clear_purchase_capability_keeps_api_key(tmp_path):
    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)
    repository = SqliteAccountRepository(build_session_factory(engine))
    repository.create_account(build_account("a1", "账号1"))
    repository.update_account(
        "a1",
        api_key="abc123",
        c5_user_id="10001",
        c5_nick_name="nick",
        cookie_raw="cookie=value",
        purchase_capability_state=PurchaseCapabilityState.BOUND,
    )

    cleared = repository.clear_purchase_capability("a1")

    assert cleared.api_key == "abc123"
    assert cleared.c5_user_id is None
    assert cleared.cookie_raw is None
    assert cleared.purchase_capability_state == PurchaseCapabilityState.UNBOUND


def test_repository_can_delete_account(tmp_path):
    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)
    repository = SqliteAccountRepository(build_session_factory(engine))
    repository.create_account(build_account("a1", "账号1"))

    repository.delete_account("a1")

    assert repository.list_accounts() == []
