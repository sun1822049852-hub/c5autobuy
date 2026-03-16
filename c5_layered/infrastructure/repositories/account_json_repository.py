from __future__ import annotations

import json
from pathlib import Path

from c5_layered.domain.models import AccountProfile


class JsonAccountRepository:
    def __init__(self, account_dir: Path) -> None:
        self._account_dir = account_dir

    def list_accounts(self) -> list[AccountProfile]:
        if not self._account_dir.exists():
            return []

        accounts: list[AccountProfile] = []
        for file in sorted(self._account_dir.glob("*.json")):
            try:
                with file.open("r", encoding="utf-8") as f:
                    raw = json.load(f)
                account = AccountProfile(
                    user_id=str(raw.get("userId", "")),
                    name=raw.get("name", f"user_{file.stem}"),
                    proxy=raw.get("proxy"),
                    login=bool(raw.get("login", False)),
                    api_key=raw.get("api_key"),
                    created_at=raw.get("created_at"),
                    last_updated=raw.get("last_updated"),
                    file_path=str(file),
                )
                if account.user_id:
                    accounts.append(account)
            except (OSError, json.JSONDecodeError):
                continue
        return accounts

