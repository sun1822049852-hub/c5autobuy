from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, Awaitable, Callable

SleepFunc = Callable[[float], Awaitable[None]]
TimeProvider = Callable[[], float]
MonitorRequestGetter = Callable[[], dict[str, Any] | None]


class LoginRefreshVerifier:
    SUCCESS_URL_PATTERN = "https://www.c5game.com/user/user/"
    LOGIN_URL_PREFIX = "https://www.c5game.com/login"

    def __init__(
        self,
        *,
        sleep_func: SleepFunc | None = None,
        time_provider: TimeProvider | None = None,
        refresh_timeout_seconds: float = 10.0,
        poll_interval_seconds: float = 0.5,
    ) -> None:
        self._sleep = sleep_func or asyncio.sleep
        self._time = time_provider or time.time
        self._refresh_timeout_seconds = float(refresh_timeout_seconds)
        self._poll_interval_seconds = float(poll_interval_seconds)

    async def verify(
        self,
        *,
        driver: Any,
        expected_user_id: str,
        capture_task: asyncio.Task[dict[str, Any] | None] | None,
        monitor_request_getter: MonitorRequestGetter | None = None,
    ) -> dict[str, Any]:
        self._refresh_target_page(driver)
        started_at = self._time()

        while self._time() - started_at <= self._refresh_timeout_seconds:
            if capture_task is not None and not capture_task.done():
                await asyncio.sleep(0)

            current_url = self._current_url(driver)
            if self._is_login_page_url(current_url):
                raise RuntimeError("刷新后跳回登录页")

            network_payload = self._poll_capture_task(capture_task)
            if network_payload is not None:
                user_info = self._extract_user_info_from_request_data(network_payload)
                if user_info is not None:
                    self._assert_user_match(expected_user_id, str(user_info.get("userId") or ""))
                    cookie_raw = self._extract_cookie_from_request_data(network_payload)
                    if not cookie_raw:
                        cookie_raw = self._serialize_browser_cookies(driver)
                    self._assert_key_cookies(cookie_raw)
                    return {
                        "probe": "network",
                        "user_info": user_info,
                        "cookie_raw": cookie_raw,
                    }

            monitor_payload = monitor_request_getter() if monitor_request_getter else None
            if monitor_payload is not None:
                user_info = self._extract_user_info_from_request_data(monitor_payload)
                if user_info is not None:
                    self._assert_user_match(expected_user_id, str(user_info.get("userId") or ""))
                    cookie_raw = self._extract_cookie_from_request_data(monitor_payload)
                    if not cookie_raw:
                        cookie_raw = self._serialize_browser_cookies(driver)
                    self._assert_key_cookies(cookie_raw)
                    return {
                        "probe": "monitor",
                        "user_info": user_info,
                        "cookie_raw": cookie_raw,
                    }

            if self.SUCCESS_URL_PATTERN in current_url:
                user_info = self._extract_user_info_directly(driver)
                if user_info is not None and user_info.get("userId"):
                    self._assert_user_match(expected_user_id, str(user_info.get("userId") or ""))
                    cookie_raw = self._serialize_browser_cookies(driver)
                    self._assert_key_cookies(cookie_raw)
                    return {
                        "probe": "page",
                        "user_info": user_info,
                        "cookie_raw": cookie_raw,
                    }

            if self._poll_interval_seconds > 0:
                await self._sleep(self._poll_interval_seconds)
            else:
                await self._sleep(0)

        raise RuntimeError("刷新后登录验真失败")

    @classmethod
    def _refresh_target_page(cls, driver: Any) -> None:
        refresh = getattr(driver, "refresh", None)
        if callable(refresh):
            refresh()
            return
        driver.get(cls.SUCCESS_URL_PATTERN)

    @staticmethod
    def _poll_capture_task(
        task: asyncio.Task[dict[str, Any] | None] | None,
    ) -> dict[str, Any] | None:
        if task is None or not task.done() or task.cancelled():
            return None
        try:
            result = task.result()
        except Exception:
            return None
        return result if isinstance(result, dict) else None

    @staticmethod
    def _current_url(driver: Any) -> str:
        try:
            return str(getattr(driver, "current_url", "") or "")
        except Exception:
            return ""

    @classmethod
    def _is_login_page_url(cls, url: str) -> bool:
        return bool(url) and url.startswith(cls.LOGIN_URL_PREFIX)

    @staticmethod
    def _extract_user_info_from_request_data(request_data: dict[str, Any] | None) -> dict[str, Any] | None:
        if not request_data:
            return None
        response_text = str(request_data.get("response") or "")
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
            "nickName": str(personal_data.get("nickName") or ""),
            "userName": str(personal_data.get("userName") or ""),
            "avatar": str(personal_data.get("avatar") or ""),
            "level": personal_data.get("level") or 0,
        }

    @staticmethod
    def _extract_user_info_directly(driver: Any) -> dict[str, Any] | None:
        try:
            page_source = str(getattr(driver, "page_source", "") or "")
        except Exception:
            return None

        user_id = None
        for pattern in (
            r'"userId":\s*"?(?P<user_id>\d+)"?',
            r'userId["\']?\s*:\s*["\']?(?P<user_id>\d+)',
        ):
            match = re.search(pattern, page_source)
            if match:
                user_id = match.group("user_id")
                break

        nick_name = None
        for pattern in (
            r'"nickName":\s*"(?P<nick_name>[^"]+)"',
            r'nickName["\']?\s*:\s*["\'](?P<nick_name>[^"\']+)["\']',
        ):
            match = re.search(pattern, page_source)
            if match:
                nick_name = match.group("nick_name")
                break

        if not user_id:
            return None
        return {
            "userId": str(user_id),
            "nickName": str(nick_name or ""),
            "userName": "",
            "avatar": "",
            "level": 0,
        }

    @staticmethod
    def _extract_cookie_from_request_data(request_data: dict[str, Any] | None) -> str:
        if not request_data:
            return ""
        return str(request_data.get("cookies") or request_data.get("Cookie") or "")

    @staticmethod
    def _serialize_browser_cookies(driver: Any) -> str:
        try:
            browser_cookies = driver.get_cookies()
        except Exception:
            return ""

        parts: list[str] = []
        for item in browser_cookies or []:
            name = str(item.get("name") or "")
            value = str(item.get("value") or "")
            if name:
                parts.append(f"{name}={value}")
        return "; ".join(parts)

    @staticmethod
    def _assert_user_match(expected_user_id: str, actual_user_id: str) -> None:
        if expected_user_id and actual_user_id and expected_user_id != actual_user_id:
            raise RuntimeError("刷新后用户不一致")

    @staticmethod
    def _assert_key_cookies(cookie_raw: str) -> None:
        names = {
            item.split("=", 1)[0].strip()
            for item in cookie_raw.split(";")
            if "=" in item
        }
        if "NC5_accessToken" in names and "NC5_deviceId" not in names:
            raise RuntimeError("无法获取NC5_deviceId")
        if "NC5_accessToken" not in names or "NC5_deviceId" not in names:
            raise RuntimeError("刷新后关键Cookie缺失")
