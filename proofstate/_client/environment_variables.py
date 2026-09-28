"""Environment variable definitions for ProofState OpenTelemetry integration.

This module defines environment variables used to configure the ProofState OpenTelemetry integration.
Each environment variable includes documentation on its purpose, expected values, and defaults.
"""

PROOFSTATE_TRACING_ENVIRONMENT = "PROOFSTATE_TRACING_ENVIRONMENT"
"""
.. envvar:: PROOFSTATE_TRACING_ENVIRONMENT

The tracing environment. Can be any lowercase alphanumeric string with hyphens and underscores that does not start with 'proofstate'.

**Default value:** ``"default"``
"""

PROOFSTATE_RELEASE = "PROOFSTATE_RELEASE"
"""
.. envvar:: PROOFSTATE_RELEASE

Release number/hash of the application to provide analytics grouped by release.
"""


PROOFSTATE_PUBLIC_KEY = "PROOFSTATE_PUBLIC_KEY"
"""
.. envvar:: PROOFSTATE_PUBLIC_KEY

Public API key of ProofState project
"""

PROOFSTATE_SECRET_KEY = "PROOFSTATE_SECRET_KEY"
"""
.. envvar:: PROOFSTATE_SECRET_KEY

Secret API key of ProofState project
"""

PROOFSTATE_BASE_URL = "PROOFSTATE_BASE_URL"
"""
.. envvar:: PROOFSTATE_BASE_URL

Base URL of ProofState API. Can be set via `PROOFSTATE_BASE_URL` environment variable.

**Default value:** ``"https://proofstate.ai"``
"""

PROOFSTATE_HOST = "PROOFSTATE_HOST"
"""
.. envvar:: PROOFSTATE_HOST

Deprecated. Use PROOFSTATE_BASE_URL instead. Host of ProofState API. Can be set via `PROOFSTATE_HOST` environment variable.

**Default value:** ``"https://proofstate.ai"``
"""

PROOFSTATE_OTEL_TRACES_EXPORT_PATH = "PROOFSTATE_OTEL_TRACES_EXPORT_PATH"
"""
.. envvar:: PROOFSTATE_OTEL_TRACES_EXPORT_PATH

URL path on the configured host to export traces to.

**Default value:** ``/api/public/otel/v1/traces``
"""

PROOFSTATE_DEBUG = "PROOFSTATE_DEBUG"
"""
.. envvar:: PROOFSTATE_DEBUG

Enables debug mode for more verbose logging.

**Default value:** ``"False"``
"""

PROOFSTATE_TRACING_ENABLED = "PROOFSTATE_TRACING_ENABLED"
"""
.. envvar:: PROOFSTATE_TRACING_ENABLED

Enables or disables the ProofState client. If disabled, all observability calls to the backend will be no-ops. Default is True. Set to `False` to disable tracing.

**Default value:** ``"True"``
"""

PROOFSTATE_MEDIA_UPLOAD_THREAD_COUNT = "PROOFSTATE_MEDIA_UPLOAD_THREAD_COUNT"
"""
.. envvar:: PROOFSTATE_MEDIA_UPLOAD_THREAD_COUNT

Number of background threads to handle media uploads from trace ingestion.

**Default value:** ``1``
"""

PROOFSTATE_FLUSH_AT = "PROOFSTATE_FLUSH_AT"
"""
.. envvar:: PROOFSTATE_FLUSH_AT

Max batch size until a new ingestion batch is sent to the API.
**Default value:** same as OTEL ``OTEL_BSP_MAX_EXPORT_BATCH_SIZE``
"""

PROOFSTATE_FLUSH_INTERVAL = "PROOFSTATE_FLUSH_INTERVAL"
"""
.. envvar:: PROOFSTATE_FLUSH_INTERVAL

Max delay in seconds until a new ingestion batch is sent to the API.
**Default value:** same as OTEL ``OTEL_BSP_SCHEDULE_DELAY``
"""

PROOFSTATE_SAMPLE_RATE = "PROOFSTATE_SAMPLE_RATE"
"""
.. envvar: PROOFSTATE_SAMPLE_RATE

Float between 0 and 1 indicating the sample rate of traces to bet sent to ProofState servers.

**Default value**: ``1.0``

"""
PROOFSTATE_OBSERVE_DECORATOR_IO_CAPTURE_ENABLED = (
    "PROOFSTATE_OBSERVE_DECORATOR_IO_CAPTURE_ENABLED"
)
"""
.. envvar: PROOFSTATE_OBSERVE_DECORATOR_IO_CAPTURE_ENABLED

Default capture of function args, kwargs and return value when using the @observe decorator.

Having default IO capture enabled for observe decorated function may have a performance impact on your application
if large or deeply nested objects are attempted to be serialized. Set this value to `False` and use manual
input/output setting on your observation to avoid this.

**Default value**: ``True``
"""

PROOFSTATE_MEDIA_UPLOAD_ENABLED = "PROOFSTATE_MEDIA_UPLOAD_ENABLED"
"""
.. envvar: PROOFSTATE_MEDIA_UPLOAD_ENABLED

Controls whether media detection and upload is attempted by the SDK.

**Default value**: ``True``
"""

PROOFSTATE_TIMEOUT = "PROOFSTATE_TIMEOUT"
"""
.. envvar: PROOFSTATE_TIMEOUT

Controls the timeout for all API requests in seconds

**Default value**: ``5``
"""

PROOFSTATE_PROMPT_CACHE_DEFAULT_TTL_SECONDS = (
    "PROOFSTATE_PROMPT_CACHE_DEFAULT_TTL_SECONDS"
)
"""
.. envvar: PROOFSTATE_PROMPT_CACHE_DEFAULT_TTL_SECONDS

Controls the default time-to-live (TTL) in seconds for cached prompts.
This setting determines how long prompt responses are cached before they expire.

**Default value**: ``60``
"""

PROOFSTATE_OPENAI_SKIP_RAW_RESPONSES = "PROOFSTATE_OPENAI_SKIP_RAW_RESPONSES"
"""
.. envvar: PROOFSTATE_OPENAI_SKIP_RAW_RESPONSES

Controls whether the OpenAI integration skips instrumenting calls made via the
OpenAI SDK's `.with_raw_response` and `.with_streaming_response` APIs.

Set this to `True` when another instrumented library calls the OpenAI SDK
internally through the raw-response API (e.g. an instrumented LiteLLM callback)
to avoid duplicate observations for the same LLM call.

**Default value**: ``False``
"""
