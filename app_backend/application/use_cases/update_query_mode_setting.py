from __future__ import annotations

from datetime import datetime


class UpdateQueryModeSettingUseCase:
    def __init__(self, repository) -> None:
        self._repository = repository

    def execute(
        self,
        *,
        config_id: str,
        mode_type: str,
        enabled: bool,
        window_enabled: bool,
        start_hour: int,
        start_minute: int,
        end_hour: int,
        end_minute: int,
        base_cooldown_min: float,
        base_cooldown_max: float,
        random_delay_enabled: bool,
        random_delay_min: float,
        random_delay_max: float,
    ):
        return self._repository.update_mode_setting(
            config_id,
            mode_type,
            enabled=int(enabled),
            window_enabled=int(window_enabled),
            start_hour=start_hour,
            start_minute=start_minute,
            end_hour=end_hour,
            end_minute=end_minute,
            base_cooldown_min=base_cooldown_min,
            base_cooldown_max=base_cooldown_max,
            random_delay_enabled=int(random_delay_enabled),
            random_delay_min=random_delay_min,
            random_delay_max=random_delay_max,
            updated_at=datetime.now().isoformat(timespec="seconds"),
        )
