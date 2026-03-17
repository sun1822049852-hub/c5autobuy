from __future__ import annotations

import asyncio
import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

ProgressCallback = Callable[[str], Awaitable[None] | None]
LoginRunner = Callable[[str | None, ProgressCallback], Awaitable["LoginCapture | dict[str, Any]"]]


async def _noop_emit(_: str) -> None:
    return None


async def _safe_emit(callback: ProgressCallback, state: str) -> None:
    result = callback(state)
    if asyncio.iscoroutine(result):
        await result


@dataclass(slots=True)
class LoginCapture:
    c5_user_id: str
    c5_nick_name: str
    cookie_raw: str


class LegacySeleniumLoginAdapter:
    def __init__(self, login_runner: LoginRunner | None = None) -> None:
        self._login_runner = login_runner or self._run_with_legacy_manager

    async def run_login(
        self,
        *,
        proxy_url: str | None,
        emit_state: ProgressCallback | None = None,
    ) -> LoginCapture:
        callback = emit_state or _noop_emit
        payload = await self._login_runner(proxy_url, callback)
        return self._normalize_payload(payload)

    async def _run_with_legacy_manager(
        self,
        proxy_url: str | None,
        emit_state: ProgressCallback,
    ) -> dict[str, Any]:
        legacy_module = _load_legacy_autobuy_module()
        manager = _build_phase1_login_manager(legacy_module, emit_state)
        success, user_info, cookie_raw, error = await manager.login_with_proxy(proxy_url or "direct")
        if not success or not user_info or not cookie_raw:
            raise RuntimeError(error or "登录失败")

        return {
            "c5_user_id": str(user_info.get("userId") or ""),
            "c5_nick_name": user_info.get("nickName") or "",
            "cookie_raw": cookie_raw,
        }

    @staticmethod
    def _normalize_payload(payload: LoginCapture | dict[str, Any]) -> LoginCapture:
        if isinstance(payload, LoginCapture):
            return payload

        return LoginCapture(
            c5_user_id=str(payload.get("c5_user_id") or ""),
            c5_nick_name=str(payload.get("c5_nick_name") or ""),
            cookie_raw=str(payload.get("cookie_raw") or ""),
        )


def _load_legacy_autobuy_module():
    project_root = Path(__file__).resolve().parents[3]
    autobuy_path = project_root / "autobuy.py"
    if not autobuy_path.exists():
        raise FileNotFoundError(f"未找到 legacy 登录入口: {autobuy_path}")

    spec = importlib.util.spec_from_file_location("legacy_autobuy_phase1", autobuy_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 legacy 模块: {autobuy_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build_phase1_login_manager(legacy_module, emit_state: ProgressCallback):
    base_class = legacy_module.SeleniumLoginManager

    class Phase1LoginManager(base_class):
        def __init__(self) -> None:
            super().__init__()
            self._captured_user_info: dict[str, Any] | None = None
            self._captured_cookie_raw = ""

        async def wait_for_login_success(self, timeout=300):
            await _safe_emit(emit_state, "waiting_for_scan")
            success = await super().wait_for_login_success(timeout)
            if not success:
                return False

            user_info = self.extract_user_info_from_response()
            if not user_info:
                user_info = await super().extract_user_info_directly()

            cookie_raw = ""
            if self.target_request_data:
                cookie_raw = self.target_request_data.get("cookies", "") or self.target_request_data.get(
                    "Cookie", ""
                )

            if not cookie_raw:
                try:
                    browser_cookies = self.driver.get_cookies()
                    cookie_raw = "; ".join(f"{item['name']}={item['value']}" for item in browser_cookies)
                except Exception:
                    cookie_raw = ""

            if not user_info or not user_info.get("userId") or not cookie_raw:
                return False

            self._captured_user_info = {
                "userId": str(user_info.get("userId") or ""),
                "nickName": str(user_info.get("nickName") or ""),
                "userName": str(user_info.get("userName") or ""),
                "avatar": str(user_info.get("avatar") or ""),
                "level": user_info.get("level") or 0,
            }
            self._captured_cookie_raw = cookie_raw
            self.target_request_data = _build_target_request_data(self._captured_user_info, cookie_raw)

            await _safe_emit(emit_state, "captured_login_info")
            await _safe_emit(emit_state, "waiting_for_browser_close")
            while self._is_browser_alive():
                await asyncio.sleep(1)
            self._browser_closed_by_user = True
            return True

        def extract_user_info_from_response(self):
            if self._captured_user_info:
                return self._captured_user_info
            return _extract_user_info_from_target(self.target_request_data)

    return Phase1LoginManager()


def _build_target_request_data(user_info: dict[str, Any], cookie_raw: str) -> dict[str, Any]:
    response_payload = {
        "success": True,
        "data": {
            "personalData": {
                "userId": user_info.get("userId") or "",
                "nickName": user_info.get("nickName") or "",
                "userName": user_info.get("userName") or "",
                "avatar": user_info.get("avatar") or "",
                "level": user_info.get("level") or 0,
            }
        },
    }
    return {
        "response": json.dumps(response_payload, ensure_ascii=False),
        "cookies": cookie_raw,
    }


def _extract_user_info_from_target(target_request_data: dict[str, Any] | None) -> dict[str, Any] | None:
    if not target_request_data:
        return None

    response_text = target_request_data.get("response")
    if not response_text:
        return None

    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError:
        return None

    personal_data = payload.get("data", {}).get("personalData", {})
    user_id = personal_data.get("userId")
    if not user_id:
        return None

    return {
        "userId": str(user_id),
        "nickName": personal_data.get("nickName") or "",
        "userName": personal_data.get("userName") or "",
        "avatar": personal_data.get("avatar") or "",
        "level": personal_data.get("level") or 0,
    }
