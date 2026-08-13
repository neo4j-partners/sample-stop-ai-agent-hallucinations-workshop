# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Unit tests for the memory helper module. No database or AWS calls.

Pins the configuration contract the Demo 08 plan locks in: Titan Text
Embeddings V2 with 1024 dimensions, an explicit Bedrock embedder, an explicit
target database, extraction off, and multi-tenant enforcement on. Also covers
the workshop-owned write helpers (provenance edge, ownership marker) against
a fake driver, and the scoping guarantees of the cleanup Cypher. The live
connect, write, and index checks are exercised by ``smoke_test.py``, not here.

Run with:  uv run --with-requirements requirements.txt python test_memory_helpers.py
"""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from neo4j_agent_memory import EmbeddingProvider, ExtractorType, MemoryClient
from neo4j_agent_memory.memory.short_term import ShortTermMemory

import cleanup_memory
import memory_helpers
from memory_helpers import (
    DEMO_ID_PREFIX,
    HERO_HOTEL_NAME,
    HOTEL_RELATIONSHIP,
    MEMORY_EMBEDDING_DIMENSIONS,
    MEMORY_EMBEDDING_MODEL,
    PROVENANCE_RELATIONSHIP,
    WORKSHOP_OWNER,
    MemoryDemoConfig,
    build_memory_client,
    build_memory_embedder,
    build_memory_settings,
    get_actor_preferences_for_hotel,
    link_preference_to_message_and_hotel,
    load_config,
    tag_demo_records,
)

CONFIG = MemoryDemoConfig(
    uri="neo4j+s://example.databases.neo4j.io",
    username="neo4j",
    password="secret-password",
    database="hotels",
    region="eu-west-1",
)


class TestLoadConfig(unittest.TestCase):
    """load_config reads the shared environment settings lazily."""

    def setUp(self) -> None:
        # Point the .env lookup at an empty directory so a developer's real
        # .env files cannot leak into these assertions.
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        empty_dir = Path(tmp.name) / "demo"
        empty_dir.mkdir()
        patcher = mock.patch.object(memory_helpers, "_DEMO_DIR", empty_dir)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_reads_environment_values(self) -> None:
        env = {
            "NEO4J_URI": "neo4j+s://abc.databases.neo4j.io",
            "NEO4J_USERNAME": "reader",
            "NEO4J_PASSWORD": "pw",
            "NEO4J_DATABASE": "hotels",
            "AWS_REGION": "us-west-2",
        }
        with mock.patch.dict("os.environ", env, clear=True):
            config = load_config()
        self.assertEqual(config.uri, "neo4j+s://abc.databases.neo4j.io")
        self.assertEqual(config.username, "reader")
        self.assertEqual(config.password, "pw")
        self.assertEqual(config.database, "hotels")
        self.assertEqual(config.region, "us-west-2")

    def test_defaults_match_the_other_demos(self) -> None:
        with mock.patch.dict(
            "os.environ", {"NEO4J_PASSWORD": "pw"}, clear=True
        ):
            config = load_config()
        self.assertEqual(config.uri, "bolt://localhost:7687")
        self.assertEqual(config.username, "neo4j")
        self.assertEqual(config.database, "neo4j")
        self.assertEqual(config.region, "us-east-1")

    def test_missing_password_raises_with_hint(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                load_config()
        self.assertIn("NEO4J_PASSWORD", str(ctx.exception))
        self.assertIn(".env", str(ctx.exception))


class TestBuildMemorySettings(unittest.TestCase):
    """The settings pin the contract the Demo 08 plan decisions lock in."""

    def setUp(self) -> None:
        self.settings = build_memory_settings(CONFIG)

    def test_multi_tenant_is_on(self) -> None:
        self.assertTrue(self.settings.memory.multi_tenant)

    def test_database_is_passed_explicitly(self) -> None:
        self.assertEqual(self.settings.neo4j.database, "hotels")

    def test_neo4j_connection_settings(self) -> None:
        self.assertEqual(
            self.settings.neo4j.uri, "neo4j+s://example.databases.neo4j.io"
        )
        self.assertEqual(self.settings.neo4j.username, "neo4j")
        self.assertEqual(
            self.settings.neo4j.password.get_secret_value(), "secret-password"
        )

    def test_embedding_contract_is_titan_v2(self) -> None:
        embedding = self.settings.embedding
        self.assertEqual(embedding.provider, EmbeddingProvider.BEDROCK)
        self.assertEqual(embedding.model, MEMORY_EMBEDDING_MODEL)
        self.assertEqual(embedding.dimensions, MEMORY_EMBEDDING_DIMENSIONS)
        self.assertEqual(embedding.aws_region, "eu-west-1")

    def test_extraction_is_off(self) -> None:
        self.assertEqual(
            self.settings.extraction.extractor_type, ExtractorType.NONE
        )
        self.assertIsNone(self.settings.llm)


class TestBuildMemoryEmbedder(unittest.TestCase):
    """The explicit Bedrock embedder matches the pinned model."""

    def test_dimensions_match_the_pinned_model(self) -> None:
        embedder = build_memory_embedder(CONFIG)
        self.assertEqual(embedder.dimensions, MEMORY_EMBEDDING_DIMENSIONS)


class TestBuildMemoryClient(unittest.TestCase):
    """The client carries the explicit embedder and stays unconnected."""

    def test_client_is_unconnected_with_explicit_embedder(self) -> None:
        client = build_memory_client(CONFIG)
        self.assertIsInstance(client, MemoryClient)
        self.assertFalse(client.is_connected)
        # In 0.5.0 MemoryClient._create_embedder returns None for the Bedrock
        # provider, so the explicit override is what prevents zero-length
        # vectors. Private attribute, pinned deliberately against ==0.5.0.
        self.assertIsNotNone(client._embedder_override)
        self.assertEqual(
            client._embedder_override.dimensions, MEMORY_EMBEDDING_DIMENSIONS
        )


class TestMultiTenantEnforcement(unittest.TestCase):
    """An unscoped write is rejected before any database work happens."""

    def test_unscoped_add_message_raises(self) -> None:
        # client=None proves the rejection happens before any Neo4j call:
        # a write that reached the store would fail on the missing client.
        short_term = ShortTermMemory(client=None, multi_tenant=True)
        with self.assertRaises(ValueError) as ctx:
            asyncio.run(
                short_term.add_message("session", "user", "unscoped write")
            )
        self.assertIn("user_identifier", str(ctx.exception))

    def test_scoped_add_message_passes_enforcement(self) -> None:
        short_term = ShortTermMemory(client=None, multi_tenant=True)
        # With a user identifier the enforcement gate passes; the call then
        # fails on the absent client, proving the gate was the only barrier.
        with self.assertRaises(AttributeError):
            asyncio.run(
                short_term.add_message(
                    "session",
                    "user",
                    "scoped write",
                    user_identifier="actor-a",
                )
            )


class FakeSession:
    """Record queries and return canned rows, standing in for a bolt session."""

    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, dict]] = []

    def __enter__(self) -> "FakeSession":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def run(self, query: str, parameters: dict) -> list[dict]:
        self.calls.append((query, parameters))
        return self.rows


class FakeDriver:
    """Hand out one FakeSession and record whether close() was called."""

    def __init__(self, rows: list[dict]) -> None:
        self.session_obj = FakeSession(rows)
        self.closed = False

    def session(self, database: str | None = None) -> FakeSession:
        self.database = database
        return self.session_obj

    def close(self) -> None:
        self.closed = True


class TestLinkPreferenceToMessageAndHotel(unittest.TestCase):
    """The workshop links report whether all three records matched."""

    def test_linked_when_both_ids_match(self) -> None:
        driver = FakeDriver([{"linked": 1}])
        result = link_preference_to_message_and_hotel(
            CONFIG,
            "pref-id",
            "msg-id",
            HERO_HOTEL_NAME,
            driver=driver,
        )
        self.assertTrue(result)
        query, params = driver.session_obj.calls[0]
        self.assertIn(PROVENANCE_RELATIONSHIP, query)
        self.assertIn(HOTEL_RELATIONSHIP, query)
        self.assertEqual(params["preference_id"], "pref-id")
        self.assertEqual(params["message_id"], "msg-id")
        self.assertEqual(params["hotel_name"], HERO_HOTEL_NAME)
        self.assertEqual(params["owner"], WORKSHOP_OWNER)

    def test_false_when_either_id_matches_nothing(self) -> None:
        # A MATCH that fails yields no rows at all, which must not read as
        # success: the caller needs to distinguish a silent no-op.
        driver = FakeDriver([])
        self.assertFalse(
            link_preference_to_message_and_hotel(
                CONFIG,
                "pref-id",
                "msg-id",
                HERO_HOTEL_NAME,
                driver=driver,
            )
        )

    def test_caller_supplied_driver_stays_open(self) -> None:
        driver = FakeDriver([{"linked": 1}])
        link_preference_to_message_and_hotel(
            CONFIG, "p", "m", HERO_HOTEL_NAME, driver=driver
        )
        self.assertFalse(driver.closed)
        self.assertEqual(driver.database, "hotels")


class TestActorScopedPreferenceRead(unittest.TestCase):
    """The recall path anchors on both actor and Hotel."""

    def test_actor_and_hotel_are_parameters(self) -> None:
        rows = [{"preference": "high floor", "hotel": HERO_HOTEL_NAME}]
        driver = FakeDriver(rows)
        result = get_actor_preferences_for_hotel(
            CONFIG,
            "demo08-actor-a",
            HERO_HOTEL_NAME,
            driver=driver,
        )
        self.assertEqual(result, rows)
        query, params = driver.session_obj.calls[0]
        self.assertIn("HAS_PREFERENCE", query)
        self.assertIn(HOTEL_RELATIONSHIP, query)
        self.assertEqual(params["user_identifier"], "demo08-actor-a")
        self.assertEqual(params["hotel_name"], HERO_HOTEL_NAME)


class TestTagDemoRecords(unittest.TestCase):
    """The ownership marker write scopes to the demo's sessions and users."""

    def test_marks_and_counts_records(self) -> None:
        driver = FakeDriver([{"marked": 7}])
        marked = tag_demo_records(
            CONFIG,
            session_ids=["demo08-session-a1"],
            user_identifiers=["demo08-guest-alice"],
            driver=driver,
        )
        self.assertEqual(marked, 7)
        query, params = driver.session_obj.calls[0]
        self.assertIn("workshop_owner", query)
        self.assertEqual(params["owner"], WORKSHOP_OWNER)
        self.assertEqual(params["session_ids"], ["demo08-session-a1"])
        self.assertEqual(params["user_identifiers"], ["demo08-guest-alice"])

    def test_zero_when_nothing_matches(self) -> None:
        driver = FakeDriver([])
        self.assertEqual(
            tag_demo_records(
                CONFIG, session_ids=[], user_identifiers=[], driver=driver
            ),
            0,
        )


