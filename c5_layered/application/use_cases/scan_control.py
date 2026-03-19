from __future__ import annotations

from typing import Any

from c5_layered.application.ports import ConfigRepository, ScanRuntime


class ScanControlUseCase:
    """Scan runtime control use case."""

    def __init__(self, config_repo: ConfigRepository, scan_runtime: ScanRuntime) -> None:
        self._config_repo = config_repo
        self._scan_runtime = scan_runtime

    def list_config_names(self) -> list[str]:
        return [cfg.name for cfg in self._config_repo.list_configs() if cfg.name]

    def start_scan(
        self,
        config_name: str,
        query_only: bool = False,
        purchase_user_ids: list[str] | None = None,
    ) -> tuple[bool, str]:
        name = (config_name or "").strip()
        if not name:
            return False, "配置名不能为空"
        if not self._config_repo.get_by_name(name):
            return False, f"未找到配置: {name}"
        return self._scan_runtime.start(
            name,
            query_only=query_only,
            purchase_user_ids=purchase_user_ids,
        )

    def stop_scan(self) -> tuple[bool, str]:
        return self._scan_runtime.stop()

    def get_status(self) -> dict[str, Any]:
        return self._scan_runtime.status()
