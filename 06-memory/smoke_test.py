# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Smoke test for the inspectable Neo4j memory foundations.

Connects with the shared environment configuration and proves the memory
layer is usable before the scenario notebook is run:

1. An unscoped write (no ``user_identifier``) is rejected by multi-tenant
   enforcement.
2. One message written in a throwaway session reads back through
   ``get_context``.
3. The library-managed memory vector indexes exist with Titan V2's 1024
   dimensions.
4. The stored message embedding is non-empty, which is the zero-length-vector
   failure mode this lab's explicit embedder exists to prevent.

Everything the test writes is deleted afterwards, including the throwaway
``User`` node.

Requires live Neo4j and AWS credentials. Without them the script prints a
skip message and exits 0, so it is safe in credential-free environments.

Run with:
    uv run --with-requirements requirements.txt python smoke_test.py
"""

from __future__ import annotations

import asyncio
import sys
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from neo4j import GraphDatabase
from neo4j.exceptions import DriverError, Neo4jError

# ProviderError is the library's base for embedding failures, including the
# connect-time EmbeddingDimensionMismatchError raised when an existing memory
# vector index disagrees with the configured embedder. Not re-exported from
# the package root in 0.5.0, hence the deep import; the requirement is pinned
# to ==0.5.0.
from neo4j_agent_memory.llm.errors import ProviderError

from memory_helpers import (
    DEMO_ID_PREFIX,
    MEMORY_EMBEDDING_DIMENSIONS,
    MEMORY_VECTOR_INDEXES,
    MemoryDemoConfig,
    build_memory_client,
    load_config,
)

SKIP_MESSAGE = (
    "skipped: set NEO4J_URI/NEO4J_USERNAME/NEO4J_PASSWORD and AWS "
    "credentials to run the live memory smoke test."
)

MESSAGE_TEXT = (
    "Smoke test marker: the guest prefers hotels with a rooftop pool."
)


def check(label: str, passed: bool, detail: str = "") -> None:
    """Print one check result and raise if it failed."""
    status = "PASS" if passed else "FAIL"
    suffix = f" ({detail})" if detail else ""
    print(f"  [{status}] {label}{suffix}")
    if not passed:
        raise AssertionError(f"{label}{suffix}")


def index_dimensions(rows: list[dict]) -> dict[str, int | None]:
    """Map vector index name to its configured dimensions."""
    dimensions: dict[str, int | None] = {}
    for row in rows:
        options = row.get("options") or {}
        index_config = options.get("indexConfig") or {}
        dimensions[row["name"]] = index_config.get("vector.dimensions")
    return dimensions


def delete_smoke_user(config: MemoryDemoConfig, user_identifier: str) -> None:
    """Remove the throwaway User node the scoped write created.

    ``memory.query.cypher`` is read-only by design, so this one cleanup write
    goes through a short-lived direct driver session.
    """
    driver = GraphDatabase.driver(
        config.uri, auth=(config.username, config.password)
    )
    try:
        with driver.session(database=config.database) as session:
            session.run(
                "CYPHER 25 "
                "MATCH (u:User {identifier: $identifier}) DETACH DELETE u",
                identifier=user_identifier,
            ).consume()
    finally:
        driver.close()


async def run_checks(config: MemoryDemoConfig) -> int:
    """Run the four validation checks against live Neo4j and Bedrock."""
    # Both ids sit inside the lab namespace so that anything an interrupted
    # smoke test leaves behind is still reachable by cleanup_memory.py.
    session_id = f"{DEMO_ID_PREFIX}smoke-{uuid.uuid4().hex[:8]}"
    user_identifier = f"{DEMO_ID_PREFIX}smoke-user-{uuid.uuid4().hex[:8]}"
    print(f"Throwaway session: {session_id}")
    print(f"Throwaway user:    {user_identifier}")

    memory = build_memory_client(config)
    await memory.connect()
    print("Memory client connected.")

    try:
        # 1. Multi-tenant enforcement rejects a write with no user identifier.
        try:
            await memory.short_term.add_message(
                session_id, "user", "unscoped write that must be rejected"
            )
            rejected = False
        except ValueError:
            rejected = True
        check("unscoped write rejected by multi-tenant enforcement", rejected)

        # 2. Write one scoped message and read it back.
        message = await memory.short_term.add_message(
            session_id,
            "user",
            MESSAGE_TEXT,
            user_identifier=user_identifier,
        )
        check("scoped message written", message.id is not None)

        context = await memory.get_context(
            "What kind of hotel does the guest prefer?",
            session_id=session_id,
            include_long_term=False,
            include_reasoning=False,
        )
        check("message reads back through get_context", "rooftop pool" in context)

        # 3. The memory vector indexes exist with the pinned dimensions.
        rows = await memory.query.cypher(
            "SHOW VECTOR INDEXES YIELD name, options RETURN name, options"
        )
        dimensions = index_dimensions(rows)
        for index_name in MEMORY_VECTOR_INDEXES:
            check(
                f"vector index {index_name} has "
                f"{MEMORY_EMBEDDING_DIMENSIONS} dimensions",
                dimensions.get(index_name) == MEMORY_EMBEDDING_DIMENSIONS,
                detail=f"found {dimensions.get(index_name)}",
            )

        # 4. The stored embedding is non-empty and full width.
        rows = await memory.query.cypher(
            """
            CYPHER 25
            MATCH (c:Conversation {session_id: $session_id})
                  -[:HAS_MESSAGE]->(m:Message)
            RETURN size(m.embedding) AS width
            """,
            {"session_id": session_id},
        )
        widths = [row["width"] for row in rows]
        check(
            "stored message embedding is non-empty",
            widths == [MEMORY_EMBEDDING_DIMENSIONS],
            detail=f"widths {widths}",
        )
    finally:
        await memory.short_term.clear_session(session_id)
        await memory.close()
        delete_smoke_user(config, user_identifier)
        print("Cleaned up throwaway session and user.")

    print("\nSmoke test passed.")
    return 0


def main() -> int:
    """Check prerequisites, then run the live checks."""
    try:
        config = load_config()
    except RuntimeError:
        print(SKIP_MESSAGE)
        return 0
    if boto3.Session().get_credentials() is None:
        print(SKIP_MESSAGE)
        return 0

    try:
        return asyncio.run(run_checks(config))
    except AssertionError as exc:
        print(f"\nSmoke test failed: {exc}")
        return 1
    except (DriverError, Neo4jError) as exc:
        print(f"\nSmoke test could not use Neo4j at {config.uri}: {exc}")
        return 1
    except (BotoCoreError, ClientError) as exc:
        print(f"\nSmoke test could not call Bedrock in {config.region}: {exc}")
        return 1
    except ProviderError as exc:
        print(f"\nSmoke test failed in the embedding layer: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
