from __future__ import annotations

from typing import Any


class QuerySystemViewModel:
    def __init__(self) -> None:
        self._configs: list[dict[str, Any]] = []
        self.selected_config_id: str | None = None
        self.runtime_status: dict[str, Any] = {
            "running": False,
            "config_id": None,
            "config_name": None,
            "message": "未运行",
            "account_count": 0,
            "modes": {},
        }

    def set_configs(self, configs: list[dict[str, Any]]) -> None:
        self._configs = [dict(config) for config in configs]
        config_ids = {config["config_id"] for config in self._configs}
        if self.selected_config_id not in config_ids:
            self.selected_config_id = None

    def select_config(self, config_id: str | None) -> None:
        self.selected_config_id = config_id

    def upsert_config(self, config: dict[str, Any]) -> None:
        normalized = dict(config)
        for index, current in enumerate(self._configs):
            if current["config_id"] == normalized["config_id"]:
                self._configs[index] = normalized
                break
        else:
            self._configs.append(normalized)

    def remove_config(self, config_id: str) -> None:
        self._configs = [config for config in self._configs if config["config_id"] != config_id]
        if self.selected_config_id == config_id:
            self.selected_config_id = None

    def update_mode_setting(self, config_id: str, mode_setting: dict[str, Any]) -> None:
        normalized = dict(mode_setting)
        for config in self._configs:
            if config["config_id"] != config_id:
                continue
            settings = list(config.get("mode_settings") or [])
            for index, current in enumerate(settings):
                if current.get("mode_setting_id") == normalized.get("mode_setting_id") or current.get("mode_type") == normalized.get(
                    "mode_type"
                ):
                    settings[index] = normalized
                    break
            else:
                settings.append(normalized)
            config["mode_settings"] = settings
            return

    def upsert_item(self, config_id: str, item: dict[str, Any]) -> None:
        normalized = dict(item)
        for config in self._configs:
            if config["config_id"] != config_id:
                continue
            items = list(config.get("items") or [])
            for index, current in enumerate(items):
                if current.get("query_item_id") == normalized.get("query_item_id"):
                    items[index] = normalized
                    break
            else:
                items.append(normalized)
            items.sort(key=lambda value: (int(value.get("sort_order", 0)), str(value.get("query_item_id", ""))))
            config["items"] = items
            return

    def remove_item(self, config_id: str, query_item_id: str) -> None:
        for config in self._configs:
            if config["config_id"] != config_id:
                continue
            config["items"] = [item for item in (config.get("items") or []) if item.get("query_item_id") != query_item_id]
            return

    def set_runtime_status(self, status: dict[str, Any]) -> None:
        self.runtime_status = dict(status)

    @property
    def config_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "config_id": config["config_id"],
                "name": config["name"],
                "description": config.get("description") or "",
                "item_count": len(config.get("items") or []),
                "mode_summary": self._mode_summary(config.get("mode_settings") or []),
            }
            for config in self._configs
        ]

    @property
    def detail_config(self) -> dict[str, Any] | None:
        if self.selected_config_id is None:
            return None
        for config in self._configs:
            if config["config_id"] == self.selected_config_id:
                return dict(config)
        return None

    @property
    def runtime_summary(self) -> str:
        if self.runtime_status.get("running"):
            return (
                f"{self.runtime_status.get('message')}: "
                f"{self.runtime_status.get('config_name')} "
                f"(账号 {self.runtime_status.get('account_count', 0)})"
            )
        return str(self.runtime_status.get("message") or "未运行")

    @staticmethod
    def _mode_summary(mode_settings: list[dict[str, Any]]) -> str:
        if not mode_settings:
            return ""
        parts = []
        for setting in mode_settings:
            mode_type = str(setting.get("mode_type") or "")
            if setting.get("enabled", False):
                parts.append(mode_type)
            else:
                parts.append(f"{mode_type}(关)")
        return " / ".join(parts)
