from __future__ import annotations

from pathlib import Path

from app_backend.infrastructure.db.base import build_engine, build_session_factory, create_schema
from app_backend.infrastructure.repositories.account_session_bundle_repository import (
    SqliteAccountSessionBundleRepository,
)
from app_backend.infrastructure.session_bundle.models import AccountSessionBundleState


def _build_repository(tmp_path: Path) -> SqliteAccountSessionBundleRepository:
    engine = build_engine(tmp_path / "app.db")
    create_schema(engine)
    return SqliteAccountSessionBundleRepository(
        build_session_factory(engine),
        storage_root=tmp_path / "session-bundles",
    )


def test_bundle_repository_uses_lifecycle_and_only_exposes_active_bundle(tmp_path):
    repository = _build_repository(tmp_path)

    staged = repository.stage_bundle(
        account_id="a1",
        captured_c5_user_id="10001",
        payload={"cookie_raw": "cookie-1"},
    )
    assert staged.state == AccountSessionBundleState.STAGED
    assert repository.get_active_bundle("a1") is None

    verified = repository.mark_bundle_verified(staged.bundle_id)
    assert verified.state == AccountSessionBundleState.VERIFIED
    assert repository.get_active_bundle("a1") is None

    active = repository.activate_bundle(verified.bundle_id, account_id="a1")
    loaded = repository.get_active_bundle("a1")

    assert active.state == AccountSessionBundleState.ACTIVE
    assert loaded is not None
    assert loaded.bundle_id == active.bundle_id
    assert loaded.payload == {"cookie_raw": "cookie-1"}


def test_bundle_repository_supersedes_previous_active_bundle_for_same_account(tmp_path):
    repository = _build_repository(tmp_path)

    first = repository.activate_bundle(
        repository.mark_bundle_verified(
            repository.stage_bundle(
                account_id="a1",
                captured_c5_user_id="10001",
                payload={"cookie_raw": "cookie-1"},
            ).bundle_id
        ).bundle_id,
        account_id="a1",
    )
    second = repository.activate_bundle(
        repository.mark_bundle_verified(
            repository.stage_bundle(
                account_id="a1",
                captured_c5_user_id="10001",
                payload={"cookie_raw": "cookie-2"},
            ).bundle_id
        ).bundle_id,
        account_id="a1",
    )

    first_row = repository.get_bundle(first.bundle_id)
    active = repository.get_active_bundle("a1")

    assert first_row is not None
    assert first_row.state == AccountSessionBundleState.SUPERSEDED
    assert active is not None
    assert active.bundle_id == second.bundle_id
    assert active.payload == {"cookie_raw": "cookie-2"}


def test_bundle_repository_delete_account_bundles_marks_rows_deleted_and_removes_payloads(tmp_path):
    repository = _build_repository(tmp_path)

    active = repository.activate_bundle(
        repository.mark_bundle_verified(
            repository.stage_bundle(
                account_id="a1",
                captured_c5_user_id="10001",
                payload={"cookie_raw": "cookie-1"},
            ).bundle_id
        ).bundle_id,
        account_id="a1",
    )
    superseded = repository.activate_bundle(
        repository.mark_bundle_verified(
            repository.stage_bundle(
                account_id="a1",
                captured_c5_user_id="10001",
                payload={"cookie_raw": "cookie-2"},
            ).bundle_id
        ).bundle_id,
        account_id="a1",
    )

    active_path = active.payload_path
    superseded_path = superseded.payload_path

    repository.delete_account_bundles("a1")

    deleted_rows = repository.list_bundles(account_id="a1", include_deleted=True)

    assert repository.get_active_bundle("a1") is None
    assert {bundle.state for bundle in deleted_rows} == {AccountSessionBundleState.DELETED}
    assert not active_path.exists()
    assert not superseded_path.exists()
