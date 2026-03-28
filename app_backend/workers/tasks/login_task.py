from __future__ import annotations

from datetime import datetime

from app_backend.application.use_cases.create_account import CreateAccountUseCase
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


def _find_existing_account_by_c5_user_id(repository, *, c5_user_id: str, exclude_account_id: str) -> object | None:
    normalized_c5_user_id = str(c5_user_id or "").strip()
    if not normalized_c5_user_id:
        return None
    list_accounts = getattr(repository, "list_accounts", None)
    if not callable(list_accounts):
        return None
    for account in list_accounts():
        candidate_account_id = str(getattr(account, "account_id", "") or "")
        if candidate_account_id == str(exclude_account_id or ""):
            continue
        if str(getattr(account, "c5_user_id", "") or "").strip() == normalized_c5_user_id:
            return account
    return None


def _is_api_key_only_account(account) -> bool:
    return bool(str(getattr(account, "api_key", "") or "").strip()) and not bool(
        str(getattr(account, "c5_user_id", "") or "").strip()
    ) and not bool(str(getattr(account, "cookie_raw", "") or "").strip())


def _create_login_result_account(repository) -> object:
    return CreateAccountUseCase(repository).execute(
        remark_name=None,
        browser_proxy_mode="direct",
        browser_proxy_url=None,
        api_proxy_mode="direct",
        api_proxy_url=None,
        api_key=None,
    )


def _schedule_open_api_watch(
    open_api_binding_sync_service,
    *,
    final_account_id: str,
    result: LoginExecutionResult,
    source_account=None,
) -> None:
    if open_api_binding_sync_service is None:
        return
    schedule_watch = getattr(open_api_binding_sync_service, "schedule_account_watch", None)
    if not callable(schedule_watch):
        return

    debugger_address = result.session_payload.get("debugger_address")
    source_account_id = None
    source_api_key = None
    if source_account is not None and _is_api_key_only_account(source_account):
        source_account_id = str(getattr(source_account, "account_id", "") or "") or None
        source_api_key = str(getattr(source_account, "api_key", "") or "").strip() or None

    try:
        schedule_watch(
            final_account_id,
            debugger_address=debugger_address,
            source_account_id=source_account_id,
            source_api_key=source_api_key,
        )
    except TypeError as exc:
        if "source_account_id" not in str(exc) and "source_api_key" not in str(exc):
            raise
        schedule_watch(
            final_account_id,
            debugger_address=debugger_address,
        )


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

        source_account = repository.get_account(account_id)
        if source_account is None:
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

        if source_account.c5_user_id and source_account.c5_user_id != capture.c5_user_id:
            task_manager.set_pending_conflict(
                task_id,
                {
                    "account_id": source_account.account_id,
                    "existing_c5_user_id": source_account.c5_user_id,
                    "existing_c5_nick_name": source_account.c5_nick_name,
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

        matched_account = _find_existing_account_by_c5_user_id(
            repository,
            c5_user_id=capture.c5_user_id,
            exclude_account_id=account_id,
        )
        final_account = matched_account
        if final_account is None and _is_api_key_only_account(source_account):
            final_account = _create_login_result_account(repository)
        if final_account is None:
            final_account = source_account

        task_manager.set_state(task_id, "saving_account")
        now = datetime.now().isoformat(timespec="seconds")
        updated = repository.update_account(
            str(getattr(final_account, "account_id", "") or account_id),
            c5_user_id=capture.c5_user_id,
            c5_nick_name=capture.c5_nick_name,
            cookie_raw=capture.cookie_raw,
            purchase_capability_state=PurchaseCapabilityState.BOUND,
            purchase_pool_state=PurchasePoolState.NOT_CONNECTED,
            last_login_at=now,
            last_error=None,
            updated_at=now,
        )
        bundle_repository.activate_bundle(staged_bundle_id, account_id=updated.account_id)
        bundle_activated = True
        refresh_inventory_after_token_binding(
            account=updated,
            purchase_runtime_service=purchase_runtime_service,
        )
        _schedule_open_api_watch(
            open_api_binding_sync_service,
            final_account_id=updated.account_id,
            result=result,
            source_account=source_account,
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

