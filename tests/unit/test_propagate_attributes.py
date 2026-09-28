"""Comprehensive tests for propagate_attributes functionality.

This module tests the propagate_attributes context manager that allows setting
trace-level attributes (user_id, session_id, metadata) that automatically propagate
to all child spans within the context.
"""

import concurrent.futures
from datetime import datetime

import pytest
from opentelemetry.instrumentation.threading import ThreadingInstrumentor

from proofstate import propagate_attributes
from proofstate._client.attributes import ProofStateOtelSpanAttributes, _serialize
from proofstate._client.constants import PROOFSTATE_SDK_EXPERIMENT_ENVIRONMENT
from proofstate._client.datasets import DatasetClient
from proofstate.api import Dataset, DatasetItem, DatasetStatus
from tests.unit.test_otel import TestOTelBase


class TestPropagateAttributesBase(TestOTelBase):
    """Base class for propagate_attributes tests with shared helper methods."""

    @pytest.fixture
    def proofstate_client(self, monkeypatch, tracer_provider, mock_processor_init):
        """Create a mocked ProofState client with explicit tracer_provider for testing."""
        from proofstate import ProofState

        # Set environment variables
        monkeypatch.setenv("PROOFSTATE_PUBLIC_KEY", "test-public-key")
        monkeypatch.setenv("PROOFSTATE_SECRET_KEY", "test-secret-key")

        # Create test client with explicit tracer_provider
        client = ProofState(
            public_key="test-public-key",
            secret_key="test-secret-key",
            host="http://test-host",
            tracing_enabled=True,
            tracer_provider=tracer_provider,  # Pass the test provider explicitly
        )

        yield client

    def get_span_by_name(self, memory_exporter, name: str) -> dict:
        """Get single span by name (assert exactly one exists).

        Args:
            memory_exporter: The in-memory span exporter fixture
            name: The name of the span to retrieve

        Returns:
            dict: The span data as a dictionary

        Raises:
            AssertionError: If zero or more than one span with the name exists
        """
        spans = self.get_spans_by_name(memory_exporter, name)
        assert len(spans) > 0, f"Expected at least 1 span named '{name}'"
        return spans[0]

    def verify_missing_attribute(self, span_data: dict, attr_key: str):
        """Verify that a span does NOT have a specific attribute.

        Args:
            span_data: The span data dictionary
            attr_key: The attribute key to check for absence

        Raises:
            AssertionError: If the attribute exists on the span
        """
        attributes = span_data["attributes"]
        assert attr_key not in attributes, (
            f"Attribute '{attr_key}' should NOT be on span '{span_data['name']}'"
        )


class TestPropagateAttributesBasic(TestPropagateAttributesBase):
    """Tests for basic propagate_attributes functionality."""

    def test_user_id_propagates_to_child_spans(
        self, proofstate_client, memory_exporter
    ):
        """Verify user_id propagates to all child spans within context."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(user_id="test_user_123"):
                child1 = proofstate_client.start_observation(name="child-span-1")
                child1.end()

                child2 = proofstate_client.start_observation(name="child-span-2")
                child2.end()

        # Verify both children have user_id
        child1_span = self.get_span_by_name(memory_exporter, "child-span-1")
        self.verify_span_attribute(
            child1_span,
            ProofStateOtelSpanAttributes.TRACE_USER_ID,
            "test_user_123",
        )

        child2_span = self.get_span_by_name(memory_exporter, "child-span-2")
        self.verify_span_attribute(
            child2_span,
            ProofStateOtelSpanAttributes.TRACE_USER_ID,
            "test_user_123",
        )

    def test_session_id_propagates_to_child_spans(
        self, proofstate_client, memory_exporter
    ):
        """Verify session_id propagates to all child spans within context."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(session_id="session_abc"):
                child1 = proofstate_client.start_observation(name="child-span-1")
                child1.end()

                child2 = proofstate_client.start_observation(name="child-span-2")
                child2.end()

        # Verify both children have session_id
        child1_span = self.get_span_by_name(memory_exporter, "child-span-1")
        self.verify_span_attribute(
            child1_span,
            ProofStateOtelSpanAttributes.TRACE_SESSION_ID,
            "session_abc",
        )

        child2_span = self.get_span_by_name(memory_exporter, "child-span-2")
        self.verify_span_attribute(
            child2_span,
            ProofStateOtelSpanAttributes.TRACE_SESSION_ID,
            "session_abc",
        )

    def test_metadata_propagates_to_child_spans(
        self, proofstate_client, memory_exporter
    ):
        """Verify metadata propagates to all child spans within context."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(
                metadata={"experiment": "variant_a", "version": "1.0"}
            ):
                child1 = proofstate_client.start_observation(name="child-span-1")
                child1.end()

                child2 = proofstate_client.start_observation(name="child-span-2")
                child2.end()

        # Verify both children have metadata
        child1_span = self.get_span_by_name(memory_exporter, "child-span-1")
        self.verify_span_attribute(
            child1_span,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.experiment",
            "variant_a",
        )
        self.verify_span_attribute(
            child1_span,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.version",
            "1.0",
        )

        child2_span = self.get_span_by_name(memory_exporter, "child-span-2")
        self.verify_span_attribute(
            child2_span,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.experiment",
            "variant_a",
        )
        self.verify_span_attribute(
            child2_span,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.version",
            "1.0",
        )

    def test_all_attributes_propagate_together(
        self, proofstate_client, memory_exporter
    ):
        """Verify user_id, session_id, and metadata all propagate together."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(
                user_id="user_123",
                session_id="session_abc",
                metadata={"experiment": "test", "env": "prod"},
            ):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        # Verify child has all attributes
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_span_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_USER_ID, "user_123"
        )
        self.verify_span_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_SESSION_ID, "session_abc"
        )
        self.verify_span_attribute(
            child_span,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.experiment",
            "test",
        )
        self.verify_span_attribute(
            child_span,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.env",
            "prod",
        )


class TestPropagateAttributesHierarchy(TestPropagateAttributesBase):
    """Tests for propagation across span hierarchies."""

    def test_propagation_to_direct_children(self, proofstate_client, memory_exporter):
        """Verify attributes propagate to all direct children."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(user_id="user_123"):
                child1 = proofstate_client.start_observation(name="child-1")
                child1.end()

                child2 = proofstate_client.start_observation(name="child-2")
                child2.end()

                child3 = proofstate_client.start_observation(name="child-3")
                child3.end()

        # Verify all three children have user_id
        for i in range(1, 4):
            child_span = self.get_span_by_name(memory_exporter, f"child-{i}")
            self.verify_span_attribute(
                child_span, ProofStateOtelSpanAttributes.TRACE_USER_ID, "user_123"
            )

    def test_propagation_to_grandchildren(self, proofstate_client, memory_exporter):
        """Verify attributes propagate through multiple levels of nesting."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(user_id="user_123", session_id="session_abc"):
                with proofstate_client.start_as_current_observation(name="child-span"):
                    grandchild = proofstate_client.start_observation(
                        name="grandchild-span"
                    )
                    grandchild.end()

        # Verify all three levels have attributes
        parent_span = self.get_span_by_name(memory_exporter, "parent-span")
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        grandchild_span = self.get_span_by_name(memory_exporter, "grandchild-span")

        for span in [parent_span, child_span, grandchild_span]:
            self.verify_span_attribute(
                span, ProofStateOtelSpanAttributes.TRACE_USER_ID, "user_123"
            )
            self.verify_span_attribute(
                span, ProofStateOtelSpanAttributes.TRACE_SESSION_ID, "session_abc"
            )

    def test_propagation_across_observation_types(
        self, proofstate_client, memory_exporter
    ):
        """Verify attributes propagate to different observation types."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(user_id="user_123"):
                # Create span
                span = proofstate_client.start_observation(name="test-span")
                span.end()

                # Create generation
                generation = proofstate_client.start_observation(
                    as_type="generation", name="test-generation"
                )
                generation.end()

        # Verify both observation types have user_id
        span_data = self.get_span_by_name(memory_exporter, "test-span")
        self.verify_span_attribute(
            span_data, ProofStateOtelSpanAttributes.TRACE_USER_ID, "user_123"
        )

        generation_data = self.get_span_by_name(memory_exporter, "test-generation")
        self.verify_span_attribute(
            generation_data, ProofStateOtelSpanAttributes.TRACE_USER_ID, "user_123"
        )


class TestPropagateAttributesTiming(TestPropagateAttributesBase):
    """Critical tests for early vs late propagation timing."""

    def test_early_propagation_all_spans_covered(
        self, proofstate_client, memory_exporter
    ):
        """Verify setting attributes early covers all child spans."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            # Set attributes BEFORE creating any children
            with propagate_attributes(user_id="user_123"):
                child1 = proofstate_client.start_observation(name="child-1")
                child1.end()

                child2 = proofstate_client.start_observation(name="child-2")
                child2.end()

                child3 = proofstate_client.start_observation(name="child-3")
                child3.end()

        # Verify ALL children have user_id
        for i in range(1, 4):
            child_span = self.get_span_by_name(memory_exporter, f"child-{i}")
            self.verify_span_attribute(
                child_span, ProofStateOtelSpanAttributes.TRACE_USER_ID, "user_123"
            )

    def test_late_propagation_only_future_spans_covered(
        self, proofstate_client, memory_exporter
    ):
        """Verify late propagation only affects spans created after context entry."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            # Create child1 BEFORE propagate_attributes
            child1 = proofstate_client.start_observation(name="child-1")
            child1.end()

            # NOW set attributes
            with propagate_attributes(user_id="user_123"):
                # Create child2 AFTER propagate_attributes
                child2 = proofstate_client.start_observation(name="child-2")
                child2.end()

        # Verify: child1 does NOT have user_id, child2 DOES
        child1_span = self.get_span_by_name(memory_exporter, "child-1")
        self.verify_missing_attribute(
            child1_span, ProofStateOtelSpanAttributes.TRACE_USER_ID
        )

        child2_span = self.get_span_by_name(memory_exporter, "child-2")
        self.verify_span_attribute(
            child2_span, ProofStateOtelSpanAttributes.TRACE_USER_ID, "user_123"
        )

    def test_current_span_gets_attributes(self, proofstate_client, memory_exporter):
        """Verify the currently active span gets attributes when propagate_attributes is called."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            # Call propagate_attributes while parent-span is active
            with propagate_attributes(user_id="user_123"):
                pass

        # Verify parent span itself has the attribute
        parent_span = self.get_span_by_name(memory_exporter, "parent-span")
        self.verify_span_attribute(
            parent_span, ProofStateOtelSpanAttributes.TRACE_USER_ID, "user_123"
        )

    def test_spans_outside_context_unaffected(self, proofstate_client, memory_exporter):
        """Verify spans created outside context don't get attributes."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            # Span before context
            span1 = proofstate_client.start_observation(name="span-1")
            span1.end()

            # Span inside context
            with propagate_attributes(user_id="user_123"):
                span2 = proofstate_client.start_observation(name="span-2")
                span2.end()

            # Span after context
            span3 = proofstate_client.start_observation(name="span-3")
            span3.end()

        # Verify: only span2 has user_id
        span1_data = self.get_span_by_name(memory_exporter, "span-1")
        self.verify_missing_attribute(
            span1_data, ProofStateOtelSpanAttributes.TRACE_USER_ID
        )

        span2_data = self.get_span_by_name(memory_exporter, "span-2")
        self.verify_span_attribute(
            span2_data, ProofStateOtelSpanAttributes.TRACE_USER_ID, "user_123"
        )

        span3_data = self.get_span_by_name(memory_exporter, "span-3")
        self.verify_missing_attribute(
            span3_data, ProofStateOtelSpanAttributes.TRACE_USER_ID
        )


class TestPropagateAttributesValidation(TestPropagateAttributesBase):
    """Tests for validation of propagated attribute values."""

    def test_user_id_over_200_chars_dropped(self, proofstate_client, memory_exporter):
        """Verify user_id over 200 characters is dropped with warning."""
        long_user_id = "x" * 201

        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(user_id=long_user_id):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        # Verify child does NOT have user_id
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_missing_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_USER_ID
        )

    def test_session_id_over_200_chars_dropped(
        self, proofstate_client, memory_exporter
    ):
        """Verify session_id over 200 characters is dropped with warning."""
        long_session_id = "y" * 201

        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(session_id=long_session_id):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        # Verify child does NOT have session_id
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_missing_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_SESSION_ID
        )

    def test_metadata_value_over_200_chars_dropped(
        self, proofstate_client, memory_exporter
    ):
        """Verify metadata values over 200 characters are dropped with warning."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(metadata={"key": "z" * 201}):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        # Verify child does NOT have metadata.key
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_missing_attribute(
            child_span, f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.key"
        )

    def test_exactly_200_chars_accepted(self, proofstate_client, memory_exporter):
        """Verify exactly 200 characters is accepted (boundary test)."""
        user_id_200 = "x" * 200

        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(user_id=user_id_200):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        # Verify child HAS user_id
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_span_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_USER_ID, user_id_200
        )

    def test_201_chars_rejected(self, proofstate_client, memory_exporter):
        """Verify 201 characters is rejected (boundary test)."""
        user_id_201 = "x" * 201

        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(user_id=user_id_201):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        # Verify child does NOT have user_id
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_missing_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_USER_ID
        )

    def test_non_string_user_id_dropped(self, proofstate_client, memory_exporter):
        """Verify non-string user_id is dropped with warning."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(user_id=12345):  # type: ignore
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        # Verify child does NOT have user_id
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_missing_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_USER_ID
        )

    def test_non_string_metadata_values_coerced(
        self, proofstate_client, memory_exporter, caplog
    ):
        """Verify non-string metadata values are coerced instead of dropped."""

        caplog.set_level("WARNING", logger="proofstate")
        metadata = {
            "langgraph_step": 1,
            "langgraph_triggers": ["branch:agent"],
            "langgraph_path": ("root", "agent"),
            "max_search_results": 5,
        }

        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(metadata=metadata):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        child_span = self.get_span_by_name(memory_exporter, "child-span")

        for key, value in metadata.items():
            self.verify_span_attribute(
                child_span,
                f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.{key}",
                str(value),
            )

        assert "value is not a string. Dropping value." not in caplog.text

    def test_mixed_valid_invalid_metadata(self, proofstate_client, memory_exporter):
        """Verify mixed valid/invalid metadata - valid entries kept, invalid dropped."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(
                metadata={
                    "valid_key": "valid_value",
                    "invalid_key": "x" * 201,  # Too long
                    "another_valid": "ok",
                }
            ):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        # Verify: valid keys present, invalid key absent
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_span_attribute(
            child_span,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.valid_key",
            "valid_value",
        )
        self.verify_span_attribute(
            child_span,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.another_valid",
            "ok",
        )
        self.verify_missing_attribute(
            child_span, f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.invalid_key"
        )


