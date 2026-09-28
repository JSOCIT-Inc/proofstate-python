"""Span processor for ProofState OpenTelemetry integration.

This module defines the ProofStateSpanProcessor class, which extends OpenTelemetry's
BatchSpanProcessor with ProofState-specific functionality. It handles exporting
spans to the ProofState API with proper authentication and filtering.

Key features:
- HTTP-based span export to ProofState API
- Basic authentication with ProofState API keys
- Configurable batch processing behavior
- Project-scoped span filtering to prevent cross-project data leakage
"""

import base64
import logging
import os
import threading
from typing import Callable, Dict, List, Optional, cast

from opentelemetry import context as context_api
from opentelemetry.context import Context
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import ReadableSpan, Span
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.trace import format_span_id, format_trace_id

from proofstate._client.attributes import ProofStateOtelSpanAttributes
from proofstate._client.environment_variables import (
    PROOFSTATE_FLUSH_AT,
    PROOFSTATE_FLUSH_INTERVAL,
    PROOFSTATE_OTEL_TRACES_EXPORT_PATH,
)
from proofstate._client.propagation import (
    _get_proofstate_trace_id_from_baggage,
    _get_propagated_attributes_from_context,
)
from proofstate._client.span_exporter import ProofStateTransformingSpanExporter
from proofstate._client.span_filter import (
    is_app_root_eligible,
    is_default_export_span,
    is_proofstate_span,
)
from proofstate._client.utils import span_formatter
from proofstate._task_manager.media_manager import MediaManager
from proofstate._version import __version__ as proofstate_version
from proofstate.logger import proofstate_logger
from proofstate.types import MaskOtelSpansFunction


