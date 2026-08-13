# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Focused offline tests for the Demo 06 hybrid retrieval boundary."""

import inspect
import io
import json
import os
import unittest
from unittest.mock import Mock, patch

from neo4j_graphrag.types import HybridSearchRanker, RetrieverResultItem

import contracts
import hybrid_retrieval


class HybridRetrievalTests(unittest.TestCase):
    def tearDown(self) -> None:
        hybrid_retrieval._get_driver.cache_clear()
        hybrid_retrieval._get_retriever.cache_clear()

    def test_public_tool_accepts_only_query(self) -> None:
        parameters = inspect.signature(
            hybrid_retrieval.search_hotel_knowledge
        ).parameters
        self.assertEqual(list(parameters), ["query"])

    def test_search_uses_frozen_ranker_and_top_k(self) -> None:
        retriever = Mock()
        retriever.search.return_value.items = []

        with patch.object(
            hybrid_retrieval,
            "_get_retriever",
            return_value=retriever,
        ):
            results = hybrid_retrieval.search_hotel_knowledge("Cairo hotel")

        self.assertEqual(results, [])
        retriever.search.assert_called_once_with(
            query_text="Cairo hotel",
            top_k=5,
            ranker=HybridSearchRanker.NAIVE,
        )

    def test_retriever_uses_fixed_indexes_and_static_traversal(self) -> None:
        config = hybrid_retrieval.Neo4jConfig(
            uri="neo4j+s://example.test",
            username="reader",
            password="secret",
            database="neo4j",
        )
        driver = Mock()
        embedder = Mock()

        with (
            patch.object(hybrid_retrieval, "_get_driver", return_value=driver),
            patch.object(hybrid_retrieval, "HybridCypherRetriever") as factory,
        ):
            hybrid_retrieval.build_retriever(config, embedder=embedder)

        factory.assert_called_once_with(
            driver=driver,
            vector_index_name=contracts.CHUNK_VECTOR_INDEX,
            fulltext_index_name=contracts.CHUNK_FULLTEXT_INDEX,
            retrieval_query=hybrid_retrieval.RETRIEVAL_QUERY,
            embedder=embedder,
            result_formatter=hybrid_retrieval._format_record,
            neo4j_database="neo4j",
        )
        query = hybrid_retrieval.RETRIEVAL_QUERY
        self.assertIn("(node:Chunk)<-[:FROM_CHUNK]-(candidate:Hotel)", query)
        self.assertIn("[:OFFERS_AMENITY]", query)
        self.assertIn("LIMIT 12", query)
        self.assertIn("ORDER BY combined_score DESC", query)
        self.assertNotIn("NULLS LAST", query)
        self.assertNotIn("$query", query)

    def test_results_preserve_descending_fused_score_order(self) -> None:
        retriever = Mock()
        retriever.search.return_value.items = [
            RetrieverResultItem(
                content="lower",
                metadata={"combined_score": 0.25, "hotel_id": "b"},
            ),
            RetrieverResultItem(
                content="higher",
                metadata={"combined_score": 0.75, "hotel_id": "a"},
            ),
        ]

        with patch.object(
            hybrid_retrieval,
            "_get_retriever",
            return_value=retriever,
        ):
            results = hybrid_retrieval.search_hotel_knowledge("hotel")

        self.assertEqual(
            [item["combined_score"] for item in results],
            [0.75, 0.25],
        )

    def test_result_boundary_rejects_invalid_graph_types(self) -> None:
        item = RetrieverResultItem(
            content="evidence",
            metadata={"combined_score": "not-a-number", "hotel_id": 42},
        )

        with self.assertRaisesRegex(ValueError, "combined_score"):
            hybrid_retrieval._to_evidence("query", item)

    def test_results_are_bounded_sorted_and_null_safe(self) -> None:
        retriever = Mock()
        retriever.search.return_value.items = [
            RetrieverResultItem(
                content="AnyCompany Cairo Nile View has a Spa." + "x" * 2_000,
                metadata={
                    "combined_score": "0.75",
                    "hotel_id": "hotel_demo_01",
                    "hotel_name": "AnyCompany Cairo Nile View",
                    "address": None,
                    "guest_rating": None,
                    "amenities": [
                        "Spa",
                        None,
                        " pool ",
                        "Spa",
                        "Wi-Fi",
                        "Airport shuttle",
                        "Gym",
                        "Breakfast",
                        "Concierge",
                        "Laundry",
                        "Parking",
                        "Restaurant",
                        "Room service",
                        "Sauna",
                        "Business center",
                    ],
                },
            )
        ]

        with patch.object(
            hybrid_retrieval,
            "_get_retriever",
            return_value=retriever,
        ):
            results = hybrid_retrieval.search_hotel_knowledge(
                "What does anycompany Cairo offer?"
            )

        self.assertEqual(len(results), 1)
        item = results[0]
        self.assertEqual(set(item), set(contracts.HotelEvidence.__annotations__))
        self.assertLessEqual(
            len(item["chunk_evidence"]),
            hybrid_retrieval.MAX_EVIDENCE_CHARS,
        )
        self.assertEqual(item["combined_score"], 0.75)
        self.assertEqual(item["exact_terms"], ["AnyCompany", "Cairo"])
        self.assertIsNone(item["address"])
        self.assertIsNone(item["guest_rating"])
        self.assertEqual(len(item["amenities"]), 12)
        self.assertNotIn(None, item["amenities"])
        self.assertEqual(
            item["amenities"],
            sorted(item["amenities"], key=str.casefold),
        )

    def test_unsupported_availability_claim_stays_unsupported(self) -> None:
        retriever = Mock()
        retriever.search.return_value.items = [
            RetrieverResultItem(
                content=(
                    "AnyCompany Cairo Nile View offers a pool and has a 4.7 "
                    "guest rating."
                ),
                metadata={
                    "combined_score": 0.8,
                    "hotel_id": "hotel_demo_01",
                    "hotel_name": "AnyCompany Cairo Nile View",
                    "address": "Cairo",
                    "guest_rating": 4.7,
                    "amenities": ["Pool"],
                },
            )
        ]
        question = (
            "Does AnyCompany Cairo Nile View guarantee room availability "
            "next weekend?"
        )

        with patch.object(
            hybrid_retrieval,
            "_get_retriever",
            return_value=retriever,
        ):
            item = hybrid_retrieval.search_hotel_knowledge(question)[0]

        evidence = item["chunk_evidence"].casefold()
        self.assertNotIn("guarantee", evidence)
        self.assertNotIn("availability", evidence)
        self.assertNotIn("guarantee", [term.casefold() for term in item["exact_terms"]])
        self.assertNotIn(
            "availability",
            [term.casefold() for term in item["exact_terms"]],
        )
        instructions = hybrid_retrieval.GROUNDING_INSTRUCTIONS.casefold()
        self.assertIn("subject to availability", instructions)
        self.assertIn("cannot determine", instructions)
        self.assertIn("do not infer live room inventory", instructions)

    def test_exact_terms_do_not_match_inside_other_words(self) -> None:
        self.assertEqual(
            hybrid_retrieval._exact_terms("in Cairo", "rating near Cairo"),
            ["Cairo"],
        )

    def test_nova_query_embedding_matches_frozen_contract(self) -> None:
        client = Mock()
        client.invoke_model.return_value = {
            "body": io.BytesIO(json.dumps({"embeddings": [{"embedding": [0.1]}]}).encode())
        }
        embedder = hybrid_retrieval.NovaEmbeddings(bedrock_client=client)

        self.assertEqual(embedder.embed_query("Cairo"), [0.1])

        kwargs = client.invoke_model.call_args.kwargs
        self.assertEqual(kwargs["modelId"], contracts.EMBEDDING_MODEL_ID)
        body = json.loads(kwargs["body"])
        params = body["singleEmbeddingParams"]
        self.assertEqual(params["embeddingPurpose"], contracts.EMBEDDING_PURPOSE)
        self.assertEqual(params["embeddingDimension"], contracts.EMBEDDING_DIMENSIONS)
        self.assertEqual(params["text"]["value"], "Cairo")

    def test_local_config_and_driver_are_reused(self) -> None:
        environment = {
            "NEO4J_URI": "neo4j+s://example.test",
            "NEO4J_USERNAME": "reader",
            "NEO4J_PASSWORD": "secret",
            "NEO4J_DATABASE": "neo4j",
        }
        with patch.dict(os.environ, environment, clear=True):
            config = hybrid_retrieval.Neo4jConfig.from_environment()

        with patch.object(hybrid_retrieval.GraphDatabase, "driver") as factory:
            first = hybrid_retrieval._get_driver(config)
            second = hybrid_retrieval._get_driver(config)

        self.assertIs(first, second)
        factory.assert_called_once_with(
            config.uri,
            auth=(config.username, config.password),
            notifications_min_severity="OFF",
        )

    def test_read_secret_uses_frozen_shape(self) -> None:
        client = Mock()
        client.get_secret_value.return_value = {
            "SecretString": json.dumps(
                {
                    "uri": "neo4j+s://example.test",
                    "username": "reader",
                    "password": "secret",
                    "database": "neo4j",
                }
            )
        }

        config = hybrid_retrieval.Neo4jConfig.from_secret(
            "demo/read",
            secrets_client=client,
        )

        self.assertEqual(config.username, "reader")
        client.get_secret_value.assert_called_once_with(SecretId="demo/read")

    def test_deployed_retriever_selects_only_the_read_secret(self) -> None:
        config = hybrid_retrieval.Neo4jConfig(
            uri="neo4j+s://example.test",
            username="reader",
            password="secret",
            database="neo4j",
        )
        retriever = Mock()
        with (
            patch.dict(
                os.environ,
                {contracts.READ_SECRET_ID_ENV: "demo/read"},
                clear=True,
            ),
            patch.object(
                hybrid_retrieval.Neo4jConfig,
                "from_secret",
                return_value=config,
            ) as from_secret,
            patch.object(
                hybrid_retrieval,
                "build_retriever",
                return_value=retriever,
            ) as build,
        ):
            self.assertIs(hybrid_retrieval._get_retriever(), retriever)

        from_secret.assert_called_once_with("demo/read")
        build.assert_called_once_with(config)


if __name__ == "__main__":
    unittest.main()
