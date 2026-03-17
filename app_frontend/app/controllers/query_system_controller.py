from __future__ import annotations

from typing import Any, Callable


class QuerySystemController:
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

    def load_configs(self) -> None:
        if self.backend_client is None:
            return
        self.publish_status("正在加载查询配置...")
        self.task_runner.submit(
            lambda: self.backend_client.list_query_configs(),
            on_success=self._handle_configs_loaded,
            on_error=self.publish_error,
        )

    def create_config(self, payload: dict[str, Any]) -> None:
        if self.backend_client is None:
            return
        self.publish_status("正在创建查询配置...")
        self.task_runner.submit(
            lambda: self.backend_client.create_query_config(payload),
            on_success=self._handle_config_created,
            on_error=self.publish_error,
        )

    def update_selected_config(self, payload: dict[str, Any]) -> None:
        if self.backend_client is None:
            return
        config = self.view_model.detail_config
        if config is None:
            return
        self.publish_status("正在更新查询配置...")
        self.task_runner.submit(
            lambda: self.backend_client.update_query_config(config["config_id"], payload),
            on_success=self._handle_config_updated,
            on_error=self.publish_error,
        )

    def delete_selected_config(self) -> None:
        if self.backend_client is None:
            return
        config = self.view_model.detail_config
        if config is None:
            return
        self.publish_status("正在删除查询配置...")
        self.task_runner.submit(
            lambda: self.backend_client.delete_query_config(config["config_id"]),
            on_success=lambda _result: self._handle_config_deleted(config["config_id"]),
            on_error=self.publish_error,
        )

    def update_selected_mode_setting(self, mode_type: str, payload: dict[str, Any]) -> None:
        if self.backend_client is None:
            return
        config = self.view_model.detail_config
        if config is None:
            return
        self.publish_status("正在更新模式参数...")
        self.task_runner.submit(
            lambda: self.backend_client.update_query_mode_setting(config["config_id"], mode_type, payload),
            on_success=lambda setting: self._handle_mode_setting_updated(config["config_id"], setting),
            on_error=self.publish_error,
        )

    def add_item_to_selected_config(self, payload: dict[str, Any]) -> None:
        if self.backend_client is None:
            return
        config = self.view_model.detail_config
        if config is None:
            return
        self.publish_status("正在新增商品...")
        self.task_runner.submit(
            lambda: self.backend_client.add_query_item(config["config_id"], payload),
            on_success=lambda item: self._handle_item_added(config["config_id"], item),
            on_error=self.publish_error,
        )

    def update_selected_item(self, item_id: str, payload: dict[str, Any]) -> None:
        if self.backend_client is None:
            return
        config = self.view_model.detail_config
        if config is None:
            return
        self.publish_status("正在更新商品...")
        self.task_runner.submit(
            lambda: self.backend_client.update_query_item(config["config_id"], item_id, payload),
            on_success=lambda item: self._handle_item_updated(config["config_id"], item),
            on_error=self.publish_error,
        )

    def refresh_selected_item_detail(self, item_id: str) -> None:
        if self.backend_client is None:
            return
        config = self.view_model.detail_config
        if config is None:
            return
        self.publish_status("正在刷新商品详情...")
        self.task_runner.submit(
            lambda: self.backend_client.refresh_query_item_detail(config["config_id"], item_id),
            on_success=lambda item: self._handle_item_detail_refreshed(config["config_id"], item),
            on_error=self.publish_error,
        )

    def delete_selected_item(self, item_id: str) -> None:
        if self.backend_client is None:
            return
        config = self.view_model.detail_config
        if config is None:
            return
        self.publish_status("正在删除商品...")
        self.task_runner.submit(
            lambda: self.backend_client.delete_query_item(config["config_id"], item_id),
            on_success=lambda _result: self._handle_item_deleted(config["config_id"], item_id),
            on_error=self.publish_error,
        )

    def start_runtime_for_selected(self) -> None:
        if self.backend_client is None:
            return
        config = self.view_model.detail_config
        if config is None:
            return
        self.publish_status("正在启动查询任务...")
        self.task_runner.submit(
            lambda: self.backend_client.start_query_runtime(config["config_id"]),
            on_success=self._handle_runtime_started,
            on_error=self.publish_error,
        )

    def stop_runtime(self) -> None:
        if self.backend_client is None:
            return
        self.publish_status("正在停止查询任务...")
        self.task_runner.submit(
            lambda: self.backend_client.stop_query_runtime(),
            on_success=self._handle_runtime_stopped,
            on_error=self.publish_error,
        )

    def refresh_runtime_status(
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
            self.publish_status("正在刷新运行状态...")
        self.task_runner.submit(
            lambda: self.backend_client.get_query_runtime_status(),
            on_success=lambda status: self._handle_runtime_status_refreshed(status, on_complete=on_complete),
            on_error=self._build_runtime_refresh_error_handler(on_complete),
        )

    def _handle_configs_loaded(self, configs: list[dict[str, Any]]) -> None:
        self.view_model.set_configs(configs)
        self.refresh_view()
        self.refresh_runtime_status(silent=True)
        self.publish_status(f"已加载 {len(configs)} 个查询配置")

    def _handle_runtime_status_loaded(self, status: dict[str, Any]) -> None:
        self.view_model.set_runtime_status(status)
        self.refresh_view()

    def _handle_runtime_status_refreshed(
        self,
        status: dict[str, Any],
        *,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        try:
            self._handle_runtime_status_loaded(status)
        finally:
            if on_complete is not None:
                on_complete()

    def _handle_config_created(self, config: dict[str, Any]) -> None:
        self.view_model.upsert_config(config)
        self.view_model.select_config(config["config_id"])
        self.publish_status("查询配置已创建")
        self.refresh_view()

    def _handle_config_updated(self, config: dict[str, Any]) -> None:
        self.view_model.upsert_config(config)
        self.view_model.select_config(config["config_id"])
        self.publish_status("查询配置已更新")
        self.refresh_view()

    def _handle_config_deleted(self, config_id: str) -> None:
        self.view_model.remove_config(config_id)
        self.publish_status("查询配置已删除")
        self.refresh_view()

    def _handle_mode_setting_updated(self, config_id: str, setting: dict[str, Any]) -> None:
        self.view_model.update_mode_setting(config_id, setting)
        self.publish_status("模式参数已更新")
        self.refresh_view()

    def _handle_item_added(self, config_id: str, item: dict[str, Any]) -> None:
        self.view_model.upsert_item(config_id, item)
        self.publish_status("商品已新增")
        self.refresh_view()

    def _handle_item_updated(self, config_id: str, item: dict[str, Any]) -> None:
        self.view_model.upsert_item(config_id, item)
        self.publish_status("商品已更新")
        self.refresh_view()

    def _handle_item_detail_refreshed(self, config_id: str, item: dict[str, Any]) -> None:
        self.view_model.upsert_item(config_id, item)
        self.publish_status("商品详情已刷新")
        self.refresh_view()

    def _handle_item_deleted(self, config_id: str, item_id: str) -> None:
        self.view_model.remove_item(config_id, item_id)
        self.publish_status("商品已删除")
        self.refresh_view()

    def _handle_runtime_started(self, status: dict[str, Any]) -> None:
        self.view_model.set_runtime_status(status)
        self.publish_status("查询任务运行中")
        self.refresh_view()

    def _handle_runtime_stopped(self, status: dict[str, Any]) -> None:
        self.view_model.set_runtime_status(status)
        self.publish_status("查询任务已停止")
        self.refresh_view()

    def _build_runtime_refresh_error_handler(self, on_complete: Callable[[], None] | None):
        def handler(message: str) -> None:
            try:
                self.publish_error(message)
            finally:
                if on_complete is not None:
                    on_complete()

        return handler
