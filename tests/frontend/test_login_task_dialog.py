from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication


def _task_payload(state: str, events: list[str], *, pending_conflict: dict | None = None) -> dict:
    return {
        "task_id": "task-1",
        "task_type": "login",
        "state": state,
        "created_at": "2026-03-16T12:00:00",
        "updated_at": "2026-03-16T12:00:00",
        "events": [
            {
                "state": event_state,
                "timestamp": "2026-03-16T12:00:00",
                "message": None,
                "payload": None,
            }
            for event_state in events
        ],
        "result": None,
        "error": None,
        "pending_conflict": pending_conflict,
    }


def test_login_task_dialog_shows_localized_progress_states(qtbot):
    from app_frontend.app.dialogs.login_task_dialog import LoginTaskDialog

    dialog = LoginTaskDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.update_task(
        _task_payload(
            "succeeded",
            [
                "pending",
                "starting_browser",
                "waiting_for_scan",
                "captured_login_info",
                "waiting_for_browser_close",
                "saving_account",
                "succeeded",
            ],
        )
    )

    assert dialog.status_label.text() == "当前状态: 登录完成"
    assert dialog.meta_label.text() == (
        "任务ID: task-1\n"
        "任务类型: login\n"
        "创建时间: 2026-03-16 12:00:00\n"
        "更新时间: 2026-03-16 12:00:00"
    )
    rendered_states = [dialog.state_list.item(index).text() for index in range(dialog.state_list.count())]
    assert rendered_states == [
        "12:00:00 · 等待任务开始",
        "12:00:00 · 正在启动浏览器",
        "12:00:00 · 等待扫码",
        "12:00:00 · 已捕获登录信息",
        "12:00:00 · 等待用户关闭浏览器",
        "12:00:00 · 正在保存账号",
        "12:00:00 · 登录完成",
    ]
    assert dialog.state_list.currentRow() == dialog.state_list.count() - 1
    assert dialog.result_group.isHidden()


def test_login_task_dialog_shows_failed_error_message(qtbot):
    from app_frontend.app.dialogs.login_task_dialog import LoginTaskDialog

    dialog = LoginTaskDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    payload = _task_payload("failed", ["pending", "starting_browser", "failed"])
    payload["error"] = "代理连接失败"

    dialog.update_task(payload)

    assert dialog.status_label.text() == "当前状态: 登录失败 - 代理连接失败"
    assert dialog.copy_error_button.isVisible()
    assert dialog.copy_error_button.isEnabled()
    assert dialog.result_group.isHidden()


def test_login_task_dialog_copies_error_to_clipboard(qtbot):
    from app_frontend.app.dialogs.login_task_dialog import LoginTaskDialog

    dialog = LoginTaskDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    payload = _task_payload("failed", ["failed"])
    payload["error"] = "浏览器启动失败"
    QApplication.clipboard().clear()

    dialog.update_task(payload)
    qtbot.mouseClick(dialog.copy_error_button, Qt.LeftButton)

    assert QApplication.clipboard().text() == "浏览器启动失败"


def test_login_task_dialog_copies_full_task_log(qtbot):
    from app_frontend.app.dialogs.login_task_dialog import LoginTaskDialog

    dialog = LoginTaskDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    payload = _task_payload("failed", ["pending", "starting_browser", "failed"])
    payload["error"] = "浏览器启动失败"
    payload["events"][1]["message"] = "代理插件加载成功"
    QApplication.clipboard().clear()

    dialog.update_task(payload)
    qtbot.mouseClick(dialog.copy_task_log_button, Qt.LeftButton)

    assert QApplication.clipboard().text() == (
        "任务ID: task-1\n"
        "任务类型: login\n"
        "创建时间: 2026-03-16 12:00:00\n"
        "更新时间: 2026-03-16 12:00:00\n"
        "当前状态: 登录失败\n"
        "错误: 浏览器启动失败\n"
        "事件:\n"
        "12:00:00 · 等待任务开始\n"
        "12:00:00 · 正在启动浏览器 - 代理插件加载成功\n"
        "12:00:00 · 登录失败"
    )


