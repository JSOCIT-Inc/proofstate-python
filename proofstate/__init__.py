"""ProofState Python SDK — observability, evaluation, and prompt management for LLM applications.

Capabilities:

- **Tracing / observability**: `@observe` decorator, `ProofState.start_observation` /
  `start_as_current_observation` context managers, OpenTelemetry-based; integrations
  for OpenAI (`proofstate.openai`) and LangChain (`proofstate.langchain.CallbackHandler`).
- **Trace attributes**: `propagate_attributes` (top-level function) sets user_id,
  session_id, tags, and metadata on all spans in a context.
- **Datasets & experiments**: `ProofState.get_dataset`, `ProofState.run_experiment` for
  offline evaluation and regression testing of prompt/model changes.
- **Evaluation / LLM-as-a-judge**: `Evaluation` results from custom or model-based
  evaluators; scores via `ProofState.create_score` / `span.score`.
- **Prompt management**: `ProofState.get_prompt`, `ProofState.create_prompt` with
  client-side caching and version/label control.
- **Full REST API**: `ProofState.api` (sync) / `ProofState.async_api` (async) clients.

Quickstart:

```python
# env: PROOFSTATE_PUBLIC_KEY, PROOFSTATE_SECRET_KEY, PROOFSTATE_BASE_URL
from proofstate import get_client

client = get_client()

# Create a span using a context manager
with client.start_as_current_observation(as_type="span", name="process-request") as span:
    # Your processing logic here
    span.update(output="Processing complete")

    # Create a nested generation for an LLM call
    with client.start_as_current_observation(as_type="generation", name="llm-response", model="gpt-3.5-turbo") as generation:
        # Your LLM call logic here
        generation.update(output="Generated response")

# All spans are automatically closed when exiting their context blocks

# Flush events in short-lived applications
client.flush()
```

Configuration is via constructor args or environment variables: `PROOFSTATE_PUBLIC_KEY`,
`PROOFSTATE_SECRET_KEY`, `PROOFSTATE_BASE_URL` (defaults to https://proofstate.ai). See `proofstate._client.environment_variables`
for the full list.

Docs: https://proofstate.ai

.. include:: ../README.md
"""

from proofstate.batch_evaluation import (
    BatchEvaluationResult,
    BatchEvaluationResumeToken,
    CompositeEvaluatorFunction,
    EvaluatorInputs,
    EvaluatorStats,
    MapperFunction,
)
from proofstate.experiment import Evaluation, RegressionError, RunnerContext

from ._client import client as _client_module
from ._client.attributes import ProofStateOtelSpanAttributes
from ._client.constants import ObservationTypeLiteral
from ._client.get_client import get_client
from ._client.observe import observe
from ._client.propagation import propagate_attributes
from ._client.span import (
    ProofStateAgent,
    ProofStateChain,
    ProofStateEmbedding,
    ProofStateEvaluator,
    ProofStateEvent,
    ProofStateGeneration,
    ProofStateGuardrail,
    ProofStateRetriever,
    ProofStateSpan,
    ProofStateTool,
)
from ._version import __version__
from .media import ProofStateMedia, ProofStateMediaReference
from .span_filter import (
    KNOWN_LLM_INSTRUMENTATION_SCOPE_PREFIXES,
    is_default_export_span,
    is_genai_span,
    is_known_llm_instrumentor,
    is_proofstate_span,
)
from .types import (
    MaskOtelSpansFunction,
    MaskOtelSpansParams,
    MaskOtelSpansResult,
    OtelSpanData,
    OtelSpanIdentifier,
    OtelSpanPatch,
)

ProofState = _client_module.ProofState

__all__ = [
    "ProofState",
    "ProofStateMedia",
    "ProofStateMediaReference",
    "get_client",
    "observe",
    "propagate_attributes",
    "ObservationTypeLiteral",
    "ProofStateSpan",
    "ProofStateGeneration",
    "ProofStateEvent",
    "ProofStateOtelSpanAttributes",
    "ProofStateAgent",
    "ProofStateTool",
    "ProofStateChain",
    "ProofStateEmbedding",
    "ProofStateEvaluator",
    "ProofStateRetriever",
    "ProofStateGuardrail",
    "Evaluation",
    "EvaluatorInputs",
    "MapperFunction",
    "CompositeEvaluatorFunction",
    "EvaluatorStats",
    "BatchEvaluationResumeToken",
    "BatchEvaluationResult",
    "RunnerContext",
    "RegressionError",
    "__version__",
    "is_default_export_span",
    "is_proofstate_span",
    "is_genai_span",
    "is_known_llm_instrumentor",
    "KNOWN_LLM_INSTRUMENTATION_SCOPE_PREFIXES",
    "MaskOtelSpansFunction",
    "MaskOtelSpansParams",
    "MaskOtelSpansResult",
    "OtelSpanData",
    "OtelSpanIdentifier",
    "OtelSpanPatch",
    "experiment",
    "api",
]
