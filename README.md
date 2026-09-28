# ProofState Python SDK

Python client for [ProofState](https://proofstate.ai): OpenTelemetry tracing, prompts, datasets, evaluations, scores, and the public REST API. The required MIT license notice is in [LICENSE](LICENSE).

The protocol used by the `4.15.6rc2` prerelease was checked against the ProofState server deployed at `https://proofstate.ai` on 2026-09-28. Use a test project when adopting a prerelease.

## Install

Use Python 3.10 or newer. After publication, install the prerelease from PyPI:

```bash
python -m pip install --pre proofstate==4.15.6rc2
```

The distribution and import name are both `proofstate`. To install from a source checkout instead, run `python -m pip install .` in the repository root.

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

Use a matching ProofState server protocol. Authenticated production checks on 2026-09-28 covered project authentication, prompts, datasets, scores, experiments, span ingestion, v2 observation readback, and MCP tool discovery. No legacy-named fallback is emitted by this SDK. On a server running v4 `events_only` mode, the legacy `client.api.trace.get()` endpoint returns 404; read spans through `client.api.observations.get_many(trace_id=...)` instead.

The generated `proofstate/api/` client mirrors an API schema snapshot. When ProofState's API diverges, regenerate it from ProofState's OpenAPI/Fern source before publishing a new SDK release.

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

Before each release, review the generated API against the deployed server, run server-backed tests, and install the built wheel and source archive in clean environments. Tag only a version that passed those checks.

The `.github/workflows/publish.yml` workflow builds and checks the distributions, then publishes a GitHub prerelease whose tag matches the package version using PyPI Trusted Publishing. It does not use a stored PyPI token. The PyPI publisher is scoped to owner `JSOCIT-Inc`, repository `proofstate-python`, workflow `publish.yml`, and environment `pypi`. The GitHub `pypi` environment requires release review. After server-backed compatibility checks pass, set repository variable `PROOFSTATE_RELEASE_COMPAT_VERIFIED_TAG` to the exact release tag; the workflow fails closed if it does not match.
