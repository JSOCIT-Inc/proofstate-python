"""Public span filter helpers for ProofState OpenTelemetry export control."""

from proofstate._client.span_filter import (
    KNOWN_LLM_INSTRUMENTATION_SCOPE_PREFIXES,
    is_default_export_span,
    is_genai_span,
    is_known_llm_instrumentor,
    is_proofstate_span,
)

__all__ = [
    "is_default_export_span",
    "is_proofstate_span",
    "is_genai_span",
    "is_known_llm_instrumentor",
    "KNOWN_LLM_INSTRUMENTATION_SCOPE_PREFIXES",
]
