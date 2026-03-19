from __future__ import annotations

from functools import partial
from typing import Any, Callable

from app_frontend.app.formatters.task_display import task_state_label


class AccountCenterController:
    def __init__(
        self,
        *,
        view_model,
        backend_client,
        task_runner,
        publish_status: Callable[[str], None],
        refresh_view: Callable[[], None],
        publish_login_task: Callable[[dict[str, Any]], None],
        publish_error: Callable[[str], None],
    ) -> None:
        self.view_model = view_model
        self.backend_client = backend_client
        self.task_runner = task_runner
        self.publish_status = publish_status
        self.refresh_view = refresh_view
        self.publish_login_task = publish_login_task
        self.publish_error = publish_error
        self.active_login_account_id: str | None = None
        self.active_login_task_id: str | None = None

    def load_accounts(self) -> None:
        if self.backend_client is None:
            return
        self.publish_status("正在加载账号列表...")
        self.task_runner.submit(
            lambda: self.backend_client.list_account_center_accounts(),
            on_success=self._handle_accounts_loaded,
            on_error=self.publish_error,
        )

    def create_account(self, payload: dict[str, Any]) -> None:
        if self.backend_client is None:
            return
        self.publish_status("正在创建账号...")
        self.task_runner.submit(
            lambda: self.backend_client.create_account(payload),
            on_success=lambda _result: self.load_accounts(),
            on_error=self.publish_error,
        )

    def edit_account_remark(self, account_id: str, payload: dict[str, Any]) -> None:
        if self.backend_client is None:
            return
        account = self._account_for(account_id)
        if account is None:
            return
        self.publish_status("正在更新账号...")
        update_payload = {
            "remark_name": payload.get("remark_name"),
            "proxy_mode": account.get("proxy_mode") or "direct",
            "proxy_url": account.get("proxy_url"),
            "api_key": account.get("api_key"),
        }
        self.task_runner.submit(
            lambda: self.backend_client.update_account(account_id, update_payload),
            on_success=lambda _result: self.load_accounts(),
            on_error=self.publish_error,
        )

    def edit_account_api_key(self, account_id: str, payload: dict[str, Any]) -> None:
        if self.backend_client is None:
            return
        account = self._account_for(account_id)
        if account is None:
            return
        self.publish_status("正在更新账号...")
        update_payload = {
            "remark_name": account.get("remark_name"),
            "proxy_mode": account.get("proxy_mode") or "direct",
            "proxy_url": account.get("proxy_url"),
            "api_key": payload.get("api_key"),
        }
        self.task_runner.submit(
            lambda: self.backend_client.update_account(account_id, update_payload),
            on_success=lambda _result: self.load_accounts(),
            on_error=self.publish_error,
        )

    def edit_account_proxy(self, account_id: str, proxy_payload: dict[str, Any] | None) -> None:
        self._submit_login_proxy(
            account_id=account_id,
            proxy_payload=proxy_payload,
            start_when_unchanged=False,
        )

    def submit_login_proxy_for_account(self, account_id: str, proxy_payload: dict[str, Any] | None) -> None:
        self._submit_login_proxy(
            account_id=account_id,
            proxy_payload=proxy_payload,
            start_when_unchanged=True,
        )

    def update_account_purchase_config(self, account_id: str, payload: dict[str, Any]) -> None:
        if self.backend_client is None:
            return
        self.publish_status("正在更新购买配置...")
        self.task_runner.submit(
            lambda: self.backend_client.update_account_purchase_config(account_id, payload),
            on_success=lambda _result: self.load_accounts(),
            on_error=self.publish_error,
        )

    def load_purchase_inventory_detail(
        self,
        account_id: str,
        on_loaded: Callable[[dict[str, Any]], None],
    ) -> None:
        if self.backend_client is None:
            return
        self.publish_status("正在加载仓库配置...")
        self.task_runner.submit(
            lambda: self.backend_client.get_purchase_runtime_inventory_detail(account_id),
            on_success=lambda detail: self._handle_purchase_inventory_detail_loaded(detail, on_loaded),
            on_error=self.publish_error,
        )

    def edit_detail_account(self, payload: dict[str, Any], query_mode_payload: dict[str, Any] | None = None) -> None:
        if self.backend_client is None:
            return
        account = self.view_model.detail_account
        if account is None:
            return
        self.publish_status("正在更新账号...")

        async def update_account_bundle() -> dict[str, Any]:
            updated_account = await self.backend_client.update_account(account["account_id"], payload)
            if query_mode_payload is None:
                return updated_account
            return await self.backend_client.update_account_query_modes(account["account_id"], query_mode_payload)

        self.task_runner.submit(
            update_account_bundle,
            on_success=self._handle_account_updated,
            on_error=self.publish_error,
        )

    def start_login_for_detail(self) -> None:
        if self.backend_client is None:
            return
        account = self.view_model.detail_account
        if account is None:
            return
        self.active_login_account_id = account["account_id"]
        self.publish_status("正在发起登录...")
        self.task_runner.submit(
            lambda: self.backend_client.start_login(account["account_id"]),
            on_success=partial(self._handle_login_started, account["account_id"]),
            on_error=self.publish_error,
        )

    def submit_login_proxy_for_detail(self, proxy_payload: dict[str, Any] | None) -> None:
        account = self.view_model.detail_account
        if account is None:
            return
        self.submit_login_proxy_for_account(account["account_id"], proxy_payload)

    def resolve_login_conflict(self, action: str) -> None:
        if self.backend_client is None or self.active_login_account_id is None or self.active_login_task_id is None:
            return
        self.publish_status("正在处理账号冲突...")
        self.task_runner.submit(
            lambda: self.backend_client.resolve_login_conflict(
                self.active_login_account_id,
                task_id=self.active_login_task_id,
                action=action,
            ),
            on_success=self._handle_conflict_resolved,
            on_error=self.publish_error,
        )

    def clear_purchase_capability_for_detail(self) -> None:
        if self.backend_client is None:
            return
        account = self.view_model.detail_account
        if account is None:
            return
        self.publish_status("正在清除购买能力...")
        self.task_runner.submit(
            lambda: self.backend_client.clear_purchase_capability(account["account_id"]),
            on_success=self._handle_account_updated,
            on_error=self.publish_error,
        )

    def delete_detail_account(self) -> None:
        if self.backend_client is None:
            return
        account = self.view_model.detail_account
        if account is None:
            return
        self.publish_status("正在删除账号...")
        self.task_runner.submit(
            lambda: self.backend_client.delete_account(account["account_id"]),
            on_success=lambda _result: self._handle_account_deleted(account["account_id"]),
            on_error=self.publish_error,
        )

    def delete_account(self, account_id: str) -> None:
        if self.backend_client is None:
            return
        self.publish_status("正在删除账号...")
        self.task_runner.submit(
            lambda: self.backend_client.delete_account(account_id),
            on_success=lambda _result: self.load_accounts(),
            on_error=self.publish_error,
        )

    def _handle_accounts_loaded(self, accounts: list[dict[str, Any]]) -> None:
        self.view_model.set_accounts(accounts)
        self.publish_status(f"已加载 {len(accounts)} 个账号")
        self.refresh_view()

    def _handle_account_updated(self, account: dict[str, Any]) -> None:
        self.view_model.upsert_account(account)
        self.publish_status("账号已更新")
        self.refresh_view()

    def _handle_account_deleted(self, account_id: str) -> None:
        self.view_model.remove_account(account_id)
        self.publish_status("账号已删除")
        self.refresh_view()

    def _handle_purchase_inventory_detail_loaded(
        self,
        detail: dict[str, Any],
        on_loaded: Callable[[dict[str, Any]], None],
    ) -> None:
        self.publish_status("仓库配置已加载")
        on_loaded(detail)

    def _handle_login_proxy_updated(self, account_id: str, account: dict[str, Any]) -> None:
        self.view_model.upsert_account(account)
        self.refresh_view()
        self._start_login(account_id)

    def _submit_login_proxy(
        self,
        *,
        account_id: str,
        proxy_payload: dict[str, Any] | None,
        start_when_unchanged: bool,
    ) -> None:
        if self.backend_client is None or proxy_payload is None:
            return
        account = self._account_for(account_id)
        if account is None:
            return

        next_proxy_mode = proxy_payload.get("proxy_mode") or "direct"
        next_proxy_url = proxy_payload.get("proxy_url")
        current_proxy_mode = account.get("proxy_mode") or "direct"
        current_proxy_url = account.get("proxy_url")
        if current_proxy_mode == next_proxy_mode and current_proxy_url == next_proxy_url:
            if start_when_unchanged:
                self._start_login(account_id)
            return

        self.publish_status("正在更新登录代理...")
        update_payload = {
            "remark_name": account.get("remark_name"),
            "proxy_mode": next_proxy_mode,
            "proxy_url": next_proxy_url,
            "api_key": account.get("api_key"),
        }
        self.task_runner.submit(
            lambda: self.backend_client.update_account(account_id, update_payload),
            on_success=partial(self._handle_login_proxy_updated, account_id),
            on_error=self.publish_error,
        )

    def _start_login(self, account_id: str) -> None:
        if self.backend_client is None:
            return
        self.active_login_account_id = account_id
        self.publish_status("正在发起登录...")
        self.task_runner.submit(
            lambda: self.backend_client.start_login(account_id),
            on_success=partial(self._handle_login_started, account_id),
            on_error=self.publish_error,
        )

    def _account_for(self, account_id: str) -> dict[str, Any] | None:
        account = self.view_model.account_by_id(account_id)
        if account is not None:
            return account
        detail_account = self.view_model.detail_account
        if detail_account is not None and detail_account.get("account_id") == account_id:
            return detail_account
        return None

    def _handle_login_started(self, account_id: str, task_payload: dict[str, Any]) -> None:
        self.active_login_account_id = account_id
        self.active_login_task_id = task_payload["task_id"]
        self.publish_login_task(task_payload)
        self.publish_status("登录任务已启动")
        self.task_runner.stream(
            lambda: self.backend_client.watch_task(task_payload["task_id"]),
            on_item=partial(self._handle_task_snapshot, account_id),
            on_error=self.publish_error,
        )

    def _handle_task_snapshot(self, account_id: str, task_payload: dict[str, Any]) -> None:
        self.active_login_account_id = account_id
        self.active_login_task_id = task_payload["task_id"]
        self.publish_login_task(task_payload)
        self.publish_status(f"登录任务状态: {task_state_label(task_payload.get('state'))}")
        if task_payload["state"] in {"succeeded", "failed", "cancelled"}:
            self.load_accounts()

    def _handle_conflict_resolved(self, task_payload: dict[str, Any]) -> None:
        self.publish_login_task(task_payload)
        self.publish_status(f"冲突处理完成: {task_state_label(task_payload.get('state'))}")
        if task_payload["state"] in {"succeeded", "failed", "cancelled"}:
            self.load_accounts()
