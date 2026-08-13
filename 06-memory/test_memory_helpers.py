# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Unit tests for the memory helper module. No database or AWS calls.

Pins the configuration contract this lab depends on: Titan Text Embeddings V2
with 1024 dimensions, an explicit Bedrock embedder, an explicit target
database, extraction off, and multi-tenant enforcement on. Also covers the
workshop-owned write helpers, meaning the provenance edge and the ownership
marker, against a fake driver, the per-actor preference categories that keep
the library's deduplication from merging two actors' preferences, the scoping
guarantees of the cleanup Cypher, the scope the cleanup command line resolves
to, and the hotel-count guard that makes cleanup refuse to finish if the hotel
graph moved. The live connect, write, and index checks are exercised by
``smoke_test.py``, not here.

Run with:  uv run --with pytest --with-requirements requirements.txt -m pytest
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
    PREFERENCE_CATEGORY_PREFIX,
    PROVENANCE_RELATIONSHIP,
    WORKSHOP_OWNER,
    MemoryDemoConfig,
    build_memory_client,
    build_memory_embedder,
    build_memory_settings,
    get_actor_preferences_for_hotel,
    link_preference_to_message_and_hotel,
    load_config,
    preference_category,
    preference_category_prefix,
    tag_demo_records,
)

RUN_PREFIX = f"{DEMO_ID_PREFIX}a1b2c3d4-"

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
        empty_dir = Path(tmp.name) / "lab"
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

    def test_defaults_match_the_other_labs(self) -> None:
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
    """The settings pin the contract the rest of this lab depends on."""

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
    """The ownership marker write scopes to the lab's sessions and users."""

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


class FakeCounters:
    """The two counters run_cleanup reads off a consumed result."""

    def __init__(self, nodes: int = 0, relationships: int = 0) -> None:
        self.nodes_deleted = nodes
        self.relationships_deleted = relationships


class FakeSummary:
    def __init__(self, counters: FakeCounters) -> None:
        self.counters = counters


class FakeCleanupResult:
    def __init__(
        self,
        row: dict | None = None,
        counters: FakeCounters | None = None,
    ) -> None:
        self._row = row
        self._counters = counters or FakeCounters()

    def single(self) -> dict | None:
        return self._row

    def consume(self) -> FakeSummary:
        return FakeSummary(self._counters)


COUNT_QUERIES = frozenset(count_query for _, _, count_query in cleanup_memory.SWEEPS)


class FakeCleanupSession:
    """Answer COUNT_HOTELS from a scripted list, count deletes for the rest.

    cleanup_memory calls ``session.run(COUNT_HOTELS)`` with no parameters and
    ``session.run(query, params)`` for the sweeps, so both shapes are handled.
    A dry run asks the per-sweep count queries for a ``records`` row instead.
    """

    def __init__(self, hotel_counts: list[int]) -> None:
        self.hotel_counts = list(hotel_counts)
        self.calls: list[tuple[str, dict]] = []

    def __enter__(self) -> "FakeCleanupSession":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def run(self, query: str, parameters: dict | None = None):
        self.calls.append((query, parameters or {}))
        if query == cleanup_memory.COUNT_HOTELS:
            return FakeCleanupResult(row={"hotels": self.hotel_counts.pop(0)})
        if query in COUNT_QUERIES:
            return FakeCleanupResult(row={"records": 3})
        return FakeCleanupResult(counters=FakeCounters(nodes=1, relationships=2))

    def queries(self) -> list[str]:
        return [query for query, _ in self.calls]


class FakeCleanupDriver:
    def __init__(self, hotel_counts: list[int]) -> None:
        self.session_obj = FakeCleanupSession(hotel_counts)
        self.closed = False

    def session(self, database: str | None = None) -> FakeCleanupSession:
        self.database = database
        return self.session_obj

    def close(self) -> None:
        self.closed = True


