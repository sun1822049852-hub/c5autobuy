from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RuntimeSettingsModePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    cooldown_min_seconds: float = Field(ge=0.0)
    cooldown_max_seconds: float = Field(ge=0.0)
    random_delay_enabled: bool
    random_delay_min_seconds: float = Field(ge=0.0)
    random_delay_max_seconds: float = Field(ge=0.0)
    window_enabled: bool
    start_hour: int = Field(ge=0, le=23)
    start_minute: int = Field(ge=0, le=59)
    end_hour: int = Field(ge=0, le=23)
    end_minute: int = Field(ge=0, le=59)

    @model_validator(mode="after")
    def validate_ranges(self):
        if self.cooldown_max_seconds < self.cooldown_min_seconds:
            raise ValueError("cooldown_max_seconds must be >= cooldown_min_seconds")
        if self.random_delay_max_seconds < self.random_delay_min_seconds:
            raise ValueError("random_delay_max_seconds must be >= random_delay_min_seconds")
        return self


class RuntimeSettingsModesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_api: RuntimeSettingsModePayload
    fast_api: RuntimeSettingsModePayload
    token: RuntimeSettingsModePayload

    @model_validator(mode="after")
    def validate_minimums(self):
        if self.new_api.cooldown_min_seconds < 1.0:
            raise ValueError("new_api.cooldown_min_seconds must be >= 1.0")
        if self.new_api.cooldown_max_seconds < 1.0:
            raise ValueError("new_api.cooldown_max_seconds must be >= 1.0")
        if self.fast_api.cooldown_min_seconds < 0.2:
            raise ValueError("fast_api.cooldown_min_seconds must be >= 0.2")
        if self.fast_api.cooldown_max_seconds < 0.2:
            raise ValueError("fast_api.cooldown_max_seconds must be >= 0.2")
        if self.token.cooldown_min_seconds < 10.0:
            raise ValueError("token.cooldown_min_seconds must be >= 10.0")
        if self.token.cooldown_max_seconds < 10.0:
            raise ValueError("token.cooldown_max_seconds must be >= 10.0")
        return self


class RuntimeSettingsItemPacingPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: str
    fixed_seconds: float = Field(ge=0.0)


class RuntimeSettingsItemPacingGroupPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_api: RuntimeSettingsItemPacingPayload
    fast_api: RuntimeSettingsItemPacingPayload
    token: RuntimeSettingsItemPacingPayload


class RuntimeQuerySettingsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modes: RuntimeSettingsModesPayload
    item_pacing: RuntimeSettingsItemPacingGroupPayload


class RuntimePurchaseBucketPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concurrency_limit: int = Field(ge=1)


class RuntimePurchaseSettingsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ip_bucket_limits: dict[str, RuntimePurchaseBucketPayload] = Field(default_factory=dict)


class RuntimeSettingsResponse(BaseModel):
    settings_id: str
    query_settings: RuntimeQuerySettingsPayload
    purchase_settings: RuntimePurchaseSettingsPayload
    updated_at: str