class TestPropagateAttributesNesting(TestPropagateAttributesBase):
    """Tests for nested propagate_attributes contexts."""

    def test_nested_contexts_inner_overwrites(self, proofstate_client, memory_exporter):
        """Verify inner context overwrites outer context values."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(user_id="user1"):
                # Create span in outer context
                span1 = proofstate_client.start_observation(name="span-1")
                span1.end()

                # Inner context with different user_id
                with propagate_attributes(user_id="user2"):
                    span2 = proofstate_client.start_observation(name="span-2")
                    span2.end()

        # Verify: span1 has user1, span2 has user2
        span1_data = self.get_span_by_name(memory_exporter, "span-1")
        self.verify_span_attribute(
            span1_data, ProofStateOtelSpanAttributes.TRACE_USER_ID, "user1"
        )

        span2_data = self.get_span_by_name(memory_exporter, "span-2")
        self.verify_span_attribute(
            span2_data, ProofStateOtelSpanAttributes.TRACE_USER_ID, "user2"
        )

    def test_after_inner_context_outer_restored(
        self, proofstate_client, memory_exporter
    ):
        """Verify outer context is restored after exiting inner context."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(user_id="user1"):
                # Span in outer context
                span1 = proofstate_client.start_observation(name="span-1")
                span1.end()

                # Inner context
                with propagate_attributes(user_id="user2"):
                    span2 = proofstate_client.start_observation(name="span-2")
                    span2.end()

                # Back to outer context
                span3 = proofstate_client.start_observation(name="span-3")
                span3.end()

        # Verify: span1 and span3 have user1, span2 has user2
        span1_data = self.get_span_by_name(memory_exporter, "span-1")
        self.verify_span_attribute(
            span1_data, ProofStateOtelSpanAttributes.TRACE_USER_ID, "user1"
        )

        span2_data = self.get_span_by_name(memory_exporter, "span-2")
        self.verify_span_attribute(
            span2_data, ProofStateOtelSpanAttributes.TRACE_USER_ID, "user2"
        )

        span3_data = self.get_span_by_name(memory_exporter, "span-3")
        self.verify_span_attribute(
            span3_data, ProofStateOtelSpanAttributes.TRACE_USER_ID, "user1"
        )

    def test_nested_different_attributes(self, proofstate_client, memory_exporter):
        """Verify nested contexts with different attributes merge correctly."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(user_id="user1"):
                # Inner context adds session_id
                with propagate_attributes(session_id="session1"):
                    span = proofstate_client.start_observation(name="span-1")
                    span.end()

        # Verify: span has BOTH user_id and session_id
        span_data = self.get_span_by_name(memory_exporter, "span-1")
        self.verify_span_attribute(
            span_data, ProofStateOtelSpanAttributes.TRACE_USER_ID, "user1"
        )
        self.verify_span_attribute(
            span_data, ProofStateOtelSpanAttributes.TRACE_SESSION_ID, "session1"
        )

    def test_nested_metadata_merges_additively(
        self, proofstate_client, memory_exporter
    ):
        """Verify nested contexts merge metadata keys additively."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(metadata={"env": "prod", "region": "us-east"}):
                # Outer span should have outer metadata
                outer_span = proofstate_client.start_observation(name="outer-span")
                outer_span.end()

                # Inner context adds more metadata
                with propagate_attributes(
                    metadata={"experiment": "A", "version": "2.0"}
                ):
                    inner_span = proofstate_client.start_observation(name="inner-span")
                    inner_span.end()

                # Back to outer context
                after_span = proofstate_client.start_observation(name="after-span")
                after_span.end()

        # Verify: outer span has only outer metadata
        outer_span_data = self.get_span_by_name(memory_exporter, "outer-span")
        self.verify_span_attribute(
            outer_span_data,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.env",
            "prod",
        )
        self.verify_span_attribute(
            outer_span_data,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.region",
            "us-east",
        )
        self.verify_missing_attribute(
            outer_span_data, f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.experiment"
        )

        # Verify: inner span has ALL metadata (merged)
        inner_span_data = self.get_span_by_name(memory_exporter, "inner-span")
        self.verify_span_attribute(
            inner_span_data,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.env",
            "prod",
        )
        self.verify_span_attribute(
            inner_span_data,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.region",
            "us-east",
        )
        self.verify_span_attribute(
            inner_span_data,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.experiment",
            "A",
        )
        self.verify_span_attribute(
            inner_span_data,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.version",
            "2.0",
        )

        # Verify: after span has only outer metadata (inner context exited)
        after_span_data = self.get_span_by_name(memory_exporter, "after-span")
        self.verify_span_attribute(
            after_span_data,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.env",
            "prod",
        )
        self.verify_span_attribute(
            after_span_data,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.region",
            "us-east",
        )
        self.verify_missing_attribute(
            after_span_data, f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.experiment"
        )

    def test_nested_metadata_inner_overwrites_conflicting_keys(
        self, proofstate_client, memory_exporter
    ):
        """Verify nested contexts: inner metadata overwrites outer for same keys."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(
                metadata={"env": "staging", "version": "1.0", "region": "us-west"}
            ):
                # Inner context overwrites some keys
                with propagate_attributes(
                    metadata={"env": "production", "experiment": "B"}
                ):
                    span = proofstate_client.start_observation(name="span-1")
                    span.end()

        # Verify: inner values overwrite outer for conflicting keys
        span_data = self.get_span_by_name(memory_exporter, "span-1")

        # Overwritten key
        self.verify_span_attribute(
            span_data,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.env",
            "production",  # Inner value wins
        )

        # Preserved keys from outer
        self.verify_span_attribute(
            span_data,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.version",
            "1.0",  # From outer
        )
        self.verify_span_attribute(
            span_data,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.region",
            "us-west",  # From outer
        )

        # New key from inner
        self.verify_span_attribute(
            span_data,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.experiment",
            "B",  # From inner
        )

    def test_triple_nested_metadata_accumulates(
        self, proofstate_client, memory_exporter
    ):
        """Verify metadata accumulates across three levels of nesting."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(metadata={"level": "1", "a": "outer"}):
                with propagate_attributes(metadata={"level": "2", "b": "middle"}):
                    with propagate_attributes(metadata={"level": "3", "c": "inner"}):
                        span = proofstate_client.start_observation(name="deep-span")
                        span.end()

        # Verify: deepest span has all metadata with innermost level winning
        span_data = self.get_span_by_name(memory_exporter, "deep-span")

        # Conflicting key: innermost wins
        self.verify_span_attribute(
            span_data,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.level",
            "3",
        )

        # Unique keys from each level
        self.verify_span_attribute(
            span_data,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.a",
            "outer",
        )
        self.verify_span_attribute(
            span_data,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.b",
            "middle",
        )
        self.verify_span_attribute(
            span_data,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.c",
            "inner",
        )

    def test_metadata_merge_with_empty_inner(self, proofstate_client, memory_exporter):
        """Verify empty inner metadata dict doesn't clear outer metadata."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(metadata={"key1": "value1", "key2": "value2"}):
                # Inner context with empty metadata
                with propagate_attributes(metadata={}):
                    span = proofstate_client.start_observation(name="span-1")
                    span.end()

        # Verify: outer metadata is preserved
        span_data = self.get_span_by_name(memory_exporter, "span-1")
        self.verify_span_attribute(
            span_data,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.key1",
            "value1",
        )
        self.verify_span_attribute(
            span_data,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.key2",
            "value2",
        )

    def test_metadata_merge_preserves_user_session(
        self, proofstate_client, memory_exporter
    ):
        """Verify metadata merging doesn't affect user_id/session_id."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(
                user_id="user1",
                session_id="session1",
                metadata={"outer": "value"},
            ):
                with propagate_attributes(metadata={"inner": "value"}):
                    span = proofstate_client.start_observation(name="span-1")
                    span.end()

        # Verify: user_id and session_id are preserved, metadata merged
        span_data = self.get_span_by_name(memory_exporter, "span-1")
        self.verify_span_attribute(
            span_data, ProofStateOtelSpanAttributes.TRACE_USER_ID, "user1"
        )
        self.verify_span_attribute(
            span_data, ProofStateOtelSpanAttributes.TRACE_SESSION_ID, "session1"
        )
        self.verify_span_attribute(
            span_data,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.outer",
            "value",
        )
        self.verify_span_attribute(
            span_data,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.inner",
            "value",
        )


class TestPropagateAttributesEdgeCases(TestPropagateAttributesBase):
    """Tests for edge cases and unusual scenarios."""

    def test_propagate_attributes_with_no_args(
        self, proofstate_client, memory_exporter
    ):
        """Verify calling propagate_attributes() with no args doesn't error."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes():
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        # Should not crash, spans created normally
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        assert child_span is not None

    def test_none_values_ignored(self, proofstate_client, memory_exporter):
        """Verify None values are ignored without error."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(user_id=None, session_id=None, metadata=None):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        # Should not crash, no attributes set
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_missing_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_USER_ID
        )
        self.verify_missing_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_SESSION_ID
        )

    def test_empty_metadata_dict(self, proofstate_client, memory_exporter):
        """Verify empty metadata dict doesn't cause errors."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(metadata={}):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        # Should not crash, no metadata attributes set
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        assert child_span is not None

    def test_all_invalid_metadata_values(self, proofstate_client, memory_exporter):
        """Verify all invalid metadata values results in no metadata attributes."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(
                metadata={
                    "key1": "x" * 201,  # Too long
                    "key2": "y" * 201,  # Too long
                }
            ):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        # No metadata attributes should be set
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_missing_attribute(
            child_span, f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.key1"
        )
        self.verify_missing_attribute(
            child_span, f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.key2"
        )

    def test_propagate_with_no_active_span(self, proofstate_client, memory_exporter):
        """Verify propagate_attributes works even with no active span."""
        # Call propagate_attributes without creating a parent span first
        with propagate_attributes(user_id="user_123"):
            # Now create a span
            with proofstate_client.start_as_current_observation(name="span-1"):
                pass

        # Should not crash, span should have user_id
        span_data = self.get_span_by_name(memory_exporter, "span-1")
        self.verify_span_attribute(
            span_data, ProofStateOtelSpanAttributes.TRACE_USER_ID, "user_123"
        )


