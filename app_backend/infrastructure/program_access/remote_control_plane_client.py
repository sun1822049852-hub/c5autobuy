from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import httpx


@dataclass(frozen=True, slots=True)
class RemoteMessageResult:
    message: str
    expires_in_seconds: int | None = None


@dataclass(frozen=True, slots=True)
class RemoteAuthBundle:
    refresh_token: str
    snapshot: dict[str, object]
    signature: str
    kid: str


@dataclass(frozen=True, slots=True)
class RemoteAuthResult:
    message: str
    auth_bundle: RemoteAuthBundle
    user: dict[str, object]


@dataclass(frozen=True, slots=True)
class RemoteRuntimePermit:
    snapshot: dict[str, object]
    signature: str
    kid: str


@dataclass(frozen=True, slots=True)
class RemotePermitResult:
    message: str
    permit: RemoteRuntimePermit


@dataclass(frozen=True, slots=True)
class RemoteRegisterResult:
    message: str
    user: dict[str, object]


@dataclass(frozen=True, slots=True)
class _JsonPayload:
    status_code: int
    data: dict[str, object]


class RemoteControlPlaneError(RuntimeError):
    def __init__(
        self,
        *,
        status_code: int,
        reason: str,
        message: str,
        payload: dict[str, object] | None = None,
    ) -> None:
        super().__init__(f"{status_code} {reason}: {message}")
        self.status_code = status_code
        self.reason = reason
        self.message = message
        self.payload = payload or {}


class RemoteControlPlaneTransportError(RuntimeError):
    pass


class _InvalidResponseShapeError(ValueError):
    pass


