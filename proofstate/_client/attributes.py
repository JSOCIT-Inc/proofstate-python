"""Span attribute management for ProofState OpenTelemetry integration.

This module defines constants and functions for managing OpenTelemetry span attributes
used by ProofState. It provides a structured approach to creating and manipulating
attributes for different span types (trace, span, generation) while ensuring consistency.

The module includes:
- Attribute name constants organized by category
- Functions to create attribute dictionaries for different entity types
- Utilities for serializing and processing attribute values
"""

import json
from datetime import datetime
from typing import Any, Dict, Literal, Optional, Union

from proofstate._client.constants import (
    ObservationTypeGenerationLike,
    ObservationTypeSpanLike,
)
from proofstate._utils.serializer import EventSerializer
from proofstate.api import MapValue
from proofstate.model import PromptClient
from proofstate.types import SpanLevel


class ProofStateOtelSpanAttributes:
    # ProofState-Trace attributes
    TRACE_NAME = "proofstate.trace.name"
    TRACE_USER_ID = "user.id"
    TRACE_SESSION_ID = "session.id"
    TRACE_TAGS = "proofstate.trace.tags"
    TRACE_PUBLIC = "proofstate.trace.public"
    TRACE_METADATA = "proofstate.trace.metadata"
    TRACE_INPUT = "proofstate.trace.input"
    TRACE_OUTPUT = "proofstate.trace.output"

    # ProofState-observation attributes
    OBSERVATION_TYPE = "proofstate.observation.type"
    OBSERVATION_METADATA = "proofstate.observation.metadata"
    OBSERVATION_LEVEL = "proofstate.observation.level"
    OBSERVATION_STATUS_MESSAGE = "proofstate.observation.status_message"
    OBSERVATION_INPUT = "proofstate.observation.input"
    OBSERVATION_OUTPUT = "proofstate.observation.output"

    # ProofState-observation of type Generation attributes
    OBSERVATION_COMPLETION_START_TIME = "proofstate.observation.completion_start_time"
    OBSERVATION_MODEL = "proofstate.observation.model.name"
    OBSERVATION_MODEL_PARAMETERS = "proofstate.observation.model.parameters"
    OBSERVATION_USAGE_DETAILS = "proofstate.observation.usage_details"
    OBSERVATION_COST_DETAILS = "proofstate.observation.cost_details"
    OBSERVATION_PROMPT_NAME = "proofstate.observation.prompt.name"
    OBSERVATION_PROMPT_VERSION = "proofstate.observation.prompt.version"

    # General
    ENVIRONMENT = "proofstate.environment"
    RELEASE = "proofstate.release"
    VERSION = "proofstate.version"

    # Internal
    AS_ROOT = "proofstate.internal.as_root"
    IS_APP_ROOT = "proofstate.internal.is_app_root"

    # Experiments
    EXPERIMENT_ID = "proofstate.experiment.id"
    EXPERIMENT_NAME = "proofstate.experiment.name"
    EXPERIMENT_DESCRIPTION = "proofstate.experiment.description"
    EXPERIMENT_METADATA = "proofstate.experiment.metadata"
    EXPERIMENT_DATASET_ID = "proofstate.experiment.dataset.id"
    EXPERIMENT_ITEM_ID = "proofstate.experiment.item.id"
    EXPERIMENT_ITEM_EXPECTED_OUTPUT = "proofstate.experiment.item.expected_output"
    EXPERIMENT_ITEM_METADATA = "proofstate.experiment.item.metadata"
    EXPERIMENT_ITEM_ROOT_OBSERVATION_ID = (
        "proofstate.experiment.item.root_observation_id"
    )


def create_trace_attributes(
    *,
    input: Optional[Any] = None,
    output: Optional[Any] = None,
    public: Optional[bool] = None,
) -> dict:
    attributes = {
        ProofStateOtelSpanAttributes.TRACE_INPUT: _serialize(input),
        ProofStateOtelSpanAttributes.TRACE_OUTPUT: _serialize(output),
        ProofStateOtelSpanAttributes.TRACE_PUBLIC: public,
    }

    return {k: v for k, v in attributes.items() if v is not None}


