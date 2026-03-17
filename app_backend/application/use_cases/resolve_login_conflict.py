from __future__ import annotations

from datetime import datetime

from app_backend.application.use_cases.create_account import CreateAccountUseCase
from app_backend.domain.enums.account_states import PurchaseCapabilityState, PurchasePoolState


class ResolveLoginConflictUseCase:
    def __init__(self, repository, task_manager) -> None:
        self._repository = repository
        self._task_manager = task_manager

    def execute(
        self,
        *,
        account_id: str,
        task_id: str,
        action: str,
    ):
        task = self._task_manager.get_task(task_id)
        if task is None:
            raise KeyError(task_id)

        conflict = task.pending_conflict
        if not conflict or conflict.get("account_id") != account_id:
            raise ValueError("Task is not waiting for conflict resolution")

        if action == "cancel":
            self._task_manager.clear_pending_conflict(task_id)
            self._task_manager.set_result(
                task_id,
                {"account_id": account_id, "cancelled": True},
                state="cancelled",
            )
            return self._task_manager.get_task(task_id)

        if action not in {"create_new_account", "replace_with_new_account"}:
            raise ValueError(f"Unsupported action: {action}")

        captured_login = conflict["captured_login"]
        self._task_manager.set_state(task_id, "saving_account")

        if action == "replace_with_new_account":
            self._repository.delete_account(account_id)

        new_account = CreateAccountUseCase(self._repository).execute(
            remark_name=None,
            proxy_mode="direct",
            proxy_url=None,
            api_key=None,
        )

        now = datetime.now().isoformat(timespec="seconds")
        bound_account = self._repository.update_account(
            new_account.account_id,
            c5_user_id=captured_login["c5_user_id"],
            c5_nick_name=captured_login["c5_nick_name"],
            cookie_raw=captured_login["cookie_raw"],
            purchase_capability_state=PurchaseCapabilityState.BOUND,
            purchase_pool_state=PurchasePoolState.NOT_CONNECTED,
            last_login_at=now,
            last_error=None,
            updated_at=now,
        )

        self._task_manager.clear_pending_conflict(task_id)
        self._task_manager.set_result(
            task_id,
            {
                "account_id": bound_account.account_id,
                "c5_user_id": bound_account.c5_user_id,
                "action": action,
            },
            state="succeeded",
        )
        return self._task_manager.get_task(task_id)