class ProofStateSpanProcessor(BatchSpanProcessor):
    """OpenTelemetry span processor that exports spans to the ProofState API.

    This processor extends OpenTelemetry's BatchSpanProcessor with ProofState-specific functionality:
    1. Project-scoped span filtering to prevent cross-project data leakage
    2. Instrumentation scope filtering to block spans from specific libraries/frameworks
    3. Configurable batch processing parameters for optimal performance
    4. HTTP-based span export to the ProofState OTLP endpoint
    5. Debug logging for span processing operations
    6. Authentication with ProofState API using Basic Auth

    The processor is designed to efficiently handle large volumes of spans with
    minimal overhead, while ensuring spans are only sent to the correct project.
    It integrates with OpenTelemetry's standard span lifecycle, adding ProofState-specific
    filtering and export capabilities.
    """

    def __init__(
        self,
        *,
        public_key: str,
        secret_key: str,
        base_url: str,
        timeout: Optional[int] = None,
        flush_at: Optional[int] = None,
        flush_interval: Optional[float] = None,
        blocked_instrumentation_scopes: Optional[List[str]] = None,
        should_export_span: Optional[Callable[[ReadableSpan], bool]] = None,
        additional_headers: Optional[Dict[str, str]] = None,
        span_exporter: Optional[SpanExporter] = None,
        media_manager: Optional[MediaManager] = None,
        mask_otel_spans: Optional[MaskOtelSpansFunction] = None,
    ):
        self.public_key = public_key
        self.blocked_instrumentation_scopes = (
            blocked_instrumentation_scopes
            if blocked_instrumentation_scopes is not None
            else []
        )
        self._should_export_span = should_export_span or is_default_export_span

        self._app_root_lock = threading.Lock()
        self._span_export_expectation_by_id: Dict[str, bool] = {}

        env_flush_at = os.environ.get(PROOFSTATE_FLUSH_AT, None)
        if flush_at is None and env_flush_at is not None:
            flush_at = int(env_flush_at)

        env_flush_interval = os.environ.get(PROOFSTATE_FLUSH_INTERVAL, None)
        if flush_interval is None and env_flush_interval is not None:
            flush_interval = float(env_flush_interval)

        if span_exporter is None:
            basic_auth_header = "Basic " + base64.b64encode(
                f"{public_key}:{secret_key}".encode("utf-8")
            ).decode("ascii")

            # Prepare default headers
            default_headers = {
                "Authorization": basic_auth_header,
                "x-proofstate-sdk-name": "proofstate-python",
                "x-proofstate-sdk-version": proofstate_version,
                "x-proofstate-public-key": public_key,
                "x-proofstate-ingestion-version": "4",
            }

            # Merge additional headers if provided
            headers = {**default_headers, **(additional_headers or {})}

            traces_export_path = os.environ.get(
                PROOFSTATE_OTEL_TRACES_EXPORT_PATH, None
            )

            endpoint = (
                f"{base_url.rstrip('/')}/{traces_export_path.lstrip('/')}"
                if traces_export_path
                else f"{base_url.rstrip('/')}/api/public/otel/v1/traces"
            )

            span_exporter = OTLPSpanExporter(
                endpoint=endpoint,
                headers=headers,
                timeout=timeout,
            )

        if media_manager is not None or mask_otel_spans is not None:
            span_exporter = ProofStateTransformingSpanExporter(
                exporter=span_exporter,
                media_manager=media_manager,
                mask_otel_spans=mask_otel_spans,
            )

        super().__init__(
            span_exporter=span_exporter,
            export_timeout_millis=timeout * 1_000 if timeout else None,
            max_export_batch_size=flush_at,
            schedule_delay_millis=flush_interval * 1_000
            if flush_interval is not None
            else None,
        )

    def on_start(self, span: Span, parent_context: Optional[Context] = None) -> None:
        context = parent_context or context_api.get_current()
        propagated_attributes = _get_propagated_attributes_from_context(context)

        # An explicit prompt set at span creation takes precedence over a propagated one
        existing_attributes = span.attributes or {}
        if ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_NAME in existing_attributes:
            propagated_attributes = {
                key: value
                for key, value in propagated_attributes.items()
                if key
                not in (
                    ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_NAME,
                    ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_VERSION,
                )
            }

        if propagated_attributes:
            span.set_attributes(propagated_attributes)

            proofstate_logger.debug(
                "Propagated %s attributes to span '%s': %s",
                len(propagated_attributes),
                format_span_id(span.context.span_id),
                propagated_attributes,
            )

        try:
            self._mark_app_root_candidate(span=span, parent_context=context)
        except Exception as error:
            proofstate_logger.debug(
                "Trace: app-root start-time check failed. Span will not be marked as app "
                "root | span_name='%s' | Error: %s",
                getattr(span, "name", "<unknown>"),
                error,
            )

        return super().on_start(span, parent_context)

    def on_end(self, span: ReadableSpan) -> None:
        try:
            # Only export spans that belong to the scoped project
            # This is important to not send spans to wrong project in multi-project setups
            if is_proofstate_span(span) and not self._is_proofstate_project_span(span):
                proofstate_logger.debug(
                    "Security: Span rejected - belongs to project '%s' but processor is for "
                    "'%s'. This prevents cross-project data leakage in multi-project "
                    "environments.",
                    span.instrumentation_scope.attributes.get("public_key")
                    if span.instrumentation_scope
                    and span.instrumentation_scope.attributes
                    else None,
                    self.public_key,
                )
                return

            # Do not export spans from blocked instrumentation scopes
            if self._is_blocked_instrumentation_scope(span):
                proofstate_logger.debug(
                    "Trace: Dropping span due to blocked instrumentation scope | "
                    "span_name='%s' | instrumentation_scope='%s'",
                    span.name,
                    self._get_scope_name(span),
                )
                return

            # Apply custom or default span filter
            try:
                should_export = self._should_export_span(span)
            except Exception as error:
                proofstate_logger.error(
                    "Trace: should_export_span callback raised an error. Dropping span "
                    "name='%s' scope='%s'. Error: %s",
                    span.name,
                    self._get_scope_name(span),
                    error,
                )
                return

            if not should_export:
                proofstate_logger.debug(
                    "Trace: Dropping span due to should_export_span filter | span_name='%s' | "
                    "instrumentation_scope='%s'",
                    span.name,
                    self._get_scope_name(span),
                )
                return

            # span_formatter serializes the full span; skip it unless DEBUG is on
            if proofstate_logger.isEnabledFor(logging.DEBUG):
                proofstate_logger.debug(
                    "Trace: Processing span name='%s' | Full details:\n%s",
                    span.name,
                    span_formatter(span),
                )

            super().on_end(span)
        finally:
            self._cleanup_app_root_state(span)

    def _mark_app_root_candidate(self, *, span: Span, parent_context: Context) -> None:
        trace_id = format_trace_id(span.context.trace_id)
        span_id = format_span_id(span.context.span_id)
        parent_span_id = format_span_id(span.parent.span_id) if span.parent else None
        expected_exported = self._is_expected_exported_at_start(span)
        propagated_trace_id = _get_proofstate_trace_id_from_baggage(parent_context)

        with self._app_root_lock:
            parent_expected_exported = (
                parent_span_id is not None
                and self._span_export_expectation_by_id.get(parent_span_id) is True
            )
            suppressed_by_parent_claim = propagated_trace_id == trace_id

            self._span_export_expectation_by_id[span_id] = expected_exported

            mark_app_root = (
                expected_exported
                and is_app_root_eligible(cast(ReadableSpan, span))
                and not parent_expected_exported
                and not suppressed_by_parent_claim
            )

        if mark_app_root:
            span.set_attribute(ProofStateOtelSpanAttributes.IS_APP_ROOT, True)

    def _cleanup_app_root_state(self, span: ReadableSpan) -> None:
        span_id = format_span_id(span.context.span_id)

        with self._app_root_lock:
            self._span_export_expectation_by_id.pop(span_id, None)

    def _is_expected_exported_at_start(self, span: Span) -> bool:
        readable_span = cast(ReadableSpan, span)

        if is_proofstate_span(readable_span) and not self._is_proofstate_project_span(
            readable_span
        ):
            return False

        if self._is_blocked_instrumentation_scope(readable_span):
            return False

        try:
            return bool(self._should_export_span(readable_span))
        except Exception as error:
            proofstate_logger.debug(
                "Trace: should_export_span callback raised during app-root start-time "
                "check. Span will not be marked as app root | span_name='%s' | "
                "instrumentation_scope='%s' | Error: %s",
                readable_span.name,
                self._get_scope_name(readable_span),
                error,
            )

            return False

    def _is_blocked_instrumentation_scope(self, span: ReadableSpan) -> bool:
        return (
            span.instrumentation_scope is not None
            and span.instrumentation_scope.name in self.blocked_instrumentation_scopes
        )

    def _is_proofstate_project_span(self, span: ReadableSpan) -> bool:
        if not is_proofstate_span(span):
            return False

        if span.instrumentation_scope is not None:
            public_key_on_span = (
                span.instrumentation_scope.attributes.get("public_key", None)
                if span.instrumentation_scope.attributes
                else None
            )

            return public_key_on_span == self.public_key

        return False

    @staticmethod
    def _get_scope_name(span: ReadableSpan) -> Optional[str]:
        if span.instrumentation_scope is None:
            return None

        return span.instrumentation_scope.name
