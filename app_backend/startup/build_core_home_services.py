from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Mapping

from app_backend.application.services.account_center_snapshot_service import AccountCenterSnapshotService
from app_backend.application.services.account_balance_service import AccountBalanceService


PROGRAM_ACCESS_APP_NAME = "C5AutoBug"


@dataclass(frozen=True)
class ProgramAccessBuildOptions:
    stage: str | None = None
    app_data_root: Path | None = None
    secret_stage: str | None = None
    secret_platform: str | None = None
    control_plane_base_url: str | None = None
    control_plane_ca_cert_path: Path | None = None
    key_cache_path: Path | None = None
    refresh_interval_seconds: float | None = None
    probe_registration_readiness: bool | None = None
    start_refresh_scheduler: bool = True


@dataclass(frozen=True)
class CoreHomeBuildParams:
    database_path: Path
    program_access: ProgramAccessBuildOptions = field(default_factory=ProgramAccessBuildOptions)


@dataclass(frozen=True)
class CoreHomeServices:
    engine: object
    session_factory: object
    account_repository: object
    managed_browser_runtime: object
    account_session_bundle_repository: object
    program_access_gateway: object
    program_access_stage: str
    program_access_credential_store: object | None
    program_access_secret_store: object | None
    program_access_device_id_store: object | None
    program_access_refresh_scheduler: object | None
    account_update_hub: object
    runtime_update_hub: object
    account_balance_service: object
    account_center_snapshot_service: AccountCenterSnapshotService


def require_core_home_services(services: Mapping[str, object]) -> CoreHomeServices:
    return CoreHomeServices(
        engine=services["engine"],
        session_factory=services["session_factory"],
        account_repository=services["account_repository"],
        managed_browser_runtime=services["managed_browser_runtime"],
        account_session_bundle_repository=services["account_session_bundle_repository"],
        program_access_gateway=services["program_access_gateway"],
        program_access_stage=str(services["program_access_stage"]),
        program_access_credential_store=services.get("program_access_credential_store"),
        program_access_secret_store=services.get("program_access_secret_store"),
        program_access_device_id_store=services.get("program_access_device_id_store"),
        program_access_refresh_scheduler=services.get("program_access_refresh_scheduler"),
        account_update_hub=services["account_update_hub"],
        runtime_update_hub=services["runtime_update_hub"],
        account_balance_service=services["account_balance_service"],
        account_center_snapshot_service=services["account_center_snapshot_service"],
    )


def build_core_home_services(
    params: CoreHomeBuildParams,
    *,
    program_access_services_factory=None,
) -> dict[str, object]:
    from app_backend.infrastructure.db.base import build_engine, build_session_factory, create_schema
    from app_backend.infrastructure.events import AccountUpdateHub
    from app_backend.infrastructure.events.runtime_update_hub import RuntimeUpdateHub
    from app_backend.infrastructure.repositories.account_session_bundle_repository import (
        SqliteAccountSessionBundleRepository,
    )
    from app_backend.infrastructure.repositories.account_repository import SqliteAccountRepository
    from app_backend.infrastructure.browser_runtime.managed_browser_runtime import ManagedBrowserRuntime

    database_path = Path(params.database_path)
    engine = build_engine(database_path)
    create_schema(engine)
    session_factory = build_session_factory(engine)
    account_repository = SqliteAccountRepository(session_factory)
    managed_browser_runtime = ManagedBrowserRuntime.from_environment(
        default_root=database_path.parent / "app-private",
    )
    account_session_bundle_repository = SqliteAccountSessionBundleRepository(
        session_factory,
        storage_root=managed_browser_runtime.bundle_root,
    )
    account_update_hub = AccountUpdateHub()
    runtime_update_hub = RuntimeUpdateHub()
    account_balance_service = AccountBalanceService(
        account_repository=account_repository,
        account_update_hub=account_update_hub,
    )
    account_center_snapshot_service = AccountCenterSnapshotService(account_repository)
    resolved_program_access_stage = _resolve_program_access_stage(params.program_access.stage)
    if program_access_services_factory is None:
        program_access_services_factory = _build_program_access_services
    (
        program_access_gateway,
        program_access_credential_store,
        program_access_secret_store,
        program_access_device_id_store,
        program_access_refresh_scheduler,
    ) = program_access_services_factory(
        stage=resolved_program_access_stage,
        managed_browser_runtime=managed_browser_runtime,
        options=params.program_access,
    )

    return {
        "engine": engine,
        "session_factory": session_factory,
        "account_repository": account_repository,
        "managed_browser_runtime": managed_browser_runtime,
        "account_session_bundle_repository": account_session_bundle_repository,
        "program_access_gateway": program_access_gateway,
        "program_access_stage": resolved_program_access_stage,
        "program_access_credential_store": program_access_credential_store,
        "program_access_secret_store": program_access_secret_store,
        "program_access_device_id_store": program_access_device_id_store,
        "program_access_refresh_scheduler": program_access_refresh_scheduler,
        "program_access_start_refresh_scheduler": bool(params.program_access.start_refresh_scheduler),
        "account_update_hub": account_update_hub,
        "runtime_update_hub": runtime_update_hub,
        "account_balance_service": account_balance_service,
        "account_center_snapshot_service": account_center_snapshot_service,
    }


def _resolve_program_access_stage(explicit_stage: str | None) -> str:
    return str(explicit_stage or os.getenv("C5_PROGRAM_ACCESS_STAGE") or "prepackaging")


