from __future__ import annotations

from datetime import datetime
from uuid import uuid4


class AccountNameService:
    @staticmethod
    def build_default_name() -> str:
        suffix = uuid4().hex[:6]
        timestamp = datetime.now().strftime("%H%M%S")
        return f"账号-{timestamp}-{suffix}"
