from __future__ import annotations


class PurchaseCapabilityState:
    UNBOUND = "unbound"
    BOUND = "bound"
    EXPIRED = "expired"


class PurchasePoolState:
    NOT_CONNECTED = "not_connected"
    ACTIVE = "active"
    AVAILABLE = "available"
    PAUSED_NO_INVENTORY = "paused_no_inventory"
    PAUSED_NOT_LOGIN = "paused_not_login"
    PAUSED_AUTH_INVALID = "paused_auth_invalid"
