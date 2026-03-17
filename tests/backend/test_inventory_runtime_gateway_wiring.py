from __future__ import annotations


def test_create_app_uses_inventory_refresh_gateway_by_default(tmp_path):
    from app_backend.main import create_app
    from app_backend.infrastructure.purchase.runtime.inventory_refresh_gateway import (
        InventoryRefreshGateway,
    )

    app = create_app(db_path=tmp_path / "app.db")

    assert app.state.purchase_runtime_service._inventory_refresh_gateway_factory is InventoryRefreshGateway


def test_purchase_runtime_package_exports_inventory_refresh_gateway():
    from app_backend.infrastructure.purchase import runtime

    assert hasattr(runtime, "InventoryRefreshGateway")
    assert not hasattr(runtime, "LegacyInventoryRefreshGateway")
