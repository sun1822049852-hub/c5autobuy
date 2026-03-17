from __future__ import annotations

import importlib
from typing import Any

from app_backend.infrastructure.query.runtime.runtime_account_adapter import RuntimeAccountAdapter

from .runtime_events import PurchaseExecutionResult


class LegacyPurchaseGateway:
    def __init__(self, *, legacy_module: Any | None = None) -> None:
        self._legacy_module = legacy_module

    async def execute(self, *, account, batch, selected_steam_id: str) -> PurchaseExecutionResult:
        runtime_account = account if isinstance(account, RuntimeAccountAdapter) else RuntimeAccountAdapter(account)
        if not runtime_account.get_x_access_token() or not runtime_account.get_x_device_id():
            return PurchaseExecutionResult.auth_invalid("Not login")

        item_id = str(getattr(batch, "external_item_id", None) or "")
        product_url = str(getattr(batch, "product_url", None) or "")
        if not item_id or not product_url:
            return PurchaseExecutionResult(
                status="invalid_batch",
                purchased_count=0,
                error="Missing external_item_id or product_url",
            )

        if not list(getattr(batch, "product_list", []) or []):
            return PurchaseExecutionResult(
                status="invalid_batch",
                purchased_count=0,
                error="Missing product_list",
            )

        legacy_module = self._get_legacy_module()
        order_creator = legacy_module.OrderCreator(runtime_account)
        payment_processor = legacy_module.PaymentProcessor(runtime_account)

        order_success, order_id, order_error = await order_creator.create_order(
            item_id=item_id,
            total_price=float(getattr(batch, "total_price", 0.0) or 0.0),
            steam_id=selected_steam_id,
            product_list=list(getattr(batch, "product_list", []) or []),
            product_url=product_url,
        )
        if not order_success:
            return self._build_error_result("order_failed", order_error)

        payment_success, success_count, payment_error = await payment_processor.process_payment(
            order_id=order_id,
            pay_amount=float(getattr(batch, "total_price", 0.0) or 0.0),
            steam_id=selected_steam_id,
            product_url=product_url,
        )
        if not payment_success:
            return self._build_error_result("payment_failed", payment_error)

        purchased_count = int(success_count or 0)
        if purchased_count <= 0:
            return PurchaseExecutionResult(status="payment_success_no_items", purchased_count=0)
        return PurchaseExecutionResult.success(purchased_count=purchased_count)

    def _get_legacy_module(self) -> Any:
        if self._legacy_module is None:
            self._legacy_module = importlib.import_module("autobuy")
        return self._legacy_module

    @staticmethod
    def _build_error_result(status: str, error: str | None) -> PurchaseExecutionResult:
        if LegacyPurchaseGateway._is_auth_invalid(error):
            return PurchaseExecutionResult.auth_invalid(error or "Not login")
        return PurchaseExecutionResult(
            status=status,
            purchased_count=0,
            error=error,
        )

    @staticmethod
    def _is_auth_invalid(error: str | None) -> bool:
        normalized = str(error or "").lower()
        return "not login" in normalized or "403" in normalized
