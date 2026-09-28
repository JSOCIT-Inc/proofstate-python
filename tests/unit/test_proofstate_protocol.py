"""Checks for the ProofState protocol shared by tracing and the REST client."""

import httpx

from proofstate._client.attributes import ProofStateOtelSpanAttributes
from proofstate._client.constants import PROOFSTATE_TRACER_NAME
from proofstate._utils.request import ProofStateClient
from proofstate.api.commons.types.model import Model
from proofstate.api.core.client_wrapper import BaseClientWrapper
from proofstate.api.core.serialization import convert_and_respect_annotation_metadata
from proofstate.api.evaluation_commons.types.legacy_prompt_variable_mapping import (
    LegacyPromptVariableMapping,
)


def test_ingestion_client_sends_proofstate_identity() -> None:
    with httpx.Client() as session:
        client = ProofStateClient(
            public_key="pk-ps-test",
            secret_key="sk-ps-test",
            base_url="https://proofstate.ai",
            version="4.15.6",
            timeout=5,
            session=session,
        )
        headers = client.generate_headers()

    assert headers["x-proofstate-sdk-name"] == "proofstate-python"
    assert headers["x-proofstate-sdk-version"] == "4.15.6"
    assert headers["x-proofstate-public-key"] == "pk-ps-test"
    assert headers["x-proofstate-ingestion-version"] == "4"
    assert headers["Authorization"].startswith("Basic ")
    assert set(headers) == {
        "Authorization",
        "Content-Type",
        "x-proofstate-sdk-name",
        "x-proofstate-sdk-version",
        "x-proofstate-public-key",
        "x-proofstate-ingestion-version",
    }


def test_generated_rest_client_uses_proofstate_headers() -> None:
    wrapper = BaseClientWrapper(
        x_proofstate_sdk_name="proofstate-python",
        x_proofstate_sdk_version="4.15.6",
        x_proofstate_public_key="pk-ps-test",
        base_url="https://proofstate.ai",
    )
    headers = wrapper.get_headers()

    assert headers["X-ProofState-Sdk-Name"] == "proofstate-python"
    assert headers["X-ProofState-Sdk-Version"] == "4.15.6"
    assert headers["X-ProofState-Public-Key"] == "pk-ps-test"
    assert headers["X-ProofState-Ingestion-Version"] == "4"
    assert set(headers) == {
        "X-Fern-Language",
        "X-ProofState-Sdk-Name",
        "X-ProofState-Sdk-Version",
        "X-ProofState-Public-Key",
        "X-ProofState-Ingestion-Version",
    }


def test_generated_json_field_names_are_proofstate_names() -> None:
    model_wire = convert_and_respect_annotation_metadata(
        object_={"is_proofstate_managed": True},
        annotation=Model,
        direction="write",
    )
    mapping_wire = convert_and_respect_annotation_metadata(
        object_={"proofstate_object": "trace", "variable": "input", "source": "input"},
        annotation=LegacyPromptVariableMapping,
        direction="write",
    )

    assert model_wire == {"isProofStateManaged": True}
    assert mapping_wire["proofstateObject"] == "trace"


def test_tracing_identity_and_attributes_are_proofstate_names() -> None:
    assert PROOFSTATE_TRACER_NAME == "proofstate-sdk"
    assert ProofStateOtelSpanAttributes.TRACE_NAME == "proofstate.trace.name"
    assert (
        ProofStateOtelSpanAttributes.OBSERVATION_TYPE == "proofstate.observation.type"
    )