class TestPropagateAttributesFormat(TestPropagateAttributesBase):
    """Tests for correct attribute formatting and naming."""

    def test_user_id_uses_correct_attribute_name(
        self, proofstate_client, memory_exporter
    ):
        """Verify user_id uses the correct OTel attribute name."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(user_id="user_123"):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        child_span = self.get_span_by_name(memory_exporter, "child-span")
        # Verify the exact attribute key is used
        assert ProofStateOtelSpanAttributes.TRACE_USER_ID in child_span["attributes"]
        assert (
            child_span["attributes"][ProofStateOtelSpanAttributes.TRACE_USER_ID]
            == "user_123"
        )

    def test_session_id_uses_correct_attribute_name(
        self, proofstate_client, memory_exporter
    ):
        """Verify session_id uses the correct OTel attribute name."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(session_id="session_abc"):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        child_span = self.get_span_by_name(memory_exporter, "child-span")
        # Verify the exact attribute key is used
        assert ProofStateOtelSpanAttributes.TRACE_SESSION_ID in child_span["attributes"]
        assert (
            child_span["attributes"][ProofStateOtelSpanAttributes.TRACE_SESSION_ID]
            == "session_abc"
        )

    def test_metadata_keys_properly_prefixed(self, proofstate_client, memory_exporter):
        """Verify metadata keys are properly prefixed with TRACE_METADATA."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(
                metadata={"experiment": "A", "version": "1.0", "env": "prod"}
            ):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        child_span = self.get_span_by_name(memory_exporter, "child-span")
        attributes = child_span["attributes"]

        # Verify each metadata key is properly prefixed
        expected_keys = [
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.experiment",
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.version",
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.env",
        ]

        for key in expected_keys:
            assert key in attributes, f"Expected key '{key}' not found in attributes"

    def test_multiple_metadata_keys_independent(
        self, proofstate_client, memory_exporter
    ):
        """Verify multiple metadata keys are stored as independent attributes."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(metadata={"k1": "v1", "k2": "v2", "k3": "v3"}):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        child_span = self.get_span_by_name(memory_exporter, "child-span")
        attributes = child_span["attributes"]

        # Verify all three are separate attributes with correct values
        assert attributes[f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.k1"] == "v1"
        assert attributes[f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.k2"] == "v2"
        assert attributes[f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.k3"] == "v3"


class TestPropagateAttributesThreading(TestPropagateAttributesBase):
    """Tests for propagate_attributes with ThreadPoolExecutor."""

    @pytest.fixture(autouse=True)
    def instrument_threading(self):
        """Auto-instrument threading for all tests in this class."""
        instrumentor = ThreadingInstrumentor()
        instrumentor.instrument()
        yield
        instrumentor.uninstrument()

    def test_propagation_with_threadpoolexecutor(
        self, proofstate_client, memory_exporter
    ):
        """Verify attributes propagate from main thread to worker threads."""

        def worker_function(span_name: str):
            """Worker creates a span in thread pool."""
            span = proofstate_client.start_observation(name=span_name)
            span.end()
            return span_name

        with proofstate_client.start_as_current_observation(name="main-span"):
            with propagate_attributes(user_id="main_user", session_id="main_session"):
                # Execute work in thread pool
                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                    futures = [
                        executor.submit(worker_function, f"worker-span-{i}")
                        for i in range(3)
                    ]
                    concurrent.futures.wait(futures)

        # Verify all worker spans have propagated attributes
        for i in range(3):
            worker_span = self.get_span_by_name(memory_exporter, f"worker-span-{i}")
            self.verify_span_attribute(
                worker_span,
                ProofStateOtelSpanAttributes.TRACE_USER_ID,
                "main_user",
            )
            self.verify_span_attribute(
                worker_span,
                ProofStateOtelSpanAttributes.TRACE_SESSION_ID,
                "main_session",
            )

    def test_propagation_isolated_between_threads(
        self, proofstate_client, memory_exporter
    ):
        """Verify each thread's context is isolated from others."""

        def create_trace_with_user(user_id: str):
            """Create a trace with specific user_id."""
            with proofstate_client.start_as_current_observation(
                name=f"trace-{user_id}"
            ):
                with propagate_attributes(user_id=user_id):
                    span = proofstate_client.start_observation(name=f"span-{user_id}")
                    span.end()

        # Run two traces concurrently with different user_ids
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(create_trace_with_user, "user1")
            future2 = executor.submit(create_trace_with_user, "user2")
            concurrent.futures.wait([future1, future2])

        # Verify each trace has the correct user_id (no mixing)
        span1 = self.get_span_by_name(memory_exporter, "span-user1")
        self.verify_span_attribute(
            span1, ProofStateOtelSpanAttributes.TRACE_USER_ID, "user1"
        )

        span2 = self.get_span_by_name(memory_exporter, "span-user2")
        self.verify_span_attribute(
            span2, ProofStateOtelSpanAttributes.TRACE_USER_ID, "user2"
        )

    def test_nested_propagation_across_thread_boundary(
        self, proofstate_client, memory_exporter
    ):
        """Verify nested spans across thread boundaries inherit attributes."""

        def worker_creates_child():
            """Worker thread creates a child span."""
            child = proofstate_client.start_observation(name="worker-child-span")
            child.end()

        with proofstate_client.start_as_current_observation(name="main-parent-span"):
            with propagate_attributes(user_id="main_user"):
                # Create span in main thread
                main_child = proofstate_client.start_observation(name="main-child-span")
                main_child.end()

                # Create span in worker thread
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(worker_creates_child)
                    future.result()

        # Verify both spans (main and worker) have user_id
        main_child_span = self.get_span_by_name(memory_exporter, "main-child-span")
        self.verify_span_attribute(
            main_child_span, ProofStateOtelSpanAttributes.TRACE_USER_ID, "main_user"
        )

        worker_child_span = self.get_span_by_name(memory_exporter, "worker-child-span")
        self.verify_span_attribute(
            worker_child_span, ProofStateOtelSpanAttributes.TRACE_USER_ID, "main_user"
        )

    def test_worker_thread_can_override_propagated_attrs(
        self, proofstate_client, memory_exporter
    ):
        """Verify worker thread can override propagated attributes."""

        def worker_overrides_user():
            """Worker thread sets its own user_id."""
            with propagate_attributes(user_id="worker_user"):
                span = proofstate_client.start_observation(name="worker-span")
                span.end()

        with proofstate_client.start_as_current_observation(name="main-span"):
            with propagate_attributes(user_id="main_user"):
                # Create span in main thread
                main_span = proofstate_client.start_observation(name="main-child-span")
                main_span.end()

                # Worker overrides with its own user_id
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(worker_overrides_user)
                    future.result()

        # Verify: main span has main_user, worker span has worker_user
        main_child = self.get_span_by_name(memory_exporter, "main-child-span")
        self.verify_span_attribute(
            main_child, ProofStateOtelSpanAttributes.TRACE_USER_ID, "main_user"
        )

        worker_span = self.get_span_by_name(memory_exporter, "worker-span")
        self.verify_span_attribute(
            worker_span, ProofStateOtelSpanAttributes.TRACE_USER_ID, "worker_user"
        )

    def test_multiple_workers_with_same_propagated_context(
        self, proofstate_client, memory_exporter
    ):
        """Verify multiple workers all inherit same propagated context."""

        def worker_function(worker_id: int):
            """Worker creates a span."""
            span = proofstate_client.start_observation(name=f"worker-{worker_id}")
            span.end()

        with proofstate_client.start_as_current_observation(name="main-span"):
            with propagate_attributes(session_id="shared_session"):
                # Submit 5 workers
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    futures = [executor.submit(worker_function, i) for i in range(5)]
                    concurrent.futures.wait(futures)

        # Verify all 5 workers have same session_id
        for i in range(5):
            worker_span = self.get_span_by_name(memory_exporter, f"worker-{i}")
            self.verify_span_attribute(
                worker_span,
                ProofStateOtelSpanAttributes.TRACE_SESSION_ID,
                "shared_session",
            )

    def test_concurrent_traces_with_different_attributes(
        self, proofstate_client, memory_exporter
    ):
        """Verify concurrent traces with different attributes don't mix."""

        def create_trace(trace_id: int):
            """Create a trace with unique user_id."""
            with proofstate_client.start_as_current_observation(
                name=f"trace-{trace_id}"
            ):
                with propagate_attributes(user_id=f"user_{trace_id}"):
                    span = proofstate_client.start_observation(name=f"span-{trace_id}")
                    span.end()

        # Create 10 traces concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_trace, i) for i in range(10)]
            concurrent.futures.wait(futures)

        # Verify each trace has its correct user_id (no mixing)
        for i in range(10):
            span = self.get_span_by_name(memory_exporter, f"span-{i}")
            self.verify_span_attribute(
                span, ProofStateOtelSpanAttributes.TRACE_USER_ID, f"user_{i}"
            )

    def test_exception_in_worker_preserves_context(
        self, proofstate_client, memory_exporter
    ):
        """Verify exception in worker doesn't corrupt main thread context."""

        def worker_raises_exception():
            """Worker creates span then raises exception."""
            span = proofstate_client.start_observation(name="worker-span")
            span.end()
            raise ValueError("Test exception")

        with proofstate_client.start_as_current_observation(name="main-span"):
            with propagate_attributes(user_id="main_user"):
                # Create span before worker
                span1 = proofstate_client.start_observation(name="span-before")
                span1.end()

                # Worker raises exception (catch it)
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(worker_raises_exception)
                    try:
                        future.result()
                    except ValueError:
                        pass  # Expected

                # Create span after exception
                span2 = proofstate_client.start_observation(name="span-after")
                span2.end()

        # Verify both main thread spans still have correct user_id
        span_before = self.get_span_by_name(memory_exporter, "span-before")
        self.verify_span_attribute(
            span_before, ProofStateOtelSpanAttributes.TRACE_USER_ID, "main_user"
        )

        span_after = self.get_span_by_name(memory_exporter, "span-after")
        self.verify_span_attribute(
            span_after, ProofStateOtelSpanAttributes.TRACE_USER_ID, "main_user"
        )


class TestPropagateAttributesCrossTracer(TestPropagateAttributesBase):
    """Tests for propagate_attributes with different OpenTelemetry tracers."""

    def test_different_tracer_spans_get_attributes(
        self, proofstate_client, memory_exporter, tracer_provider
    ):
        """Verify spans from different tracers get propagated attributes."""
        # Get a different tracer (not the ProofState tracer)
        other_tracer = tracer_provider.get_tracer("other-library", "1.0.0")

        with proofstate_client.start_as_current_observation(name="proofstate-parent"):
            with propagate_attributes(user_id="user_123", session_id="session_abc"):
                # Create span with ProofState tracer
                proofstate_span = proofstate_client.start_observation(
                    name="proofstate-child"
                )
                proofstate_span.end()

                # Create span with different tracer
                with other_tracer.start_as_current_span(name="other-library-span"):
                    pass

        # Verify both spans have the propagated attributes
        proofstate_span_data = self.get_span_by_name(
            memory_exporter, "proofstate-child"
        )
        self.verify_span_attribute(
            proofstate_span_data,
            ProofStateOtelSpanAttributes.TRACE_USER_ID,
            "user_123",
        )
        self.verify_span_attribute(
            proofstate_span_data,
            ProofStateOtelSpanAttributes.TRACE_SESSION_ID,
            "session_abc",
        )

        other_span_data = self.get_span_by_name(memory_exporter, "other-library-span")
        self.verify_span_attribute(
            other_span_data,
            ProofStateOtelSpanAttributes.TRACE_USER_ID,
            "user_123",
        )
        self.verify_span_attribute(
            other_span_data,
            ProofStateOtelSpanAttributes.TRACE_SESSION_ID,
            "session_abc",
        )

    def test_nested_spans_from_multiple_tracers(
        self, proofstate_client, memory_exporter, tracer_provider
    ):
        """Verify nested spans from multiple tracers all get propagated attributes."""
        tracer_a = tracer_provider.get_tracer("library-a", "1.0.0")
        tracer_b = tracer_provider.get_tracer("library-b", "2.0.0")

        with proofstate_client.start_as_current_observation(name="root"):
            with propagate_attributes(
                user_id="user_123", metadata={"experiment": "cross_tracer"}
            ):
                # Create nested spans from different tracers
                with tracer_a.start_as_current_span(name="library-a-span"):
                    with tracer_b.start_as_current_span(name="library-b-span"):
                        proofstate_leaf = proofstate_client.start_observation(
                            name="proofstate-leaf"
                        )
                        proofstate_leaf.end()

        # Verify all spans have the attributes
        for span_name in ["library-a-span", "library-b-span", "proofstate-leaf"]:
            span_data = self.get_span_by_name(memory_exporter, span_name)
            self.verify_span_attribute(
                span_data,
                ProofStateOtelSpanAttributes.TRACE_USER_ID,
                "user_123",
            )
            self.verify_span_attribute(
                span_data,
                f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.experiment",
                "cross_tracer",
            )

    def test_other_tracer_span_before_propagate_context(
        self, proofstate_client, memory_exporter, tracer_provider
    ):
        """Verify spans created before propagate_attributes don't get attributes."""
        other_tracer = tracer_provider.get_tracer("other-library", "1.0.0")

        with proofstate_client.start_as_current_observation(name="root"):
            # Create span BEFORE propagate_attributes
            with other_tracer.start_as_current_span(name="span-before"):
                pass

            # NOW set attributes
            with propagate_attributes(user_id="user_123"):
                # Create span AFTER propagate_attributes
                with other_tracer.start_as_current_span(name="span-after"):
                    pass

        # Verify: span-before does NOT have user_id, span-after DOES
        span_before = self.get_span_by_name(memory_exporter, "span-before")
        self.verify_missing_attribute(
            span_before, ProofStateOtelSpanAttributes.TRACE_USER_ID
        )

        span_after = self.get_span_by_name(memory_exporter, "span-after")
        self.verify_span_attribute(
            span_after, ProofStateOtelSpanAttributes.TRACE_USER_ID, "user_123"
        )

    def test_mixed_tracers_with_metadata(
        self, proofstate_client, memory_exporter, tracer_provider
    ):
        """Verify metadata propagates correctly to spans from different tracers."""
        other_tracer = tracer_provider.get_tracer("instrumented-library", "1.0.0")

        with proofstate_client.start_as_current_observation(name="main"):
            with propagate_attributes(
                metadata={
                    "env": "production",
                    "version": "2.0",
                    "feature_flag": "enabled",
                }
            ):
                # Create spans from both tracers
                proofstate_span = proofstate_client.start_observation(
                    name="proofstate-operation"
                )
                proofstate_span.end()

                with other_tracer.start_as_current_span(name="library-operation"):
                    pass

        # Verify both spans have all metadata
        for span_name in ["proofstate-operation", "library-operation"]:
            span_data = self.get_span_by_name(memory_exporter, span_name)
            self.verify_span_attribute(
                span_data,
                f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.env",
                "production",
            )
            self.verify_span_attribute(
                span_data,
                f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.version",
                "2.0",
            )
            self.verify_span_attribute(
                span_data,
                f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.feature_flag",
                "enabled",
            )

    def test_propagate_without_proofstate_parent(
        self, proofstate_client, memory_exporter, tracer_provider
    ):
        """Verify propagate_attributes works even when parent span is from different tracer."""
        other_tracer = tracer_provider.get_tracer("other-library", "1.0.0")

        # Parent span is from different tracer
        with other_tracer.start_as_current_span(name="other-parent"):
            with propagate_attributes(user_id="user_123", session_id="session_xyz"):
                # Create children from both tracers
                with other_tracer.start_as_current_span(name="other-child"):
                    pass

                proofstate_child = proofstate_client.start_observation(
                    name="proofstate-child"
                )
                proofstate_child.end()

        # Verify all spans have attributes (including non-ProofState parent)
        for span_name in ["other-parent", "other-child", "proofstate-child"]:
            span_data = self.get_span_by_name(memory_exporter, span_name)
            self.verify_span_attribute(
                span_data,
                ProofStateOtelSpanAttributes.TRACE_USER_ID,
                "user_123",
            )
            self.verify_span_attribute(
                span_data,
                ProofStateOtelSpanAttributes.TRACE_SESSION_ID,
                "session_xyz",
            )

    def test_attributes_persist_across_tracer_changes(
        self, proofstate_client, memory_exporter, tracer_provider
    ):
        """Verify attributes persist as execution moves between different tracers."""
        tracer_1 = tracer_provider.get_tracer("library-1", "1.0.0")
        tracer_2 = tracer_provider.get_tracer("library-2", "1.0.0")
        tracer_3 = tracer_provider.get_tracer("library-3", "1.0.0")

        with proofstate_client.start_as_current_observation(name="root"):
            with propagate_attributes(user_id="persistent_user"):
                # Bounce between different tracers
                with tracer_1.start_as_current_span(name="step-1"):
                    pass

                with tracer_2.start_as_current_span(name="step-2"):
                    with tracer_3.start_as_current_span(name="step-3"):
                        pass

                proofstate_span = proofstate_client.start_observation(name="step-4")
                proofstate_span.end()

        # Verify all steps have the user_id
        for step_name in ["step-1", "step-2", "step-3", "step-4"]:
            span_data = self.get_span_by_name(memory_exporter, step_name)
            self.verify_span_attribute(
                span_data,
                ProofStateOtelSpanAttributes.TRACE_USER_ID,
                "persistent_user",
            )


class TestPropagateAttributesAsync(TestPropagateAttributesBase):
    """Tests for propagate_attributes with async/await."""

    @pytest.mark.asyncio
    async def test_async_propagation_basic(self, proofstate_client, memory_exporter):
        """Verify attributes propagate in async context."""

        async def async_operation():
            """Async function that creates a span."""
            span = proofstate_client.start_observation(name="async-span")
            span.end()

        with proofstate_client.start_as_current_observation(name="parent"):
            with propagate_attributes(user_id="async_user", session_id="async_session"):
                await async_operation()

        # Verify async span has attributes
        async_span = self.get_span_by_name(memory_exporter, "async-span")
        self.verify_span_attribute(
            async_span, ProofStateOtelSpanAttributes.TRACE_USER_ID, "async_user"
        )
        self.verify_span_attribute(
            async_span, ProofStateOtelSpanAttributes.TRACE_SESSION_ID, "async_session"
        )

    @pytest.mark.asyncio
    async def test_async_nested_operations(self, proofstate_client, memory_exporter):
        """Verify attributes propagate through nested async operations."""

        async def level_3():
            span = proofstate_client.start_observation(name="level-3-span")
            span.end()

        async def level_2():
            span = proofstate_client.start_observation(name="level-2-span")
            span.end()
            await level_3()

        async def level_1():
            span = proofstate_client.start_observation(name="level-1-span")
            span.end()
            await level_2()

        with proofstate_client.start_as_current_observation(name="root"):
            with propagate_attributes(
                user_id="nested_user", metadata={"level": "nested"}
            ):
                await level_1()

        # Verify all levels have attributes
        for span_name in ["level-1-span", "level-2-span", "level-3-span"]:
            span_data = self.get_span_by_name(memory_exporter, span_name)
            self.verify_span_attribute(
                span_data, ProofStateOtelSpanAttributes.TRACE_USER_ID, "nested_user"
            )
            self.verify_span_attribute(
                span_data,
                f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.level",
                "nested",
            )

    @pytest.mark.asyncio
    async def test_async_context_manager(self, proofstate_client, memory_exporter):
        """Verify propagate_attributes works as context manager in async function."""
        with proofstate_client.start_as_current_observation(name="parent"):
            # propagate_attributes supports both sync and async contexts via regular 'with'
            with propagate_attributes(user_id="async_ctx_user"):
                span = proofstate_client.start_observation(name="inside-async-ctx")
                span.end()

        span_data = self.get_span_by_name(memory_exporter, "inside-async-ctx")
        self.verify_span_attribute(
            span_data, ProofStateOtelSpanAttributes.TRACE_USER_ID, "async_ctx_user"
        )

    @pytest.mark.asyncio
    async def test_multiple_async_tasks_concurrent(
        self, proofstate_client, memory_exporter
    ):
        """Verify context isolation between concurrent async tasks."""
        import asyncio

        async def create_trace_with_user(user_id: str):
            """Create a trace with specific user_id."""
            with proofstate_client.start_as_current_observation(
                name=f"trace-{user_id}"
            ):
                with propagate_attributes(user_id=user_id):
                    await asyncio.sleep(0.001)  # Simulate async work
                    span = proofstate_client.start_observation(name=f"span-{user_id}")
                    span.end()

        # Run multiple traces concurrently
        await asyncio.gather(
            create_trace_with_user("user1"),
            create_trace_with_user("user2"),
            create_trace_with_user("user3"),
        )

        # Verify each trace has correct user_id (no mixing)
        for user_id in ["user1", "user2", "user3"]:
            span_data = self.get_span_by_name(memory_exporter, f"span-{user_id}")
            self.verify_span_attribute(
                span_data, ProofStateOtelSpanAttributes.TRACE_USER_ID, user_id
            )

    @pytest.mark.asyncio
    async def test_async_with_sync_nested(self, proofstate_client, memory_exporter):
        """Verify attributes propagate from async to sync code."""

        def sync_operation():
            """Sync function called from async context."""
            span = proofstate_client.start_observation(name="sync-in-async")
            span.end()

        async def async_operation():
            """Async function that calls sync code."""
            span1 = proofstate_client.start_observation(name="async-span")
            span1.end()
            sync_operation()

        with proofstate_client.start_as_current_observation(name="root"):
            with propagate_attributes(user_id="mixed_user"):
                await async_operation()

        # Verify both spans have attributes
        async_span = self.get_span_by_name(memory_exporter, "async-span")
        self.verify_span_attribute(
            async_span, ProofStateOtelSpanAttributes.TRACE_USER_ID, "mixed_user"
        )

        sync_span = self.get_span_by_name(memory_exporter, "sync-in-async")
        self.verify_span_attribute(
            sync_span, ProofStateOtelSpanAttributes.TRACE_USER_ID, "mixed_user"
        )

    @pytest.mark.asyncio
    async def test_async_exception_preserves_context(
        self, proofstate_client, memory_exporter
    ):
        """Verify context is preserved even when async operation raises exception."""

        async def failing_operation():
            """Async operation that raises exception."""
            span = proofstate_client.start_observation(name="span-before-error")
            span.end()
            raise ValueError("Test error")

        with proofstate_client.start_as_current_observation(name="root"):
            with propagate_attributes(user_id="error_user"):
                span1 = proofstate_client.start_observation(name="span-before-async")
                span1.end()

                try:
                    await failing_operation()
                except ValueError:
                    pass  # Expected

                span2 = proofstate_client.start_observation(name="span-after-error")
                span2.end()

        # Verify all spans have attributes
        for span_name in ["span-before-async", "span-before-error", "span-after-error"]:
            span_data = self.get_span_by_name(memory_exporter, span_name)
            self.verify_span_attribute(
                span_data, ProofStateOtelSpanAttributes.TRACE_USER_ID, "error_user"
            )

    @pytest.mark.asyncio
    async def test_async_with_metadata(self, proofstate_client, memory_exporter):
        """Verify metadata propagates correctly in async context."""

        async def async_with_metadata():
            span = proofstate_client.start_observation(name="async-metadata-span")
            span.end()

        with proofstate_client.start_as_current_observation(name="root"):
            with propagate_attributes(
                user_id="metadata_user",
                metadata={"async": "true", "operation": "test"},
            ):
                await async_with_metadata()

        span_data = self.get_span_by_name(memory_exporter, "async-metadata-span")
        self.verify_span_attribute(
            span_data, ProofStateOtelSpanAttributes.TRACE_USER_ID, "metadata_user"
        )
        self.verify_span_attribute(
            span_data,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.async",
            "true",
        )
        self.verify_span_attribute(
            span_data,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.operation",
            "test",
        )


class TestPropagateAttributesBaggage(TestPropagateAttributesBase):
    """Tests for as_baggage=True parameter and OpenTelemetry baggage propagation."""

    def test_baggage_is_set_when_as_baggage_true(self, proofstate_client):
        """Verify baggage entries are created with correct keys when as_baggage=True."""
        from opentelemetry import baggage
        from opentelemetry import context as otel_context

        with proofstate_client.start_as_current_observation(name="parent"):
            with propagate_attributes(
                user_id="user_123",
                session_id="session_abc",
                metadata={"env": "test", "version": "2.0"},
                as_baggage=True,
            ):
                # Get current context and inspect baggage
                current_context = otel_context.get_current()
                baggage_entries = baggage.get_all(context=current_context)

                # Verify baggage entries exist with correct keys
                assert "proofstate_user_id" in baggage_entries
                assert baggage_entries["proofstate_user_id"] == "user_123"

                assert "proofstate_session_id" in baggage_entries
                assert baggage_entries["proofstate_session_id"] == "session_abc"

                assert "proofstate_metadata_env" in baggage_entries
                assert baggage_entries["proofstate_metadata_env"] == "test"

                assert "proofstate_metadata_version" in baggage_entries
                assert baggage_entries["proofstate_metadata_version"] == "2.0"

    def test_spans_receive_attributes_from_baggage(
        self, proofstate_client, memory_exporter
    ):
        """Verify child spans get attributes when parent uses as_baggage=True."""
        with proofstate_client.start_as_current_observation(name="parent"):
            with propagate_attributes(
                user_id="baggage_user",
                session_id="baggage_session",
                metadata={"source": "baggage"},
                as_baggage=True,
            ):
                # Create child span
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        # Verify child span has all attributes
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_span_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_USER_ID, "baggage_user"
        )
        self.verify_span_attribute(
            child_span,
            ProofStateOtelSpanAttributes.TRACE_SESSION_ID,
            "baggage_session",
        )
        self.verify_span_attribute(
            child_span,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.source",
            "baggage",
        )

    def test_baggage_disabled_by_default(self, proofstate_client):
        """Verify as_baggage=False (default) doesn't create baggage entries."""
        from opentelemetry import baggage
        from opentelemetry import context as otel_context

        from proofstate._client.propagation import PROOFSTATE_TRACE_ID_BAGGAGE_KEY

        with proofstate_client.start_as_current_observation(name="parent"):
            with propagate_attributes(
                user_id="user_123",
                session_id="session_abc",
            ):
                # Get current context and inspect baggage
                current_context = otel_context.get_current()
                baggage_entries = baggage.get_all(context=current_context)
                user_baggage_entries = {
                    key: value
                    for key, value in baggage_entries.items()
                    if key != PROOFSTATE_TRACE_ID_BAGGAGE_KEY
                }

                assert user_baggage_entries == {}

    def test_metadata_key_with_user_id_substring_doesnt_collide(
        self, proofstate_client, memory_exporter
    ):
        """Verify metadata key containing 'user_id' substring doesn't map to TRACE_USER_ID."""
        with proofstate_client.start_as_current_observation(name="parent"):
            with propagate_attributes(
                metadata={"user_info": "some_data", "user_id_copy": "another"},
                as_baggage=True,
            ):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        child_span = self.get_span_by_name(memory_exporter, "child-span")

        # Should NOT have TRACE_USER_ID attribute
        self.verify_missing_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_USER_ID
        )

        # Should have metadata attributes with correct keys
        self.verify_span_attribute(
            child_span,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.user_info",
            "some_data",
        )
        self.verify_span_attribute(
            child_span,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.user_id_copy",
            "another",
        )

    def test_metadata_key_with_session_substring_doesnt_collide(
        self, proofstate_client, memory_exporter
    ):
        """Verify metadata key containing 'session_id' substring doesn't map to TRACE_SESSION_ID."""
        with proofstate_client.start_as_current_observation(name="parent"):
            with propagate_attributes(
                metadata={"session_data": "value1", "session_id_backup": "value2"},
                as_baggage=True,
            ):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        child_span = self.get_span_by_name(memory_exporter, "child-span")

        # Should NOT have TRACE_SESSION_ID attribute
        self.verify_missing_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_SESSION_ID
        )

        # Should have metadata attributes with correct keys
        self.verify_span_attribute(
            child_span,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.session_data",
            "value1",
        )
        self.verify_span_attribute(
            child_span,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.session_id_backup",
            "value2",
        )

    def test_metadata_keys_extract_correctly_from_baggage(
        self, proofstate_client, memory_exporter
    ):
        """Verify metadata keys are correctly formatted in baggage and extracted back."""
        with proofstate_client.start_as_current_observation(name="parent"):
            with propagate_attributes(
                metadata={
                    "env": "production",
                    "region": "us-west",
                    "experiment_id": "exp_123",
                },
                as_baggage=True,
            ):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        child_span = self.get_span_by_name(memory_exporter, "child-span")

        # All metadata should be under TRACE_METADATA prefix
        self.verify_span_attribute(
            child_span,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.env",
            "production",
        )
        self.verify_span_attribute(
            child_span,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.region",
            "us-west",
        )
        self.verify_span_attribute(
            child_span,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.experiment_id",
            "exp_123",
        )

    def test_baggage_and_context_both_propagate(
        self, proofstate_client, memory_exporter
    ):
        """Verify attributes propagate when both baggage and context mechanisms are active."""
        with proofstate_client.start_as_current_observation(name="parent"):
            # Enable baggage
            with propagate_attributes(
                user_id="user_both",
                session_id="session_both",
                metadata={"source": "both"},
                as_baggage=True,
            ):
                # Create multiple levels of nesting
                with proofstate_client.start_as_current_observation(name="middle"):
                    child = proofstate_client.start_observation(name="leaf")
                    child.end()

        # Verify all spans have attributes
        for span_name in ["parent", "middle", "leaf"]:
            span_data = self.get_span_by_name(memory_exporter, span_name)
            self.verify_span_attribute(
                span_data, ProofStateOtelSpanAttributes.TRACE_USER_ID, "user_both"
            )
            self.verify_span_attribute(
                span_data, ProofStateOtelSpanAttributes.TRACE_SESSION_ID, "session_both"
            )
            self.verify_span_attribute(
                span_data,
                f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.source",
                "both",
            )

    def test_baggage_survives_context_isolation(
        self, proofstate_client, memory_exporter
    ):
        """Simulate cross-process scenario: baggage persists when context is detached/reattached."""
        from opentelemetry import context as otel_context

        # Step 1: Create context with baggage
        with proofstate_client.start_as_current_observation(name="original-process"):
            with propagate_attributes(
                user_id="cross_process_user",
                session_id="cross_process_session",
                as_baggage=True,
            ):
                # Capture the context with baggage
                context_with_baggage = otel_context.get_current()

        # Step 2: Simulate "remote" process by creating span in saved context
        # This mimics what happens when receiving an HTTP request with baggage headers
        token = otel_context.attach(context_with_baggage)
        try:
            with proofstate_client.start_as_current_observation(name="remote-process"):
                child = proofstate_client.start_observation(name="remote-child")
                child.end()
        finally:
            otel_context.detach(token)

        # Verify remote spans have the propagated attributes from baggage
        remote_child = self.get_span_by_name(memory_exporter, "remote-child")
        self.verify_span_attribute(
            remote_child,
            ProofStateOtelSpanAttributes.TRACE_USER_ID,
            "cross_process_user",
        )
        self.verify_span_attribute(
            remote_child,
            ProofStateOtelSpanAttributes.TRACE_SESSION_ID,
            "cross_process_session",
        )


