from __future__ import annotations

from .query_executor_router import QueryExecutorRouter


class LegacyScannerAdapter(QueryExecutorRouter):
    """Compatibility alias for the renamed query executor router."""
