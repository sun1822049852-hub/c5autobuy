from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from app_backend.startup.build_core_home_services import CoreHomeServices, require_core_home_services
from app_backend.startup.build_runtime_full_services import RuntimeFullServices, require_runtime_full_services


@dataclass(frozen=True)
class BrowserActionBuildParams:
    database_path: Path


@dataclass(frozen=True)
class BrowserActionServices:
    account_browser_profile_store: object
    login_adapter: object
    open_api_binding_page_launcher: object


def require_browser_action_services(services: Mapping[str, object]) -> BrowserActionServices:
    return BrowserActionServices(
        account_browser_profile_store=services["account_browser_profile_store"],
        login_adapter=services["login_adapter"],
        open_api_binding_page_launcher=services["open_api_binding_page_launcher"],
    )


def build_browser_action_services(
    *,
    core_services: CoreHomeServices | Mapping[str, object],
    runtime_services: RuntimeFullServices | Mapping[str, object],
    params: BrowserActionBuildParams,
) -> dict[str, object]:
    from app_backend.infrastructure.browser_runtime.account_browser_profile_store import (
        AccountBrowserProfileStore,
    )
    from app_backend.infrastructure.browser_runtime.login_adapter import (
        ManagedEdgeCdpLoginRunner,
        BrowserLoginAdapter,
    )
    from app_backend.infrastructure.browser_runtime.open_api_binding_page_launcher import (
        OpenApiBindingPageLauncher,
    )

    shared = (
        core_services
        if isinstance(core_services, CoreHomeServices)
        else require_core_home_services(core_services)
    )
    _ = (
        runtime_services
        if isinstance(runtime_services, RuntimeFullServices)
        else require_runtime_full_services(runtime_services)
    )
    database_path = Path(params.database_path)

    account_browser_profile_store = AccountBrowserProfileStore(runtime=shared.managed_browser_runtime)
    login_adapter = BrowserLoginAdapter(
        login_runner=ManagedEdgeCdpLoginRunner(
            runtime=shared.managed_browser_runtime,
            profile_store=account_browser_profile_store,
        ).run
    )
    open_api_binding_page_launcher = OpenApiBindingPageLauncher(
        runtime=shared.managed_browser_runtime,
        profile_store=account_browser_profile_store,
        debug_log_path=database_path.parent / "runtime" / "open_api_binding_page_launcher.runtime.jsonl",
    )

    return {
        "account_browser_profile_store": account_browser_profile_store,
        "login_adapter": login_adapter,
        "open_api_binding_page_launcher": open_api_binding_page_launcher,
    }