class TestPropagateAttributesEnvironment(TestPropagateAttributesBase):
    """Tests for first-class ProofState environment propagation."""

    def _capture_score_events(self, monkeypatch, proofstate_client):
        """Capture score ingestion events before they reach the background queue."""

        score_events = []
        assert proofstate_client._resources is not None

        def capture_score_event(event, *, force_sample=False):
            score_events.append(event)

        monkeypatch.setattr(
            proofstate_client._resources,
            "add_score_task",
            capture_score_event,
        )

        return score_events

    def test_environment_propagates_to_child_spans(
        self, proofstate_client, memory_exporter
    ):
        """Verify environment propagates as proofstate.environment, not metadata."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(environment="staging"):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_span_attribute(
            child_span, ProofStateOtelSpanAttributes.ENVIRONMENT, "staging"
        )
        self.verify_missing_attribute(
            child_span, f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.environment"
        )

    def test_environment_with_baggage(self, proofstate_client, memory_exporter):
        """Verify environment is written to baggage and extracted onto spans."""
        from opentelemetry import baggage
        from opentelemetry import context as otel_context

        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(environment="qa", as_baggage=True):
                current_context = otel_context.get_current()
                baggage_entries = baggage.get_all(context=current_context)

                assert baggage_entries["proofstate_environment"] == "qa"

                child = proofstate_client.start_observation(name="child-span")
                child.end()

        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_span_attribute(
            child_span, ProofStateOtelSpanAttributes.ENVIRONMENT, "qa"
        )

    def test_environment_overrides_client_default_inside_context(
        self, proofstate_client, memory_exporter
    ):
        """Propagated environment wins over the local client environment."""
        proofstate_client._environment = "proxy-prod"

        with propagate_attributes(environment="staging"):
            with proofstate_client.start_as_current_observation(name="request-span"):
                pass

        with proofstate_client.start_as_current_observation(name="local-span"):
            pass

        request_span = self.get_span_by_name(memory_exporter, "request-span")
        self.verify_span_attribute(
            request_span, ProofStateOtelSpanAttributes.ENVIRONMENT, "staging"
        )

        local_span = self.get_span_by_name(memory_exporter, "local-span")
        self.verify_span_attribute(
            local_span, ProofStateOtelSpanAttributes.ENVIRONMENT, "proxy-prod"
        )

    def test_environment_baggage_overrides_client_default_after_context_attach(
        self, proofstate_client, memory_exporter
    ):
        """Simulate cross-process extraction where caller environment beats proxy default."""
        from opentelemetry import context as otel_context

        proofstate_client._environment = "proxy-prod"

        with propagate_attributes(environment="dev", as_baggage=True):
            context_with_baggage = otel_context.get_current()

        token = otel_context.attach(context_with_baggage)
        try:
            with proofstate_client.start_as_current_observation(name="proxy-request"):
                child = proofstate_client.start_observation(name="proxy-child")
                child.end()
        finally:
            otel_context.detach(token)

        proxy_request = self.get_span_by_name(memory_exporter, "proxy-request")
        self.verify_span_attribute(
            proxy_request, ProofStateOtelSpanAttributes.ENVIRONMENT, "dev"
        )

        proxy_child = self.get_span_by_name(memory_exporter, "proxy-child")
        self.verify_span_attribute(
            proxy_child, ProofStateOtelSpanAttributes.ENVIRONMENT, "dev"
        )

    def test_span_score_uses_propagated_environment(
        self, monkeypatch, proofstate_client
    ):
        """Score events created from a span use the span's resolved environment."""
        score_events = self._capture_score_events(monkeypatch, proofstate_client)
        proofstate_client._environment = "proxy-prod"

        with propagate_attributes(environment="dev"):
            with proofstate_client.start_as_current_observation(
                name="request-span"
            ) as span:
                span.score(name="quality", value=1.0, data_type="NUMERIC")

        assert len(score_events) == 1
        assert score_events[0]["body"].environment == "dev"

    def test_span_score_trace_uses_propagated_environment(
        self, monkeypatch, proofstate_client
    ):
        """Trace scores created from a span use the span's resolved environment."""
        score_events = self._capture_score_events(monkeypatch, proofstate_client)
        proofstate_client._environment = "proxy-prod"

        with propagate_attributes(environment="staging"):
            with proofstate_client.start_as_current_observation(
                name="request-span"
            ) as span:
                span.score_trace(name="overall-quality", value=0.95)

        assert len(score_events) == 1
        assert score_events[0]["body"].environment == "staging"

    def test_current_score_helpers_use_propagated_environment(
        self, monkeypatch, proofstate_client
    ):
        """Current-span and current-trace scores use the active span environment."""
        score_events = self._capture_score_events(monkeypatch, proofstate_client)
        proofstate_client._environment = "proxy-prod"

        with propagate_attributes(environment="qa"):
            with proofstate_client.start_as_current_observation(name="request-span"):
                proofstate_client.score_current_span(
                    name="span-quality", value=0.9, data_type="NUMERIC"
                )
                proofstate_client.score_current_trace(
                    name="trace-quality", value=0.8, data_type="NUMERIC"
                )

        assert [event["body"].environment for event in score_events] == ["qa", "qa"]

    def test_environment_exactly_40_chars_is_accepted(
        self, proofstate_client, memory_exporter
    ):
        """Verify environment accepts ProofState's 40-character public limit."""
        environment_40 = "e" * 40

        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(environment=environment_40):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_span_attribute(
            child_span, ProofStateOtelSpanAttributes.ENVIRONMENT, environment_40
        )

    @pytest.mark.parametrize(
        "environment",
        [
            "Production",
            "proofstate-prod",
            "prod.us",
            "",
            "p" * 41,
            "prod\n",
            "\nprod",
            123,
        ],
    )
    def test_invalid_environment_is_dropped(
        self, proofstate_client, memory_exporter, environment
    ):
        """Invalid propagated environments do not set proofstate.environment."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(environment=environment):  # type: ignore[arg-type]
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_missing_attribute(
            child_span, ProofStateOtelSpanAttributes.ENVIRONMENT
        )


class TestPropagateAttributesVersion(TestPropagateAttributesBase):
    """Tests for version parameter propagation."""

    def test_version_propagates_to_child_spans(
        self, proofstate_client, memory_exporter
    ):
        """Verify version propagates to all child spans within context."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(version="v1.2.3"):
                child1 = proofstate_client.start_observation(name="child-span-1")
                child1.end()

                child2 = proofstate_client.start_observation(name="child-span-2")
                child2.end()

        # Verify both children have version
        child1_span = self.get_span_by_name(memory_exporter, "child-span-1")
        self.verify_span_attribute(
            child1_span,
            ProofStateOtelSpanAttributes.VERSION,
            "v1.2.3",
        )

        child2_span = self.get_span_by_name(memory_exporter, "child-span-2")
        self.verify_span_attribute(
            child2_span,
            ProofStateOtelSpanAttributes.VERSION,
            "v1.2.3",
        )

    def test_version_with_user_and_session(self, proofstate_client, memory_exporter):
        """Verify version works together with user_id and session_id."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(
                user_id="user_123",
                session_id="session_abc",
                version="2.0.0",
            ):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        # Verify child has all attributes
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_span_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_USER_ID, "user_123"
        )
        self.verify_span_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_SESSION_ID, "session_abc"
        )
        self.verify_span_attribute(
            child_span, ProofStateOtelSpanAttributes.VERSION, "2.0.0"
        )

    def test_version_with_metadata(self, proofstate_client, memory_exporter):
        """Verify version works together with metadata."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(
                version="1.0.0",
                metadata={"env": "production", "region": "us-east"},
            ):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_span_attribute(
            child_span, ProofStateOtelSpanAttributes.VERSION, "1.0.0"
        )
        self.verify_span_attribute(
            child_span,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.env",
            "production",
        )
        self.verify_span_attribute(
            child_span,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.region",
            "us-east",
        )

    def test_version_validation_over_200_chars(
        self, proofstate_client, memory_exporter
    ):
        """Verify version over 200 characters is dropped with warning."""
        long_version = "v" + "1.0.0" * 50  # Create a very long version string

        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(version=long_version):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        # Verify child does NOT have version
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_missing_attribute(child_span, ProofStateOtelSpanAttributes.VERSION)

    def test_version_exactly_200_chars(self, proofstate_client, memory_exporter):
        """Verify exactly 200 character version is accepted."""
        version_200 = "v" * 200

        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(version=version_200):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        # Verify child HAS version
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_span_attribute(
            child_span, ProofStateOtelSpanAttributes.VERSION, version_200
        )

    def test_version_nested_contexts_inner_overwrites(
        self, proofstate_client, memory_exporter
    ):
        """Verify inner context overwrites outer version."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(version="1.0.0"):
                # Create span in outer context
                span1 = proofstate_client.start_observation(name="span-1")
                span1.end()

                # Inner context with different version
                with propagate_attributes(version="2.0.0"):
                    span2 = proofstate_client.start_observation(name="span-2")
                    span2.end()

                # Back to outer context
                span3 = proofstate_client.start_observation(name="span-3")
                span3.end()

        # Verify: span1 and span3 have version 1.0.0, span2 has 2.0.0
        span1_data = self.get_span_by_name(memory_exporter, "span-1")
        self.verify_span_attribute(
            span1_data, ProofStateOtelSpanAttributes.VERSION, "1.0.0"
        )

        span2_data = self.get_span_by_name(memory_exporter, "span-2")
        self.verify_span_attribute(
            span2_data, ProofStateOtelSpanAttributes.VERSION, "2.0.0"
        )

        span3_data = self.get_span_by_name(memory_exporter, "span-3")
        self.verify_span_attribute(
            span3_data, ProofStateOtelSpanAttributes.VERSION, "1.0.0"
        )

    def test_version_with_baggage(self, proofstate_client, memory_exporter):
        """Verify version propagates through baggage."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(
                version="baggage_version",
                user_id="user_123",
                as_baggage=True,
            ):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        # Verify child has version
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_span_attribute(
            child_span, ProofStateOtelSpanAttributes.VERSION, "baggage_version"
        )
        self.verify_span_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_USER_ID, "user_123"
        )

    def test_version_semantic_versioning_formats(
        self, proofstate_client, memory_exporter
    ):
        """Verify various semantic versioning formats work correctly."""
        test_versions = [
            "1.0.0",
            "v2.3.4",
            "1.0.0-alpha",
            "2.0.0-beta.1",
            "3.1.4-rc.2+build.123",
            "0.1.0",
        ]

        with proofstate_client.start_as_current_observation(name="parent-span"):
            for idx, version in enumerate(test_versions):
                with propagate_attributes(version=version):
                    span = proofstate_client.start_observation(name=f"span-{idx}")
                    span.end()

        # Verify all versions are correctly set
        for idx, expected_version in enumerate(test_versions):
            span_data = self.get_span_by_name(memory_exporter, f"span-{idx}")
            self.verify_span_attribute(
                span_data, ProofStateOtelSpanAttributes.VERSION, expected_version
            )

    def test_version_non_string_dropped(self, proofstate_client, memory_exporter):
        """Verify non-string version is dropped with warning."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(version=123):  # type: ignore
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        # Verify child does NOT have version
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_missing_attribute(child_span, ProofStateOtelSpanAttributes.VERSION)

    def test_version_propagates_to_grandchildren(
        self, proofstate_client, memory_exporter
    ):
        """Verify version propagates through multiple levels of nesting."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(version="nested_v1"):
                with proofstate_client.start_as_current_observation(name="child-span"):
                    grandchild = proofstate_client.start_observation(
                        name="grandchild-span"
                    )
                    grandchild.end()

        # Verify all three levels have version
        parent_span = self.get_span_by_name(memory_exporter, "parent-span")
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        grandchild_span = self.get_span_by_name(memory_exporter, "grandchild-span")

        for span in [parent_span, child_span, grandchild_span]:
            self.verify_span_attribute(
                span, ProofStateOtelSpanAttributes.VERSION, "nested_v1"
            )

    @pytest.mark.asyncio
    async def test_version_with_async(self, proofstate_client, memory_exporter):
        """Verify version propagates in async context."""

        async def async_operation():
            span = proofstate_client.start_observation(name="async-span")
            span.end()

        with proofstate_client.start_as_current_observation(name="parent"):
            with propagate_attributes(version="async_v1.0"):
                await async_operation()

        async_span = self.get_span_by_name(memory_exporter, "async-span")
        self.verify_span_attribute(
            async_span, ProofStateOtelSpanAttributes.VERSION, "async_v1.0"
        )

    def test_version_attribute_key_format(self, proofstate_client, memory_exporter):
        """Verify version uses correct attribute key format."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(version="key_test_v1"):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        child_span = self.get_span_by_name(memory_exporter, "child-span")
        attributes = child_span["attributes"]

        # Verify exact attribute key
        assert ProofStateOtelSpanAttributes.VERSION in attributes
        assert attributes[ProofStateOtelSpanAttributes.VERSION] == "key_test_v1"


class TestPropagateAttributesTags(TestPropagateAttributesBase):
    """Tests for tags parameter propagation."""

    def test_tags_propagate_to_child_spans(self, proofstate_client, memory_exporter):
        """Verify tags propagate to all child spans within context."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(tags=["production", "api-v2", "critical"]):
                child1 = proofstate_client.start_observation(name="child-span-1")
                child1.end()

                child2 = proofstate_client.start_observation(name="child-span-2")
                child2.end()

        # Verify both children have tags
        child1_span = self.get_span_by_name(memory_exporter, "child-span-1")
        self.verify_span_attribute(
            child1_span,
            ProofStateOtelSpanAttributes.TRACE_TAGS,
            tuple(["production", "api-v2", "critical"]),
        )

        child2_span = self.get_span_by_name(memory_exporter, "child-span-2")
        self.verify_span_attribute(
            child2_span,
            ProofStateOtelSpanAttributes.TRACE_TAGS,
            tuple(["production", "api-v2", "critical"]),
        )

    def test_tags_with_single_tag(self, proofstate_client, memory_exporter):
        """Verify single tag works correctly."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(tags=["experiment"]):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_span_attribute(
            child_span,
            ProofStateOtelSpanAttributes.TRACE_TAGS,
            tuple(["experiment"]),
        )

    def test_empty_tags_list(self, proofstate_client, memory_exporter):
        """Verify empty tags list is handled correctly."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(tags=[]):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        # With empty list, tags should not be set
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_missing_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_TAGS
        )

    def test_tags_with_user_and_session(self, proofstate_client, memory_exporter):
        """Verify tags work together with user_id and session_id."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(
                user_id="user_123",
                session_id="session_abc",
                tags=["test", "debug"],
            ):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        # Verify child has all attributes
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_span_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_USER_ID, "user_123"
        )
        self.verify_span_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_SESSION_ID, "session_abc"
        )
        self.verify_span_attribute(
            child_span,
            ProofStateOtelSpanAttributes.TRACE_TAGS,
            tuple(["test", "debug"]),
        )

    def test_tags_with_metadata(self, proofstate_client, memory_exporter):
        """Verify tags work together with metadata."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(
                tags=["experiment-a", "variant-1"],
                metadata={"env": "staging"},
            ):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_span_attribute(
            child_span,
            ProofStateOtelSpanAttributes.TRACE_TAGS,
            tuple(["experiment-a", "variant-1"]),
        )
        self.verify_span_attribute(
            child_span,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.env",
            "staging",
        )

    def test_tags_validation_with_invalid_tag(self, proofstate_client, memory_exporter):
        """Verify tags with one invalid entry drops all tags."""
        long_tag = "x" * 201  # Over 200 chars

        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(tags=["valid_tag", long_tag]):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_span_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_TAGS, tuple(["valid_tag"])
        )

    def test_tags_nested_contexts_inner_appends(
        self, proofstate_client, memory_exporter
    ):
        """Verify inner context appends to outer tags."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(tags=["outer", "tag1"]):
                # Create span in outer context
                span1 = proofstate_client.start_observation(name="span-1")
                span1.end()

                # Inner context with more tags
                with propagate_attributes(tags=["inner", "tag2"]):
                    span2 = proofstate_client.start_observation(name="span-2")
                    span2.end()

                # Back to outer context
                span3 = proofstate_client.start_observation(name="span-3")
                span3.end()

        # Verify: span1 and span3 have outer tags, span2 has inner tags
        span1_data = self.get_span_by_name(memory_exporter, "span-1")
        self.verify_span_attribute(
            span1_data,
            ProofStateOtelSpanAttributes.TRACE_TAGS,
            tuple(["outer", "tag1"]),
        )

        span2_data = self.get_span_by_name(memory_exporter, "span-2")
        self.verify_span_attribute(
            span2_data,
            ProofStateOtelSpanAttributes.TRACE_TAGS,
            tuple(
                [
                    "outer",
                    "tag1",
                    "inner",
                    "tag2",
                ]
            ),
        )

        span3_data = self.get_span_by_name(memory_exporter, "span-3")
        self.verify_span_attribute(
            span3_data,
            ProofStateOtelSpanAttributes.TRACE_TAGS,
            tuple(["outer", "tag1"]),
        )

    def test_tags_with_baggage(self, proofstate_client, memory_exporter):
        """Verify tags propagate through baggage."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(
                tags=["baggage_tag1", "baggage_tag2"],
                as_baggage=True,
            ):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        # Verify child has tags
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_span_attribute(
            child_span,
            ProofStateOtelSpanAttributes.TRACE_TAGS,
            tuple(["baggage_tag1", "baggage_tag2"]),
        )

    def test_tags_propagate_to_grandchildren(self, proofstate_client, memory_exporter):
        """Verify tags propagate through multiple levels of nesting."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(tags=["level1", "level2", "level3"]):
                with proofstate_client.start_as_current_observation(name="child-span"):
                    grandchild = proofstate_client.start_observation(
                        name="grandchild-span"
                    )
                    grandchild.end()

        # Verify all three levels have tags
        parent_span = self.get_span_by_name(memory_exporter, "parent-span")
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        grandchild_span = self.get_span_by_name(memory_exporter, "grandchild-span")

        for span in [parent_span, child_span, grandchild_span]:
            self.verify_span_attribute(
                span,
                ProofStateOtelSpanAttributes.TRACE_TAGS,
                tuple(["level1", "level2", "level3"]),
            )

    @pytest.mark.asyncio
    async def test_tags_with_async(self, proofstate_client, memory_exporter):
        """Verify tags propagate in async context."""

        async def async_operation():
            span = proofstate_client.start_observation(name="async-span")
            span.end()

        with proofstate_client.start_as_current_observation(name="parent"):
            with propagate_attributes(tags=["async", "test"]):
                await async_operation()

        async_span = self.get_span_by_name(memory_exporter, "async-span")
        self.verify_span_attribute(
            async_span,
            ProofStateOtelSpanAttributes.TRACE_TAGS,
            tuple(["async", "test"]),
        )

    def test_tags_attribute_key_format(self, proofstate_client, memory_exporter):
        """Verify tags use correct attribute key format."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(tags=["key_test"]):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        child_span = self.get_span_by_name(memory_exporter, "child-span")
        attributes = child_span["attributes"]

        # Verify exact attribute key
        assert ProofStateOtelSpanAttributes.TRACE_TAGS in attributes
        assert attributes[ProofStateOtelSpanAttributes.TRACE_TAGS] == tuple(
            ["key_test"]
        )


