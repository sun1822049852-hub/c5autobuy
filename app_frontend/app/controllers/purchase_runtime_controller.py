from __future__ import annotations

from typing import Callable


class PurchaseRuntimeController:
    def __init__(
        self,
        *,
        view_model,
        backend_client,
        task_runner,
        publish_status: Callable[[str], None],
        refresh_view: Callable[[], None],
        publish_error: Callable[[str], None],
    ) -> None:
        self.view_model = view_model
        self.backend_client = backend_client
        self.task_runner = task_runner
        self.publish_status = publish_status
        self.refresh_view = refresh_view
        self.publish_error = publish_error

    def load_status(
        self,
        *,
        silent: bool = True,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        if self.backend_client is None:
            if on_complete is not None:
                on_complete()
            return
        if not silent:
            self.publish_status("正在刷新购买运行状态...")
        self.task_runner.submit(
            lambda: self.backend_client.get_purchase_runtime_status(),
            on_success=lambda status: self._handle_status_loaded(status, success_message="购买运行状态已刷新", on_complete=on_complete),
            on_error=self._build_error_handler(on_complete),
        )

    def start_runtime(self) -> None:
        if self.backend_client is None:
            return
        self.publish_status("正在启动购买运行...")
        self.task_runner.submit(
            lambda: self.backend_client.start_purchase_runtime(),
            on_success=lambda status: self._handle_status_loaded(status, success_message="购买运行中"),
            on_error=self.publish_error,
        )

    def stop_runtime(self) -> None:
        if self.backend_client is None:
            return
        self.publish_status("正在停止购买运行...")
        self.task_runner.submit(
            lambda: self.backend_client.stop_purchase_runtime(),
            on_success=lambda status: self._handle_status_loaded(status, success_message="购买运行已停止"),
            on_error=self.publish_error,
        )

    def load_inventory_detail(
        self,
        account_id: str,
        *,
        on_success: Callable[[dict[str, Any]], None],
        on_error: Callable[[str], None],
    ) -> None:
        if self.backend_client is None:
            return
        self.publish_status("正在加载库存详情...")
        self.task_runner.submit(
            lambda: self.backend_client.get_purchase_runtime_inventory_detail(account_id),
            on_success=lambda detail: self._handle_inventory_detail_loaded(detail, on_success=on_success),
            on_error=lambda message: self._handle_inventory_detail_error(message, on_error=on_error),
        )

    def _handle_status_loaded(
        self,
        status: dict[str, Any],
        *,
        success_message: str,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        try:
            self.view_model.load_status(status)
            self.refresh_view()
            self.publish_status(success_message)
        finally:
            if on_complete is not None:
                on_complete()

    def _build_error_handler(self, on_complete: Callable[[], None] | None):
        def handler(message: str) -> None:
            try:
                self.publish_error(message)
            finally:
                if on_complete is not None:
                    on_complete()

        return handler

    def _handle_inventory_detail_loaded(
        self,
        detail: dict[str, Any],
        *,
        on_success: Callable[[dict[str, Any]], None],
    ) -> None:
        on_success(detail)
        self.publish_status("库存详情已加载")

    def _handle_inventory_detail_error(
        self,
        message: str,
        *,
        on_error: Callable[[str], None],
    ) -> None:
        self.publish_status(f"加载库存详情失败: {message}")
        on_error(message)