class TestCleanupScoping(unittest.TestCase):
    """The cleanup Cypher can only ever touch demo-owned memory records."""

    def test_hotel_link_delete_requires_owner(self) -> None:
        query = cleanup_memory.DELETE_DEMO_HOTEL_LINKS
        self.assertIn(HOTEL_RELATIONSHIP, query)
        self.assertIn("r.workshop_owner = $owner", query)

    def test_prefix_sweeps_use_the_demo_namespace(self) -> None:
        self.assertIn("STARTS WITH $prefix", cleanup_memory.DELETE_PREFIXED_SESSIONS)
        self.assertIn("STARTS WITH $prefix", cleanup_memory.DELETE_PREFIXED_USERS)
        self.assertEqual(DEMO_ID_PREFIX, "demo08-")

    def test_preferences_are_deleted_only_after_they_are_orphaned(self) -> None:
        query = cleanup_memory.DELETE_ORPHANED_DEMO_PREFERENCES
        self.assertIn("p.workshop_owner = $owner", query)
        self.assertIn("NOT EXISTS", query)
        self.assertIn("HAS_PREFERENCE", query)

    def test_cleanup_never_mutates_hotel_nodes(self) -> None:
        queries = (
            cleanup_memory.DELETE_DEMO_HOTEL_LINKS,
            cleanup_memory.DELETE_PREFIXED_SESSIONS,
            cleanup_memory.DELETE_PREFIXED_USERS,
            cleanup_memory.DELETE_ORPHANED_DEMO_PREFERENCES,
            cleanup_memory.REMOVE_SHARED_PREFERENCE_MARKERS,
        )
        for query in queries:
            self.assertNotIn("REMOVE h:", query)
            self.assertNotIn("DELETE h", query)


if __name__ == "__main__":
    unittest.main()