class TestPropagateAttributesExperiment(TestPropagateAttributesBase):
    """Tests for experiment attribute propagation."""

    @pytest.mark.asyncio
    async def test_experiment_propagates_user_id_in_async_context(
        self, proofstate_client, memory_exporter
    ):
        """Verify run_experiment keeps propagated attributes when called from async code."""
        import asyncio

        local_data = [{"input": "test input", "expected_output": "expected output"}]

        async def async_task(*, item, **kwargs):
            await asyncio.sleep(0.001)
            return f"processed: {item['input']}"

        with propagate_attributes(user_id="async-experiment-user"):
            proofstate_client.run_experiment(
                name="Async Experiment",
                data=local_data,
                task=async_task,
            )

        proofstate_client.flush()

        root_span = self.get_span_by_name(memory_exporter, "experiment-item-run")
        self.verify_span_attribute(
            root_span,
            ProofStateOtelSpanAttributes.TRACE_USER_ID,
            "async-experiment-user",
        )

    def test_experiment_attributes_propagate_without_dataset(
        self, proofstate_client, memory_exporter
    ):
        """Test experiment attribute propagation with local data (no ProofState dataset)."""
        # Create local dataset with metadata
        local_data = [
            {
                "input": "test input 1",
                "expected_output": "expected result 1",
                "metadata": {"item_type": "test", "priority": "high"},
            },
        ]

        # Task function that creates child spans
        def task_with_child_spans(*, item, **kwargs):
            # Create child spans to verify propagation
            child1 = proofstate_client.start_observation(name="child-span-1")
            child1.end()

            child2 = proofstate_client.start_observation(name="child-span-2")
            child2.end()

            return f"processed: {item.get('input') if isinstance(item, dict) else item.input}"

        # Run experiment with local data
        experiment_metadata = {"version": "1.0", "model": "test-model"}
        result = proofstate_client.run_experiment(
            name="Test Experiment",
            description="Test experiment description",
            data=local_data,
            task=task_with_child_spans,
            metadata=experiment_metadata,
        )

        # Flush to ensure spans are exported
        proofstate_client.flush()

        # Get the root span
        root_spans = self.get_spans_by_name(memory_exporter, "experiment-item-run")
        assert len(root_spans) >= 1, "Should have at least 1 root span"
        first_root = root_spans[0]

        # Root-only attributes should be on root
        self.verify_span_attribute(
            first_root,
            ProofStateOtelSpanAttributes.EXPERIMENT_DESCRIPTION,
            "Test experiment description",
        )
        self.verify_span_attribute(
            first_root,
            ProofStateOtelSpanAttributes.EXPERIMENT_ITEM_EXPECTED_OUTPUT,
            _serialize("expected result 1"),
        )

        # Propagated attributes should also be on root
        experiment_id = first_root["attributes"][
            ProofStateOtelSpanAttributes.EXPERIMENT_ID
        ]
        assert result.experiment_id == experiment_id
        experiment_item_id = first_root["attributes"][
            ProofStateOtelSpanAttributes.EXPERIMENT_ITEM_ID
        ]
        root_observation_id = first_root["attributes"][
            ProofStateOtelSpanAttributes.EXPERIMENT_ITEM_ROOT_OBSERVATION_ID
        ]

        self.verify_span_attribute(
            first_root,
            ProofStateOtelSpanAttributes.EXPERIMENT_NAME,
            result.run_name,
        )
        for metadata_key, metadata_value in experiment_metadata.items():
            self.verify_span_attribute(
                first_root,
                f"{ProofStateOtelSpanAttributes.EXPERIMENT_METADATA}.{metadata_key}",
                metadata_value,
            )

        self.verify_span_attribute(
            first_root,
            f"{ProofStateOtelSpanAttributes.EXPERIMENT_ITEM_METADATA}.item_type",
            "test",
        )
        self.verify_span_attribute(
            first_root,
            f"{ProofStateOtelSpanAttributes.EXPERIMENT_ITEM_METADATA}.priority",
            "high",
        )

        # Environment should be set to sdk-experiment
        self.verify_span_attribute(
            first_root,
            ProofStateOtelSpanAttributes.ENVIRONMENT,
            PROOFSTATE_SDK_EXPERIMENT_ENVIRONMENT,
        )

        # Dataset ID should not be set for local data
        self.verify_missing_attribute(
            first_root,
            ProofStateOtelSpanAttributes.EXPERIMENT_DATASET_ID,
        )

        # Verify child spans have propagated attributes but NOT root-only attributes
        child_spans = self.get_spans_by_name(
            memory_exporter, "child-span-1"
        ) + self.get_spans_by_name(memory_exporter, "child-span-2")

        assert len(child_spans) >= 2, "Should have at least 2 child spans"

        for child_span in child_spans[:2]:  # Check first item's children
            # Propagated attributes should be present
            self.verify_span_attribute(
                child_span,
                ProofStateOtelSpanAttributes.EXPERIMENT_ID,
                experiment_id,
            )
            self.verify_span_attribute(
                child_span,
                ProofStateOtelSpanAttributes.EXPERIMENT_NAME,
                result.run_name,
            )
            for metadata_key, metadata_value in experiment_metadata.items():
                self.verify_span_attribute(
                    child_span,
                    f"{ProofStateOtelSpanAttributes.EXPERIMENT_METADATA}.{metadata_key}",
                    metadata_value,
                )
            self.verify_span_attribute(
                child_span,
                ProofStateOtelSpanAttributes.EXPERIMENT_ITEM_ID,
                experiment_item_id,
            )
            self.verify_span_attribute(
                child_span,
                ProofStateOtelSpanAttributes.EXPERIMENT_ITEM_ROOT_OBSERVATION_ID,
                root_observation_id,
            )

            # Environment should be propagated to children
            self.verify_span_attribute(
                child_span,
                ProofStateOtelSpanAttributes.ENVIRONMENT,
                PROOFSTATE_SDK_EXPERIMENT_ENVIRONMENT,
            )

            # Root-only attributes should NOT be present on children
            self.verify_missing_attribute(
                child_span,
                ProofStateOtelSpanAttributes.EXPERIMENT_DESCRIPTION,
            )
            self.verify_missing_attribute(
                child_span,
                ProofStateOtelSpanAttributes.EXPERIMENT_ITEM_EXPECTED_OUTPUT,
            )

            # Dataset ID should not be set for local data
            self.verify_missing_attribute(
                child_span,
                ProofStateOtelSpanAttributes.EXPERIMENT_DATASET_ID,
            )

    def test_experiment_id_is_stable_across_local_items(
        self, proofstate_client, memory_exporter
    ):
        """Test local experiments reuse one experiment ID across all items."""
        local_data = [
            {"input": "test input 1", "expected_output": "expected result 1"},
            {"input": "test input 2", "expected_output": "expected result 2"},
        ]

        result = proofstate_client.run_experiment(
            name="Stable Local Experiment",
            data=local_data,
            task=lambda *, item, **kwargs: f"processed: {item['input']}",
        )

        proofstate_client.flush()

        root_spans = self.get_spans_by_name(memory_exporter, "experiment-item-run")
        experiment_ids = {
            span["attributes"][ProofStateOtelSpanAttributes.EXPERIMENT_ID]
            for span in root_spans
        }

        assert len(experiment_ids) == 1
        assert result.experiment_id == next(iter(experiment_ids))

    def test_experiment_run_metadata_overrides_item_metadata(
        self, proofstate_client, memory_exporter
    ):
        proofstate_client.run_experiment(
            name="Metadata precedence",
            run_name="run-name",
            data=[
                {
                    "input": "test",
                    "metadata": {"shared": "item", "item_only": "yes"},
                }
            ],
            task=lambda *, item, **kwargs: "result",
            metadata={"shared": "run"},
        )
        proofstate_client.flush()

        span = self.get_span_by_name(memory_exporter, "experiment-item-run")
        self.verify_span_attribute(
            span,
            f"{ProofStateOtelSpanAttributes.OBSERVATION_METADATA}.shared",
            "run",
        )
        self.verify_span_attribute(
            span,
            f"{ProofStateOtelSpanAttributes.OBSERVATION_METADATA}.experiment_run_name",
            "run-name",
        )
        self.verify_span_attribute(
            span,
            f"{ProofStateOtelSpanAttributes.OBSERVATION_METADATA}.item_only",
            "yes",
        )

    def test_experiment_attributes_propagate_with_dataset(
        self, proofstate_client, memory_exporter, monkeypatch
    ):
        """Test experiment attribute propagation with ProofState dataset."""
        created_run_items = []

        # Mock the sync API used by run_experiment to create dataset run items
        def mock_create_dataset_run_item(*args, **kwargs):
            from proofstate.api import DatasetRunItem

            created_run_items.append(kwargs)
            return DatasetRunItem(
                id="mock-run-item-id",
                dataset_run_id="mock-dataset-run-id-123",
                dataset_run_name=kwargs.get("run_name", "Dataset Test"),
                dataset_item_id=kwargs.get("dataset_item_id", "mock-item-id"),
                trace_id="mock-trace-id",
                observation_id=kwargs.get("observation_id"),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

        monkeypatch.setattr(
            proofstate_client.api.dataset_run_items,
            "create",
            mock_create_dataset_run_item,
        )

        # Create a mock dataset with items
        dataset_id = "test-dataset-id-456"
        dataset_item_id = "test-dataset-item-id-789"

        mock_dataset = Dataset(
            id=dataset_id,
            name="Test Dataset",
            description="Test dataset description",
            project_id="test-project-id",
            metadata={"test": "metadata"},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        mock_dataset_item = DatasetItem(
            id=dataset_item_id,
            status=DatasetStatus.ACTIVE,
            input="Germany",
            expected_output="Berlin",
            metadata={"source": "dataset", "index": 0},
            source_trace_id=None,
            source_observation_id=None,
            dataset_id=dataset_id,
            dataset_name="Test Dataset",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            media_references=[],
        )

        # Create dataset client with items
        dataset = DatasetClient(
            dataset=mock_dataset,
            items=[mock_dataset_item],
            proofstate_client=proofstate_client,
        )

        # Task with child spans
        def task_with_children(*, item, **kwargs):
            child1 = proofstate_client.start_observation(name="dataset-child-1")
            child1.end()

            child2 = proofstate_client.start_observation(name="dataset-child-2")
            child2.end()

            return f"Capital: {item.expected_output}"

        # Run experiment
        experiment_metadata = {"dataset_version": "v2", "test_run": "true"}
        result = dataset.run_experiment(
            name="Dataset Test",
            description="Dataset experiment description",
            task=task_with_children,
            metadata=experiment_metadata,
        )

        proofstate_client.flush()

        # Verify root has dataset-specific attributes
        root_spans = self.get_spans_by_name(memory_exporter, "experiment-item-run")
        assert len(root_spans) >= 1, "Should have at least 1 root span"
        first_root = root_spans[0]
        task_span = self.get_span_by_name(memory_exporter, "experiment-item-task")
        assert result.experiment_id == "mock-dataset-run-id-123"
        assert len(created_run_items) == 1
        assert created_run_items[0]["observation_id"] == task_span["span_id"]

        # Root-only attributes should be on root
        self.verify_span_attribute(
            first_root,
            ProofStateOtelSpanAttributes.EXPERIMENT_DESCRIPTION,
            "Dataset experiment description",
        )
        self.verify_span_attribute(
            first_root,
            ProofStateOtelSpanAttributes.EXPERIMENT_ITEM_EXPECTED_OUTPUT,
            _serialize("Berlin"),
        )

        # Should have dataset ID (this is the key difference from local data)
        self.verify_span_attribute(
            first_root,
            ProofStateOtelSpanAttributes.EXPERIMENT_DATASET_ID,
            dataset_id,
        )

        # Should have the dataset item ID
        self.verify_span_attribute(
            first_root,
            ProofStateOtelSpanAttributes.EXPERIMENT_ITEM_ID,
            dataset_item_id,
        )
        self.verify_span_attribute(
            first_root,
            ProofStateOtelSpanAttributes.EXPERIMENT_ID,
            result.experiment_id,
        )

        # Should have experiment metadata
        for metadata_key, metadata_value in experiment_metadata.items():
            self.verify_span_attribute(
                first_root,
                f"{ProofStateOtelSpanAttributes.EXPERIMENT_METADATA}.{metadata_key}",
                metadata_value,
            )

        # Environment should be set to sdk-experiment
        self.verify_span_attribute(
            first_root,
            ProofStateOtelSpanAttributes.ENVIRONMENT,
            PROOFSTATE_SDK_EXPERIMENT_ENVIRONMENT,
        )

        # Verify child spans have dataset-specific propagated attributes
        child_spans = self.get_spans_by_name(
            memory_exporter, "dataset-child-1"
        ) + self.get_spans_by_name(memory_exporter, "dataset-child-2")

        assert len(child_spans) >= 2, "Should have at least 2 child spans"

        for child_span in child_spans[:2]:
            # Dataset ID should be propagated to children
            self.verify_span_attribute(
                child_span,
                ProofStateOtelSpanAttributes.EXPERIMENT_DATASET_ID,
                dataset_id,
            )

            # Dataset item ID should be propagated
            self.verify_span_attribute(
                child_span,
                ProofStateOtelSpanAttributes.EXPERIMENT_ITEM_ID,
                dataset_item_id,
            )

            # Experiment metadata should be propagated
            for metadata_key, metadata_value in experiment_metadata.items():
                self.verify_span_attribute(
                    child_span,
                    f"{ProofStateOtelSpanAttributes.EXPERIMENT_METADATA}.{metadata_key}",
                    metadata_value,
                )

            # Item metadata should be propagated
            self.verify_span_attribute(
                child_span,
                f"{ProofStateOtelSpanAttributes.EXPERIMENT_ITEM_METADATA}.source",
                "dataset",
            )
            self.verify_span_attribute(
                child_span,
                f"{ProofStateOtelSpanAttributes.EXPERIMENT_ITEM_METADATA}.index",
                "0",
            )

            # Environment should be propagated to children
            self.verify_span_attribute(
                child_span,
                ProofStateOtelSpanAttributes.ENVIRONMENT,
                PROOFSTATE_SDK_EXPERIMENT_ENVIRONMENT,
            )

            # Root-only attributes should NOT be present on children
            self.verify_missing_attribute(
                child_span,
                ProofStateOtelSpanAttributes.EXPERIMENT_DESCRIPTION,
            )
            self.verify_missing_attribute(
                child_span,
                ProofStateOtelSpanAttributes.EXPERIMENT_ITEM_EXPECTED_OUTPUT,
            )

    def test_experiment_attributes_propagate_to_nested_children(
        self, proofstate_client, memory_exporter
    ):
        """Test experiment attributes propagate to deeply nested child spans."""
        local_data = [{"input": "test", "expected_output": "result"}]

        # Task with deeply nested spans
        def task_with_nested_spans(*, item, **kwargs):
            with proofstate_client.start_as_current_observation(name="child-span"):
                with proofstate_client.start_as_current_observation(
                    name="grandchild-span"
                ):
                    great_grandchild = proofstate_client.start_observation(
                        name="great-grandchild-span"
                    )
                    great_grandchild.end()

            return "processed"

        result = proofstate_client.run_experiment(
            name="Nested Test",
            description="Nested test",
            data=local_data,
            task=task_with_nested_spans,
            metadata={"depth": "test"},
        )

        proofstate_client.flush()

        root_spans = self.get_spans_by_name(memory_exporter, "experiment-item-run")
        first_root = root_spans[0]
        experiment_id = first_root["attributes"][
            ProofStateOtelSpanAttributes.EXPERIMENT_ID
        ]
        root_observation_id = first_root["attributes"][
            ProofStateOtelSpanAttributes.EXPERIMENT_ITEM_ROOT_OBSERVATION_ID
        ]

        # Verify root has environment set
        self.verify_span_attribute(
            first_root,
            ProofStateOtelSpanAttributes.ENVIRONMENT,
            PROOFSTATE_SDK_EXPERIMENT_ENVIRONMENT,
        )

        # Verify all nested children have propagated attributes
        for span_name in ["child-span", "grandchild-span", "great-grandchild-span"]:
            span_data = self.get_span_by_name(memory_exporter, span_name)

            # Propagated attributes should be present
            self.verify_span_attribute(
                span_data,
                ProofStateOtelSpanAttributes.EXPERIMENT_ID,
                experiment_id,
            )
            self.verify_span_attribute(
                span_data,
                ProofStateOtelSpanAttributes.EXPERIMENT_NAME,
                result.run_name,
            )
            self.verify_span_attribute(
                span_data,
                ProofStateOtelSpanAttributes.EXPERIMENT_ITEM_ROOT_OBSERVATION_ID,
                root_observation_id,
            )

            # Environment should be propagated to all nested children
            self.verify_span_attribute(
                span_data,
                ProofStateOtelSpanAttributes.ENVIRONMENT,
                PROOFSTATE_SDK_EXPERIMENT_ENVIRONMENT,
            )

            # Root-only attributes should NOT be present
            self.verify_missing_attribute(
                span_data,
                ProofStateOtelSpanAttributes.EXPERIMENT_DESCRIPTION,
            )
            self.verify_missing_attribute(
                span_data,
                ProofStateOtelSpanAttributes.EXPERIMENT_ITEM_EXPECTED_OUTPUT,
            )

    def test_experiment_metadata_merging(self, proofstate_client, memory_exporter):
        """Test that experiment metadata and item metadata are both propagated correctly."""
        from proofstate._client.attributes import _serialize

        # Rich metadata
        experiment_metadata = {
            "experiment_type": "A/B test",
            "model_version": "2.0",
            "temperature": 0.7,
        }
        item_metadata = {
            "item_category": "finance",
            "difficulty": "hard",
            "language": "en",
        }

        local_data = [
            {
                "input": "test",
                "expected_output": {"status": "success"},
                "metadata": item_metadata,
            }
        ]

        def task_with_child(*, item, **kwargs):
            child = proofstate_client.start_observation(name="metadata-child")
            child.end()
            return "result"

        proofstate_client.run_experiment(
            name="Metadata Test",
            description="Metadata test",
            data=local_data,
            task=task_with_child,
            metadata=experiment_metadata,
        )

        proofstate_client.flush()

        # Verify root span has environment set
        root_span = self.get_span_by_name(memory_exporter, "experiment-item-run")
        self.verify_span_attribute(
            root_span,
            ProofStateOtelSpanAttributes.ENVIRONMENT,
            PROOFSTATE_SDK_EXPERIMENT_ENVIRONMENT,
        )

        # Verify child span has both experiment and item metadata propagated
        child_span = self.get_span_by_name(memory_exporter, "metadata-child")

        # Verify experiment metadata is flattened and propagated
        for metadata_key, metadata_value in experiment_metadata.items():
            self.verify_span_attribute(
                child_span,
                f"{ProofStateOtelSpanAttributes.EXPERIMENT_METADATA}.{metadata_key}",
                _serialize(metadata_value),
            )

        # Verify item metadata is flattened and propagated
        for metadata_key, metadata_value in item_metadata.items():
            self.verify_span_attribute(
                child_span,
                f"{ProofStateOtelSpanAttributes.EXPERIMENT_ITEM_METADATA}.{metadata_key}",
                _serialize(metadata_value),
            )

        # Verify environment is propagated to child
        self.verify_span_attribute(
            child_span,
            ProofStateOtelSpanAttributes.ENVIRONMENT,
            PROOFSTATE_SDK_EXPERIMENT_ENVIRONMENT,
        )

    def test_experiment_metadata_values_are_validated_individually(
        self, proofstate_client, memory_exporter, caplog
    ):
        """Experiment metadata is flattened so large combined dicts still propagate."""

        caplog.set_level("WARNING", logger="proofstate")

        experiment_metadata = {
            "job_name": "j" * 150,
            "build_url": "b" * 150,
            "mode": "offline",
        }

        local_data = [{"input": "test", "expected_output": "success"}]

        def task_with_child(*, item, **kwargs):
            child = proofstate_client.start_observation(name="large-metadata-child")
            child.end()
            return "result"

        proofstate_client.run_experiment(
            name="Large Metadata Test",
            data=local_data,
            task=task_with_child,
            metadata=experiment_metadata,
        )

        proofstate_client.flush()

        child_span = self.get_span_by_name(memory_exporter, "large-metadata-child")

        for metadata_key, metadata_value in experiment_metadata.items():
            self.verify_span_attribute(
                child_span,
                f"{ProofStateOtelSpanAttributes.EXPERIMENT_METADATA}.{metadata_key}",
                metadata_value,
            )

        self.verify_missing_attribute(
            child_span,
            ProofStateOtelSpanAttributes.EXPERIMENT_METADATA,
        )
        assert "experiment_metadata' value is over 200 characters" not in caplog.text


class TestPropagateAttributesTraceName(TestPropagateAttributesBase):
    """Tests for trace_name parameter propagation."""

    def test_trace_name_propagates_to_child_spans(
        self, proofstate_client, memory_exporter
    ):
        """Verify trace_name propagates to all child spans within context."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(trace_name="my-trace-name"):
                child1 = proofstate_client.start_observation(name="child-span-1")
                child1.end()

                child2 = proofstate_client.start_observation(name="child-span-2")
                child2.end()

        # Verify both children have trace_name
        child1_span = self.get_span_by_name(memory_exporter, "child-span-1")
        self.verify_span_attribute(
            child1_span,
            ProofStateOtelSpanAttributes.TRACE_NAME,
            "my-trace-name",
        )

        child2_span = self.get_span_by_name(memory_exporter, "child-span-2")
        self.verify_span_attribute(
            child2_span,
            ProofStateOtelSpanAttributes.TRACE_NAME,
            "my-trace-name",
        )

    def test_trace_name_propagates_to_grandchildren(
        self, proofstate_client, memory_exporter
    ):
        """Verify trace_name propagates through multiple levels of nesting."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(trace_name="nested-trace"):
                with proofstate_client.start_as_current_observation(name="child-span"):
                    grandchild = proofstate_client.start_observation(
                        name="grandchild-span"
                    )
                    grandchild.end()

        # Verify all three levels have trace_name
        parent_span = self.get_span_by_name(memory_exporter, "parent-span")
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        grandchild_span = self.get_span_by_name(memory_exporter, "grandchild-span")

        for span in [parent_span, child_span, grandchild_span]:
            self.verify_span_attribute(
                span, ProofStateOtelSpanAttributes.TRACE_NAME, "nested-trace"
            )

    def test_trace_name_with_user_and_session(self, proofstate_client, memory_exporter):
        """Verify trace_name works together with user_id and session_id."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(
                user_id="user_123",
                session_id="session_abc",
                trace_name="combined-trace",
            ):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        # Verify child has all attributes
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_span_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_USER_ID, "user_123"
        )
        self.verify_span_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_SESSION_ID, "session_abc"
        )
        self.verify_span_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_NAME, "combined-trace"
        )

    def test_trace_name_with_version(self, proofstate_client, memory_exporter):
        """Verify trace_name works together with version."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(
                trace_name="versioned-trace",
                version="1.0.0",
            ):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_span_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_NAME, "versioned-trace"
        )
        self.verify_span_attribute(
            child_span, ProofStateOtelSpanAttributes.VERSION, "1.0.0"
        )

    def test_trace_name_with_metadata(self, proofstate_client, memory_exporter):
        """Verify trace_name works together with metadata."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(
                trace_name="metadata-trace",
                metadata={"env": "production", "region": "us-east"},
            ):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_span_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_NAME, "metadata-trace"
        )
        self.verify_span_attribute(
            child_span,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.env",
            "production",
        )
        self.verify_span_attribute(
            child_span,
            f"{ProofStateOtelSpanAttributes.TRACE_METADATA}.region",
            "us-east",
        )

    def test_trace_name_validation_over_200_chars(
        self, proofstate_client, memory_exporter
    ):
        """Verify trace_name over 200 characters is dropped with warning."""
        long_name = "trace-" + "a" * 200  # Create a very long trace name

        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(trace_name=long_name):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        # Verify child does NOT have trace_name
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_missing_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_NAME
        )

    def test_trace_name_exactly_200_chars(self, proofstate_client, memory_exporter):
        """Verify exactly 200 character trace_name is accepted."""
        trace_name_200 = "t" * 200

        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(trace_name=trace_name_200):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        # Verify child HAS trace_name
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_span_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_NAME, trace_name_200
        )

    def test_trace_name_nested_contexts_inner_overwrites(
        self, proofstate_client, memory_exporter
    ):
        """Verify inner context overwrites outer trace_name."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(trace_name="outer-trace"):
                # Create span in outer context
                span1 = proofstate_client.start_observation(name="span-1")
                span1.end()

                # Inner context with different trace_name
                with propagate_attributes(trace_name="inner-trace"):
                    span2 = proofstate_client.start_observation(name="span-2")
                    span2.end()

                # Back to outer context
                span3 = proofstate_client.start_observation(name="span-3")
                span3.end()

        # Verify: span1 and span3 have outer-trace, span2 has inner-trace
        span1_data = self.get_span_by_name(memory_exporter, "span-1")
        self.verify_span_attribute(
            span1_data, ProofStateOtelSpanAttributes.TRACE_NAME, "outer-trace"
        )

        span2_data = self.get_span_by_name(memory_exporter, "span-2")
        self.verify_span_attribute(
            span2_data, ProofStateOtelSpanAttributes.TRACE_NAME, "inner-trace"
        )

        span3_data = self.get_span_by_name(memory_exporter, "span-3")
        self.verify_span_attribute(
            span3_data, ProofStateOtelSpanAttributes.TRACE_NAME, "outer-trace"
        )

    def test_trace_name_sets_on_current_span(self, proofstate_client, memory_exporter):
        """Verify trace_name is set on the current span when entering context."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(trace_name="current-trace"):
                pass  # Just enter and exit context

        # Verify parent span has trace_name set
        parent_span = self.get_span_by_name(memory_exporter, "parent-span")
        self.verify_span_attribute(
            parent_span, ProofStateOtelSpanAttributes.TRACE_NAME, "current-trace"
        )

    def test_trace_name_non_string_dropped(self, proofstate_client, memory_exporter):
        """Verify non-string trace_name is dropped with warning."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(trace_name=123):  # type: ignore
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        # Verify child does NOT have trace_name
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_missing_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_NAME
        )

    def test_trace_name_with_baggage(self, proofstate_client, memory_exporter):
        """Verify trace_name propagates through baggage."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(
                trace_name="baggage-trace",
                user_id="user_123",
                as_baggage=True,
            ):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        # Verify child has trace_name
        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_span_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_NAME, "baggage-trace"
        )
        self.verify_span_attribute(
            child_span, ProofStateOtelSpanAttributes.TRACE_USER_ID, "user_123"
        )


class TestPropagateAttributesPrompt(TestPropagateAttributesBase):
    """Tests for prompt linking via propagate_attributes."""

    def _make_prompt_client(self, name="test-prompt", version=3, is_fallback=False):
        from proofstate.api import Prompt_Text
        from proofstate.model import TextPromptClient

        prompt = Prompt_Text(
            name=name,
            version=version,
            prompt="Make me laugh",
            type="text",
            labels=[],
            config={},
            tags=[],
        )

        return TextPromptClient(prompt, is_fallback=is_fallback)

    def test_prompt_client_propagates_to_child_spans(
        self, proofstate_client, memory_exporter
    ):
        """Verify a PromptClient propagates name and version to all child spans."""
        prompt = self._make_prompt_client(name="test-prompt", version=3)

        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(prompt=prompt):
                child1 = proofstate_client.start_observation(name="child-span-1")
                child1.end()

                child2 = proofstate_client.start_observation(
                    name="child-span-2", as_type="generation"
                )
                child2.end()

        for name in ("child-span-1", "child-span-2"):
            child_span = self.get_span_by_name(memory_exporter, name)
            self.verify_span_attribute(
                child_span,
                ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_NAME,
                "test-prompt",
            )
            self.verify_span_attribute(
                child_span,
                ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_VERSION,
                3,
            )

    def test_prompt_dict_propagates_to_child_spans(
        self, proofstate_client, memory_exporter
    ):
        """Verify a plain dict with name and version keys is supported."""
        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(prompt={"name": "dict-prompt", "version": 7}):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_span_attribute(
            child_span,
            ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_NAME,
            "dict-prompt",
        )
        self.verify_span_attribute(
            child_span,
            ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_VERSION,
            7,
        )

    def test_prompt_duck_typed_object_supported(
        self, proofstate_client, memory_exporter
    ):
        """Verify any object exposing name and version attributes is supported."""

        class MyPrompt:
            name = "duck-prompt"
            version = 2

        with proofstate_client.start_as_current_observation(name="parent-span"):
            with propagate_attributes(prompt=MyPrompt()):
                child = proofstate_client.start_observation(name="child-span")
                child.end()

        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_span_attribute(
            child_span,
            ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_NAME,
            "duck-prompt",
        )
        self.verify_span_attribute(
            child_span,
            ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_VERSION,
            2,
        )

    def test_prompt_version_digit_string_coerced_to_int(
        self, proofstate_client, memory_exporter
    ):
        """Verify a numeric string version is coerced to an integer."""
        with propagate_attributes(prompt={"name": "prompt", "version": "5"}):
            child = proofstate_client.start_observation(name="child-span")
            child.end()

        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_span_attribute(
            child_span,
            ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_VERSION,
            5,
        )

    def test_fallback_prompt_not_linked(self, proofstate_client, memory_exporter):
        """Verify fallback prompts are never linked."""
        prompt = self._make_prompt_client(is_fallback=True)

        with propagate_attributes(prompt=prompt):
            child = proofstate_client.start_observation(name="child-span")
            child.end()

        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_missing_attribute(
            child_span, ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_NAME
        )
        self.verify_missing_attribute(
            child_span, ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_VERSION
        )

    def test_prompt_without_name_dropped(self, proofstate_client, memory_exporter):
        """Verify a prompt without a valid name is dropped entirely."""
        with propagate_attributes(prompt={"version": 3}):
            child = proofstate_client.start_observation(name="child-span")
            child.end()

        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_missing_attribute(
            child_span, ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_NAME
        )
        self.verify_missing_attribute(
            child_span, ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_VERSION
        )

    def test_prompt_without_valid_version_dropped(
        self, proofstate_client, memory_exporter
    ):
        """Verify a prompt without an integer version is dropped entirely."""
        with propagate_attributes(prompt={"name": "prompt", "version": "latest"}):
            child = proofstate_client.start_observation(name="child-span")
            child.end()

        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_missing_attribute(
            child_span, ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_NAME
        )
        self.verify_missing_attribute(
            child_span, ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_VERSION
        )

    def test_explicit_prompt_takes_precedence_over_propagated(
        self, proofstate_client, memory_exporter
    ):
        """Verify an explicit prompt on an observation wins over the propagated one."""
        propagated = self._make_prompt_client(name="propagated-prompt", version=1)
        explicit = self._make_prompt_client(name="explicit-prompt", version=9)

        with propagate_attributes(prompt=propagated):
            child = proofstate_client.start_observation(
                name="explicit-child", as_type="generation", prompt=explicit
            )
            child.end()

            other = proofstate_client.start_observation(name="propagated-child")
            other.end()

        explicit_span = self.get_span_by_name(memory_exporter, "explicit-child")
        self.verify_span_attribute(
            explicit_span,
            ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_NAME,
            "explicit-prompt",
        )
        self.verify_span_attribute(
            explicit_span,
            ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_VERSION,
            9,
        )

        propagated_span = self.get_span_by_name(memory_exporter, "propagated-child")
        self.verify_span_attribute(
            propagated_span,
            ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_NAME,
            "propagated-prompt",
        )

    def test_nested_prompt_inner_overwrites(self, proofstate_client, memory_exporter):
        """Verify a nested propagated prompt shadows the outer one within its scope."""
        with propagate_attributes(prompt={"name": "outer-prompt", "version": 1}):
            with propagate_attributes(prompt={"name": "inner-prompt", "version": 2}):
                inner = proofstate_client.start_observation(name="inner-span")
                inner.end()

            outer = proofstate_client.start_observation(name="outer-span")
            outer.end()

        inner_span = self.get_span_by_name(memory_exporter, "inner-span")
        self.verify_span_attribute(
            inner_span,
            ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_NAME,
            "inner-prompt",
        )
        self.verify_span_attribute(
            inner_span,
            ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_VERSION,
            2,
        )

        outer_span = self.get_span_by_name(memory_exporter, "outer-span")
        self.verify_span_attribute(
            outer_span,
            ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_NAME,
            "outer-prompt",
        )

    def test_prompt_propagates_via_baggage(self, proofstate_client, memory_exporter):
        """Verify prompt propagates through baggage with version restored as int."""
        with propagate_attributes(
            prompt={"name": "baggage-prompt", "version": 4},
            as_baggage=True,
        ):
            child = proofstate_client.start_observation(name="child-span")
            child.end()

        child_span = self.get_span_by_name(memory_exporter, "child-span")
        self.verify_span_attribute(
            child_span,
            ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_NAME,
            "baggage-prompt",
        )
        self.verify_span_attribute(
            child_span,
            ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_VERSION,
            4,
        )

    def test_prompt_composes_with_outer_propagated_attributes(
        self, proofstate_client, memory_exporter
    ):
        """Verify a nested prompt-only context preserves outer attributes."""
        with propagate_attributes(session_id="session_abc", user_id="user_123"):
            with propagate_attributes(prompt={"name": "my-prompt", "version": 3}):
                inner = proofstate_client.start_observation(name="inner-span")
                inner.end()

            after = proofstate_client.start_observation(name="after-span")
            after.end()

        # Inner span has outer session/user attributes AND the prompt
        inner_span = self.get_span_by_name(memory_exporter, "inner-span")
        self.verify_span_attribute(
            inner_span, ProofStateOtelSpanAttributes.TRACE_SESSION_ID, "session_abc"
        )
        self.verify_span_attribute(
            inner_span, ProofStateOtelSpanAttributes.TRACE_USER_ID, "user_123"
        )
        self.verify_span_attribute(
            inner_span,
            ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_NAME,
            "my-prompt",
        )
        self.verify_span_attribute(
            inner_span,
            ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_VERSION,
            3,
        )

        # After the inner context exits, the prompt is gone but outer attributes remain
        after_span = self.get_span_by_name(memory_exporter, "after-span")
        self.verify_span_attribute(
            after_span, ProofStateOtelSpanAttributes.TRACE_SESSION_ID, "session_abc"
        )
        self.verify_missing_attribute(
            after_span, ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_NAME
        )
