from __future__ import annotations

from datetime import datetime, timedelta


class QueryItemDetailRefreshService:
    NO_ELIGIBLE_ACCOUNT_ERROR = "没有可用于商品信息补全的已登录账号"

    def __init__(
        self,
        *,
        repository,
        collector,
        now_provider=None,
        threshold_hours: int = 12,
    ) -> None:
        self._repository = repository
        self._collector = collector
        self._now_provider = now_provider or datetime.now
        self._threshold_hours = int(threshold_hours)

    async def refresh_item(self, *, config_id: str, query_item_id: str):
        config = self._repository.get_config(config_id)
        if config is None:
            raise KeyError(config_id)

        query_item = next((item for item in config.items if item.query_item_id == query_item_id), None)
        if query_item is None:
            raise KeyError(query_item_id)

        return await self._refresh_query_item(query_item, now=self._now_provider())

    async def prepare(self, *, config_id: str, force_refresh: bool = False) -> dict[str, object]:
        config = self._repository.get_config(config_id)
        if config is None:
            raise KeyError(config_id)

        now = self._now_provider()
        items: list[dict[str, object]] = []
        updated_count = 0
        skipped_count = 0
        failed_count = 0

        for query_item in config.items:
            if not force_refresh and not self._should_refresh(query_item.last_detail_sync_at, now=now):
                skipped_count += 1
                items.append(
                    {
                        "query_item_id": query_item.query_item_id,
                        "external_item_id": query_item.external_item_id,
                        "item_name": query_item.item_name,
                        "status": "skipped",
                        "message": "12小时内已同步，跳过",
                        "last_market_price": query_item.last_market_price,
                        "min_wear": query_item.min_wear,
                        "detail_max_wear": query_item.detail_max_wear,
                        "last_detail_sync_at": query_item.last_detail_sync_at,
                    }
                )
                continue

            try:
                updated_item = await self._refresh_query_item(query_item, now=now)
                updated_count += 1
                items.append(
                    {
                        "query_item_id": updated_item.query_item_id,
                        "external_item_id": updated_item.external_item_id,
                        "item_name": updated_item.item_name,
                        "status": "updated",
                        "message": "商品详情已刷新",
                        "last_market_price": updated_item.last_market_price,
                        "min_wear": updated_item.min_wear,
                        "detail_max_wear": updated_item.detail_max_wear,
                        "last_detail_sync_at": updated_item.last_detail_sync_at,
                    }
                )
            except Exception as exc:
                if str(exc) == self.NO_ELIGIBLE_ACCOUNT_ERROR:
                    raise ValueError(self.NO_ELIGIBLE_ACCOUNT_ERROR) from exc
                failed_count += 1
                items.append(
                    {
                        "query_item_id": query_item.query_item_id,
                        "external_item_id": query_item.external_item_id,
                        "item_name": query_item.item_name,
                        "status": "failed",
                        "message": str(exc),
                        "last_market_price": query_item.last_market_price,
                        "min_wear": query_item.min_wear,
                        "detail_max_wear": query_item.detail_max_wear,
                        "last_detail_sync_at": query_item.last_detail_sync_at,
                    }
                )

        return {
            "config_id": config.config_id,
            "config_name": config.name,
            "threshold_hours": self._threshold_hours,
            "updated_count": updated_count,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
            "items": items,
        }

    async def _refresh_query_item(self, query_item, *, now: datetime):
        try:
            detail = await self._collector.fetch_detail(
                external_item_id=query_item.external_item_id,
                product_url=query_item.product_url,
            )
        except Exception as exc:
            if str(exc) == self.NO_ELIGIBLE_ACCOUNT_ERROR:
                raise ValueError(self.NO_ELIGIBLE_ACCOUNT_ERROR) from exc
            raise

        synced_at = now.isoformat(timespec="seconds")
        return self._repository.update_item_detail(
            query_item.query_item_id,
            item_name=detail.item_name,
            market_hash_name=detail.market_hash_name,
            min_wear=detail.min_wear,
            detail_max_wear=detail.max_wear,
            last_market_price=detail.last_market_price,
            last_detail_sync_at=synced_at,
        )

    def _should_refresh(self, last_detail_sync_at: str | None, *, now: datetime) -> bool:
        if not last_detail_sync_at:
            return True

        try:
            synced_at = datetime.fromisoformat(last_detail_sync_at)
        except ValueError:
            return True
        return synced_at <= now - timedelta(hours=self._threshold_hours)
