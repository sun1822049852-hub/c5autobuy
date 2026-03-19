from __future__ import annotations

from dataclasses import dataclass

from c5_layered.application.use_cases import DashboardQueryUseCase, ScanControlUseCase


@dataclass(slots=True)
class ApplicationFacade:
    dashboard: DashboardQueryUseCase
    scan: ScanControlUseCase

