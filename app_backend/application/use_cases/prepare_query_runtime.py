from __future__ import annotations


class PrepareQueryRuntimeUseCase:
    def __init__(self, refresh_service) -> None:
        self._refresh_service = refresh_service

    async def execute(self, *, config_id: str, force_refresh: bool = False) -> dict[str, object]:
        return await self._refresh_service.prepare(config_id=config_id, force_refresh=force_refresh)
