"""
Compatibility shim.

Canonical location:
- c5_layered.infrastructure.query.pipeline
"""

from c5_layered.infrastructure.query.pipeline import (  # noqa: F401
    AccountAttachResult,
    LegacyQueryPipeline,
    QueryMetrics,
)

__all__ = ["AccountAttachResult", "LegacyQueryPipeline", "QueryMetrics"]
