from __future__ import annotations

import pytest


class FakeClock:
    def __init__(self) -> None:
        self.current = 0.0

    def time(self) -> float:
        return self.current

    async def sleep(self, seconds: float) -> None:
        self.current += float(seconds)


class FakeDriver:
    def __init__(
        self,
        *,
        current_urls: list[str] | None = None,
        monitor_request_data: dict | None = None,
        page_source: str = "",
        browser_cookies: list[dict[str, str]] | None = None,
    ) -> None:
        self._current_urls = list(current_urls or ["https://www.c5game.com/login"])
        self._current_url_index = 0
        self.monitor_request_data = monitor_request_data
        self.page_source = page_source
        self.browser_cookies = list(browser_cookies or [])
        self.session_id = "session-1"
        self.title = "C5 Login"
        self.opened_urls: list[str] = []
        self.executed_scripts: list[str] = []
        self.cdp_calls: list[tuple[str, dict[str, object]]] = []
        self.quit_called = False
        self.page_load_timeout: float | None = None

    @property
    def current_url(self) -> str:
        if self._current_url_index >= len(self._current_urls):
            return self._current_urls[-1]
        value = self._current_urls[self._current_url_index]
        self._current_url_index += 1
        return value

    def execute_script(self, script: str):
        self.executed_scripts.append(script)
        if "window.__C5GAME_USERINFO_MONITOR__.requestData" in script:
            return self.monitor_request_data
        return None

    def execute_cdp_cmd(self, cmd: str, payload: dict[str, object]):
        self.cdp_calls.append((cmd, payload))
        return {}

    def get(self, url: str) -> None:
        self.opened_urls.append(url)

    def get_cookies(self) -> list[dict[str, str]]:
        return list(self.browser_cookies)

    def set_page_load_timeout(self, seconds: float) -> None:
        self.page_load_timeout = seconds

    def quit(self) -> None:
        self.quit_called = True


def _sequence_checker(values: list[bool]):
    queue = list(values)
    last = queue[-1] if queue else False

    def checker(_driver) -> bool:
        nonlocal last
        if queue:
            last = queue.pop(0)
        return last

    return checker


def _build_monitor_payload(
    *,
    user_id: str = "10001",
    nick_name: str = "测试账号",
    cookie_raw: str = "foo=bar; NC5_accessToken=token-1; NC5_deviceId=old-device",
) -> dict[str, object]:
    return {
        "response": (
            '{"success": true, "data": {"personalData": {"userId": "'
            + user_id
            + '", "nickName": "'
            + nick_name
            + '", "userName": "", "avatar": "", "level": 1}}}'
        ),
        "cookies": cookie_raw,
        "hasUserData": True,
    }


@pytest.mark.asyncio
async def test_selenium_login_runner_returns_capture_after_browser_closed():
    from app_backend.infrastructure.selenium.selenium_login_runner import SeleniumLoginRunner

    states: list[str] = []
    clock = FakeClock()
    driver = FakeDriver(
        current_urls=["https://www.c5game.com/user/user/"],
        monitor_request_data=_build_monitor_payload(),
    )

    runner = SeleniumLoginRunner(
        browser_factory=lambda proxy_url: driver,
        sleep_func=clock.sleep,
        time_provider=clock.time,
        now_ms_provider=lambda: 1700000000123,
        random_int_provider=lambda _start, _end: 42,
        browser_alive_checker=_sequence_checker([True, False]),
        page_ready_wait_seconds=0,
        post_success_wait_seconds=0,
        login_poll_interval_seconds=0,
        browser_close_poll_seconds=0,
    )

    result = await runner.run(proxy_url="direct", emit_state=states.append)

    assert result["user_info"]["userId"] == "10001"
    assert result["cookie_raw"] != "foo=bar; NC5_accessToken=token-1; NC5_deviceId=old-device"
    assert "NC5_deviceId=170000000012300042" in result["cookie_raw"]
    assert states == ["waiting_for_scan", "captured_login_info", "waiting_for_browser_close"]
    assert driver.quit_called is True


@pytest.mark.asyncio
async def test_selenium_login_runner_returns_cancelled_when_browser_closed_before_login():
    from app_backend.infrastructure.selenium.selenium_login_runner import SeleniumLoginRunner

    clock = FakeClock()
    driver = FakeDriver(current_urls=["https://www.c5game.com/login"])
    runner = SeleniumLoginRunner(
        browser_factory=lambda proxy_url: driver,
        sleep_func=clock.sleep,
        time_provider=clock.time,
        browser_alive_checker=_sequence_checker([False]),
        page_ready_wait_seconds=0,
        post_success_wait_seconds=0,
        login_poll_interval_seconds=0,
        browser_close_poll_seconds=0,
    )

    with pytest.raises(RuntimeError, match="用户取消了登录"):
        await runner.run(proxy_url="direct")


@pytest.mark.asyncio
async def test_selenium_login_runner_returns_timeout_when_login_not_completed():
    from app_backend.infrastructure.selenium.selenium_login_runner import SeleniumLoginRunner

    clock = FakeClock()
    driver = FakeDriver(current_urls=["https://www.c5game.com/login"] * 5)
    runner = SeleniumLoginRunner(
        browser_factory=lambda proxy_url: driver,
        sleep_func=clock.sleep,
        time_provider=clock.time,
        browser_alive_checker=_sequence_checker([True, True, True, True]),
        login_timeout_seconds=3,
        page_ready_wait_seconds=0,
        post_success_wait_seconds=0,
        login_poll_interval_seconds=2,
        browser_close_poll_seconds=0,
    )

    with pytest.raises(RuntimeError, match="登录失败或超时"):
        await runner.run(proxy_url="direct")


