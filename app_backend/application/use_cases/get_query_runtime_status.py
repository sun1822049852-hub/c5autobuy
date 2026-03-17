from __future__ import annotations


class GetQueryRuntimeStatusUseCase:
    def __init__(self, runtime_service) -> None:
        self._runtime_service = runtime_service

    def execute(self) -> dict[str, object]:
        return self._runtime_service.get_status()
