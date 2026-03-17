from __future__ import annotations


def test_window_status_label_applies_semantic_tones(qtbot, monkeypatch):
    from app_frontend.app.viewmodels.account_center_vm import AccountCenterViewModel
    from app_frontend.app.windows.account_center_window import AccountCenterWindow

    warning_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "app_frontend.app.windows.account_center_window.QMessageBox.warning",
        lambda _parent, title, message: warning_calls.append((title, message)),
    )

    window = AccountCenterWindow(view_model=AccountCenterViewModel())
    qtbot.addWidget(window)

    assert window.status_label.property("tone") == "neutral"

    window._publish_status("已加载 1 个账号")
    assert window.status_label.text() == "已加载 1 个账号"
    assert window.status_label.property("tone") == "ok"

    window._publish_status("登录任务状态: 检测到账号冲突")
    assert window.status_label.property("tone") == "warn"

    window._publish_status("冲突处理完成: 登录完成")
    assert window.status_label.property("tone") == "ok"

    window._publish_status("已取消删除账号")
    assert window.status_label.property("tone") == "warn"

    window._handle_error("代理连接失败")
    assert window.status_label.text() == "操作失败: 代理连接失败"
    assert window.status_label.property("tone") == "error"
    assert warning_calls == [("操作失败", "代理连接失败")]