@pytest.mark.asyncio
async def test_selenium_login_runner_falls_back_to_direct_user_info_extraction():
    from app_backend.infrastructure.selenium.selenium_login_runner import SeleniumLoginRunner

    clock = FakeClock()
    driver = FakeDriver(
        current_urls=["https://www.c5game.com/user/user/"],
        monitor_request_data=None,
        page_source='{"userId": 10001, "nickName": "页面账号"}',
        browser_cookies=[
            {"name": "foo", "value": "bar"},
            {"name": "NC5_accessToken", "value": "token-1"},
            {"name": "NC5_deviceId", "value": "old-device"},
        ],
    )
    runner = SeleniumLoginRunner(
        browser_factory=lambda proxy_url: driver,
        sleep_func=clock.sleep,
        time_provider=clock.time,
        now_ms_provider=lambda: 1700000000123,
        random_int_provider=lambda _start, _end: 42,
        browser_alive_checker=_sequence_checker([True, False]),
        page_ready_wait_seconds=0,
        post_success_wait_seconds=0,
        login_poll_interval_seconds=0,
        browser_close_poll_seconds=0,
    )

    result = await runner.run(proxy_url="direct")

    assert result["user_info"]["userId"] == "10001"
    assert result["user_info"]["nickName"] == "页面账号"
    assert "NC5_accessToken=token-1" in result["cookie_raw"]


@pytest.mark.asyncio
async def test_selenium_login_runner_falls_back_to_browser_cookies_when_monitor_cookie_missing():
    from app_backend.infrastructure.selenium.selenium_login_runner import SeleniumLoginRunner

    clock = FakeClock()
    driver = FakeDriver(
        current_urls=["https://www.c5game.com/user/user/"],
        monitor_request_data={
            "response": '{"success": true, "data": {"personalData": {"userId": "10001", "nickName": "测试账号"}}}',
            "cookies": "",
        },
        browser_cookies=[
            {"name": "NC5_accessToken", "value": "token-1"},
            {"name": "NC5_deviceId", "value": "old-device"},
        ],
    )
    runner = SeleniumLoginRunner(
        browser_factory=lambda proxy_url: driver,
        sleep_func=clock.sleep,
        time_provider=clock.time,
        now_ms_provider=lambda: 1700000000123,
        random_int_provider=lambda _start, _end: 42,
        browser_alive_checker=_sequence_checker([True, False]),
        page_ready_wait_seconds=0,
        post_success_wait_seconds=0,
        login_poll_interval_seconds=0,
        browser_close_poll_seconds=0,
    )

    result = await runner.run(proxy_url="direct")

    assert "NC5_accessToken=token-1" in result["cookie_raw"]
    assert "NC5_deviceId=170000000012300042" in result["cookie_raw"]


@pytest.mark.asyncio
async def test_selenium_login_runner_fails_when_cookie_missing_device_id():
    from app_backend.infrastructure.selenium.selenium_login_runner import SeleniumLoginRunner

    clock = FakeClock()
    driver = FakeDriver(
        current_urls=["https://www.c5game.com/user/user/"],
        monitor_request_data=_build_monitor_payload(
            cookie_raw="foo=bar; NC5_accessToken=token-1"
        ),
    )
    runner = SeleniumLoginRunner(
        browser_factory=lambda proxy_url: driver,
        sleep_func=clock.sleep,
        time_provider=clock.time,
        browser_alive_checker=_sequence_checker([True, False]),
        page_ready_wait_seconds=0,
        post_success_wait_seconds=0,
        login_poll_interval_seconds=0,
        browser_close_poll_seconds=0,
    )

    with pytest.raises(RuntimeError, match="无法获取NC5_deviceId"):
        await runner.run(proxy_url="direct")


@pytest.mark.asyncio
async def test_selenium_login_runner_passes_proxy_url_to_browser_factory():
    from app_backend.infrastructure.selenium.selenium_login_runner import SeleniumLoginRunner

    states: list[str] = []
    captured: dict[str, str | None] = {}
    clock = FakeClock()
    driver = FakeDriver(
        current_urls=["https://www.c5game.com/user/user/"],
        monitor_request_data=_build_monitor_payload(),
    )

    def browser_factory(proxy_url: str | None):
        captured["proxy_url"] = proxy_url
        return driver

    runner = SeleniumLoginRunner(
        browser_factory=browser_factory,
        sleep_func=clock.sleep,
        time_provider=clock.time,
        now_ms_provider=lambda: 1700000000123,
        random_int_provider=lambda _start, _end: 42,
        browser_alive_checker=_sequence_checker([True, False]),
        page_ready_wait_seconds=0,
        post_success_wait_seconds=0,
        login_poll_interval_seconds=0,
        browser_close_poll_seconds=0,
    )

    await runner.run(proxy_url="http://127.0.0.1:8888", emit_state=states.append)

    assert captured["proxy_url"] == "http://127.0.0.1:8888"
