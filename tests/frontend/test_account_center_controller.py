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
        "purchase_disabled": False,
        "new_api_enabled": True,
        "fast_api_enabled": True,
        "token_enabled": True,
    }


def _account_center_row(
    account_id: str,
    *,
    display_name: str,
    purchase_status_code: str = "selected_warehouse",
    purchase_status_text: str = "steam-1",
    api_key_present: bool = False,
    proxy_display: str = "直连",
) -> dict:
    return {
        "account_id": account_id,
        "display_name": display_name,
        "remark_name": display_name,
        "c5_nick_name": None,
        "default_name": f"默认-{account_id}",
        "api_key_present": api_key_present,
        "api_key": "api-key" if api_key_present else None,
        "proxy_mode": "direct",
        "proxy_url": None if proxy_display == "直连" else proxy_display,
        "proxy_display": proxy_display,
        "purchase_capability_state": "bound",
        "purchase_pool_state": "not_connected",
        "purchase_disabled": purchase_status_code == "disabled",
        "selected_steam_id": purchase_status_text if purchase_status_code == "selected_warehouse" else None,
        "selected_warehouse_text": purchase_status_text if purchase_status_code == "selected_warehouse" else None,
        "purchase_status_code": purchase_status_code,
        "purchase_status_text": purchase_status_text,
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
        self.account_center_rows = self._build_account_center_rows()
        self.created_payloads: list[dict] = []
        self.updated_payloads: list[tuple[str, dict]] = []
        self.deleted_account_ids: list[str] = []
        self.cleared_account_ids: list[str] = []
        self.started_login_account_ids: list[str] = []
        self.resolved_actions: list[tuple[str, str, str]] = []
        self.updated_query_mode_payloads: list[tuple[str, dict]] = []
        self.call_log: list[str] = []

    async def list_accounts(self) -> list[dict]:
        self.call_log.append("list_accounts")
        return [dict(account) for account in self.accounts]

    async def list_account_center_accounts(self) -> list[dict]:
        self.call_log.append("list_account_center_accounts")
        self.account_center_rows = self._build_account_center_rows()
        return [dict(row) for row in self.account_center_rows]

    async def create_account(self, payload: dict) -> dict:
        self.call_log.append("create_account")
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
        self.account_center_rows = self._build_account_center_rows()
        return dict(created)

    async def update_account(self, account_id: str, payload: dict) -> dict:
        self.call_log.append("update_account")
        self.updated_payloads.append((account_id, dict(payload)))
        for account in self.accounts:
            if account["account_id"] == account_id:
                account.update(payload)
                account["display_name"] = account.get("remark_name") or account.get("c5_nick_name") or account["default_name"]
                self.account_center_rows = self._build_account_center_rows()
                return dict(account)
        raise KeyError(account_id)

    async def delete_account(self, account_id: str) -> None:
        self.call_log.append("delete_account")
        self.deleted_account_ids.append(account_id)
        self.accounts = [account for account in self.accounts if account["account_id"] != account_id]
        self.account_center_rows = self._build_account_center_rows()

    async def update_account_query_modes(self, account_id: str, payload: dict) -> dict:
        self.call_log.append("update_account_query_modes")
        self.updated_query_mode_payloads.append((account_id, dict(payload)))
        for account in self.accounts:
            if account["account_id"] == account_id:
                account.update(payload)
                self.account_center_rows = self._build_account_center_rows()
                return dict(account)
        raise KeyError(account_id)

    async def update_account_purchase_config(self, account_id: str, payload: dict) -> dict:
        self.call_log.append("update_account_purchase_config")
        for account in self.accounts:
            if account["account_id"] != account_id:
                continue
            account["purchase_disabled"] = bool(
                payload.get("purchase_disabled", account.get("purchase_disabled", False))
            )
            if payload.get("selected_steam_id") is not None:
                account["selected_steam_id"] = payload.get("selected_steam_id")
        for row in self.account_center_rows:
            if row["account_id"] != account_id:
                continue
            row["purchase_disabled"] = bool(
                payload.get("purchase_disabled", row.get("purchase_disabled", False))
            )
            if payload.get("selected_steam_id") is not None:
                row["selected_steam_id"] = payload.get("selected_steam_id")
                row["selected_warehouse_text"] = payload.get("selected_steam_id")
            if row["purchase_status_code"] != "not_logged_in":
                if row["purchase_disabled"]:
                    row["purchase_status_code"] = "disabled"
                    row["purchase_status_text"] = "禁用"
                else:
                    row["purchase_status_code"] = "selected_warehouse"
                    row["purchase_status_text"] = str(row.get("selected_warehouse_text") or "steam-1")
            return dict(row)
        raise KeyError(account_id)

    async def get_purchase_runtime_inventory_detail(self, account_id: str) -> dict:
        self.call_log.append("get_purchase_runtime_inventory_detail")
        for row in self.account_center_rows:
            if row["account_id"] != account_id:
                continue
            selected_steam_id = row.get("selected_steam_id") or "steam-1"
            return {
                "account_id": account_id,
                "display_name": row.get("display_name") or row.get("remark_name") or account_id,
                "selected_steam_id": selected_steam_id,
                "refreshed_at": "2026-03-18T10:00:00",
                "last_error": None,
                "inventories": [
                    {
                        "steamId": selected_steam_id,
                        "inventory_num": 900,
                        "inventory_max": 1000,
                        "remaining_capacity": 100,
                        "is_selected": True,
                        "is_available": True,
                    },
                    {
                        "steamId": "steam-full",
                        "inventory_num": 1000,
                        "inventory_max": 1000,
                        "remaining_capacity": 0,
                        "is_selected": False,
                        "is_available": False,
                    },
                ],
            }
        raise KeyError(account_id)

    async def clear_purchase_capability(self, account_id: str) -> dict:
        self.call_log.append("clear_purchase_capability")
        self.cleared_account_ids.append(account_id)
        for account in self.accounts:
            if account["account_id"] == account_id:
                account["c5_user_id"] = None
                account["c5_nick_name"] = None
                account["cookie_raw"] = None
                account["purchase_capability_state"] = "unbound"
                self.account_center_rows = self._build_account_center_rows()
                return dict(account)
        raise KeyError(account_id)

    async def start_login(self, account_id: str) -> dict:
        self.call_log.append("start_login")
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
        self.call_log.append("watch_task")
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
        self.call_log.append("resolve_login_conflict")
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
        self.account_center_rows = self._build_account_center_rows()
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

    def _build_account_center_rows(self) -> list[dict]:
        rows: list[dict] = []
        for account in self.accounts:
            purchase_status_code = "selected_warehouse" if account.get("cookie_raw") else "not_logged_in"
            if account.get("purchase_disabled"):
                purchase_status_code = "disabled"
            selected_steam_id = str(account.get("selected_steam_id") or "steam-1")
            purchase_status_text = selected_steam_id if purchase_status_code == "selected_warehouse" else "未登录"
            if purchase_status_code == "disabled":
                purchase_status_text = "禁用"
            rows.append(
                _account_center_row(
                    str(account.get("account_id") or ""),
                    display_name=str(account.get("display_name") or account.get("default_name") or ""),
                    purchase_status_code=purchase_status_code,
                    purchase_status_text=purchase_status_text,
                    api_key_present=bool(account.get("api_key")),
                    proxy_display=str(account.get("proxy_url") or "直连"),
                )
                | {
                    "remark_name": account.get("remark_name"),
                    "c5_nick_name": account.get("c5_nick_name"),
                    "proxy_mode": account.get("proxy_mode") or "direct",
                    "proxy_url": account.get("proxy_url"),
                    "api_key": account.get("api_key"),
                    "selected_steam_id": None if purchase_status_code == "not_logged_in" else selected_steam_id,
                    "selected_warehouse_text": None if purchase_status_code == "not_logged_in" else selected_steam_id,
                    "purchase_disabled": bool(account.get("purchase_disabled", False)),
                }
            )
        return rows


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


def test_controller_updates_proxy_before_starting_login():
    controller, view_model, backend_client, statuses, published_tasks, errors, refresh_counter = _build_controller()

    controller.load_accounts()
    view_model.select_account("a-1")
    view_model.open_selected_account_detail()

    controller.submit_login_proxy_for_detail(
        {
            "proxy_mode": "custom",
            "proxy_url": "http://127.0.0.1:9500",
        }
    )

    assert backend_client.updated_payloads == [
        (
            "a-1",
            {
                "remark_name": "旧备注",
                "proxy_mode": "custom",
                "proxy_url": "http://127.0.0.1:9500",
                "api_key": "api-old",
            },
        )
    ]
    assert backend_client.started_login_account_ids == ["a-1"]
    assert backend_client.call_log.index("update_account") < backend_client.call_log.index("start_login")
    assert view_model.detail_account["proxy_url"] == "http://127.0.0.1:9500"
    assert published_tasks[-1]["state"] == "conflict"
    assert refresh_counter["count"] >= 2
    assert errors == []
    assert "正在发起登录..." in statuses


def test_controller_starts_login_directly_when_proxy_is_unchanged():
    controller, view_model, backend_client, statuses, published_tasks, errors, _refresh_counter = _build_controller()

    controller.load_accounts()
    view_model.select_account("a-1")
    view_model.open_selected_account_detail()

    controller.submit_login_proxy_for_detail(
        {
            "proxy_mode": "custom",
            "proxy_url": "http://127.0.0.1:9400",
        }
    )

    assert backend_client.updated_payloads == []
    assert backend_client.started_login_account_ids == ["a-1"]
    assert published_tasks[-1]["state"] == "conflict"
    assert errors == []
    assert "正在发起登录..." in statuses


def test_controller_does_nothing_when_login_proxy_submission_is_cancelled():
    controller, view_model, backend_client, statuses, _published_tasks, errors, _refresh_counter = _build_controller()

    controller.load_accounts()
    view_model.select_account("a-1")
    view_model.open_selected_account_detail()
    statuses_before = list(statuses)

    controller.submit_login_proxy_for_detail(None)

    assert backend_client.updated_payloads == []
    assert backend_client.started_login_account_ids == []
    assert statuses == statuses_before
    assert errors == []


def test_controller_loads_account_center_rows_from_new_endpoint():
    controller, view_model, backend_client, statuses, _tasks, errors, refresh_counter = _build_controller()

    controller.load_accounts()

    assert backend_client.call_log[0] == "list_account_center_accounts"
    assert view_model.table_rows[0]["c5_nickname"] == "旧备注"
    assert view_model.table_rows[0]["purchase_status"] == "steam-1"
    assert refresh_counter["count"] == 1
    assert errors == []
    assert statuses[-1] == "已加载 1 个账号"


def test_controller_updates_api_key_without_starting_login():
    controller, view_model, backend_client, statuses, _tasks, errors, refresh_counter = _build_controller()

    controller.load_accounts()
    view_model.select_account("a-1")

    controller.edit_account_api_key("a-1", {"api_key": "api-new"})

    assert backend_client.updated_payloads[-1] == (
        "a-1",
        {
            "remark_name": "旧备注",
            "proxy_mode": "custom",
            "proxy_url": "http://127.0.0.1:9400",
            "api_key": "api-new",
        },
    )
    assert backend_client.started_login_account_ids == []
    assert refresh_counter["count"] >= 2
    assert errors == []
    assert statuses[-1] == "已加载 1 个账号"


def test_controller_updates_purchase_config_and_refreshes_rows():
    controller, view_model, backend_client, statuses, _tasks, errors, refresh_counter = _build_controller()

    controller.load_accounts()
    view_model.select_account("a-1")

    controller.update_account_purchase_config(
        "a-1",
        {
            "purchase_disabled": True,
            "selected_steam_id": "steam-2",
        },
    )

    assert backend_client.call_log[-1] == "list_account_center_accounts"
    assert view_model.table_rows[0]["purchase_status"] == "禁用"
    assert refresh_counter["count"] >= 2
    assert errors == []
    assert statuses[-1] == "已加载 1 个账号"


def test_controller_loads_purchase_inventory_detail_before_opening_config():
    controller, view_model, backend_client, statuses, _tasks, errors, refresh_counter = _build_controller()
    loaded_details: list[dict] = []

    controller.load_accounts()
    view_model.select_account("a-1")
    controller.load_purchase_inventory_detail("a-1", loaded_details.append)

    assert backend_client.call_log[-1] == "get_purchase_runtime_inventory_detail"
    assert loaded_details == [
        {
            "account_id": "a-1",
            "display_name": "旧备注",
            "selected_steam_id": "steam-1",
            "refreshed_at": "2026-03-18T10:00:00",
            "last_error": None,
            "inventories": [
                {
                    "steamId": "steam-1",
                    "inventory_num": 900,
                    "inventory_max": 1000,
                    "remaining_capacity": 100,
                    "is_selected": True,
                    "is_available": True,
                },
                {
                    "steamId": "steam-full",
                    "inventory_num": 1000,
                    "inventory_max": 1000,
                    "remaining_capacity": 0,
                    "is_selected": False,
                    "is_available": False,
                },
            ],
        }
    ]
    assert refresh_counter["count"] == 1
    assert errors == []
    assert "正在加载仓库配置..." in statuses


def test_controller_deletes_account_by_row_id():
    controller, view_model, backend_client, statuses, _tasks, errors, refresh_counter = _build_controller()

    controller.load_accounts()

    controller.delete_account("a-1")

    assert backend_client.deleted_account_ids == ["a-1"]
    assert refresh_counter["count"] >= 2
    assert errors == []
    assert statuses[-1] == "已加载 0 个账号"
