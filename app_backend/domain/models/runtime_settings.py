from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app_backend.domain.enums.query_modes import QueryMode
from app_backend.domain.models.query_config import QueryModeSetting

DEFAULT_RUNTIME_SETTINGS_ID = "default"

DEFAULT_QUERY_SETTINGS_JSON: dict[str, Any] = {
    "modes": {
        QueryMode.NEW_API: {
            "enabled": True,
            "cooldown_min_seconds": 1.0,
            "cooldown_max_seconds": 1.0,
            "random_delay_enabled": False,
            "random_delay_min_seconds": 0.0,
            "random_delay_max_seconds": 0.0,
            "window_enabled": False,
            "start_hour": 0,
            "start_minute": 0,
            "end_hour": 0,
            "end_minute": 0,
        },
        QueryMode.FAST_API: {
            "enabled": True,
            "cooldown_min_seconds": 0.2,
            "cooldown_max_seconds": 0.2,
            "random_delay_enabled": False,
            "random_delay_min_seconds": 0.0,
            "random_delay_max_seconds": 0.0,
            "window_enabled": False,
            "start_hour": 0,
            "start_minute": 0,
            "end_hour": 0,
            "end_minute": 0,
        },
        QueryMode.TOKEN: {
            "enabled": True,
            "cooldown_min_seconds": 10.0,
            "cooldown_max_seconds": 10.0,
            "random_delay_enabled": False,
            "random_delay_min_seconds": 0.0,
            "random_delay_max_seconds": 0.0,
            "window_enabled": False,
            "start_hour": 0,
            "start_minute": 0,
            "end_hour": 0,
            "end_minute": 0,
        },
    },
    "item_pacing": {
        QueryMode.NEW_API: {
            "strategy": "fixed_divided_by_actual_allocated_workers",
            "fixed_seconds": 0.5,
        },
        QueryMode.FAST_API: {
            "strategy": "fixed_divided_by_actual_allocated_workers",
            "fixed_seconds": 0.5,
        },
        QueryMode.TOKEN: {
            "strategy": "fixed_divided_by_actual_allocated_workers",
            "fixed_seconds": 0.5,
        },
    },
}

DEFAULT_PURCHASE_SETTINGS_JSON: dict[str, Any] = {
    "ip_bucket_limits": {},
}


@dataclass(slots=True)
class RuntimeSettings:
    settings_id: str
    query_settings_json: dict[str, Any]
    purchase_settings_json: dict[str, Any]
    updated_at: str


@dataclass(slots=True)
class QueryItemPacingSetting:
    mode_type: str
    strategy: str
    fixed_seconds: float


def build_default_query_settings_json() -> dict[str, Any]:
    return deepcopy(DEFAULT_QUERY_SETTINGS_JSON)


def build_default_purchase_settings_json() -> dict[str, Any]:
    return deepcopy(DEFAULT_PURCHASE_SETTINGS_JSON)


def build_default_runtime_settings(*, updated_at: str | None = None) -> RuntimeSettings:
    return RuntimeSettings(
        settings_id=DEFAULT_RUNTIME_SETTINGS_ID,
        query_settings_json=build_default_query_settings_json(),
        purchase_settings_json=build_default_purchase_settings_json(),
        updated_at=updated_at or datetime.now().isoformat(timespec="seconds"),
    )


def build_query_settings_from_mode_settings(
    mode_settings: list[QueryModeSetting] | None,
) -> dict[str, Any]:
    query_settings = build_default_query_settings_json()
    for mode_setting in list(mode_settings or []):
        if mode_setting.mode_type not in QueryMode.ALL:
            continue
        query_settings["modes"][mode_setting.mode_type] = {
            "enabled": bool(mode_setting.enabled),
            "cooldown_min_seconds": float(mode_setting.base_cooldown_min),
            "cooldown_max_seconds": float(mode_setting.base_cooldown_max),
            "random_delay_enabled": bool(mode_setting.random_delay_enabled),
            "random_delay_min_seconds": float(mode_setting.random_delay_min),
            "random_delay_max_seconds": float(mode_setting.random_delay_max),
            "window_enabled": bool(mode_setting.window_enabled),
            "start_hour": int(mode_setting.start_hour),
            "start_minute": int(mode_setting.start_minute),
            "end_hour": int(mode_setting.end_hour),
            "end_minute": int(mode_setting.end_minute),
        }
    return query_settings


