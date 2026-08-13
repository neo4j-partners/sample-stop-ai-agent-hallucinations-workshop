#!/usr/bin/env -S uv run --script
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     # boto3, neo4j, and python-dotenv are deliberately absent: `workshop`
#     # declares all three, and restating them here is how this script's pins
#     # drift out of step with the package every lab installs.
#     "workshop",
# ]
#
# [tool.uv.sources]
# workshop = { path = "../workshop", editable = true }
# ///
"""Verify the two credentials the workshop runs on, before Lab 1 needs them.

Run it from anywhere inside the repository:

    uv run 00-setup/verify_setup.py
    uv run 00-setup/verify_setup.py --lab6

It connects to Neo4j, counts APOC procedures, sends one short Bedrock prompt,
and requests one embedding through the same `BedrockEmbeddings` class Lab 1
writes chunk vectors with. It writes nothing to the graph and creates no AWS
resources. The four values that must have one definition in the tree,
`DEFAULT_MODEL_ID`, `EMBEDDING_MODEL_ID`, `EMBEDDING_PURPOSE`, and
`EMBEDDING_DIMENSIONS`, are imported from `workshop` rather than restated, so a
change to the retrieval contract reaches this check without an edit here.

Exit code 0 means every required check passed.
"""

from __future__ import annotations

import sys

# This guard runs before the third-party imports below, and that ordering is
# the whole point of it. The shared `workshop` package declares
# requires-python >=3.12, so on an older interpreter the import of `boto3` or
# `workshop` fails first with a message about a missing package, which sends
# the reader off to reinstall dependencies that were never the problem.
if sys.version_info < (3, 12):
    sys.exit(
        f"Python 3.12+ is required; this interpreter is {sys.version.split()[0]}.\n"
        "Install a newer Python, or pass --python 3.12 to uv run."
    )

import argparse  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
from pathlib import Path  # noqa: E402

import boto3  # noqa: E402
from dotenv import find_dotenv, load_dotenv  # noqa: E402
from neo4j import GraphDatabase  # noqa: E402

