from __future__ import annotations

from app_backend.domain.enums.query_modes import QueryMode


class UpdateQuerySettingsUseCase:
    def __init__(self, repository) -> None:
        self._repository = repository

    def execute(self, *, modes: list[dict[str, object]]):
        normalized_modes = self._normalize_modes(modes)
        warnings = self._collect_warnings(normalized_modes)
        settings = self._repository.update_settings(normalized_modes)
        return settings, warnings

    def _normalize_modes(self, modes: list[dict[str, object]]) -> list[dict[str, object]]:
        if not isinstance(modes, list) or not modes:
            raise ValueError("查询设置不能为空")
        normalized: list[dict[str, object]] = []
        seen_modes: set[str] = set()
        for raw_mode in modes:
            mode_type = str(raw_mode.get("mode_type") or "").strip()
            if mode_type not in QueryMode.ALL:
                raise ValueError("存在未知的查询模式")
            if mode_type in seen_modes:
                raise ValueError("查询模式不能重复")
            seen_modes.add(mode_type)
            normalized_mode = {
                "mode_type": mode_type,
                "enabled": bool(raw_mode.get("enabled", True)),
                "window_enabled": bool(raw_mode.get("window_enabled", False)),
                "start_hour": int(raw_mode.get("start_hour", 0)),
                "start_minute": int(raw_mode.get("start_minute", 0)),
                "end_hour": int(raw_mode.get("end_hour", 0)),
                "end_minute": int(raw_mode.get("end_minute", 0)),
                "base_cooldown_min": float(raw_mode.get("base_cooldown_min", 0.0)),
                "base_cooldown_max": float(raw_mode.get("base_cooldown_max", 0.0)),
                "item_min_cooldown_seconds": float(raw_mode.get("item_min_cooldown_seconds", 0.5)),
                "item_min_cooldown_strategy": str(
                    raw_mode.get("item_min_cooldown_strategy", "divide_by_assigned_count")
                ),
                "random_delay_enabled": bool(raw_mode.get("random_delay_enabled", False)),
                "random_delay_min": float(raw_mode.get("random_delay_min", 0.0)),
                "random_delay_max": float(raw_mode.get("random_delay_max", 0.0)),
            }
            self._validate_mode(normalized_mode)
            normalized.append(normalized_mode)
        if seen_modes != set(QueryMode.ALL):
            raise ValueError("查询设置必须同时包含 new_api、fast_api、token")
        return normalized

    @staticmethod
    def _validate_mode(mode: dict[str, object]) -> None:
        mode_type = str(mode["mode_type"])
        base_min = float(mode["base_cooldown_min"])
        base_max = float(mode["base_cooldown_max"])
        item_min_cooldown_seconds = float(mode["item_min_cooldown_seconds"])
        item_min_cooldown_strategy = str(mode["item_min_cooldown_strategy"])
        random_min = float(mode["random_delay_min"])
        random_max = float(mode["random_delay_max"])
        start_hour = int(mode["start_hour"])
        start_minute = int(mode["start_minute"])
        end_hour = int(mode["end_hour"])
        end_minute = int(mode["end_minute"])

        if base_min < 0 or base_max < 0:
            raise ValueError(f"{mode_type} 基础冷却不能为负数")
        if base_max < base_min:
            raise ValueError(f"{mode_type} 基础冷却最大值不能小于最小值")
        if item_min_cooldown_seconds < 0:
            raise ValueError(f"{mode_type} 商品最小冷却不能为负数")
        if item_min_cooldown_strategy not in {"fixed", "divide_by_assigned_count"}:
            raise ValueError(f"{mode_type} 商品最小冷却策略无效")
        if random_min < 0 or random_max < 0:
            raise ValueError(f"{mode_type} 随机冷却不能为负数")
        if random_max < random_min:
            raise ValueError(f"{mode_type} 随机冷却最大值不能小于最小值")
        if not 0 <= start_hour <= 23 or not 0 <= end_hour <= 23:
            raise ValueError(f"{mode_type} 时间窗小时必须位于 0 到 23")
        if not 0 <= start_minute <= 59 or not 0 <= end_minute <= 59:
            raise ValueError(f"{mode_type} 时间窗分钟必须位于 0 到 59")
        if mode_type == QueryMode.NEW_API and base_min < 1.0:
            raise ValueError("new_api 基础冷却不能低于 1.0 秒")
        if mode_type == QueryMode.FAST_API and base_min < 0.2:
            raise ValueError("fast_api 基础冷却不能低于 0.2 秒")

    @staticmethod
    def _collect_warnings(modes: list[dict[str, object]]) -> list[str]:
        for mode in modes:
            if str(mode["mode_type"]) != QueryMode.TOKEN:
                continue
            if float(mode["base_cooldown_min"]) < 10.0 or float(mode["base_cooldown_max"]) < 10.0:
                return ["浏览器查询器基础冷却低于 10 秒，封号风险极高"]
        return []