def normalize_query_settings_json(query_settings_json: dict[str, Any] | None) -> dict[str, Any]:
    normalized = build_default_query_settings_json()
    if not isinstance(query_settings_json, dict):
        return normalized

    raw_modes = query_settings_json.get("modes")
    if isinstance(raw_modes, dict):
        for mode_type in QueryMode.ALL:
            raw_mode = raw_modes.get(mode_type)
            if not isinstance(raw_mode, dict):
                continue
            normalized_mode = normalized["modes"][mode_type]
            for key in tuple(normalized_mode.keys()):
                if key in raw_mode:
                    normalized_mode[key] = raw_mode[key]

    raw_item_pacing = query_settings_json.get("item_pacing")
    if isinstance(raw_item_pacing, dict):
        for mode_type in QueryMode.ALL:
            raw_pacing = raw_item_pacing.get(mode_type)
            if not isinstance(raw_pacing, dict):
                continue
            normalized_pacing = normalized["item_pacing"][mode_type]
            for key in tuple(normalized_pacing.keys()):
                if key in raw_pacing:
                    normalized_pacing[key] = raw_pacing[key]
    return normalized


def normalize_purchase_settings_json(purchase_settings_json: dict[str, Any] | None) -> dict[str, Any]:
    normalized = build_default_purchase_settings_json()
    if not isinstance(purchase_settings_json, dict):
        return normalized
    raw_limits = purchase_settings_json.get("ip_bucket_limits")
    if not isinstance(raw_limits, dict):
        return normalized
    normalized_limits: dict[str, dict[str, int]] = {}
    for bucket_key, raw_bucket in raw_limits.items():
        if not isinstance(bucket_key, str) or not isinstance(raw_bucket, dict):
            continue
        try:
            concurrency_limit = int(raw_bucket.get("concurrency_limit", 1))
        except (TypeError, ValueError):
            concurrency_limit = 1
        normalized_limits[bucket_key] = {
            "concurrency_limit": max(concurrency_limit, 1),
        }
    normalized["ip_bucket_limits"] = normalized_limits
    return normalized


def build_runtime_mode_settings(
    query_settings_json: dict[str, Any] | None,
    *,
    config_id: str,
    updated_at: str | None = None,
) -> list[QueryModeSetting]:
    normalized = normalize_query_settings_json(query_settings_json)
    timestamp = updated_at or datetime.now().isoformat(timespec="seconds")
    mode_settings: list[QueryModeSetting] = []
    for mode_type in QueryMode.ALL:
        payload = normalized["modes"][mode_type]
        mode_settings.append(
            QueryModeSetting(
                mode_setting_id=f"runtime-{mode_type}",
                config_id=str(config_id),
                mode_type=mode_type,
                enabled=bool(payload["enabled"]),
                window_enabled=bool(payload["window_enabled"]),
                start_hour=int(payload["start_hour"]),
                start_minute=int(payload["start_minute"]),
                end_hour=int(payload["end_hour"]),
                end_minute=int(payload["end_minute"]),
                base_cooldown_min=float(payload["cooldown_min_seconds"]),
                base_cooldown_max=float(payload["cooldown_max_seconds"]),
                random_delay_enabled=bool(payload["random_delay_enabled"]),
                random_delay_min=float(payload["random_delay_min_seconds"]),
                random_delay_max=float(payload["random_delay_max_seconds"]),
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
    return mode_settings


def build_item_pacing_settings(
    query_settings_json: dict[str, Any] | None,
) -> dict[str, QueryItemPacingSetting]:
    normalized = normalize_query_settings_json(query_settings_json)
    pacing_settings: dict[str, QueryItemPacingSetting] = {}
    for mode_type in QueryMode.ALL:
        payload = normalized["item_pacing"][mode_type]
        pacing_settings[mode_type] = QueryItemPacingSetting(
            mode_type=mode_type,
            strategy=str(payload["strategy"]),
            fixed_seconds=max(float(payload["fixed_seconds"]), 0.0),
        )
    return pacing_settings
