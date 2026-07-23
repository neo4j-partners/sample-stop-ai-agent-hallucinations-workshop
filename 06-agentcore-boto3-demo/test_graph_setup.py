# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Focused offline tests for Demo 06 graph preparation."""

import json
import tempfile
import unittest
from pathlib import Path

import contracts
import graph_setup


class GraphSetupTests(unittest.TestCase):
    def test_committed_manifest_is_small_opaque_and_deterministic(self) -> None:
        manifest = graph_setup.load_manifest()

        self.assertEqual(manifest.version, 1)
        self.assertEqual(
            set(manifest.hotels),
            {"hotel-cairo-001.txt", "hotel-cairo-002.txt"},
        )
        self.assertEqual(manifest.rows(), sorted(manifest.rows(), key=lambda row: row["source_filename"]))
        self.assertNotIn("cairo", " ".join(manifest.hotels.values()).casefold())

    def test_manifest_rejects_duplicate_ids(self) -> None:
        payload = {
            "manifest_version": 1,
            "hotels": {
                "hotel-cairo-001.txt": "81393d51-1df3-4f53-b58e-e4cda9736fd7",
                "hotel-cairo-002.txt": "81393d51-1df3-4f53-b58e-e4cda9736fd7",
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must be unique"):
                graph_setup.load_manifest(path)

    def test_schema_uses_cypher_25_ordinary_uniqueness_constraints(self) -> None:
        for query in (
            graph_setup.HOTEL_ID_CONSTRAINT,
            graph_setup.REQUEST_ID_CONSTRAINT,
            graph_setup.RULE_ID_CONSTRAINT,
        ):
            self.assertTrue(query.startswith("CYPHER 25"))
            self.assertIn(" IS UNIQUE", query)
            self.assertNotIn("IS NODE KEY", query)
            self.assertNotIn("GRAPH TYPE", query)

    def test_graph_writes_are_idempotent_by_construction(self) -> None:
        self.assertIn("IF NOT EXISTS", graph_setup.HOTEL_ID_CONSTRAINT)
        self.assertIn("IF NOT EXISTS", graph_setup.REQUEST_ID_CONSTRAINT)
        self.assertIn("IF NOT EXISTS", graph_setup.RULE_ID_CONSTRAINT)
        self.assertIn("MERGE (rule:Rule", graph_setup.UPSERT_RULE_QUERY)
        self.assertNotIn("CREATE (rule:Rule", graph_setup.UPSERT_RULE_QUERY)

    def test_fixture_assignment_joins_by_source_filename(self) -> None:
        query = graph_setup.APPLY_FIXTURE_IDS_QUERY

        self.assertIn("Document {source_filename: fixture.source_filename}", query)
        self.assertIn("[:FROM_DOCUMENT]", query)
        self.assertIn("[:FROM_CHUNK]", query)
        self.assertIn("hotel.demo6_fixture = true", query)

    def test_index_contract_accepts_expected_indexes(self) -> None:
        records = [
            {
                "name": contracts.CHUNK_VECTOR_INDEX,
                "type": "VECTOR",
                "state": "ONLINE",
                "labelsOrTypes": ["Chunk"],
                "properties": ["embedding"],
                "options": {
                    "indexConfig": {
                        "vector.dimensions": 1024,
                        "vector.similarity_function": "COSINE",
                    }
                },
            },
            {
                "name": contracts.CHUNK_FULLTEXT_INDEX,
                "type": "FULLTEXT",
                "state": "ONLINE",
                "labelsOrTypes": ["Chunk"],
                "properties": ["text"],
                "options": {},
            },
        ]

        self.assertEqual(graph_setup._index_problems(records), [])

    def test_index_contract_reports_missing_and_mismatched_indexes(self) -> None:
        records = [
            {
                "name": contracts.CHUNK_VECTOR_INDEX,
                "type": "VECTOR",
                "state": "POPULATING",
                "labelsOrTypes": ["Wrong"],
                "properties": ["embedding"],
                "options": {"indexConfig": {}},
            }
        ]

        problems = graph_setup._index_problems(records)

        self.assertTrue(any("not ONLINE" in problem for problem in problems))
        self.assertTrue(any("missing index" in problem for problem in problems))
        self.assertTrue(any("wrong dimensions" in problem for problem in problems))

    def test_fixture_readiness_requires_one_document_chunk_hotel_and_id(self) -> None:
        manifest = graph_setup.load_manifest()
        records = [
            {
                "source_filename": source,
                "expected_hotel_id": hotel_id,
                "documents": 1,
                "chunks": 1,
                "hotels": 1,
                "hotel_element_ids": [f"element-{index}"],
                "actual_hotel_ids": [hotel_id],
            }
            for index, (source, hotel_id) in enumerate(manifest.hotels.items())
        ]

        self.assertEqual(
            graph_setup._fixture_problems(records, manifest, require_ids=True),
            [],
        )
        records[0]["hotels"] = 2
        self.assertTrue(
            graph_setup._fixture_problems(records, manifest, require_ids=True)
        )

    def test_fixture_readiness_rejects_cross_source_hotel_reuse(self) -> None:
        manifest = graph_setup.load_manifest()
        records = [
            {
                "source_filename": source,
                "documents": 1,
                "chunks": 1,
                "hotels": 1,
                "hotel_element_ids": ["same-hotel"],
                "actual_hotel_ids": [],
            }
            for source in manifest.hotels
        ]

        problems = graph_setup._fixture_problems(
            records,
            manifest,
            require_ids=False,
        )

        self.assertTrue(any("same Hotel node" in problem for problem in problems))

    def test_constraint_readiness_verifies_shape_not_only_name(self) -> None:
        records = [
            {
                "name": "demo06_fixture_hotel_id",
                "type": "UNIQUENESS",
                "labelsOrTypes": ["Hotel"],
                "properties": ["hotel_id"],
            },
            {
                "name": "demo06_reservation_request_id",
                "type": "UNIQUENESS",
                "labelsOrTypes": ["ReservationRequest"],
                "properties": ["request_id"],
            },
            {
                "name": "demo06_rule_id",
                "type": "UNIQUENESS",
                "labelsOrTypes": ["Rule"],
                "properties": ["rule_id"],
            },
        ]

        self.assertEqual(graph_setup._constraint_problems(records), [])
        records[0]["properties"] = ["name"]
        self.assertTrue(graph_setup._constraint_problems(records))

    def test_hero_and_rule_contracts_are_strict(self) -> None:
        hero = {
            "name": graph_setup.HERO_NAME,
            "address": graph_setup.HERO_ADDRESS,
            "guest_rating": graph_setup.HERO_RATING,
            "amenities": [
                "Outdoor Swimming Pool",
                "Full-Service Spa",
                "24-Hour Fitness Center",
                "Complimentary High-Speed WiFi",
                "On-Site Restaurant",
            ],
        }
        rule = {
            "rule_count": 1,
            "max_guests": 10,
            "enabled": True,
            "rejection_message": graph_setup.RULE_REJECTION_MESSAGE,
            "steering_message": graph_setup.RULE_STEERING_MESSAGE,
            "workshop_owner": contracts.WORKSHOP_OWNER,
        }

        self.assertEqual(graph_setup._hero_problems(hero), [])
        self.assertEqual(graph_setup._rule_problems(rule), [])
        self.assertTrue(graph_setup._hero_problems({**hero, "guest_rating": 5.0}))
        self.assertTrue(graph_setup._rule_problems({**rule, "max_guests": 15}))

    def test_reservation_graph_shape_is_minimal_and_has_no_actor(self) -> None:
        self.assertEqual(
            graph_setup.FOR_HOTEL_PATTERN,
            "(:ReservationRequest)-[:FOR_HOTEL]->(:Hotel)",
        )
        self.assertNotIn("actor_id", graph_setup.RESERVATION_REQUEST_PROPERTIES)
        self.assertEqual(
            set(graph_setup.RESERVATION_REQUEST_PROPERTIES),
            {
                "request_id",
                "check_in",
                "check_out",
                "guests",
                "status",
                "workshop_owner",
                "created_at",
            },
        )


if __name__ == "__main__":
    unittest.main()
