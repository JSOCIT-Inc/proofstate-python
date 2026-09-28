# ProofState Python SDK

Python client for [ProofState](https://proofstate.ai): OpenTelemetry tracing, prompts, datasets, evaluations, scores, and the public REST API. This fork preserves the original MIT license and Git history.

This repository contains a source prerelease. No package has been published to PyPI or verified against the live ProofState deployment. Use it with a matching server revision after authenticated end-to-end checks.

## Install from this checkout

Use Python 3.10 or newer. In the repository root:

```bash
python -m pip install .
```

The distribution and import name are both `proofstate`. The package has not been published to PyPI by this checkout; `pip install proofstate` will work only after a ProofState release is published.

## Configure

Create a ProofState project and obtain its public and secret keys. Set:

```bash
PROOFSTATE_PUBLIC_KEY=pk-ps-your-public-key
PROOFSTATE_SECRET_KEY=sk-ps-your-secret-key
PROOFSTATE_BASE_URL=https://proofstate.ai
```

`PROOFSTATE_BASE_URL` is optional because `https://proofstate.ai` is the default. You can also pass `public_key`, `secret_key`, and `base_url` to `ProofState(...)` directly. Keep the secret key on the server side.

## First trace and prompt

```python
from proofstate import get_client

client = get_client()

# Fetch the production prompt; fallback is used if it is unavailable.
prompt = client.get_prompt("greeting", fallback="Hello, {{name}}!")
message = prompt.compile(name="Ada")

with client.start_as_current_observation(
    as_type="generation", name="greeting", input={"name": "Ada"}
) as generation:
    generation.update(output=message)

client.flush()  # Flush before a short-lived process exits.
```

`ProofState` also provides `@observe`, OpenAI instrumentation through `proofstate.openai`, and a LangChain `CallbackHandler` through `proofstate.langchain`.

## Protocol and rollout

The SDK sends `x-proofstate-*` headers, `proofstate.*` OpenTelemetry attributes, `proofstate-sdk` instrumentation scope, `proofstate_` baggage, `@@@proofstateMedia` references, and ProofState JSON field names. Its SDK identity is `proofstate-python` and it requests ingestion version `4`.

Deploy the matching ProofState server protocol before using this version. The currently deployed server may require the prior protocol, so ingestion and generated REST responses must be checked together in a test deployment. No legacy-named fallback is emitted by this SDK.

The generated `proofstate/api/` client mirrors the upstream API schema. When ProofState's API diverges, regenerate it from ProofState's OpenAPI/Fern source before publishing a new SDK release.

The GitHub E2E job tests a local ProofState server checkout. It is skipped unless the repository variable `PROOFSTATE_E2E_ENABLED` is `true` and the `PROOFSTATE_SERVER_REPO_TOKEN` secret can read `JSOCIT-Inc/proofstate`. Live provider tests additionally need the provider API secrets. Unit, lint, type, and build checks run without those credentials.

## Development and release preparation

```bash
uv sync --locked
uv run --frozen ruff check .
uv run --frozen mypy proofstate --no-error-summary
uv run --frozen pytest tests/unit
python scripts/sanitize_generated_api_docs.py --check
uv build --no-sources
```

Before publishing, create a ProofState-owned source repository and PyPI project, configure a ProofState-owned trusted publisher, review the generated API against the deployed server, run unit and server-backed tests, and verify the wheel and source archive install in clean environments. The upstream automated publishing workflow has been removed from this fork; no package is published by cloning or building this repository.