def create_span_attributes(
    *,
    metadata: Optional[Any] = None,
    input: Optional[Any] = None,
    output: Optional[Any] = None,
    level: Optional[SpanLevel] = None,
    status_message: Optional[str] = None,
    version: Optional[str] = None,
    observation_type: Optional[
        Union[ObservationTypeSpanLike, Literal["event"]]
    ] = "span",
) -> dict:
    attributes = {
        ProofStateOtelSpanAttributes.OBSERVATION_TYPE: observation_type,
        ProofStateOtelSpanAttributes.OBSERVATION_LEVEL: level,
        ProofStateOtelSpanAttributes.OBSERVATION_STATUS_MESSAGE: status_message,
        ProofStateOtelSpanAttributes.VERSION: version,
        ProofStateOtelSpanAttributes.OBSERVATION_INPUT: _serialize(input),
        ProofStateOtelSpanAttributes.OBSERVATION_OUTPUT: _serialize(output),
        **_flatten_and_serialize_metadata(metadata, "observation"),
    }

    return {k: v for k, v in attributes.items() if v is not None}


def create_generation_attributes(
    *,
    name: Optional[str] = None,
    completion_start_time: Optional[datetime] = None,
    metadata: Optional[Any] = None,
    level: Optional[SpanLevel] = None,
    status_message: Optional[str] = None,
    version: Optional[str] = None,
    model: Optional[str] = None,
    model_parameters: Optional[Dict[str, MapValue]] = None,
    input: Optional[Any] = None,
    output: Optional[Any] = None,
    usage_details: Optional[Dict[str, int]] = None,
    cost_details: Optional[Dict[str, float]] = None,
    prompt: Optional[PromptClient] = None,
    observation_type: Optional[ObservationTypeGenerationLike] = "generation",
) -> dict:
    attributes = {
        ProofStateOtelSpanAttributes.OBSERVATION_TYPE: observation_type,
        ProofStateOtelSpanAttributes.OBSERVATION_LEVEL: level,
        ProofStateOtelSpanAttributes.OBSERVATION_STATUS_MESSAGE: status_message,
        ProofStateOtelSpanAttributes.VERSION: version,
        ProofStateOtelSpanAttributes.OBSERVATION_INPUT: _serialize(input),
        ProofStateOtelSpanAttributes.OBSERVATION_OUTPUT: _serialize(output),
        ProofStateOtelSpanAttributes.OBSERVATION_MODEL: model,
        ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_NAME: prompt.name
        if prompt and not prompt.is_fallback
        else None,
        ProofStateOtelSpanAttributes.OBSERVATION_PROMPT_VERSION: prompt.version
        if prompt and not prompt.is_fallback
        else None,
        ProofStateOtelSpanAttributes.OBSERVATION_USAGE_DETAILS: _serialize(
            usage_details
        ),
        ProofStateOtelSpanAttributes.OBSERVATION_COST_DETAILS: _serialize(cost_details),
        ProofStateOtelSpanAttributes.OBSERVATION_COMPLETION_START_TIME: _serialize(
            completion_start_time
        ),
        ProofStateOtelSpanAttributes.OBSERVATION_MODEL_PARAMETERS: _serialize(
            model_parameters
        ),
        **_flatten_and_serialize_metadata(metadata, "observation"),
    }

    return {k: v for k, v in attributes.items() if v is not None}


def _serialize(obj: Any) -> Optional[str]:
    if obj is None or isinstance(obj, str):
        return obj

    return json.dumps(obj, cls=EventSerializer)


def _flatten_and_serialize_metadata_values(
    metadata: Optional[Dict[str, Any]],
) -> Optional[Dict[str, str]]:
    if metadata is None:
        return None

    flattened_metadata: Dict[str, str] = {}

    def flatten_value(path: str, value: Any) -> None:
        if isinstance(value, dict):
            for nested_key, nested_value in value.items():
                flatten_value(f"{path}.{nested_key}", nested_value)

            return

        serialized_value = _serialize(value)

        if serialized_value is not None:
            flattened_metadata[path] = serialized_value

    for key, value in metadata.items():
        flatten_value(str(key), value)

    return flattened_metadata


def _flatten_and_serialize_metadata(
    metadata: Any, type: Literal["observation", "trace"]
) -> dict:
    prefix = (
        ProofStateOtelSpanAttributes.OBSERVATION_METADATA
        if type == "observation"
        else ProofStateOtelSpanAttributes.TRACE_METADATA
    )

    metadata_attributes: Dict[str, Union[str, int, None]] = {}

    if not isinstance(metadata, dict):
        metadata_attributes[prefix] = _serialize(metadata)
    else:
        for key, value in metadata.items():
            metadata_attributes[f"{prefix}.{key}"] = (
                value
                if isinstance(value, str) or isinstance(value, int)
                else _serialize(value)
            )

    return metadata_attributes
