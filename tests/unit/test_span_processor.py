import logging
from typing import Sequence
from unittest.mock import patch

import pytest
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

import proofstate._client.span_processor as span_processor_module
from proofstate._client.environment_variables import (
    PROOFSTATE_FLUSH_AT,
    PROOFSTATE_FLUSH_INTERVAL,
    PROOFSTATE_OTEL_TRACES_EXPORT_PATH,
)
from proofstate._client.span_processor import ProofStateSpanProcessor
from proofstate._version import __version__


class NoOpSpanExporter(SpanExporter):
    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass


def test_otel_exporter_preserves_server_routing_headers():
    processor = ProofStateSpanProcessor(
        public_key="pk-ps-test",
        secret_key="sk-ps-test",
        base_url="https://proofstate.ai",
    )

    try:
        headers = processor.span_exporter._headers
        assert headers["x-proofstate-sdk-name"] == "proofstate-python"
        assert headers["x-proofstate-sdk-version"] == __version__
        assert __version__.startswith("4.")
        assert headers["x-proofstate-public-key"] == "pk-ps-test"
        assert headers["x-proofstate-ingestion-version"] == "4"
    finally:
        processor.shutdown()


@pytest.mark.parametrize(
    ("custom_path", "expected_endpoint"),
    [
        (None, "https://proofstate.ai/api/public/otel/v1/traces"),
        ("/custom/v1/traces", "https://proofstate.ai/custom/v1/traces"),
    ],
)
def test_otel_endpoint_normalizes_trailing_and_leading_slashes(
    monkeypatch, custom_path, expected_endpoint
):
    if custom_path is None:
        monkeypatch.delenv(PROOFSTATE_OTEL_TRACES_EXPORT_PATH, raising=False)
    else:
        monkeypatch.setenv(PROOFSTATE_OTEL_TRACES_EXPORT_PATH, custom_path)

    processor = ProofStateSpanProcessor(
        public_key="pk-ps-test",
        secret_key="sk-ps-test",
        base_url="https://proofstate.ai/",
    )
    try:
        assert processor.span_exporter._endpoint == expected_endpoint
    finally:
        processor.shutdown()


def test_span_processor_uses_constructor_flush_settings_without_env(monkeypatch):
    monkeypatch.delenv(PROOFSTATE_FLUSH_AT, raising=False)
    monkeypatch.delenv(PROOFSTATE_FLUSH_INTERVAL, raising=False)
    processor = ProofStateSpanProcessor(
        public_key="pk-test",
        secret_key="sk-test",
        base_url="http://localhost:3000",
        flush_at=17,
        flush_interval=2.5,
        span_exporter=NoOpSpanExporter(),
    )

    try:
        assert processor._batch_processor._max_export_batch_size == 17
        assert processor._batch_processor._schedule_delay_millis == 2500
    finally:
        processor.shutdown()


def test_span_processor_uses_env_flush_settings_when_constructor_omits_them(
    monkeypatch,
):
    monkeypatch.setenv(PROOFSTATE_FLUSH_AT, "19")
    monkeypatch.setenv(PROOFSTATE_FLUSH_INTERVAL, "3.25")
    processor = ProofStateSpanProcessor(
        public_key="pk-test",
        secret_key="sk-test",
        base_url="http://localhost:3000",
        span_exporter=NoOpSpanExporter(),
    )

    try:
        assert processor._batch_processor._max_export_batch_size == 19
        assert processor._batch_processor._schedule_delay_millis == 3250
    finally:
        processor.shutdown()


@pytest.fixture
def tracer_with_processor():
    processor = ProofStateSpanProcessor(
        public_key="pk-test",
        secret_key="sk-test",
        base_url="http://localhost:3000",
        span_exporter=NoOpSpanExporter(),
    )
    provider = TracerProvider()
    provider.add_span_processor(processor)
    yield provider.get_tracer("test-instrumentor")
    processor.shutdown()


@pytest.mark.parametrize(
    ("level", "expected_formatter_calls"),
    [(logging.WARNING, 0), (logging.DEBUG, 1)],
)
def test_on_end_formats_span_only_when_debug_enabled(
    caplog, tracer_with_processor, level, expected_formatter_calls
):
    caplog.set_level(level, logger="proofstate")

    with patch.object(
        span_processor_module, "span_formatter", return_value="{}"
    ) as span_formatter:
        # gen_ai.* attribute makes the span pass the default export filter
        with tracer_with_processor.start_as_current_span(
            "llm-call", attributes={"gen_ai.system": "test"}
        ):
            pass

    assert span_formatter.call_count == expected_formatter_calls
    assert ("Processing span name='llm-call'" in caplog.text) == bool(
        expected_formatter_calls
    )