from workshop.bedrock_providers import (  # noqa: E402
    DEFAULT_MODEL_ID,
    BedrockEmbeddings,
    default_model_id,
)
from workshop.contracts import (  # noqa: E402
    DEFAULT_NEO4J_DATABASE,
    REQUIRED_NEO4J_ENV,
)
from workshop.retrieval_contract import (  # noqa: E402
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL_ID,
    EMBEDDING_PURPOSE,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_AWS_REGION = "us-east-1"

# Lab 6 embeds its memory records with Titan Text Embeddings V2, a second
# embedding contract on purpose, and it is the only lab that does. The literal
# is defined for that lab in 06-memory/memory_helpers.py as
# MEMORY_EMBEDDING_MODEL. Lab 0 restates it rather than importing across a lab
# boundary, so keep the two in step if either moves.
LAB6_EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v2:0"
LAB6_EMBEDDING_DIMENSIONS = 1024

APOC_QUERY = (
    "SHOW PROCEDURES YIELD name "
    "WHERE name STARTS WITH 'apoc.' "
    "RETURN count(*) AS n"
)


class Report:
    """Collect one line per check and decide the exit code from them."""

    def __init__(self) -> None:
        self.failures = 0
        self.warnings = 0

    def ok(self, label: str, detail: str) -> None:
        print(f"  [ OK ] {label}: {detail}")

    def fail(self, label: str, detail: str) -> None:
        self.failures += 1
        print(f"  [FAIL] {label}: {detail}")

    def warn(self, label: str, detail: str) -> None:
        self.warnings += 1
        print(f"  [WARN] {label}: {detail}")

    def skip(self, label: str, detail: str) -> None:
        # A skipped check is an unverified credential, so it counts against the
        # exit code. Lab 0 is done only when every required check ran and
        # passed.
        self.failures += 1
        print(f"  [SKIP] {label}: {detail}")


def load_environment() -> list[Path]:
    """Load .env files in the precedence order every lab uses.

    A bare `load_dotenv()` walks up from the working directory and stops at the
    first `.env` it finds, so a lab-local file wins and the repository-root file
    is only reached when there is no closer one. `load_dotenv` never overwrites
    a value that is already set, so loading the nearest file first and the root
    file second reproduces that precedence exactly.
    """
    loaded: list[Path] = []

    nearest = find_dotenv(usecwd=True)
    if nearest:
        nearest_path = Path(nearest).resolve()
        load_dotenv(nearest_path)
        loaded.append(nearest_path)

    root_env = (REPO_ROOT / ".env").resolve()
    if root_env.is_file() and root_env not in loaded:
        load_dotenv(root_env)
        loaded.append(root_env)

    return loaded


def report_env_files(report: Report, loaded: list[Path]) -> None:
    """Say which `.env` supplied the values, and flag a shadowed root file."""
    root_env = (REPO_ROOT / ".env").resolve()

    if not loaded:
        report.fail(
            "Environment file",
            f"no .env found. Copy .env.example to {root_env} and fill it in",
        )
        return

    winner = loaded[0]
    report.ok("Environment file", f"{winner} supplied the values")

    if winner != root_env:
        report.warn(
            "Environment file",
            f"{winner} shadows the repository-root {root_env}. Values missing "
            "from the closer file fall through to the root one, so the two "
            "files can disagree without an error. Keep one file at the root",
        )


def resolve_neo4j(report: Report) -> dict[str, str] | None:
    """Return the Neo4j settings, or None when something required is absent."""
    # The hosted Workshop Studio CloudFormation environment writes NEO4J_USER
    # and every lab in this repository reads NEO4J_USERNAME. Accepting the
    # older spelling here keeps Lab 0 passing inside that environment; the
    # warning is what stops a participant from discovering the mismatch in
    # Lab 1 instead.
    if not os.environ.get("NEO4J_USERNAME") and os.environ.get("NEO4J_USER"):
        os.environ["NEO4J_USERNAME"] = os.environ["NEO4J_USER"]
        report.warn(
            "Neo4j username",
            "NEO4J_USERNAME is unset and NEO4J_USER is set, which is the "
            "hosted Workshop Studio spelling. This check accepts it, and "
            "Labs 1 through 6 do not. Add NEO4J_USERNAME with the same value",
        )

    missing = [name for name in REQUIRED_NEO4J_ENV if not os.environ.get(name)]
    if missing:
        report.fail(
            "Neo4j settings",
            "missing from .env: " + ", ".join(missing),
        )
        return None

    # NEO4J_DATABASE is optional, and `workshop.contracts` is where its default
    # lives. Requiring it here would fail a participant whose .env is correct
    # for every lab.
    database = os.environ.get("NEO4J_DATABASE") or DEFAULT_NEO4J_DATABASE
    source = "from .env" if os.environ.get("NEO4J_DATABASE") else "defaulted"
    report.ok("Neo4j settings", f"database {database}, {source}")

    return {
        "uri": os.environ["NEO4J_URI"],
        "username": os.environ["NEO4J_USERNAME"],
        "password": os.environ["NEO4J_PASSWORD"],
        "database": database,
    }


def check_neo4j(report: Report, settings: dict[str, str]) -> None:
    """Connect, then count the APOC procedures Lab 1's build path needs."""
    try:
        with GraphDatabase.driver(
            settings["uri"],
            auth=(settings["username"], settings["password"]),
            notifications_min_severity="OFF",
        ) as driver:
            driver.verify_connectivity()
            with driver.session(database=settings["database"]) as session:
                apoc = session.run(APOC_QUERY).single()["n"]
    except Exception as error:  # noqa: BLE001 - report it, never traceback
        report.fail(
            "Neo4j connection",
            f"{settings['uri']} refused the connection: "
            f"{type(error).__name__}: {error}",
        )
        return

    if apoc == 0:
        report.fail(
            "Neo4j APOC",
            "connected, but no APOC procedures are visible. Aura ships APOC "
            "Core, so this URI points at something other than an Aura instance",
        )
        return

    report.ok(
        "Neo4j connection",
        f"{settings['uri']}, database {settings['database']}, "
        f"{apoc} APOC procedures",
    )


def check_bedrock_chat(report: Report, region: str) -> None:
    """Send one short prompt to the workshop chat model."""
    model_id = default_model_id()
    if model_id != DEFAULT_MODEL_ID:
        report.warn(
            "Bedrock model",
            f"MODEL_ID overrides the workshop default, so this check used "
            f"{model_id} instead of {DEFAULT_MODEL_ID}",
        )

    try:
        client = boto3.client("bedrock-runtime", region_name=region)
        client.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": "Reply with the word OK."}]}],
            inferenceConfig={"maxTokens": 5},
        )
    except Exception as error:  # noqa: BLE001 - report it, never traceback
        report.fail(
            "Bedrock chat",
            f"{model_id} in {region}: {type(error).__name__}: {error}",
        )
        return

    report.ok("Bedrock chat", f"{model_id} answered in {region}")


