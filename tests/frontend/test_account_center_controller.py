from __future__ import annotations

from app_frontend.app.viewmodels.account_center_vm import AccountCenterViewModel


def _account(
    account_id: str,
    *,
    default_name: str,
    remark_name: str | None = None,
    c5_nick_name: str | None = None,
    proxy_mode: str = "direct",
    proxy_url: str | None = None,
    api_key: str | None = None,
    c5_user_id: str | None = None,
    cookie_raw: str | None = None,
) -> dict:
    return {
        "account_id": account_id,
        "default_name": default_name,
        "remark_name": remark_name,
        "display_name": remark_name or c5_nick_name or default_name,
        "proxy_mode": proxy_mode,
        "proxy_url": proxy_url,
        "api_key": api_key,
        "c5_user_id": c5_user_id,
        "c5_nick_name": c5_nick_name,
        "cookie_raw": cookie_raw,
        "purchase_capability_state": "bound" if cookie_raw else "unbound",
        "purchase_pool_state": "not_connected",
        "last_login_at": None,
        "last_error": None,
        "created_at": "2026-03-16T12:00:00",
        "updated_at": "2026-03-16T12:00:00",
        "disabled": False,
        "new_api_enabled": True,
        "fast_api_enabled": True,
        "token_enabled": True,
    }


class FakeBackendClient:
    def __init__(self) -> None:
        self.accounts = [
            _account(
                "a-1",
                default_name="默认一号",
                remark_name="旧备注",
                proxy_mode="custom",
                proxy_url="http://127.0.0.1:9400",
                api_key="api-old",
                c5_user_id="10001",
                c5_nick_name="旧平台号",
                cookie_raw="NC5_accessToken=old-token",
            )
        ]
        self.created_payloads: list[dict] = []
        self.updated_payloads: list[tuple[str, dict]] = []
        self.deleted_account_ids: list[str] = []
        self.cleared_account_ids: list[str] = []
        self.started_login_account_ids: list[str] = []
        self.resolved_actions: list[tuple[str, str, str]] = []
        self.updated_query_mode_payloads: list[tuple[str, dict]] = []

    async def list_accounts(self) -> list[dict]:
        return [dict(account) for account in self.accounts]

    async def create_account(self, payload: dict) -> dict:
        self.created_payloads.append(dict(payload))
        created = _account(
            f"a-{len(self.accounts) + 1}",
            default_name=f"默认{len(self.accounts) + 1}",
            remark_name=payload.get("remark_name"),
            proxy_mode=payload.get("proxy_mode", "direct"),
            proxy_url=payload.get("proxy_url"),
            api_key=payload.get("api_key"),
        )
        self.accounts.append(created)
        return dict(created)

    async def update_account(self, account_id: str, payload: dict) -> dict:
        self.updated_payloads.append((account_id, dict(payload)))
        for account in self.accounts:
            if account["account_id"] == account_id:
                account.update(payload)
                account["display_name"] = account.get("remark_name") or account.get("c5_nick_name") or account["default_name"]
                return dict(account)
        raise KeyError(account_id)

    async def delete_account(self, account_id: str) -> None:
        self.deleted_account_ids.append(account_id)
        self.accounts = [account for account in self.accounts if account["account_id"] != account_id]

    async def update_account_query_modes(self, account_id: str, payload: dict) -> dict:
        self.updated_query_mode_payloads.append((account_id, dict(payload)))
        for account in self.accounts:
            if account["account_id"] == account_id:
                account.update(payload)
                return dict(account)
        raise KeyError(account_id)

    async def clear_purchase_capability(self, account_id: str) -> dict:
        self.cleared_account_ids.append(account_id)
        for account in self.accounts:
            if account["account_id"] == account_id:
                account["c5_user_id"] = None
                account["c5_nick_name"] = None
                account["cookie_raw"] = None
                account["purchase_capability_state"] = "unbound"
                return dict(account)
        raise KeyError(account_id)

    async def start_login(self, account_id: str) -> dict:
        self.started_login_account_ids.append(account_id)
        return {
            "task_id": "task-1",
            "task_type": "login",
            "state": "pending",
            "created_at": "2026-03-16T12:00:00",
            "updated_at": "2026-03-16T12:00:00",
            "events": [{"state": "pending", "timestamp": "2026-03-16T12:00:00", "message": None, "payload": None}],
            "result": None,
            "error": None,
            "pending_conflict": None,
        }

    async def watch_task(self, task_id: str):
        yield {
            "task_id": task_id,
            "task_type": "login",
            "state": "conflict",
            "created_at": "2026-03-16T12:00:00",
            "updated_at": "2026-03-16T12:00:00",
            "events": [
                {"state": "pending", "timestamp": "2026-03-16T12:00:00", "message": None, "payload": None},
                {"state": "starting_browser", "timestamp": "2026-03-16T12:00:00", "message": None, "payload": None},
                {"state": "waiting_for_scan", "timestamp": "2026-03-16T12:00:00", "message": None, "payload": None},
                {"state": "conflict", "timestamp": "2026-03-16T12:00:00", "message": None, "payload": None},
            ],
            "result": None,
            "error": None,
            "pending_conflict": {
                "account_id": "a-1",
                "captured_login": {
                    "c5_user_id": "20002",
                    "c5_nick_name": "新登录号",
                    "cookie_raw": "new=cookie",
                },
            },
        }

    async def resolve_login_conflict(self, account_id: str, *, task_id: str, action: str) -> dict:
        self.resolved_actions.append((account_id, task_id, action))
        self.accounts = [
            _account(
                "a-9",
                default_name="默认九号",
                c5_user_id="20002",
                c5_nick_name="新登录号",
                cookie_raw="NC5_accessToken=new-token",
            )
        ]
        return {
            "task_id": task_id,
            "task_type": "login",
            "state": "succeeded",
            "created_at": "2026-03-16T12:00:00",
            "updated_at": "2026-03-16T12:00:00",
            "events": [
                {"state": "pending", "timestamp": "2026-03-16T12:00:00", "message": None, "payload": None},
                {"state": "conflict", "timestamp": "2026-03-16T12:00:00", "message": None, "payload": None},
                {"state": "saving_account", "timestamp": "2026-03-16T12:00:00", "message": None, "payload": None},
                {"state": "succeeded", "timestamp": "2026-03-16T12:00:00", "message": None, "payload": None},
            ],
            "result": {"account_id": "a-9", "action": action},
            "error": None,
            "pending_conflict": None,
        }