def _resolve_program_access_app_data_root(
    explicit_root: Path | None,
    *,
    managed_browser_runtime: object,
) -> Path:
    if explicit_root is not None:
        return Path(explicit_root)

    env_root = os.getenv("C5_PROGRAM_ACCESS_APP_DATA_ROOT")
    if env_root:
        return Path(env_root)

    return Path(getattr(managed_browser_runtime, "app_private_dir"))


def _resolve_program_access_control_plane_base_url(explicit_base_url: str | None) -> str:
    return str(
        explicit_base_url
        or os.getenv("C5_PROGRAM_CONTROL_PLANE_BASE_URL")
        or ""
    ).strip()


def _resolve_program_access_control_plane_ca_cert_path(explicit_path: Path | None) -> Path | None:
    if explicit_path is not None:
        return Path(explicit_path)

    env_path = os.getenv("C5_PROGRAM_CONTROL_PLANE_CA_CERT_PATH")
    if env_path:
        return Path(env_path)

    return None


def _validate_packaged_release_program_access_config(
    *,
    control_plane_base_url: str,
    control_plane_ca_cert_path: Path | None,
) -> None:
    if not control_plane_base_url:
        raise ValueError("Packaged release requires a control plane base url.")
    if not control_plane_base_url.lower().startswith("https://"):
        raise ValueError("Packaged release requires an https control plane base url.")
    if control_plane_ca_cert_path is None:
        raise ValueError("Packaged release requires a control plane CA cert path.")


def _resolve_program_access_key_cache_path(
    explicit_key_cache_path: Path | None,
    *,
    app_data_root: Path,
) -> Path:
    if explicit_key_cache_path is not None:
        return Path(explicit_key_cache_path)

    env_path = os.getenv("C5_PROGRAM_CONTROL_PLANE_KEY_CACHE_PATH")
    if env_path:
        return Path(env_path)

    return Path(app_data_root) / PROGRAM_ACCESS_APP_NAME / "program_access" / "control_plane_public.pem"


def _resolve_program_access_refresh_interval_seconds(explicit_interval: float | None) -> float:
    if explicit_interval is not None:
        return float(explicit_interval)

    raw = os.getenv("C5_PROGRAM_ACCESS_REFRESH_INTERVAL_SECONDS")
    if raw is None:
        return 300.0
    try:
        return float(raw)
    except ValueError:
        return 300.0


def _resolve_program_access_probe_registration_readiness(explicit_flag: bool | None) -> bool:
    if explicit_flag is not None:
        return bool(explicit_flag)

    raw = os.getenv("C5_PROGRAM_ACCESS_PROBE_REGISTRATION_READINESS")
    if raw is None:
        return False
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _build_program_access_bundle_path(app_data_root: Path) -> Path:
    return Path(app_data_root) / PROGRAM_ACCESS_APP_NAME / "program_access" / "bundle.json"


def _build_program_access_services(
    *,
    stage: str,
    managed_browser_runtime: object,
    options: ProgramAccessBuildOptions,
) -> tuple[object, object | None, object | None, object | None, object | None]:
    from app_backend.infrastructure.program_access import (
        EntitlementVerifier,
        FileProgramCredentialStore,
        LocalPassThroughGateway,
        RefreshScheduler,
        RemoteControlPlaneClient,
        RemoteEntitlementGateway,
        build_device_id_store,
        build_secret_store,
    )

    if stage != "packaged_release":
        return LocalPassThroughGateway(), None, None, None, None

    control_plane_base_url = _resolve_program_access_control_plane_base_url(options.control_plane_base_url)
    app_data_root = _resolve_program_access_app_data_root(
        options.app_data_root,
        managed_browser_runtime=managed_browser_runtime,
    )
    secret_stage = str(options.secret_stage or os.getenv("C5_PROGRAM_ACCESS_SECRET_STAGE") or "packaged_release")
    secret_platform = options.secret_platform or os.getenv("C5_PROGRAM_ACCESS_SECRET_PLATFORM")
    device_id_store = build_device_id_store(
        app_name=PROGRAM_ACCESS_APP_NAME,
        app_data_root=app_data_root,
    )
    secret_store = build_secret_store(
        stage=secret_stage,
        app_name=PROGRAM_ACCESS_APP_NAME,
        storage_root=app_data_root,
        platform=secret_platform,
    )
    credential_store = FileProgramCredentialStore(
        _build_program_access_bundle_path(app_data_root),
        secret_store=secret_store,
        device_id_store=device_id_store,
    )
    key_cache_path = _resolve_program_access_key_cache_path(
        options.key_cache_path,
        app_data_root=app_data_root,
    )
    control_plane_ca_cert_path = _resolve_program_access_control_plane_ca_cert_path(
        options.control_plane_ca_cert_path
    )
    _validate_packaged_release_program_access_config(
        control_plane_base_url=control_plane_base_url,
        control_plane_ca_cert_path=control_plane_ca_cert_path,
    )
    verifier = EntitlementVerifier(key_cache_path=key_cache_path)
    remote_client = RemoteControlPlaneClient(
        base_url=control_plane_base_url,
        verify=str(control_plane_ca_cert_path) if control_plane_ca_cert_path else True,
    )
    gateway = RemoteEntitlementGateway(
        remote_client=remote_client,
        verifier=verifier,
        credential_store=credential_store,
        secret_store=secret_store,
        device_id_store=device_id_store,
        stage=stage,
        probe_registration_readiness=_resolve_program_access_probe_registration_readiness(
            options.probe_registration_readiness
        ),
    )
    scheduler = RefreshScheduler(
        gateway=gateway,
        interval_seconds=_resolve_program_access_refresh_interval_seconds(options.refresh_interval_seconds),
    )
    return gateway, credential_store, secret_store, device_id_store, scheduler