def check_bedrock_embeddings(report: Report, region: str) -> None:
    """Embed one string through the class Lab 1 writes chunk vectors with."""
    try:
        vector = BedrockEmbeddings(region_name=region).embed_query("hotel amenities")
    except Exception as error:  # noqa: BLE001 - report it, never traceback
        report.fail(
            "Bedrock embeddings",
            f"{EMBEDDING_MODEL_ID} in {region}: {type(error).__name__}: {error}",
        )
        return

    if len(vector) != EMBEDDING_DIMENSIONS:
        report.fail(
            "Bedrock embeddings",
            f"{EMBEDDING_MODEL_ID} returned {len(vector)} dimensions, and the "
            f"retrieval contract is {EMBEDDING_DIMENSIONS}. Lab 1 writes the "
            "vector index at the contract width and Lab 2 queries it there",
        )
        return

    report.ok(
        "Bedrock embeddings",
        f"{EMBEDDING_MODEL_ID} returned {len(vector)} dimensions, "
        f"purpose {EMBEDDING_PURPOSE}",
    )


def check_lab6_embeddings(report: Report, region: str, required: bool) -> None:
    """Embed one string with Titan, which only the optional Lab 6 uses."""
    note = report.fail if required else report.warn
    label = "Lab 6 embeddings"

    try:
        client = boto3.client("bedrock-runtime", region_name=region)
        response = client.invoke_model(
            modelId=LAB6_EMBEDDING_MODEL_ID,
            body=json.dumps(
                {
                    "inputText": "quiet room away from the elevator",
                    "dimensions": LAB6_EMBEDDING_DIMENSIONS,
                    "normalize": True,
                }
            ),
            contentType="application/json",
            accept="application/json",
        )
        vector = json.loads(response["body"].read())["embedding"]
    except Exception as error:  # noqa: BLE001 - report it, never traceback
        note(
            label,
            f"{LAB6_EMBEDDING_MODEL_ID} in {region}: "
            f"{type(error).__name__}: {error}. Lab 6 is the only lab that "
            "needs this model, and enabling the models above proves nothing "
            "about it",
        )
        return

    if len(vector) != LAB6_EMBEDDING_DIMENSIONS:
        note(
            label,
            f"{LAB6_EMBEDDING_MODEL_ID} returned {len(vector)} dimensions, "
            f"and Lab 6's memory indexes are {LAB6_EMBEDDING_DIMENSIONS} wide",
        )
        return

    report.ok(
        label,
        f"{LAB6_EMBEDDING_MODEL_ID} returned {len(vector)} dimensions",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify the Neo4j and Amazon Bedrock credentials every workshop "
            "lab reads. Writes nothing and creates no AWS resources."
        )
    )
    parser.add_argument(
        "--lab6",
        action="store_true",
        help=(
            "treat the Titan embedding check as required. Lab 6 is optional, "
            "so without this flag a Titan failure is reported as a warning"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    print("Workshop setup check")
    print()

    report = Report()
    report_env_files(report, load_environment())

    region = os.environ.get("AWS_REGION") or DEFAULT_AWS_REGION
    if os.environ.get("AWS_REGION"):
        report.ok("AWS region", f"{region}, from .env")
    else:
        report.warn(
            "AWS region",
            f"AWS_REGION is unset, so this check used {region}. Every lab "
            "falls back to the same value, and model access is granted per "
            "region, so set it explicitly",
        )

    settings = resolve_neo4j(report)
    if settings:
        check_neo4j(report, settings)

    if boto3.Session().get_credentials() is None:
        report.skip(
            "Amazon Bedrock",
            "no AWS credentials were found. Run aws configure, refresh the "
            "SSO session, or export AWS_ACCESS_KEY_ID and "
            "AWS_SECRET_ACCESS_KEY, then run this again",
        )
    else:
        check_bedrock_chat(report, region)
        check_bedrock_embeddings(report, region)
        check_lab6_embeddings(report, region, required=args.lab6)

    print()
    if report.failures:
        checks = "check" if report.failures == 1 else "checks"
        print(
            f"{report.failures} {checks} did not pass. Lab 0 is not done yet, "
            "and the README's troubleshooting table covers each message above."
        )
        return 1

    if report.warnings:
        warnings = "warning" if report.warnings == 1 else "warnings"
        print(
            f"Every required check passed, with {report.warnings} {warnings} "
            "above. Lab 1 will run."
        )
        return 0

    print("Every check passed. Open 01-graph-build/1.1_build_graph.ipynb next.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
