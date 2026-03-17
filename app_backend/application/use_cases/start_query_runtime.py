from __future__ import annotations


class StartQueryRuntimeUseCase:
    def __init__(self, runtime_service) -> None:
        self._runtime_service = runtime_service

    def execute(self, *, config_id: str) -> tuple[bool, str]:
        return self._runtime_service.start(config_id=config_id)
