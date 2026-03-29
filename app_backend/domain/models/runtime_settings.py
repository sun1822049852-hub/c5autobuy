from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RuntimeSettings:
    settings_id: str
    query_settings_json: dict[str, object]
    purchase_settings_json: dict[str, object]
    updated_at: str | None = None
