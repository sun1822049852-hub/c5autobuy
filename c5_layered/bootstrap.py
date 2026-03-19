from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from c5_layered.application.facade import ApplicationFacade
from c5_layered.application.use_cases import DashboardQueryUseCase, ScanControlUseCase
from c5_layered.infrastructure.repositories import (
    JsonAccountRepository,
    JsonConfigRepository,
    SqliteItemRepository,
)
from c5_layered.infrastructure.runtime import LegacyCliRuntime, LegacyScanRuntime


@dataclass(slots=True)
class AppContainer:
    app: ApplicationFacade
    cli_runtime: LegacyCliRuntime


def build_container(project_root: Path | None = None) -> AppContainer:
    root = project_root or Path(__file__).resolve().parent.parent

    account_repo = JsonAccountRepository(root / "account")
    config_repo = JsonConfigRepository(root / "config" / "product_configs.json")
    item_repo = SqliteItemRepository(root / "csgo_items.db")
    cli_runtime = LegacyCliRuntime(root)
    scan_runtime = LegacyScanRuntime(root)

    dashboard_use_case = DashboardQueryUseCase(account_repo, config_repo, item_repo)
    scan_use_case = ScanControlUseCase(config_repo, scan_runtime)
    app = ApplicationFacade(dashboard=dashboard_use_case, scan=scan_use_case)

    return AppContainer(app=app, cli_runtime=cli_runtime)
