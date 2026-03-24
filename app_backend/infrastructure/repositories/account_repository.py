from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app_backend.domain.enums.account_states import PurchaseCapabilityState, PurchasePoolState
from app_backend.domain.models.account import Account
from app_backend.infrastructure.db.models import AccountRecord


class SqliteAccountRepository:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def list_accounts(self) -> list[Account]:
        with self._session_factory() as session:
            rows = session.scalars(select(AccountRecord).order_by(AccountRecord.created_at)).all()
            return [self._to_domain(row) for row in rows]

    def get_account(self, account_id: str) -> Account | None:
        with self._session_factory() as session:
            row = session.get(AccountRecord, account_id)
            return self._to_domain(row) if row else None

    def create_account(self, account: Account) -> Account:
        with self._session_factory() as session:
            account_proxy_mode = getattr(account, "account_proxy_mode", None) or getattr(account, "proxy_mode", None) or "direct"
            account_proxy_url = getattr(account, "account_proxy_url", None)
            if account_proxy_url is None:
                account_proxy_url = getattr(account, "proxy_url", None)
            api_proxy_mode = getattr(account, "api_proxy_mode", None) or account_proxy_mode
            api_proxy_url = getattr(account, "api_proxy_url", None)
            if api_proxy_url is None:
                api_proxy_url = account_proxy_url
            row = AccountRecord(
                account_id=account.account_id,
                default_name=account.default_name,
                remark_name=account.remark_name,
                proxy_mode=account_proxy_mode,
                proxy_url=account_proxy_url,
                account_proxy_mode=account_proxy_mode,
                account_proxy_url=account_proxy_url,
                api_proxy_mode=api_proxy_mode,
                api_proxy_url=api_proxy_url,
                api_key=account.api_key,
                c5_user_id=account.c5_user_id,
                c5_nick_name=account.c5_nick_name,
                cookie_raw=account.cookie_raw,
                user_agent=getattr(account, "user_agent", None),
                purchase_capability_state=account.purchase_capability_state,
                purchase_pool_state=account.purchase_pool_state,
                last_login_at=account.last_login_at,
                last_error=account.last_error,
                created_at=account.created_at,
                updated_at=account.updated_at,
                purchase_disabled=int(account.purchase_disabled),
                purchase_recovery_due_at=account.purchase_recovery_due_at,
                new_api_enabled=int(account.new_api_enabled),
                fast_api_enabled=int(account.fast_api_enabled),
                token_enabled=int(account.token_enabled),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._to_domain(row)

    def update_account(self, account_id: str, **changes: Any) -> Account:
        with self._session_factory() as session:
            row = session.get(AccountRecord, account_id)
            if row is None:
                raise KeyError(account_id)

            normalized_changes = dict(changes)
            if "account_proxy_mode" in normalized_changes and "proxy_mode" not in normalized_changes:
                normalized_changes["proxy_mode"] = normalized_changes["account_proxy_mode"]
            if "account_proxy_url" in normalized_changes and "proxy_url" not in normalized_changes:
                normalized_changes["proxy_url"] = normalized_changes["account_proxy_url"]
            if "proxy_mode" in normalized_changes and "account_proxy_mode" not in normalized_changes:
                normalized_changes["account_proxy_mode"] = normalized_changes["proxy_mode"]
            if "proxy_url" in normalized_changes and "account_proxy_url" not in normalized_changes:
                normalized_changes["account_proxy_url"] = normalized_changes["proxy_url"]

            for key, value in normalized_changes.items():
                if hasattr(row, key):
                    setattr(row, key, value)

            session.commit()
            session.refresh(row)
            return self._to_domain(row)

    def clear_purchase_capability(self, account_id: str) -> Account:
        with self._session_factory() as session:
            row = session.get(AccountRecord, account_id)
            if row is None:
                raise KeyError(account_id)

            row.c5_user_id = None
            row.c5_nick_name = None
            row.cookie_raw = None
            row.purchase_capability_state = PurchaseCapabilityState.UNBOUND
            row.purchase_pool_state = PurchasePoolState.NOT_CONNECTED
            row.last_login_at = None
            row.last_error = None

            session.commit()
            session.refresh(row)
            return self._to_domain(row)

    def delete_account(self, account_id: str) -> None:
        with self._session_factory() as session:
            row = session.get(AccountRecord, account_id)
            if row is None:
                return
            session.delete(row)
            session.commit()

    @staticmethod
    def _to_domain(row: AccountRecord) -> Account:
        account_proxy_mode = getattr(row, "account_proxy_mode", None) or row.proxy_mode or "direct"
        account_proxy_url = getattr(row, "account_proxy_url", None)
        if account_proxy_url is None:
            account_proxy_url = row.proxy_url
        api_proxy_mode = getattr(row, "api_proxy_mode", None) or account_proxy_mode
        api_proxy_url = getattr(row, "api_proxy_url", None)
        if api_proxy_url is None:
            api_proxy_url = account_proxy_url
        return Account(
            account_id=row.account_id,
            default_name=row.default_name,
            remark_name=row.remark_name,
            proxy_mode=account_proxy_mode,
            proxy_url=account_proxy_url,
            api_key=row.api_key,
            c5_user_id=row.c5_user_id,
            c5_nick_name=row.c5_nick_name,
            cookie_raw=row.cookie_raw,
            user_agent=getattr(row, "user_agent", None),
            purchase_capability_state=row.purchase_capability_state,
            purchase_pool_state=row.purchase_pool_state,
            last_login_at=row.last_login_at,
            last_error=row.last_error,
            created_at=row.created_at,
            updated_at=row.updated_at,
            purchase_disabled=bool(getattr(row, "purchase_disabled", 0)),
            purchase_recovery_due_at=getattr(row, "purchase_recovery_due_at", None),
            new_api_enabled=bool(row.new_api_enabled),
            fast_api_enabled=bool(row.fast_api_enabled),
            token_enabled=bool(row.token_enabled),
            account_proxy_mode=account_proxy_mode,
            account_proxy_url=account_proxy_url,
            api_proxy_mode=api_proxy_mode,
            api_proxy_url=api_proxy_url,
        )
