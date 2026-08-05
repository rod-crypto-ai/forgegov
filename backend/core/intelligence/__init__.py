"""ForgeGov intelligence foundation.

Adapters isolate source-specific integrations. Services combine normalized records,
evidence, and source-health information for the API layer.
"""

from .schemas import Confidence, Evidence, IntelligenceResult, SourceKind

__all__ = ["Confidence", "Evidence", "IntelligenceResult", "SourceKind"]