class InlineTaskRunner:
    def submit(self, coroutine_factory, *, on_success=None, on_error=None) -> None:
        import asyncio

        try:
            result = asyncio.run(coroutine_factory())
        except Exception as exc:  # pragma: no cover - defensive
            if on_error is not None:
                on_error(str(exc))
            return
        if on_success is not None:
            on_success(result)

    def stream(self, stream_factory, *, on_item=None, on_done=None, on_error=None) -> None:
        import asyncio

        async def consume() -> None:
            async for item in stream_factory():
                if on_item is not None:
                    on_item(item)

        try:
            asyncio.run(consume())
        except Exception as exc:  # pragma: no cover - defensive
            if on_error is not None:
                on_error(str(exc))
            return
        if on_done is not None:
            on_done()


def _build_controller():
    from app_frontend.app.controllers.account_center_controller import AccountCenterController

    view_model = AccountCenterViewModel()
    backend_client = FakeBackendClient()
    statuses: list[str] = []
    published_tasks: list[dict] = []
    errors: list[str] = []
    refresh_counter = {"count": 0}

    controller = AccountCenterController(
        view_model=view_model,
        backend_client=backend_client,
        task_runner=InlineTaskRunner(),
        publish_status=statuses.append,
        refresh_view=lambda: refresh_counter.__setitem__("count", refresh_counter["count"] + 1),
        publish_login_task=published_tasks.append,
        publish_error=errors.append,
    )
    return controller, view_model, backend_client, statuses, published_tasks, errors, refresh_counter


def test_controller_create_and_edit_refreshes_accounts():
    controller, view_model, backend_client, statuses, _tasks, errors, refresh_counter = _build_controller()

    controller.load_accounts()
    view_model.select_account("a-1")
    view_model.open_selected_account_detail()

    controller.create_account(
        {
            "remark_name": "新建备注",
            "proxy_mode": "direct",
            "proxy_url": None,
            "api_key": "api-new",
        }
    )
    controller.edit_detail_account(
        {
            "remark_name": "改后备注",
            "proxy_mode": "custom",
            "proxy_url": "http://127.0.0.1:9500",
            "api_key": "api-edited",
        },
        {
            "new_api_enabled": False,
            "fast_api_enabled": True,
            "token_enabled": False,
        },
    )

    assert backend_client.created_payloads == [
        {
            "remark_name": "新建备注",
            "proxy_mode": "direct",
            "proxy_url": None,
            "api_key": "api-new",
        }
    ]
    assert backend_client.updated_payloads == [
        (
            "a-1",
            {
                "remark_name": "改后备注",
                "proxy_mode": "custom",
                "proxy_url": "http://127.0.0.1:9500",
                "api_key": "api-edited",
            },
        )
    ]
    assert backend_client.updated_query_mode_payloads == [
        (
            "a-1",
            {
                "new_api_enabled": False,
                "fast_api_enabled": True,
                "token_enabled": False,
            },
        )
    ]
    assert view_model.detail_account["remark_name"] == "改后备注"
    assert view_model.detail_account["new_api_enabled"] is False
    assert view_model.detail_account["fast_api_enabled"] is True
    assert view_model.detail_account["token_enabled"] is False
    assert refresh_counter["count"] >= 3
    assert errors == []
    assert statuses[-1] == "账号已更新"


def test_controller_login_conflict_resolution_refreshes_accounts():
    controller, view_model, backend_client, statuses, published_tasks, errors, refresh_counter = _build_controller()

    controller.load_accounts()
    view_model.select_account("a-1")
    view_model.open_selected_account_detail()

    controller.start_login_for_detail()

    assert backend_client.started_login_account_ids == ["a-1"]
    assert published_tasks[-1]["state"] == "conflict"
    assert "登录任务状态: 检测到账号冲突" in statuses

    controller.resolve_login_conflict("replace_with_new_account")

    assert backend_client.resolved_actions == [("a-1", "task-1", "replace_with_new_account")]
    assert view_model.table_rows[0]["display_name"] == "新登录号"
    assert refresh_counter["count"] >= 2
    assert errors == []
    assert "冲突处理完成: 登录完成" in statuses
    assert statuses[-1] == "已加载 1 个账号"


def test_controller_clear_and_delete_risk_actions_update_state():
    controller, view_model, backend_client, statuses, _tasks, errors, refresh_counter = _build_controller()

    controller.load_accounts()
    view_model.select_account("a-1")
    view_model.open_selected_account_detail()

    controller.clear_purchase_capability_for_detail()
    assert backend_client.cleared_account_ids == ["a-1"]
    assert view_model.detail_account["purchase_capability_state"] == "unbound"

    controller.delete_detail_account()
    assert backend_client.deleted_account_ids == ["a-1"]
    assert view_model.table_rows == []
    assert refresh_counter["count"] >= 2
    assert errors == []
    assert statuses[-1] == "账号已删除"
