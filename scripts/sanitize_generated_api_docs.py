"""Normalize ProofState generated API documentation after regeneration.

Run this after regenerating ``proofstate/api`` from the ProofState API schema.
Protocol fields and exported names are checked for accidental changes.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1] / "proofstate" / "api"
BLOB_SOURCE_DESCRIPTION = (
    "Data to export. When omitted on update, the existing value is preserved. "
    "When omitted on create, the server selects a source supported by the "
    "deployment. Required when `exportFieldGroups` is provided."
)
WIRE_TOKENS = re.compile(
    r"X-ProofState-[A-Za-z-]+|isProofStateManaged|proofstateObject"
)


def sanitize_line(line: str) -> str:
    body = line.rstrip("\r\n")
    newline = line[len(body) :]
    stripped = body.lstrip()

    if stripped.startswith("Data to export. When omitted on update,"):
        body = body[: len(body) - len(stripped)] + BLOB_SOURCE_DESCRIPTION
    elif stripped.startswith("**Cloud-only "):
        return ""
    elif stripped.startswith("For more details, see the [Metrics API documentation]"):
        return ""
    elif (
        stripped.startswith(
            ("- Integration guide:", "- Data model:", "- Introduction to data model:")
        )
        and "https://" in stripped
    ):
        return ""
    else:
        body = re.sub(
            r", see the \[OpenTelemetry integration docs\]\(https?://[^)]+\)",
            "",
            body,
        )
        body = re.sub(r" Learn more: https?://\S+", "", body)
        body = re.sub(r" See https?://\S+$", "", body)
        body = re.sub(
            r"Submit explicit user-approved feedback about ProofState "
            r"skills, MCP tools, CLI, docs, or public API",
            "Submit explicit user-approved feedback about ProofState products or public APIs",
            body,
        )

    return body + newline


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="fail if generated prose needs sanitizing"
    )
    args = parser.parse_args()

    changed_paths: list[Path] = []
    for path in sorted(API_ROOT.rglob("*.py")):
        original = path.read_bytes().decode("utf-8")
        sanitized = "".join(sanitize_line(line) for line in original.splitlines(True))
        if sanitized == original:
            continue
        if WIRE_TOKENS.findall(original) != WIRE_TOKENS.findall(sanitized):
            raise RuntimeError(f"Wire token changed in {path}")
        changed_paths.append(path)
        if not args.check:
            path.write_bytes(sanitized.encode("utf-8"))

    if changed_paths:
        print(f"Generated API prose needs sanitizing in {len(changed_paths)} files")
        return 1 if args.check else 0

    print("Generated API prose is sanitized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
