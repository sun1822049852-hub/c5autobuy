from __future__ import annotations

import asyncio

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
        page_source: str = "",
        browser_cookies: list[dict[str, str]] | None = None,
    ) -> None:
        self._current_urls = list(current_urls or ["https://www.c5game.com/user/user/"])
        self._current_url_index = 0
        self.page_source = page_source
        self.browser_cookies = list(browser_cookies or [])
        self.refresh_calls = 0

    @property
    def current_url(self) -> str:
        if self._current_url_index >= len(self._current_urls):
            return self._current_urls[-1]
        value = self._current_urls[self._current_url_index]
        self._current_url_index += 1
        return value

    def get_cookies(self) -> list[dict[str, str]]:
        return list(self.browser_cookies)

    def refresh(self) -> None:
        self.refresh_calls += 1


async def _completed_capture_task(payload):
    async def _capture():
        return payload

    task = asyncio.create_task(_capture())
    await asyncio.sleep(0)
    return task


def _network_payload(*, user_id: str = "10001", cookie_raw: str = "foo=bar; NC5_accessToken=token-1; NC5_deviceId=device-1") -> dict[str, object]:
    return {
        "response": (
            '{"success": true, "data": {"personalData": {"userId": "'
            + user_id
            + '", "nickName": "刷新账号"}}}'
        ),
        "cookies": cookie_raw,
        "url": "https://www.c5game.com/api/v1/user/v2/userInfo",
    }


@pytest.mark.asyncio
async def test_login_refresh_verifier_accepts_matching_network_probe():
    from app_backend.infrastructure.browser_runtime.login_refresh_verifier import LoginRefreshVerifier

    clock = FakeClock()
    driver = FakeDriver()
    capture_task = await _completed_capture_task(_network_payload())
    verifier = LoginRefreshVerifier(
        sleep_func=clock.sleep,
        time_provider=clock.time,
        refresh_timeout_seconds=1.0,
        poll_interval_seconds=0.0,
    )

    result = await verifier.verify(
        driver=driver,
        expected_user_id="10001",
        capture_task=capture_task,
    )

    assert result["probe"] == "network"
    assert result["user_info"]["userId"] == "10001"
    assert result["cookie_raw"] == "foo=bar; NC5_accessToken=token-1; NC5_deviceId=device-1"
    assert driver.refresh_calls == 1


@pytest.mark.asyncio
async def test_login_refresh_verifier_falls_back_to_page_probe_when_network_probe_missing():
    from app_backend.infrastructure.browser_runtime.login_refresh_verifier import LoginRefreshVerifier

    clock = FakeClock()
    driver = FakeDriver(
        page_source='{"userId":"10001","nickName":"页面账号"}',
        browser_cookies=[
            {"name": "NC5_accessToken", "value": "token-1"},
            {"name": "NC5_deviceId", "value": "device-1"},
        ],
    )
    verifier = LoginRefreshVerifier(
        sleep_func=clock.sleep,
        time_provider=clock.time,
        refresh_timeout_seconds=1.0,
        poll_interval_seconds=0.0,
    )

    result = await verifier.verify(
        driver=driver,
        expected_user_id="10001",
        capture_task=None,
    )

    assert result["probe"] == "page"
    assert result["user_info"]["nickName"] == "页面账号"
    assert "NC5_accessToken=token-1" in result["cookie_raw"]
    assert driver.refresh_calls == 1


@pytest.mark.asyncio
async def test_login_refresh_verifier_rejects_different_user_after_refresh():
    from app_backend.infrastructure.browser_runtime.login_refresh_verifier import LoginRefreshVerifier

    clock = FakeClock()
    driver = FakeDriver()
    capture_task = await _completed_capture_task(_network_payload(user_id="20002"))
    verifier = LoginRefreshVerifier(
        sleep_func=clock.sleep,
        time_provider=clock.time,
        refresh_timeout_seconds=1.0,
        poll_interval_seconds=0.0,
    )

    with pytest.raises(RuntimeError, match="刷新后用户不一致"):
        await verifier.verify(
            driver=driver,
            expected_user_id="10001",
            capture_task=capture_task,
        )


@pytest.mark.asyncio
async def test_login_refresh_verifier_rejects_missing_key_cookie_after_refresh():
    from app_backend.infrastructure.browser_runtime.login_refresh_verifier import LoginRefreshVerifier

    clock = FakeClock()
    driver = FakeDriver()
    capture_task = await _completed_capture_task(
        _network_payload(cookie_raw="foo=bar; NC5_accessToken=token-1")
    )
    verifier = LoginRefreshVerifier(
        sleep_func=clock.sleep,
        time_provider=clock.time,
        refresh_timeout_seconds=1.0,
        poll_interval_seconds=0.0,
    )

    with pytest.raises(RuntimeError, match="无法获取NC5_deviceId"):
        await verifier.verify(
            driver=driver,
            expected_user_id="10001",
            capture_task=capture_task,
        )


@pytest.mark.asyncio
async def test_login_refresh_verifier_rejects_redirect_back_to_login():
    from app_backend.infrastructure.browser_runtime.login_refresh_verifier import LoginRefreshVerifier

    clock = FakeClock()
    driver = FakeDriver(current_urls=["https://www.c5game.com/login"])
    verifier = LoginRefreshVerifier(
        sleep_func=clock.sleep,
        time_provider=clock.time,
        refresh_timeout_seconds=1.0,
        poll_interval_seconds=0.0,
    )

    with pytest.raises(RuntimeError, match="刷新后跳回登录页"):
        await verifier.verify(
            driver=driver,
            expected_user_id="10001",
            capture_task=None,
        )

