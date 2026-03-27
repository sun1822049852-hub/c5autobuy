from __future__ import annotations

from datetime import datetime

from app_backend.application.services.post_token_inventory_refresh import (
    refresh_inventory_after_token_binding,
)
from app_backend.domain.enums.account_states import PurchaseCapabilityState, PurchasePoolState
from app_backend.infrastructure.browser_runtime.login_adapter import LoginCapture
from app_backend.infrastructure.browser_runtime.login_execution_result import (
    CapturedLoginIdentity,
    LoginExecutionResult,
    StagedBundleRef,
)


def _build_error_payload(error: Exception) -> dict[str, object] | None:
    payload: dict[str, object] = {}

    status_code = getattr(error, "status_code", None) or getattr(error, "status", None)
    if status_code is not None:
        payload["status_code"] = status_code

    request_method = getattr(error, "request_method", None) or getattr(error, "method", None)
    if request_method:
        payload["request_method"] = request_method

    request_path = getattr(error, "request_path", None) or getattr(error, "path", None)
    if request_path:
        payload["request_path"] = request_path

    response_text = getattr(error, "response_text", None) or getattr(error, "responseText", None)
    if response_text:
        payload["response_text"] = str(response_text)

    details = getattr(error, "details", None)
    if isinstance(details, dict):
        payload.update(details)

    return payload or None


def _normalize_login_result(payload) -> LoginExecutionResult:
    if isinstance(payload, LoginExecutionResult):
        return payload
    if isinstance(payload, LoginCapture):
        captured_login = CapturedLoginIdentity(
            c5_user_id=payload.c5_user_id,
            c5_nick_name=payload.c5_nick_name,
            cookie_raw=payload.cookie_raw,
        )
        return LoginExecutionResult(
            captured_login=captured_login,
            session_payload=captured_login.to_dict(),
        )
    if isinstance(payload, dict):
        captured_login = CapturedLoginIdentity(
            c5_user_id=str(payload.get("c5_user_id") or ""),
            c5_nick_name=str(payload.get("c5_nick_name") or ""),
            cookie_raw=str(payload.get("cookie_raw") or ""),
        )
        session_payload = dict(payload)
        session_payload.setdefault("c5_user_id", captured_login.c5_user_id)
        session_payload.setdefault("c5_nick_name", captured_login.c5_nick_name)
        session_payload.setdefault("cookie_raw", captured_login.cookie_raw)
        staged_bundle_ref = None
        raw_bundle_ref = payload.get("staged_bundle_ref")
        if isinstance(raw_bundle_ref, dict) and raw_bundle_ref.get("bundle_id"):
            staged_bundle_ref = StagedBundleRef(
                bundle_id=str(raw_bundle_ref.get("bundle_id") or ""),
                state=str(raw_bundle_ref.get("state") or ""),
            )
        return LoginExecutionResult(
            captured_login=captured_login,
            session_payload=session_payload,
            staged_bundle_ref=staged_bundle_ref,
        )
    raise TypeError(f"Unsupported login result payload: {type(payload)!r}")


async def run_login_task(
    *,
    task_id: str,
    account_id: str,
    repository,
    task_manager,
    login_adapter,
    bundle_repository,
    purchase_runtime_service=None,
    open_api_binding_sync_service=None,
) -> None:
    account = repository.get_account(account_id)
    if account is None:
        task_manager.set_error(task_id, "Account not found")
        return

    staged_bundle_id: str | None = None
    bundle_activated = False

    try:
        task_manager.set_state(task_id, "starting_browser")

        async def emit_state(state: str) -> None:
            task_manager.set_state(task_id, state)

        try:
            login_payload = await login_adapter.run_login(
                proxy_url=account.browser_proxy_url,
                account_id=account_id,
                emit_state=emit_state,
            )
        except TypeError as exc:
            if "account_id" not in str(exc):
                raise
            login_payload = await login_adapter.run_login(
                proxy_url=account.browser_proxy_url,
                emit_state=emit_state,
            )
        result = _normalize_login_result(login_payload)
        capture = result.captured_login

        current_account = repository.get_account(account_id)
        if current_account is None:
            if result.staged_bundle_ref is not None:
                bundle_repository.delete_bundle(result.staged_bundle_ref.bundle_id)
            task_manager.set_error(task_id, "Account not found")
            return

        if result.staged_bundle_ref is None:
            staged_bundle = bundle_repository.stage_bundle(
                payload=result.build_bundle_payload(),
                captured_c5_user_id=capture.c5_user_id,
            )
            verified_bundle = bundle_repository.mark_bundle_verified(staged_bundle.bundle_id)
            result.staged_bundle_ref = StagedBundleRef(
                bundle_id=verified_bundle.bundle_id,
                state=verified_bundle.state.value,
            )

        staged_bundle_id = result.staged_bundle_ref.bundle_id

        if current_account.c5_user_id and current_account.c5_user_id != capture.c5_user_id:
            task_manager.set_pending_conflict(
                task_id,
                {
                    "account_id": current_account.account_id,
                    "existing_c5_user_id": current_account.c5_user_id,
                    "existing_c5_nick_name": current_account.c5_nick_name,
                    "captured_login": {
                        "c5_user_id": capture.c5_user_id,
                        "c5_nick_name": capture.c5_nick_name,
                        "cookie_raw": capture.cookie_raw,
                    },
                    "bundle_ref": result.staged_bundle_ref.to_dict(),
                    "actions": [
                        "create_new_account",
                        "replace_with_new_account",
                        "cancel",
                    ],
                },
                message="登录账号与当前账号不一致，需要用户确认",
            )
            return

        task_manager.set_state(task_id, "saving_account")
        now = datetime.now().isoformat(timespec="seconds")
        updated = repository.update_account(
            account_id,
            c5_user_id=capture.c5_user_id,
            c5_nick_name=capture.c5_nick_name,
            cookie_raw=capture.cookie_raw,
            purchase_capability_state=PurchaseCapabilityState.BOUND,
            purchase_pool_state=PurchasePoolState.NOT_CONNECTED,
            last_login_at=now,
            last_error=None,
            updated_at=now,
        )
        bundle_repository.activate_bundle(staged_bundle_id, account_id=account_id)
        bundle_activated = True
        refresh_inventory_after_token_binding(
            account=updated,
            purchase_runtime_service=purchase_runtime_service,
        )
        if open_api_binding_sync_service is not None:
            schedule_watch = getattr(open_api_binding_sync_service, "schedule_account_watch", None)
            if callable(schedule_watch):
                schedule_watch(
                    account_id,
                    debugger_address=result.session_payload.get("debugger_address"),
                )
        task_manager.set_result(
            task_id,
            {
                "account_id": updated.account_id,
                "c5_user_id": updated.c5_user_id,
                "bundle_id": staged_bundle_id,
            },
            state="succeeded",
        )
    except Exception as exc:
        if staged_bundle_id is not None and not bundle_activated:
            bundle_repository.delete_bundle(staged_bundle_id)
        repository.update_account(
            account_id,
            last_error=str(exc),
            updated_at=datetime.now().isoformat(timespec="seconds"),
        )
        task_manager.set_error(task_id, str(exc), payload=_build_error_payload(exc))

