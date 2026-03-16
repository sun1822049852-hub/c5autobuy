from __future__ import annotations

import asyncio
import importlib
import sys
import threading
import time
from collections import deque
from pathlib import Path
from types import ModuleType
from typing import Any

from c5_layered.infrastructure.query import LegacyQueryPipeline


class LegacyScanRuntime:
    """
    Bridge runtime:
    - Reuses scan/purchase logic from legacy `autobuy.py`
    - Exposes start/stop/status API for the new GUI/application layer
    """

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._state_lock = threading.Lock()
        self._logs: deque[str] = deque(maxlen=300)
        self._state: dict[str, Any] = {
            "running": False,
            "query_only": False,
            "purchase_scope": "all",
            "purchase_selected_count": 0,
            "purchase_enabled_accounts": 0,
            "config_name": None,
            "message": "未运行",
            "last_error": None,
            "started_at": None,
            "stopped_at": None,
            "total_accounts": 0,
            "loaded_accounts": 0,
            "failed_accounts": 0,
            "query_count": 0,
            "found_count": 0,
            "purchased_count": 0,
        }

    def start(
        self,
        config_name: str,
        query_only: bool = False,
        purchase_user_ids: list[str] | None = None,
    ) -> tuple[bool, str]:
        with self._state_lock:
            if self._thread and self._thread.is_alive():
                return False, "扫描任务已在运行"

            normalized_purchase_ids: set[str] | None = None
            if purchase_user_ids:
                normalized_purchase_ids = {
                    str(x).strip() for x in purchase_user_ids if str(x).strip()
                }

            if query_only:
                purchase_scope = "query_only"
                purchase_selected_count = 0
            elif normalized_purchase_ids:
                purchase_scope = "selected"
                purchase_selected_count = len(normalized_purchase_ids)
            else:
                purchase_scope = "all"
                purchase_selected_count = 0

            self._stop_event = threading.Event()
            self._logs.clear()
            self._set_state_unlocked(
                running=True,
                query_only=bool(query_only),
                purchase_scope=purchase_scope,
                purchase_selected_count=purchase_selected_count,
                purchase_enabled_accounts=0,
                config_name=config_name,
                message=f"准备启动扫描: {config_name}",
                last_error=None,
                started_at=time.time(),
                stopped_at=None,
                total_accounts=0,
                loaded_accounts=0,
                failed_accounts=0,
                query_count=0,
                found_count=0,
                purchased_count=0,
            )

            self._thread = threading.Thread(
                target=self._thread_main,
                args=(config_name, bool(query_only), normalized_purchase_ids, self._stop_event),
                daemon=True,
                name="legacy-scan-runtime",
            )
            self._thread.start()

        return True, f"扫描任务已启动: {config_name}（{self._mode_text(query_only, normalized_purchase_ids)}）"

    def stop(self) -> tuple[bool, str]:
        with self._state_lock:
            thread = self._thread
            stop_event = self._stop_event

        if not thread or not thread.is_alive() or not stop_event:
            return False, "当前没有运行中的扫描任务"

        self._set_state(message="收到停止信号，正在安全停止...")
        self._append_log("收到停止信号，准备停机。")
        stop_event.set()
        thread.join(timeout=8.0)

        if thread.is_alive():
            return False, "停止请求已发送，任务仍在清理中"
        return True, "扫描任务已停止"

    def status(self) -> dict[str, Any]:
        with self._state_lock:
            data = dict(self._state)
            data["logs"] = list(self._logs)

        thread = self._thread
        if data.get("running") and thread and not thread.is_alive():
            data["running"] = False
            data["message"] = "任务已结束"
        return data

    def _thread_main(
        self,
        config_name: str,
        query_only: bool,
        purchase_user_ids: set[str] | None,
        stop_event: threading.Event,
    ) -> None:
        try:
            asyncio.run(
                self._run_scan(config_name, query_only, purchase_user_ids, stop_event)
            )
        except Exception as exc:  # noqa: BLE001
            self._set_state(
                running=False,
                message=f"扫描线程异常退出: {exc}",
                last_error=str(exc),
                stopped_at=time.time(),
            )
            self._append_log(f"异常退出: {exc}")
        finally:
            self._set_state(running=False, stopped_at=time.time())

    async def _run_scan(
        self,
        config_name: str,
        query_only: bool,
        purchase_user_ids: set[str] | None,
        stop_event: threading.Event,
    ) -> None:
        legacy = self._import_legacy_module()

        config_manager = legacy.ProductConfigManager()
        config = config_manager.get_config_by_name(config_name)
        if not config:
            msg = f"配置不存在: {config_name}"
            self._set_state(
                running=False,
                message=msg,
                last_error=msg,
                stopped_at=time.time(),
            )
            self._append_log(msg)
            return

        account_probe = legacy.AccountManager()
        all_accounts_data = account_probe.get_all_accounts()
        total_accounts = len(all_accounts_data)
        self._set_state(
            total_accounts=total_accounts,
            message=f"已读取账号 {total_accounts} 个，开始初始化...",
        )
        self._append_log(f"加载配置 {config_name}，账号总数 {total_accounts}。")

        if not all_accounts_data:
            msg = "未找到任何可用账号"
            self._set_state(
                running=False,
                message=msg,
                last_error="no_account",
                stopped_at=time.time(),
            )
            self._append_log(msg)
            return

        if not getattr(config, "products", None):
            msg = f"配置 {config_name} 下无商品规则"
            self._set_state(
                running=False,
                message=msg,
                last_error="empty_products",
                stopped_at=time.time(),
            )
            self._append_log(msg)
            return

        product_pool = [
            item.item_id for item in config.products if getattr(item, "item_id", None)
        ]
        if not product_pool:
            msg = f"配置 {config_name} 商品 ID 为空"
            self._set_state(
                running=False,
                message=msg,
                last_error="invalid_products",
                stopped_at=time.time(),
            )
            self._append_log(msg)
            return

        query_pipeline = LegacyQueryPipeline(
            legacy,
            query_only=query_only,
            logger=self._append_log,
        )
        query_pipeline.initialize(product_pool)

        loaded_managers: list[Any] = []
        failed_count = 0
        purchase_enabled_accounts = 0

        try:
            for account_data in all_accounts_data:
                if stop_event.is_set():
                    self._set_state(message="初始化阶段收到停止信号")
                    self._append_log("初始化阶段收到停止信号。")
                    break

                user_id = account_data.get("userId")
                if not user_id:
                    failed_count += 1
                    self._set_state(failed_accounts=failed_count)
                    continue

                account_manager = legacy.AccountManager()
                loaded = await account_manager.load_account_by_id(str(user_id))
                if not loaded:
                    failed_count += 1
                    self._set_state(failed_accounts=failed_count)
                    continue

                is_logged_in = bool(getattr(account_manager, "login_status", False))
                allow_purchase = (
                    (not query_only)
                    and is_logged_in
                    and (purchase_user_ids is None or str(user_id) in purchase_user_ids)
                )

                attach_result = await query_pipeline.attach_account(
                    account_manager,
                    config.products,
                    config.name,
                    allow_purchase=allow_purchase,
                )
                if not attach_result.can_query:
                    failed_count += 1
                    self._set_state(failed_accounts=failed_count)
                    continue

                if attach_result.purchase_registered:
                    purchase_enabled_accounts += 1

                loaded_managers.append(account_manager)
                self._set_state(
                    loaded_accounts=len(loaded_managers),
                    failed_accounts=failed_count,
                    purchase_enabled_accounts=purchase_enabled_accounts,
                    message=f"初始化账号中... {len(loaded_managers)}/{total_accounts}",
                )

            if not loaded_managers:
                msg = "没有可运行扫描的账号（需已登录或配置 API Key）"
                self._set_state(
                    running=False,
                    message=msg,
                    last_error="no_runnable_account",
                    stopped_at=time.time(),
                )
                self._append_log(msg)
                return

            started, reason = await query_pipeline.start()
            if not started:
                msg = f"启动查询引擎失败: {reason}"
                self._set_state(
                    running=False,
                    message=msg,
                    last_error="query_engine_start_failed",
                    stopped_at=time.time(),
                )
                self._append_log(msg)
                return

            mode_text = self._mode_text(query_only, purchase_user_ids)
            self._set_state(
                message=(
                    f"扫描运行中（配置: {config_name}，模式: {mode_text}，"
                    f"账号: {len(loaded_managers)}）"
                ),
                purchase_enabled_accounts=purchase_enabled_accounts,
            )
            self._append_log(f"扫描已启动：配置={config_name}，模式={mode_text}。")

            while not stop_event.is_set():
                self._update_metrics(query_pipeline)
                await asyncio.sleep(1.0)

            self._set_state(message="正在停止扫描任务...")
            self._append_log("开始执行停机清理。")

        finally:
            await query_pipeline.stop()

            for manager in loaded_managers:
                try:
                    await manager.close_global_session()
                except Exception:  # noqa: BLE001
                    pass
                try:
                    await manager.close_api_session()
                except Exception:  # noqa: BLE001
                    pass

            self._set_state(message="扫描任务已结束")
            self._append_log("扫描任务已结束。")

    def _update_metrics(self, query_pipeline: LegacyQueryPipeline) -> None:
        metrics = query_pipeline.collect_metrics()
        self._set_state(
            query_count=metrics.query_count,
            found_count=metrics.found_count,
            purchased_count=metrics.purchased_count,
        )

    def _import_legacy_module(self) -> ModuleType:
        root = str(self._project_root)
        if root not in sys.path:
            sys.path.insert(0, root)
        return importlib.import_module("autobuy")

    @staticmethod
    def _mode_text(
        query_only: bool,
        purchase_user_ids: set[str] | None,
    ) -> str:
        if query_only:
            return "仅查询"
        if purchase_user_ids:
            return f"查询+购买(指定账号{len(purchase_user_ids)}个)"
        return "查询+购买(全部账号)"

    def _set_state(self, **kwargs: Any) -> None:
        with self._state_lock:
            self._set_state_unlocked(**kwargs)

    def _set_state_unlocked(self, **kwargs: Any) -> None:
        self._state.update(kwargs)

    def _append_log(self, text: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        with self._state_lock:
            self._logs.append(f"[{timestamp}] {text}")
