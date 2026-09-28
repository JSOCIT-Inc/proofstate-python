# ProofState Python SDK agent guide

This repository contains the `proofstate` Python package. Retain the original MIT license and Git history.

## Layout

- `proofstate/_client/`: client, tracing, OpenTelemetry, prompts, datasets
- `proofstate/openai.py` and `proofstate/langchain/`: provider integrations
- `proofstate/_task_manager/`: background media and score consumers
- `proofstate/api/`: generated Fern REST client
- `tests/unit/`: local tests without a server
- `tests/e2e/`: tests that need a compatible server
- `tests/live_provider/`: tests that call model providers

## Development

```bash
uv sync --locked
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy proofstate --no-error-summary
uv run --frozen pytest tests/unit
uv build --no-sources
```

Use targeted unit tests while editing. Before handoff, review the diff and run checks appropriate to the changed behavior. E2E and live-provider tests require external services and keys; do not claim they ran unless they did.

## Namespace and protocol

The public package, imports, clients, and configuration use `proofstate` and `PROOFSTATE_*`. The default API base is `https://proofstate.ai`. Use `x-proofstate-*` HTTP headers, `proofstate.*` OpenTelemetry attributes, `proofstate-sdk` instrumentation scope, `proofstate_` baggage names, `@@@proofstateMedia` references, and ProofState JSON field names. Send `x-proofstate-sdk-name: proofstate-python` and `x-proofstate-ingestion-version: 4`. These require a matching server deployment.

`proofstate/api/` is generated. For endpoint or schema changes, regenerate from ProofState's Fern/OpenAPI source and apply the namespace mapping, including serialized field names. Avoid manual endpoint edits.

Keep `.env.template`, README, package metadata, tests, and CI in sync with configuration changes. Do not commit secrets.

## Release

The `publish.yml` workflow publishes tagged prereleases with PyPI Trusted Publishing. Do not trigger a release until the ProofState-owned PyPI project or pending publisher, protected `pypi` GitHub environment, clean artifact installs, and server-backed compatibility checks exist. After those checks, set `PROOFSTATE_RELEASE_COMPAT_VERIFIED_TAG` to the exact release tag. Use `bash scripts/build_reference_docs.sh` for local API reference generation.
