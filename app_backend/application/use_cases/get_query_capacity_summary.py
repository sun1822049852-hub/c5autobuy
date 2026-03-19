from __future__ import annotations


class GetQueryCapacitySummaryUseCase:
    def __init__(self, service) -> None:
        self._service = service

    def execute(self) -> dict[str, object]:
        return self._service.get_summary()