class RemoteControlPlaneClient:
    def __init__(
        self,
        *,
        base_url: str,
        client: httpx.Client | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> RemoteControlPlaneClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def send_register_code(self, email: str) -> RemoteMessageResult:
        payload = self._post("/api/auth/email/send-code", {"email": email})
        try:
            return RemoteMessageResult(
                message="注册验证码已发送",
                expires_in_seconds=_optional_int(payload.data.get("expires_in_seconds")),
            )
        except _InvalidResponseShapeError as exc:
            raise _invalid_response_error(payload.status_code, str(exc), payload.data) from exc

    def fetch_public_key_pem(self) -> str:
        payload = self._get("/api/auth/public-key")
        try:
            return _require_str(payload.data.get("public_key_pem"), field_name="public_key_pem")
        except _InvalidResponseShapeError as exc:
            raise _invalid_response_error(payload.status_code, str(exc), payload.data) from exc

    def register(
        self,
        *,
        email: str,
        code: str,
        username: str,
        password: str,
    ) -> RemoteRegisterResult:
        payload = self._post(
            "/api/auth/register",
            {
                "email": email,
                "code": code,
                "username": username,
                "password": password,
            },
        )
        try:
            return RemoteRegisterResult(
                message="注册成功",
                user=_require_dict(payload.data.get("user"), field_name="user"),
            )
        except _InvalidResponseShapeError as exc:
            raise _invalid_response_error(payload.status_code, str(exc), payload.data) from exc

    def login(
        self,
        *,
        username: str,
        password: str,
        device_id: str,
    ) -> RemoteAuthResult:
        payload = self._post(
            "/api/auth/login",
            {
                "username": username,
                "password": password,
                "device_id": device_id,
            },
        )
        return self._build_auth_result(payload, message="登录成功")

    def refresh(self, *, refresh_token: str, device_id: str) -> RemoteAuthResult:
        payload = self._post(
            "/api/auth/refresh",
            {
                "refresh_token": refresh_token,
                "device_id": device_id,
            },
        )
        return self._build_auth_result(payload, message="刷新成功")

    def logout(self, *, refresh_token: str) -> RemoteMessageResult:
        self._post("/api/auth/logout", {"refresh_token": refresh_token})
        return RemoteMessageResult(message="已退出登录")

    def send_reset_code(self, email: str) -> RemoteMessageResult:
        payload = self._post("/api/auth/password/send-reset-code", {"email": email})
        try:
            return RemoteMessageResult(
                message="密码重置验证码已发送",
                expires_in_seconds=_optional_int(payload.data.get("expires_in_seconds")),
            )
        except _InvalidResponseShapeError as exc:
            raise _invalid_response_error(payload.status_code, str(exc), payload.data) from exc

    def reset_password(
        self,
        *,
        email: str,
        code: str,
        new_password: str,
    ) -> RemoteMessageResult:
        self._post(
            "/api/auth/password/reset",
            {
                "email": email,
                "code": code,
                "new_password": new_password,
            },
        )
        return RemoteMessageResult(message="密码已重置")

    def request_runtime_permit(
        self,
        *,
        refresh_token: str,
        device_id: str,
        action: str = "runtime.start",
    ) -> RemotePermitResult:
        payload = self._post(
            "/api/auth/runtime-permit",
            {
                "refresh_token": refresh_token,
                "device_id": device_id,
                "action": action,
            },
        )
        try:
            permit_payload = _require_dict(payload.data.get("permit"), field_name="permit")
            return RemotePermitResult(
                message="运行许可已签发",
                permit=RemoteRuntimePermit(
                    snapshot=_require_dict(permit_payload.get("snapshot"), field_name="permit.snapshot"),
                    signature=_require_str(permit_payload.get("signature"), field_name="permit.signature"),
                    kid=_require_str(permit_payload.get("kid"), field_name="permit.kid"),
                ),
            )
        except _InvalidResponseShapeError as exc:
            raise _invalid_response_error(payload.status_code, str(exc), payload.data) from exc

    def _build_auth_result(
        self,
        payload: _JsonPayload,
        *,
        message: str,
    ) -> RemoteAuthResult:
        try:
            bundle_payload = _require_dict(payload.data.get("access_bundle"), field_name="access_bundle")
            return RemoteAuthResult(
                message=message,
                auth_bundle=RemoteAuthBundle(
                    refresh_token=_require_str(payload.data.get("refresh_token"), field_name="refresh_token"),
                    snapshot=_require_dict(bundle_payload.get("snapshot"), field_name="access_bundle.snapshot"),
                    signature=_require_str(bundle_payload.get("signature"), field_name="access_bundle.signature"),
                    kid=_require_str(bundle_payload.get("kid"), field_name="access_bundle.kid"),
                ),
                user=_require_dict(payload.data.get("user"), field_name="user"),
            )
        except _InvalidResponseShapeError as exc:
            raise _invalid_response_error(payload.status_code, str(exc), payload.data) from exc

    def _post(
        self,
        path: str,
        payload: dict[str, object],
    ) -> _JsonPayload:
        try:
            response = self._client.post(path, json=payload)
        except httpx.HTTPError as exc:
            raise RemoteControlPlaneTransportError(str(exc)) from exc
        return _decode_json_response(response)

    def _get(self, path: str) -> _JsonPayload:
        try:
            response = self._client.get(path)
        except httpx.HTTPError as exc:
            raise RemoteControlPlaneTransportError(str(exc)) from exc
        return _decode_json_response(response)


def _decode_json_response(response: httpx.Response) -> _JsonPayload:
    try:
        data = _decode_json(response)
    except _InvalidResponseShapeError as exc:
        raise _invalid_response_error(response.status_code, str(exc)) from exc
    if response.is_error:
            try:
                raise RemoteControlPlaneError(
                    status_code=response.status_code,
                    reason=_require_str(data.get("reason"), field_name="reason"),
                    message=_require_str(data.get("message"), field_name="message"),
                    payload=data,
                )
            except _InvalidResponseShapeError as exc:
                raise _invalid_response_error(response.status_code, str(exc), data) from exc
    return _JsonPayload(status_code=response.status_code, data=data)


def _decode_json(response: httpx.Response) -> dict[str, object]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise RemoteControlPlaneError(
            status_code=response.status_code,
            reason="invalid_json",
            message="control plane response is not valid JSON",
        ) from exc
    return _require_dict(payload, field_name="response")


def _require_dict(value: object, *, field_name: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise _InvalidResponseShapeError(f"{field_name} must be an object")
    return {str(key): value[key] for key in value}


def _require_str(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _InvalidResponseShapeError(f"{field_name} must be a non-empty string")
    return value


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise _InvalidResponseShapeError("expires_in_seconds must be an integer")
    if isinstance(value, int):
        return value
    raise _InvalidResponseShapeError("expires_in_seconds must be an integer")


def _invalid_response_error(
    status_code: int,
    detail: str,
    payload: dict[str, object] | None = None,
) -> RemoteControlPlaneError:
    return RemoteControlPlaneError(
        status_code=status_code,
        reason="invalid_response",
        message=detail,
        payload=payload,
    )
