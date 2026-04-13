from __future__ import annotations

from pydantic import BaseModel


class PurchaseRuntimeSettingsResponse(BaseModel):
    per_batch_ip_fanout_limit: int = 1
    max_inflight_per_account: int = 3
    updated_at: str | None = None


class PurchaseRuntimeSettingsUpdateRequest(BaseModel):
    per_batch_ip_fanout_limit: int
    max_inflight_per_account: int
