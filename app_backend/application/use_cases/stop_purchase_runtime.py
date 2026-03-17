from __future__ import annotations


class StopPurchaseRuntimeUseCase:
    def __init__(self, runtime_service) -> None:
        self._runtime_service = runtime_service

    def execute(self) -> tuple[bool, str]:
        return self._runtime_service.stop()
