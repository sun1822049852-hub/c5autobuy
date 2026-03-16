from __future__ import annotations

from typing import Any, Protocol


class RuntimeGateway(Protocol):
    def launch_legacy_cli_blocking(self) -> int:
        ...

    def launch_legacy_cli_detached(self) -> None:
        ...


class ScanRuntime(Protocol):
    def start(
        self,
        config_name: str,
        query_only: bool = False,
        purchase_user_ids: list[str] | None = None,
    ) -> tuple[bool, str]:
        ...

    def stop(self) -> tuple[bool, str]:
        ...

    def status(self) -> dict[str, Any]:
        ...

