from __future__ import annotations

from datetime import datetime


class UpdateAccountQueryModesUseCase:
    def __init__(self, repository) -> None:
        self._repository = repository

    def execute(
        self,
        *,
        account_id: str,
        new_api_enabled: bool,
        fast_api_enabled: bool,
        token_enabled: bool,
    ):
        return self._repository.update_account(
            account_id,
            new_api_enabled=bool(new_api_enabled),
            fast_api_enabled=bool(fast_api_enabled),
            token_enabled=bool(token_enabled),
            updated_at=datetime.now().isoformat(timespec="seconds"),
        )
