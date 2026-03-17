from __future__ import annotations

from collections.abc import Callable

from app_frontend.app.formatters.task_display import (
    task_event_label,
    task_meta_time_label,
    task_state_label,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
)


class LoginTaskDialog(QDialog):
    def __init__(self, *, on_resolve_conflict: Callable[[str], None] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("登录任务")
        self._on_resolve_conflict = on_resolve_conflict
        self._task_payload: dict | None = None

        self.status_label = QLabel("等待任务开始")
        self.state_list = QListWidget()
        self.copy_task_log_button = QPushButton("复制任务日志")
        self.meta_label = QLabel("")
        self.meta_label.setWordWrap(True)
        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.copy_error_button = QPushButton("复制错误")
        self.conflict_detail_label = QLabel("")
        self.conflict_detail_label.setWordWrap(True)

        self.meta_group = QGroupBox("任务摘要")
        meta_layout = QVBoxLayout(self.meta_group)
        meta_layout.addWidget(self.meta_label)

        self.result_group = QGroupBox("任务结果")
        result_layout = QVBoxLayout(self.result_group)
        result_layout.addWidget(self.result_label)

        self.error_group = QGroupBox("错误信息")
        error_layout = QVBoxLayout(self.error_group)
        error_layout.addWidget(self.error_label)
        error_layout.addWidget(self.copy_error_button)

        self.conflict_group = QGroupBox("账号冲突处理")
        conflict_layout = QVBoxLayout(self.conflict_group)
        conflict_layout.addWidget(self.conflict_detail_label)
        button_layout = QHBoxLayout()
        self.replace_button = QPushButton("删除当前并新增")
        self.create_new_button = QPushButton("直接新增")
        self.cancel_button = QPushButton("取消")
        button_layout.addWidget(self.replace_button)
        button_layout.addWidget(self.create_new_button)
        button_layout.addWidget(self.cancel_button)
        conflict_layout.addLayout(button_layout)

        layout = QVBoxLayout(self)
        layout.addWidget(self.status_label)
        layout.addWidget(self.meta_group)
        layout.addWidget(self.state_list)
        layout.addWidget(self.copy_task_log_button)
        layout.addWidget(self.result_group)
        layout.addWidget(self.error_group)
        layout.addWidget(self.conflict_group)

        self.replace_button.clicked.connect(lambda: self._emit_resolution("replace_with_new_account"))
        self.create_new_button.clicked.connect(lambda: self._emit_resolution("create_new_account"))
        self.cancel_button.clicked.connect(lambda: self._emit_resolution("cancel"))
        self.copy_task_log_button.clicked.connect(self._copy_task_log)
        self.copy_error_button.clicked.connect(self._copy_error)

        self.result_group.hide()
        self.error_group.hide()
        self.conflict_group.hide()

    def update_task(self, task_payload: dict) -> None:
        self._task_payload = task_payload
        error_text = task_payload.get("error") or ""
        status_text = f"当前状态: {task_state_label(task_payload.get('state'))}"
        if error_text:
            status_text = f"{status_text} - {error_text}"
        self.status_label.setText(status_text)
        self.meta_label.setText(self._build_meta_summary(task_payload))
        self.state_list.clear()
        for event in task_payload.get("events", []):
            self.state_list.addItem(task_event_label(event))
        if self.state_list.count() > 0:
            self.state_list.setCurrentRow(self.state_list.count() - 1)
            self.state_list.scrollToBottom()

        result_text = self._build_result_detail(task_payload.get("result"))
        self.result_label.setText(result_text)
        self.result_group.setVisible(bool(result_text))
        self.error_label.setText(error_text or "暂无错误")
        self.error_group.setVisible(bool(error_text))
        self.copy_error_button.setEnabled(bool(error_text))

        should_show_conflict = task_payload.get("state") == "conflict" and bool(task_payload.get("pending_conflict"))
        self.conflict_group.setVisible(should_show_conflict)
        self.conflict_detail_label.setText(self._build_conflict_detail(task_payload.get("pending_conflict")))

    def _emit_resolution(self, action: str) -> None:
        if self._on_resolve_conflict is None:
            return
        self._on_resolve_conflict(action)

    def _copy_error(self) -> None:
        if self._task_payload is None:
            return
        error_text = self._task_payload.get("error") or ""
        if not error_text:
            return
        QApplication.clipboard().setText(error_text)

    def _copy_task_log(self) -> None:
        if self._task_payload is None:
            return
        QApplication.clipboard().setText(self._build_task_log(self._task_payload))

    @staticmethod
    def _build_conflict_detail(pending_conflict: dict | None) -> str:
        if not pending_conflict:
            return ""

        existing_user_id = pending_conflict.get("existing_c5_user_id") or "未绑定"
        existing_nick_name = pending_conflict.get("existing_c5_nick_name") or "未知账号"
        captured_login = pending_conflict.get("captured_login", {})
        captured_user_id = captured_login.get("c5_user_id") or "未知"
        captured_nick_name = captured_login.get("c5_nick_name") or "未知账号"
        return (
            f"当前账号已绑定: {existing_nick_name} ({existing_user_id})\n"
            f"本次扫码得到: {captured_nick_name} ({captured_user_id})"
        )

    @staticmethod
    def _build_task_log(task_payload: dict) -> str:
        lines = [
            f"任务ID: {task_payload.get('task_id') or ''}",
            f"任务类型: {task_payload.get('task_type') or ''}",
            f"创建时间: {task_meta_time_label(task_payload.get('created_at'))}",
            f"更新时间: {task_meta_time_label(task_payload.get('updated_at'))}",
            f"当前状态: {task_state_label(task_payload.get('state'))}",
        ]
        error_text = task_payload.get("error") or ""
        if error_text:
            lines.append(f"错误: {error_text}")
        result_text = LoginTaskDialog._build_result_detail(task_payload.get("result"))
        if result_text:
            lines.append("结果:")
            lines.extend(result_text.splitlines())
        pending_conflict = task_payload.get("pending_conflict")
        if pending_conflict:
            lines.append("冲突详情:")
            lines.extend(cls_line for cls_line in LoginTaskDialog._build_conflict_detail(pending_conflict).splitlines())
        lines.append("事件:")
        for event in task_payload.get("events", []):
            lines.append(task_event_label(event))
        return "\n".join(lines)

    @staticmethod
    def _build_meta_summary(task_payload: dict) -> str:
        return "\n".join(
            [
                f"任务ID: {task_payload.get('task_id') or ''}",
                f"任务类型: {task_payload.get('task_type') or ''}",
                f"创建时间: {task_meta_time_label(task_payload.get('created_at'))}",
                f"更新时间: {task_meta_time_label(task_payload.get('updated_at'))}",
            ]
        )

    @staticmethod
    def _build_result_detail(result) -> str:
        if not result:
            return ""
        if isinstance(result, dict):
            return "\n".join(f"{key}: {value}" for key, value in result.items())
        return str(result)
