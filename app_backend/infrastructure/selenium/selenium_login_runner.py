from __future__ import annotations

import asyncio
import json
import os
import random
import re
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

ProgressCallback = Callable[[str], Awaitable[None] | None]
BrowserFactory = Callable[[str | None], "BrowserSession | Any"]
SleepFunc = Callable[[float], Awaitable[None]]
TimeProvider = Callable[[], float]
MillisProvider = Callable[[], int]
RandomIntProvider = Callable[[int, int], int]
BrowserAliveChecker = Callable[[Any], bool]


async def _noop_emit(_: str) -> None:
    return None


async def _safe_emit(callback: ProgressCallback, state: str) -> None:
    result = callback(state)
    if asyncio.iscoroutine(result):
        await result


@dataclass(slots=True)
class BrowserSession:
    driver: Any
    cleanup: Callable[[], None] | None = None


class SeleniumLoginRunner:
    LOGIN_URL = "https://www.c5game.com/login?return_url=%2Fuser%2Fuser%2F"
    SUCCESS_URL_PATTERN = "https://www.c5game.com/user/user/"

    def __init__(
        self,
        *,
        browser_factory: BrowserFactory | None = None,
        sleep_func: SleepFunc | None = None,
        time_provider: TimeProvider | None = None,
        now_ms_provider: MillisProvider | None = None,
        random_int_provider: RandomIntProvider | None = None,
        browser_alive_checker: BrowserAliveChecker | None = None,
        login_timeout_seconds: float = 300.0,
        page_ready_wait_seconds: float = 5.0,
        post_success_wait_seconds: float = 3.0,
        login_poll_interval_seconds: float = 2.0,
        browser_close_poll_seconds: float = 1.0,
    ) -> None:
        self._browser_factory = browser_factory or self._create_default_browser
        self._sleep = sleep_func or asyncio.sleep
        self._time = time_provider or time.time
        self._now_ms = now_ms_provider or (lambda: int(time.time() * 1000))
        self._random_int = random_int_provider or random.randint
        self._browser_alive_checker = browser_alive_checker or self._is_browser_alive
        self._login_timeout_seconds = float(login_timeout_seconds)
        self._page_ready_wait_seconds = float(page_ready_wait_seconds)
        self._post_success_wait_seconds = float(post_success_wait_seconds)
        self._login_poll_interval_seconds = float(login_poll_interval_seconds)
        self._browser_close_poll_seconds = float(browser_close_poll_seconds)

    async def run(
        self,
        *,
        proxy_url: str | None,
        emit_state: ProgressCallback | None = None,
    ) -> dict[str, object]:
        callback = emit_state or _noop_emit
        browser = self._browser_factory(proxy_url)
        session = browser if isinstance(browser, BrowserSession) else BrowserSession(driver=browser)
        driver = session.driver
        browser_closed_before_login = False

        try:
            self._setup_request_monitor(driver)
            driver.get(self.LOGIN_URL)
            if self._page_ready_wait_seconds > 0:
                await self._sleep(self._page_ready_wait_seconds)

            await _safe_emit(callback, "waiting_for_scan")

            request_data: dict[str, Any] | None = None
            login_detected = False
            started_at = self._time()

            while self._time() - started_at < self._login_timeout_seconds:
                if not self._browser_alive_checker(driver):
                    browser_closed_before_login = True
                    raise RuntimeError("用户取消了登录")

                current_url = str(getattr(driver, "current_url", "") or "")
                request_data = self._read_monitor_request_data(driver)
                if request_data and self._extract_user_info_from_request_data(request_data):
                    login_detected = True
                    break

                if self.SUCCESS_URL_PATTERN in current_url:
                    login_detected = True
                    break

                if self._login_poll_interval_seconds > 0:
                    await self._sleep(self._login_poll_interval_seconds)
                else:
                    await self._sleep(0)

            if not login_detected:
                raise RuntimeError("登录失败或超时")

            if self._post_success_wait_seconds > 0:
                await self._sleep(self._post_success_wait_seconds)

            if request_data is None:
                request_data = self._read_monitor_request_data(driver)

            user_info = self._extract_user_info_from_request_data(request_data)
            if not user_info:
                user_info = await self._extract_user_info_directly(driver)
            if not user_info or not user_info.get("userId"):
                raise RuntimeError("无法提取用户信息")

            cookie_raw = self._extract_cookie_raw(request_data, driver)
            if not cookie_raw:
                raise RuntimeError("无法获取Cookie")
            cookie_raw = self._rewrite_device_id(cookie_raw)

            await _safe_emit(callback, "captured_login_info")
            await _safe_emit(callback, "waiting_for_browser_close")

            while self._browser_alive_checker(driver):
                if self._browser_close_poll_seconds > 0:
                    await self._sleep(self._browser_close_poll_seconds)
                else:
                    await self._sleep(0)

            return {
                "user_info": user_info,
                "cookie_raw": cookie_raw,
                "c5_user_id": str(user_info.get("userId") or ""),
                "c5_nick_name": str(user_info.get("nickName") or ""),
            }
        except RuntimeError:
            raise
        except Exception as exc:
            if browser_closed_before_login or self._is_browser_error(exc):
                raise RuntimeError("用户取消了登录") from exc
            raise RuntimeError(f"登录过程中出错: {exc}") from exc
        finally:
            self._safe_close_browser(driver)
            if session.cleanup is not None:
                try:
                    session.cleanup()
                except Exception:
                    pass

    @classmethod
    def _build_monitor_script(cls) -> str:
        return r"""
(function() {
    'use strict';
    if (window.__C5GAME_USERINFO_MONITOR__) {
        return;
    }

    window.__C5GAME_USERINFO_MONITOR__ = {
        requestData: null,
        loginDetected: false,
        lastUrl: location.href
    };

    const monitor = window.__C5GAME_USERINFO_MONITOR__;

    const captureResponse = async (url, response) => {
        try {
            const text = await response.clone().text();
            const payload = {
                response: text,
                cookies: document.cookie,
                url: url,
                timestamp: Date.now(),
                hasUserData: false
            };
            try {
                const parsed = JSON.parse(text);
                payload.hasUserData = !!(parsed.success && parsed.data && parsed.data.personalData);
            } catch (e) {}
            monitor.requestData = payload;
        } catch (e) {}
        return response;
    };

    const isUserInfoUrl = (url) => {
        return !!url && (url.includes('/api/v1/user/v2/userInfo') || url.includes('user/v2/userInfo'));
    };

    const originalFetch = window.fetch;
    window.fetch = function(input, init) {
        const url = input && input.url ? input.url : input;
        const responsePromise = originalFetch.apply(this, arguments);
        if (!isUserInfoUrl(url)) {
            return responsePromise;
        }
        return responsePromise.then((response) => captureResponse(url, response));
    };

    if (window.XMLHttpRequest) {
        const originalOpen = XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open = function(method, url) {
            this.__c5_url = url;
            return originalOpen.apply(this, arguments);
        };
        const originalSend = XMLHttpRequest.prototype.send;
        XMLHttpRequest.prototype.send = function() {
            if (isUserInfoUrl(this.__c5_url)) {
                this.addEventListener('load', function() {
                    if (this.status === 200) {
                        monitor.requestData = {
                            response: this.responseText,
                            cookies: document.cookie,
                            url: this.__c5_url,
                            timestamp: Date.now(),
                            hasUserData: true
                        };
                    }
                });
            }
            return originalSend.apply(this, arguments);
        };
    }

    setInterval(() => {
        const currentUrl = location.href;
        if (currentUrl !== monitor.lastUrl) {
            monitor.lastUrl = currentUrl;
        }
        if (currentUrl.includes('/user/user/')) {
            monitor.loginDetected = true;
        }
    }, 1000);
})();
"""

    def _setup_request_monitor(self, driver: Any) -> None:
        script = self._build_monitor_script()
        try:
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": script})
        except Exception:
            pass
        try:
            driver.execute_script(script)
        except Exception:
            pass

    @staticmethod
    def _read_monitor_request_data(driver: Any) -> dict[str, Any] | None:
        try:
            payload = driver.execute_script(
                """
                try {
                    if (typeof window.__C5GAME_USERINFO_MONITOR__ !== 'undefined' &&
                        window.__C5GAME_USERINFO_MONITOR__.requestData) {
                        return window.__C5GAME_USERINFO_MONITOR__.requestData;
                    }
                    return null;
                } catch (e) {
                    return null;
                }
                """
            )
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

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

    async def _extract_user_info_directly(self, driver: Any) -> dict[str, Any] | None:
        try:
            page_source = str(getattr(driver, "page_source", "") or "")
        except Exception:
            return None

        user_id = None
        for pattern in (
            r'"userId":\s*"?(?P<user_id>\d+)"?',
            r'userId["\']?\s*:\s*["\']?(?P<user_id>\d+)',
            r'user["\']?\s*id["\']?\s*:\s*["\']?(?P<user_id>\d+)',
        ):
            match = re.search(pattern, page_source)
            if match:
                user_id = match.group("user_id")
                break

        nick_name = None
        for pattern in (
            r'"nickName":\s*"(?P<nick_name>[^"]+)"',
            r'nickName["\']?\s*:\s*["\'](?P<nick_name>[^"\']+)["\']',
            r'nickname["\']?\s*:\s*["\'](?P<nick_name>[^"\']+)["\']',
        ):
            match = re.search(pattern, page_source)
            if match:
                nick_name = match.group("nick_name")
                break

        if not user_id and not nick_name:
            return None

        return {
            "userId": str(user_id or ""),
            "nickName": str(nick_name or "未知"),
            "userName": "",
            "avatar": "",
            "level": 0,
        }

    @staticmethod
    def _extract_cookie_raw(request_data: dict[str, Any] | None, driver: Any) -> str:
        if request_data:
            cookie_raw = str(request_data.get("cookies") or request_data.get("Cookie") or "")
            if cookie_raw:
                return cookie_raw

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

    def _rewrite_device_id(self, cookie_raw: str) -> str:
        cookie_items = [item.strip() for item in cookie_raw.split(";")]
        cookie_dict: dict[str, str] = {}
        order: list[str] = []
        for item in cookie_items:
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            key = key.strip()
            if not key:
                continue
            if key not in cookie_dict:
                order.append(key)
            cookie_dict[key] = value.strip()

        if "NC5_deviceId" not in cookie_dict:
            raise RuntimeError("无法获取NC5_deviceId")

        new_device_id = f"{self._now_ms()}{self._random_int(0, 99999):05d}"
        cookie_dict["NC5_deviceId"] = new_device_id
        return "; ".join(f"{key}={cookie_dict[key]}" for key in order)

    @staticmethod
    def _is_browser_alive(driver: Any) -> bool:
        if driver is None:
            return False
        try:
            _ = driver.session_id
            return True
        except Exception:
            return False

    @staticmethod
    def _is_browser_error(exception: Exception) -> bool:
        error_str = str(exception).lower()
        return any(
            keyword in error_str
            for keyword in (
                "web view not found",
                "session not found",
                "no such window",
                "invalid session id",
                "chrome not reachable",
                "target frame detached",
                "browser disconnected",
            )
        )

    @staticmethod
    def _safe_close_browser(driver: Any) -> None:
        if driver is None:
            return
        try:
            _ = driver.session_id
        except Exception:
            return
        try:
            driver.quit()
        except Exception:
            return

    @classmethod
    def _create_default_browser(cls, proxy_url: str | None) -> BrowserSession:
        from selenium import webdriver
        from selenium.webdriver.edge.options import Options
        from selenium.webdriver.edge.service import Service

        os.environ["WDM_LOG_LEVEL"] = "0"
        os.environ["WEBDRIVER_CHROME_LOG"] = "false"
        os.environ["EDGE_LOG_LEVEL"] = "0"

        options = Options()
        options.add_argument("--log-level=3")
        options.add_argument("--silent")
        options.add_argument("--disable-logging")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        options.add_argument("--disable-component-extensions-with-background-pages")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-notifications")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1200,800")
        options.add_argument("--disable-gpu")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--disable-web-security")
        options.add_argument(
            f"--user-agent={random.choice(cls._default_user_agents())}"
        )

        cleanup_callbacks: list[Callable[[], None]] = []
        if proxy_url and proxy_url != "direct":
            plugin_path = cls._build_proxy_plugin(proxy_url)
            if plugin_path is not None:
                options.add_extension(plugin_path)
                cleanup_callbacks.append(lambda path=plugin_path: cls._remove_temp_file(path))
            else:
                pure_proxy = re.sub(r"https?://[^@]*@", "", proxy_url)
                pure_proxy = re.sub(r"^https?://", "", pure_proxy)
                options.add_argument(f"--proxy-server={pure_proxy}")

        project_root = Path(__file__).resolve().parents[3]
        driver_path = project_root / "msedgedriver.exe"
        if not driver_path.exists():
            raise RuntimeError(f"未找到Edge驱动: {driver_path}")

        service = Service(str(driver_path))
        driver = webdriver.Edge(service=service, options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        if proxy_url and proxy_url != "direct":
            try:
                driver.set_page_load_timeout(10)
                driver.get("http://httpbin.org/ip")
            except Exception:
                pass

        return BrowserSession(driver=driver, cleanup=lambda: cls._run_cleanups(cleanup_callbacks))

    @staticmethod
    def _default_user_agents() -> list[str]:
        return [
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 "
                "Safari/537.36 Edg/120.0.0.0"
            ),
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 "
                "Safari/537.36 Edg/119.0.0.0"
            ),
        ]

    @classmethod
    def _build_proxy_plugin(cls, proxy_url: str) -> str | None:
        pattern = r"^(?:https?://)?(?:(.+?):(.+?)@)?([^:]+)(?::(\d+))?$"
        stripped_proxy = proxy_url.replace("http://", "").replace("https://", "")
        match = re.match(pattern, stripped_proxy)
        if not match:
            return None

        username, password, host, port = match.groups()
        port = port or "80"
        manifest_json = """
        {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "Proxy Auth",
            "permissions": [
                "proxy", "tabs", "unlimitedStorage", "storage",
                "<all_urls>", "webRequest", "webRequestBlocking"
            ],
            "background": {"scripts": ["background.js"]}
        }
        """

        if username and password:
            background_js = f"""
            var config = {{
                mode: "fixed_servers",
                rules: {{
                    singleProxy: {{
                        scheme: "http",
                        host: "{host}",
                        port: parseInt({port})
                    }},
                    bypassList: ["localhost", "127.0.0.1", "<local>"]
                }}
            }};
            chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
            function callbackFn(details) {{
                return {{
                    authCredentials: {{
                        username: "{username}",
                        password: "{password}"
                    }}
                }};
            }}
            chrome.webRequest.onAuthRequired.addListener(
                callbackFn, {{urls: ["<all_urls>"]}}, ["blocking"]
            );
            """
        else:
            background_js = f"""
            var config = {{
                mode: "fixed_servers",
                rules: {{
                    singleProxy: {{
                        scheme: "http",
                        host: "{host}",
                        port: parseInt({port})
                    }},
                    bypassList: ["localhost", "127.0.0.1", "<local>"]
                }}
            }};
            chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
            """

        with tempfile.NamedTemporaryFile(
            prefix="proxy_auth_plugin_",
            suffix=".zip",
            delete=False,
        ) as temp_file:
            temp_path = temp_file.name

        with zipfile.ZipFile(temp_path, "w") as archive:
            archive.writestr("manifest.json", manifest_json)
            archive.writestr("background.js", background_js)
        return temp_path

    @staticmethod
    def _remove_temp_file(path: str) -> None:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception:
            return

    @staticmethod
    def _run_cleanups(callbacks: list[Callable[[], None]]) -> None:
        for callback in callbacks:
            try:
                callback()
            except Exception:
                continue
