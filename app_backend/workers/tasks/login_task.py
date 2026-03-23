from __future__ import annotations

from datetime import datetime

from app_backend.domain.enums.account_states import PurchaseCapabilityState, PurchasePoolState


async def run_login_task(
    *,
    task_id: str,
    account_id: str,
    repository,
    task_manager,
    login_adapter,
) -> None:
    account = repository.get_account(account_id)
    if account is None:
        task_manager.set_error(task_id, "Account not found")
        return

    try:
        task_manager.set_state(task_id, "starting_browser")

        async def emit_state(state: str) -> None:
            task_manager.set_state(task_id, state)

        capture = await login_adapter.run_login(
            proxy_url=account.account_proxy_url,
            emit_state=emit_state,
        )

        current_account = repository.get_account(account_id)
        if current_account is None:
            task_manager.set_error(task_id, "Account not found")
            return

        if current_account.c5_user_id and current_account.c5_user_id != capture.c5_user_id:
            task_manager.set_pending_conflict(
                task_id,
                {
                    "account_id": current_account.account_id,
                    "existing_c5_user_id": current_account.c5_user_id,
                    "existing_c5_nick_name": current_account.c5_nick_name,
                    "captured_login": {
                        "c5_user_id": capture.c5_user_id,
                        "c5_nick_name": capture.c5_nick_name,
                        "cookie_raw": capture.cookie_raw,
                    },
                    "actions": [
                        "create_new_account",
                        "replace_with_new_account",
                        "cancel",
                    ],
                },
                message="登录账号与当前账号不一致，需要用户确认",
            )
            return

        task_manager.set_state(task_id, "saving_account")
        now = datetime.now().isoformat(timespec="seconds")
        updated = repository.update_account(
            account_id,
            c5_user_id=capture.c5_user_id,
            c5_nick_name=capture.c5_nick_name,
            cookie_raw=capture.cookie_raw,
            purchase_capability_state=PurchaseCapabilityState.BOUND,
            purchase_pool_state=PurchasePoolState.NOT_CONNECTED,
            last_login_at=now,
            last_error=None,
            updated_at=now,
        )
        task_manager.set_result(
            task_id,
            {
                "account_id": updated.account_id,
                "c5_user_id": updated.c5_user_id,
            },
            state="succeeded",
        )
    except Exception as exc:
        repository.update_account(
            account_id,
            last_error=str(exc),
            updated_at=datetime.now().isoformat(timespec="seconds"),
        )
        task_manager.set_error(task_id, str(exc))