class TestCleanupHotelGuard(unittest.TestCase):
    """The before/after hotel count is what actually protects Lab 1's graph.

    Asserting that the cleanup Cypher does not contain ``DELETE h`` only tests
    a variable name: ``DETACH DELETE c, m`` would pass that check whatever
    ``c`` and ``m`` were bound to. This drives the real guard instead.
    """

    def test_stable_hotel_count_completes(self) -> None:
        driver = FakeCleanupDriver([12, 12])
        with mock.patch.object(
            cleanup_memory.GraphDatabase, "driver", return_value=driver
        ):
            self.assertEqual(
                cleanup_memory.run_cleanup(
                    CONFIG, cleanup_memory.run_scope(RUN_PREFIX)
                ),
                0,
            )
        self.assertTrue(driver.closed)
        self.assertEqual(driver.database, CONFIG.database)

    def test_changed_hotel_count_raises(self) -> None:
        driver = FakeCleanupDriver([12, 11])
        with mock.patch.object(
            cleanup_memory.GraphDatabase, "driver", return_value=driver
        ):
            with self.assertRaises(AssertionError) as ctx:
                cleanup_memory.run_cleanup(
                    CONFIG, cleanup_memory.run_scope(RUN_PREFIX)
                )
        message = str(ctx.exception)
        self.assertIn("12", message)
        self.assertIn("11", message)
        # The driver still has to be released on the failing path.
        self.assertTrue(driver.closed)

    def test_main_returns_nonzero_when_the_guard_fires(self) -> None:
        driver = FakeCleanupDriver([12, 13])
        with mock.patch.object(
            cleanup_memory, "load_config", return_value=CONFIG
        ):
            with mock.patch.object(
                cleanup_memory.GraphDatabase, "driver", return_value=driver
            ):
                exit_code = cleanup_memory.main(["--run-prefix", RUN_PREFIX])
        self.assertEqual(exit_code, 1)


class TestCleanupScoping(unittest.TestCase):
    """The cleanup Cypher can only ever touch this lab's memory records."""

    def test_hotel_link_delete_requires_owner_and_category(self) -> None:
        query = cleanup_memory.DELETE_DEMO_HOTEL_LINKS
        self.assertIn(HOTEL_RELATIONSHIP, query)
        self.assertIn("r.workshop_owner = $owner", query)
        # Without the category bound, one participant's cleanup would strip
        # the provenance edges every other participant just wrote.
        self.assertIn("p.category STARTS WITH $category_prefix", query)

    def test_prefix_sweeps_use_the_lab_namespace(self) -> None:
        self.assertIn("STARTS WITH $prefix", cleanup_memory.DELETE_PREFIXED_SESSIONS)
        self.assertIn("STARTS WITH $prefix", cleanup_memory.DELETE_PREFIXED_USERS)
        self.assertEqual(DEMO_ID_PREFIX, "demo08-")

    def test_preferences_are_deleted_only_after_they_are_orphaned(self) -> None:
        query = cleanup_memory.DELETE_ORPHANED_DEMO_PREFERENCES
        self.assertIn("p.workshop_owner = $owner", query)
        self.assertIn("NOT EXISTS", query)
        self.assertIn("HAS_PREFERENCE", query)

    def test_orphaned_preferences_are_also_swept_by_category_prefix(
        self,
    ) -> None:
        # The owner marker is stamped by the notebook's second-to-last cell,
        # so a run that died earlier never carries it. By the time this query
        # runs the preceding sweeps have detached every edge that could reach
        # the node, which leaves the category namespace as the only handle.
        query = cleanup_memory.DELETE_ORPHANED_DEMO_PREFERENCES
        self.assertIn("p.category STARTS WITH $category_prefix", query)
        self.assertEqual(PREFERENCE_CATEGORY_PREFIX, "hotels-demo08-")
        self.assertTrue(
            PREFERENCE_CATEGORY_PREFIX.endswith(DEMO_ID_PREFIX),
            "the preference namespace must track DEMO_ID_PREFIX",
        )

    def test_cleanup_passes_the_category_prefix_parameter(self) -> None:
        # A query that names $category_prefix but never receives it fails at
        # runtime, and only against a live database.
        driver = FakeCleanupDriver([12, 12])
        with mock.patch.object(
            cleanup_memory.GraphDatabase, "driver", return_value=driver
        ):
            cleanup_memory.run_cleanup(CONFIG, cleanup_memory.all_runs_scope())
        params = dict(driver.session_obj.calls)[
            cleanup_memory.DELETE_ORPHANED_DEMO_PREFERENCES
        ]
        self.assertEqual(
            params["category_prefix"], PREFERENCE_CATEGORY_PREFIX
        )
        self.assertEqual(params["owner"], WORKSHOP_OWNER)

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


class TestPreferenceCategories(unittest.TestCase):
    """Two actors have to write under two categories, not one.

    ``LongTermMemory.add_preference`` deduplicates inside a category: it runs a
    vector search over ``preference_embedding_idx`` filtered to
    ``node.category`` and, at cosine 0.95 or above, links the caller to the
    preference that is already there instead of creating a node. Two actors
    sharing a category and stating near-paraphrases of the same preference is
    the case the workshop's isolation lesson depends on, and it is exactly the
    case that merges.
    """

    def test_two_actors_get_two_categories(self) -> None:
        self.assertNotEqual(
            preference_category(RUN_PREFIX, "alice"),
            preference_category(RUN_PREFIX, "blake"),
        )

    def test_both_actors_stay_inside_the_run_namespace(self) -> None:
        # One prefix still reaches both categories, which is what lets cleanup
        # sweep a run without knowing the actor labels.
        run_categories = preference_category_prefix(RUN_PREFIX)
        for label in ("alice", "blake"):
            self.assertTrue(
                preference_category(RUN_PREFIX, label).startswith(
                    run_categories
                )
            )

    def test_the_run_namespace_sits_inside_the_lab_namespace(self) -> None:
        self.assertTrue(
            preference_category_prefix(RUN_PREFIX).startswith(
                PREFERENCE_CATEGORY_PREFIX
            ),
            "--all has to reach every run's categories",
        )

    def test_the_default_prefix_matches_the_constant(self) -> None:
        self.assertEqual(
            preference_category_prefix(DEMO_ID_PREFIX),
            PREFERENCE_CATEGORY_PREFIX,
        )


