from __future__ import annotations

import asyncio
import threading
from datetime import datetime
from inspect import Parameter, signature

from app_backend.domain.models.query_config import QueryConfig, QueryModeSetting

from .mode_runner import ModeRunner
from .query_item_scheduler import QueryItemScheduler


class QueryTaskRuntime:
    _RECENT_EVENT_LIMIT = 20

    def __init__(
        self,
        config: QueryConfig,
        accounts: list[object],
        *,
        runtime_session_id: str | None = None,
        mode_runner_factory=None,
        query_item_scheduler_factory=None,
        hit_sink=None,
        event_sink=None,
    ) -> None:
        self._config = config
        self._accounts = list(accounts)
        self._runtime_session_id = str(runtime_session_id or "") or None
        self._hit_sink = hit_sink
        self._event_sink = event_sink
        self._running = False
        self._started_at: str | None = None
        self._stopped_at: str | None = None
        self._background_thread: threading.Thread | None = None
        self._background_loop: asyncio.AbstractEventLoop | None = None
        self._async_stop_event = None
        self._stop_requested = threading.Event()
        factory = mode_runner_factory or self._build_default_mode_runner
        item_scheduler_factory = query_item_scheduler_factory or self._build_default_query_item_scheduler
        query_items = list(self._config.items)
        self._mode_runners = []
        for mode_setting in config.mode_settings:
            # Each mode keeps an independent scheduler state while querying the same config items.
            mode_scheduler = item_scheduler_factory(list(query_items))
            self._mode_runners.append(
                self._build_mode_runner(
                    factory,
                    mode_setting,
                    self._accounts,
                    query_items=list(query_items),
                    query_item_scheduler=mode_scheduler,
                    query_config_id=str(self._config.config_id),
                    runtime_session_id=self._runtime_session_id,
                    hit_sink=self._hit_sink,
                    event_sink=self._event_sink,
                )
            )

    @property
    def config(self) -> QueryConfig:
        return self._config

    @property
    def runtime_session_id(self) -> str | None:
        return self._runtime_session_id

    def start(self) -> None:
        self._stop_requested.clear()
        for runner in self._mode_runners:
            start = getattr(runner, "start", None)
            if callable(start):
                start()
        self._running = True
        self._started_at = datetime.now().isoformat(timespec="seconds")
        self._stopped_at = None
        self._background_thread = threading.Thread(
            target=self._run_background_loop,
            name=f"query-runtime-{self._config.config_id}",
            daemon=True,
        )
        self._background_thread.start()

    def stop(self) -> None:
        self._stop_requested.set()
        if self._background_loop is not None and self._async_stop_event is not None:
            self._background_loop.call_soon_threadsafe(self._async_stop_event.set)
        if self._background_thread is not None and self._background_thread.is_alive():
            self._background_thread.join(timeout=5.0)
        for runner in self._mode_runners:
            stop = getattr(runner, "stop", None)
            if callable(stop):
                stop()
        self._running = False
        self._stopped_at = datetime.now().isoformat(timespec="seconds")
        self._background_thread = None

    def _run_background_loop(self) -> None:
        loop = asyncio.new_event_loop()
        self._background_loop = loop
        asyncio.set_event_loop(loop)
        self._async_stop_event = asyncio.Event()
        if self._stop_requested.is_set():
            self._async_stop_event.set()
        try:
            loop.run_until_complete(self._run_mode_tasks())
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self._async_stop_event = None
            self._background_loop = None
            loop.close()

    async def _run_mode_tasks(self) -> None:
        tasks = []
        for runner in self._mode_runners:
            run_loop = getattr(runner, "run_loop", None)
            if callable(run_loop):
                tasks.append(asyncio.create_task(run_loop(self._async_stop_event)))

        try:
            if not tasks:
                while self._async_stop_event is not None and not self._async_stop_event.is_set():
                    await asyncio.sleep(0.1)
                return

            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            await self._cleanup_mode_runners()

    async def _cleanup_mode_runners(self) -> None:
        for runner in self._mode_runners:
            cleanup = getattr(runner, "cleanup", None)
            if callable(cleanup):
                await cleanup()

    def snapshot(self) -> dict[str, object]:
        mode_snapshots = [runner.snapshot() for runner in self._mode_runners]
        return {
            "running": self._running,
            "config_id": self._config.config_id,
            "config_name": self._config.name,
            "runtime_session_id": self._runtime_session_id,
            "message": "运行中" if self._running else "未运行",
            "account_count": len(self._accounts),
            "started_at": self._started_at,
            "stopped_at": self._stopped_at,
            "total_query_count": sum(int(snapshot.get("query_count", 0)) for snapshot in mode_snapshots),
            "total_found_count": sum(int(snapshot.get("found_count", 0)) for snapshot in mode_snapshots),
            "group_rows": self._collect_group_rows(mode_snapshots),
            "item_rows": self._collect_item_rows(self._config, mode_snapshots),
            "recent_events": self._collect_recent_events(mode_snapshots),
            "modes": {
                snapshot["mode_type"]: snapshot
                for snapshot in mode_snapshots
            },
        }

    @staticmethod
    def _build_default_mode_runner(
        mode_setting: QueryModeSetting,
        accounts: list[object],
        *,
        query_items: list[object] | None = None,
        query_item_scheduler=None,
        query_config_id: str | None = None,
        runtime_session_id: str | None = None,
        hit_sink=None,
        event_sink=None,
    ) -> ModeRunner:
        return ModeRunner(
            mode_setting,
            accounts,
            query_items=query_items,
            query_item_scheduler=query_item_scheduler,
            query_config_id=query_config_id,
            runtime_session_id=runtime_session_id,
            hit_sink=hit_sink,
            event_sink=event_sink,
        )

    @staticmethod
    def _build_default_query_item_scheduler(query_items: list[object]) -> QueryItemScheduler:
        return QueryItemScheduler(list(query_items))

    @staticmethod
    def _build_mode_runner(
        factory,
        mode_setting,
        accounts: list[object],
        *,
        query_items,
        query_item_scheduler,
        query_config_id,
        runtime_session_id,
        hit_sink,
        event_sink,
    ):
        kwargs = {"query_items": query_items}
        if query_item_scheduler is not None and QueryTaskRuntime._factory_accepts_parameter(factory, "query_item_scheduler"):
            kwargs["query_item_scheduler"] = query_item_scheduler
        if query_config_id is not None and QueryTaskRuntime._factory_accepts_parameter(
            factory,
            "query_config_id",
            allow_var_keyword=False,
        ):
            kwargs["query_config_id"] = query_config_id
        if runtime_session_id is not None and QueryTaskRuntime._factory_accepts_parameter(
            factory,
            "runtime_session_id",
            allow_var_keyword=False,
        ):
            kwargs["runtime_session_id"] = runtime_session_id
        if hit_sink is not None and QueryTaskRuntime._factory_accepts_parameter(factory, "hit_sink"):
            kwargs["hit_sink"] = hit_sink
        if event_sink is not None and QueryTaskRuntime._factory_accepts_parameter(factory, "event_sink"):
            kwargs["event_sink"] = event_sink
        return factory(mode_setting, accounts, **kwargs)

    @staticmethod
    def _factory_accepts_parameter(factory, parameter_name: str, *, allow_var_keyword: bool = True) -> bool:
        try:
            parameters = signature(factory).parameters.values()
        except (TypeError, ValueError):
            return False

        for parameter in parameters:
            if allow_var_keyword and parameter.kind == Parameter.VAR_KEYWORD:
                return True
            if parameter.name == parameter_name:
                return True
        return False

    @classmethod
    def _collect_recent_events(cls, mode_snapshots: list[dict[str, object]]) -> list[dict[str, object]]:
        recent_events: list[dict[str, object]] = []
        for snapshot in mode_snapshots:
            raw_events = snapshot.get("recent_events")
            if not isinstance(raw_events, list):
                continue
            for event in raw_events:
                if isinstance(event, dict):
                    recent_events.append(dict(event))
        recent_events.sort(key=lambda event: str(event.get("timestamp") or ""), reverse=True)
        return recent_events[: cls._RECENT_EVENT_LIMIT]

    @staticmethod
    def _collect_group_rows(mode_snapshots: list[dict[str, object]]) -> list[dict[str, object]]:
        group_rows: list[dict[str, object]] = []
        for snapshot in mode_snapshots:
            raw_rows = snapshot.get("group_rows")
            if not isinstance(raw_rows, list):
                continue
            for row in raw_rows:
                if isinstance(row, dict):
                    group_rows.append(dict(row))
        return group_rows

    @staticmethod
    def _collect_item_rows(config: QueryConfig, mode_snapshots: list[dict[str, object]]) -> list[dict[str, object]]:
        rows_by_item_id: dict[str, dict[str, object]] = {}
        ordered_rows: list[dict[str, object]] = []
        for item in config.items:
            item_id = str(item.query_item_id)
            row = {
                "query_item_id": item_id,
                "item_name": item.item_name or item.market_hash_name or item_id,
                "max_price": item.max_price,
                "min_wear": item.min_wear,
                "max_wear": item.max_wear,
                "detail_min_wear": item.detail_min_wear,
                "detail_max_wear": item.detail_max_wear,
                "manual_paused": bool(item.manual_paused),
                "query_count": 0,
                "modes": {},
            }
            rows_by_item_id[item_id] = row
            ordered_rows.append(row)

        for snapshot in mode_snapshots:
            raw_rows = snapshot.get("item_rows")
            if not isinstance(raw_rows, list):
                continue
            fallback_mode_type = str(snapshot.get("mode_type") or "")
            for raw_row in raw_rows:
                if not isinstance(raw_row, dict):
                    continue
                item_id = str(raw_row.get("query_item_id") or "")
                if not item_id or item_id not in rows_by_item_id:
                    continue
                mode_type = str(raw_row.get("mode_type") or fallback_mode_type)
                if not mode_type:
                    continue
                rows_by_item_id[item_id]["query_count"] += int(raw_row.get("query_count", 0))
                rows_by_item_id[item_id]["modes"][mode_type] = {
                    "mode_type": mode_type,
                    "target_dedicated_count": int(raw_row.get("target_dedicated_count", 0)),
                    "actual_dedicated_count": int(raw_row.get("actual_dedicated_count", 0)),
                    "status": str(raw_row.get("status") or ""),
                    "status_message": str(raw_row.get("status_message") or ""),
                }
        return ordered_rows