def test_login_task_dialog_copies_conflict_and_result_details_into_task_log(qtbot):
    from app_frontend.app.dialogs.login_task_dialog import LoginTaskDialog

    dialog = LoginTaskDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    payload = _task_payload(
        "succeeded",
        ["pending", "conflict", "saving_account", "succeeded"],
        pending_conflict={
            "account_id": "a-1",
            "existing_c5_user_id": "10001",
            "existing_c5_nick_name": "旧绑定账号",
            "captured_login": {
                "c5_user_id": "20002",
                "c5_nick_name": "新扫码账号",
                "cookie_raw": "foo=bar",
            },
        },
    )
    payload["result"] = {
        "account_id": "a-9",
        "action": "replace_with_new_account",
    }
    QApplication.clipboard().clear()

    dialog.update_task(payload)
    qtbot.mouseClick(dialog.copy_task_log_button, Qt.LeftButton)

    assert QApplication.clipboard().text() == (
        "任务ID: task-1\n"
        "任务类型: login\n"
        "创建时间: 2026-03-16 12:00:00\n"
        "更新时间: 2026-03-16 12:00:00\n"
        "当前状态: 登录完成\n"
        "结果:\n"
        "account_id: a-9\n"
        "action: replace_with_new_account\n"
        "冲突详情:\n"
        "当前账号已绑定: 旧绑定账号 (10001)\n"
        "本次扫码得到: 新扫码账号 (20002)\n"
        "事件:\n"
        "12:00:00 · 等待任务开始\n"
        "12:00:00 · 检测到账号冲突\n"
        "12:00:00 · 正在保存账号\n"
        "12:00:00 · 登录完成"
    )


def test_login_task_dialog_shows_result_summary_in_dialog(qtbot):
    from app_frontend.app.dialogs.login_task_dialog import LoginTaskDialog

    dialog = LoginTaskDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    payload = _task_payload("succeeded", ["saving_account", "succeeded"])
    payload["result"] = {
        "account_id": "a-9",
        "action": "replace_with_new_account",
    }

    dialog.update_task(payload)

    assert dialog.result_group.isVisible()
    assert dialog.result_label.text() == "account_id: a-9\naction: replace_with_new_account"


def test_login_task_dialog_renders_event_message_after_state(qtbot):
    from app_frontend.app.dialogs.login_task_dialog import LoginTaskDialog

    dialog = LoginTaskDialog()
    qtbot.addWidget(dialog)
    payload = _task_payload("waiting_for_scan", ["waiting_for_scan"])
    payload["events"][0]["timestamp"] = "2026-03-16T12:34:56"
    payload["events"][0]["message"] = "请在浏览器中完成扫码"

    dialog.update_task(payload)

    assert dialog.state_list.item(0).text() == "12:34:56 · 等待扫码 - 请在浏览器中完成扫码"


def test_login_task_dialog_copies_event_payload_into_task_log(qtbot):
    from app_frontend.app.dialogs.login_task_dialog import LoginTaskDialog

    dialog = LoginTaskDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    payload = _task_payload("waiting_for_scan", ["waiting_for_scan"])
    payload["events"][0]["payload"] = {
        "attempt": 1,
        "phase": "browser",
    }
    QApplication.clipboard().clear()

    dialog.update_task(payload)
    qtbot.mouseClick(dialog.copy_task_log_button, Qt.LeftButton)

    assert QApplication.clipboard().text() == (
        "任务ID: task-1\n"
        "任务类型: login\n"
        "创建时间: 2026-03-16 12:00:00\n"
        "更新时间: 2026-03-16 12:00:00\n"
        "当前状态: 等待扫码\n"
        "事件:\n"
        "12:00:00 · 等待扫码 [payload: {\"attempt\": 1, \"phase\": \"browser\"}]"
    )


def test_login_task_dialog_conflict_prompt_offers_required_actions(qtbot):
    from app_frontend.app.dialogs.login_task_dialog import LoginTaskDialog

    triggered_actions: list[str] = []
    dialog = LoginTaskDialog(on_resolve_conflict=triggered_actions.append)
    qtbot.addWidget(dialog)
    dialog.update_task(
        _task_payload(
            "conflict",
            ["pending", "starting_browser", "waiting_for_scan", "conflict"],
            pending_conflict={
                "account_id": "a-1",
                "captured_login": {
                    "c5_user_id": "20002",
                    "c5_nick_name": "冲突账号",
                    "cookie_raw": "foo=bar",
                },
            },
        )
    )

    assert dialog.replace_button.text() == "删除当前并新增"
    assert dialog.create_new_button.text() == "直接新增"
    assert dialog.cancel_button.text() == "取消"

    qtbot.mouseClick(dialog.replace_button, Qt.LeftButton)

    assert triggered_actions == ["replace_with_new_account"]


def test_login_task_dialog_renders_conflict_account_difference(qtbot):
    from app_frontend.app.dialogs.login_task_dialog import LoginTaskDialog

    dialog = LoginTaskDialog()
    qtbot.addWidget(dialog)
    dialog.update_task(
        _task_payload(
            "conflict",
            ["pending", "starting_browser", "waiting_for_scan", "conflict"],
            pending_conflict={
                "account_id": "a-1",
                "existing_c5_user_id": "10001",
                "existing_c5_nick_name": "旧绑定账号",
                "captured_login": {
                    "c5_user_id": "20002",
                    "c5_nick_name": "新扫码账号",
                    "cookie_raw": "foo=bar",
                },
            },
        )
    )

    rendered = dialog.conflict_detail_label.text()

    assert "10001" in rendered
    assert "旧绑定账号" in rendered
    assert "20002" in rendered
    assert "新扫码账号" in rendered