class TestCleanupScopeResolution(unittest.TestCase):
    """The command line defaults to one run, never to the whole instance."""

    @staticmethod
    def _scope(argv: list[str]):
        return cleanup_memory.resolve_scope(cleanup_memory.parse_args(argv))

    def test_no_arguments_resolve_to_no_scope(self) -> None:
        # The old default swept the instance. On a shared Aura instance that
        # deleted every other participant's in-flight records.
        self.assertIsNone(self._scope([]))

    def test_main_exits_nonzero_without_a_scope(self) -> None:
        with mock.patch.object(
            cleanup_memory, "load_config", return_value=CONFIG
        ):
            with mock.patch.object(
                cleanup_memory.GraphDatabase, "driver"
            ) as driver:
                self.assertEqual(cleanup_memory.main([]), 2)
        driver.assert_not_called()

    def test_run_prefix_bounds_both_namespaces(self) -> None:
        scope = self._scope(["--run-prefix", RUN_PREFIX])
        self.assertEqual(scope.id_prefix, RUN_PREFIX)
        self.assertEqual(
            scope.category_prefix, preference_category_prefix(RUN_PREFIX)
        )
        self.assertNotEqual(scope.id_prefix, DEMO_ID_PREFIX)
        self.assertNotEqual(scope.category_prefix, PREFERENCE_CATEGORY_PREFIX)

    def test_run_prefix_outside_the_lab_namespace_is_refused(self) -> None:
        self.assertIsNone(self._scope(["--run-prefix", "hotels"]))

    def test_all_needs_the_typed_confirmation(self) -> None:
        with mock.patch("builtins.input", return_value="yes"):
            self.assertIsNone(self._scope(["--all"]))
        with mock.patch(
            "builtins.input", return_value=cleanup_memory.ALL_CONFIRMATION
        ):
            scope = self._scope(["--all"])
        self.assertEqual(scope.id_prefix, DEMO_ID_PREFIX)
        self.assertEqual(scope.category_prefix, PREFERENCE_CATEGORY_PREFIX)

    def test_all_is_refused_when_no_answer_can_be_read(self) -> None:
        with mock.patch("builtins.input", side_effect=EOFError):
            self.assertIsNone(self._scope(["--all"]))

    def test_dry_run_over_all_asks_nothing_and_deletes_nothing(self) -> None:
        with mock.patch("builtins.input", side_effect=AssertionError):
            scope = self._scope(["--all", "--dry-run"])
        self.assertEqual(scope.id_prefix, DEMO_ID_PREFIX)

    def test_dry_run_issues_no_delete(self) -> None:
        driver = FakeCleanupDriver([12, 12])
        with mock.patch.object(
            cleanup_memory.GraphDatabase, "driver", return_value=driver
        ):
            cleanup_memory.run_cleanup(
                CONFIG, cleanup_memory.run_scope(RUN_PREFIX), dry_run=True
            )
        queries = driver.session_obj.queries()
        for _, delete_query, count_query in cleanup_memory.SWEEPS:
            self.assertNotIn(delete_query, queries)
            self.assertIn(count_query, queries)
        self.assertNotIn(
            cleanup_memory.REMOVE_SHARED_PREFERENCE_MARKERS, queries
        )

    def test_a_run_scoped_sweep_only_ever_sees_its_own_prefix(self) -> None:
        driver = FakeCleanupDriver([12, 12])
        with mock.patch.object(
            cleanup_memory.GraphDatabase, "driver", return_value=driver
        ):
            cleanup_memory.run_cleanup(
                CONFIG, cleanup_memory.run_scope(RUN_PREFIX)
            )
        swept = [params for _, params in driver.session_obj.calls if params]
        self.assertTrue(swept)
        for params in swept:
            self.assertEqual(params["prefix"], RUN_PREFIX)
            self.assertEqual(
                params["category_prefix"],
                preference_category_prefix(RUN_PREFIX),
            )


if __name__ == "__main__":
    unittest.main()
