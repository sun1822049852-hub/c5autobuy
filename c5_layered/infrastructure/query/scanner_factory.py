from __future__ import annotations

from types import ModuleType
from typing import Any


class LegacyScannerFactory:
    """
    Resolves legacy scanner classes by logical group type.
    """

    def __init__(self, legacy_module: ModuleType) -> None:
        self._legacy = legacy_module
        self._scanner_map: dict[str, str] = {
            "new": "C5MarketAPIScanner",
            "fast": "C5MarketAPIFastScanner",
            "old": "ProductQueryScanner",
        }

    def get_scanner_class(self, group_type: str) -> type[Any] | None:
        attr = self._scanner_map.get(group_type)
        if not attr:
            return None
        scanner_class = getattr(self._legacy, attr, None)
        if scanner_class is None:
            return None
        return scanner_class
