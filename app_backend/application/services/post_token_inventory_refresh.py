from __future__ import annotations


def refresh_inventory_after_token_binding(*, account, purchase_runtime_service) -> None:
    if purchase_runtime_service is None:
        return

    account_id = str(getattr(account, "account_id", "") or "")
    if not account_id:
        return

    cookie_raw = str(getattr(account, "cookie_raw", "") or "")
    if "NC5_accessToken=" not in cookie_raw:
        return

    refresh_inventory_detail = getattr(purchase_runtime_service, "refresh_account_inventory_detail", None)
    if not callable(refresh_inventory_detail):
        return

    try:
        refresh_inventory_detail(account_id)
    except Exception:
        return
