# Contributing

This repository contains the ProofState Python SDK. Preserve the original MIT license and Git history.

## Development

```bash
uv sync --locked
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy proofstate --no-error-summary
uv run --frozen pytest tests/unit
uv build --no-sources
```

Unit tests do not need a server. `tests/e2e` requires a locally configured compatible server and the credentials in `.env.template`. `tests/live_provider` also needs model provider keys. Do not commit real keys.

Keep the public import name, class names, environment variables, README examples, and built package metadata under `proofstate`. Keep `x-proofstate-*` headers, `proofstate.*` OpenTelemetry attributes, media markers, and generated REST field aliases aligned with the matching ProofState server. The SDK version remains 4.x for ingestion classification.

`proofstate/api/` is generated from the public API schema. Regenerate it from ProofState's Fern/OpenAPI source when the server contract changes, then apply the ProofState namespace mapping while preserving serialized field names. Avoid hand-editing individual generated endpoints.

## Pull requests

Use Conventional Commits and report the checks you ran. Run `git diff --check` and inspect changes to protocol identifiers and generated files before review.

## Reference docs

Build locally with `bash scripts/build_reference_docs.sh`. The `docs` output is ignored. Set `PDOC_CANONICAL_BASE_URL` only when a ProofState-owned reference site exists.

## Publishing

There is no publishing workflow in this fork. A ProofState-owned Git repository and PyPI project, trusted publisher configuration, clean wheel/source archive installs, unit tests, and server-backed compatibility tests are required before publication. Verify `pyproject.toml` URLs and version for each release. Never use upstream publishing credentials.
