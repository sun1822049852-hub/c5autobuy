from __future__ import annotations


class DetailAccountSelector:
    def __init__(self, repository) -> None:
        self._repository = repository
        self._next_start_index = 0

    def build_attempt_order(self) -> list[object]:
        candidates = [account for account in self._repository.list_accounts() if self._is_eligible(account)]
        if not candidates:
            raise ValueError("没有可用于商品信息补全的已登录账号")

        start_index = self._next_start_index % len(candidates)
        self._next_start_index = (start_index + 1) % len(candidates)
        return candidates[start_index:] + candidates[:start_index]

    @staticmethod
    def _is_eligible(account: object) -> bool:
        if bool(getattr(account, "disabled", False)):
            return False

        cookie_raw = getattr(account, "cookie_raw", None) or ""
        for raw_part in cookie_raw.split(";"):
            key, _, value = raw_part.strip().partition("=")
            if key == "NC5_accessToken" and bool(value):
                return True
        return False
