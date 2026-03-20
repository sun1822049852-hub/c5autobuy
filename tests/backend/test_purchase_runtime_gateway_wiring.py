from __future__ import annotations


def test_purchase_runtime_service_uses_purchase_execution_gateway_by_default():
    from app_backend.infrastructure.purchase.runtime.purchase_execution_gateway import (
        PurchaseExecutionGateway,
    )
    from app_backend.infrastructure.purchase.runtime.purchase_runtime_service import PurchaseRuntimeService

    service = PurchaseRuntimeService(
        account_repository=type("Repo", (), {"list_accounts": lambda self: []})(),
    )

    assert service._execution_gateway_factory is PurchaseExecutionGateway


def test_purchase_runtime_package_exports_purchase_execution_gateway():
    from app_backend.infrastructure.purchase import runtime

    assert hasattr(runtime, "PurchaseExecutionGateway")
