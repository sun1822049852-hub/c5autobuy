from __future__ import annotations


class RefreshQueryItemDetailUseCase:
    def __init__(self, refresh_service) -> None:
        self._refresh_service = refresh_service

    async def execute(self, *, config_id: str, query_item_id: str):
        return await self._refresh_service.refresh_item(
            config_id=config_id,
            query_item_id=query_item_id,
        )
