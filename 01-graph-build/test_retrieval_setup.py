# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Regression tests for Lab 1's deterministic preparation contract."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("NEO4J_PASSWORD", "test-only")
# `graph_config` is Lab 1's own module, so it is reached by path rather than by
# package name. Everything else now comes from the installed `workshop` package.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from graph_config import select_lite_files  # noqa: E402
from workshop.retrieval_contract import (  # noqa: E402
    CHUNK_FULLTEXT_INDEX,
    CHUNK_VECTOR_INDEX,
    EMBEDDING_DIMENSIONS,
)
from workshop.retrieval_setup import (  # noqa: E402
    _index_contract_problems,
    missing_source_fixtures,
)


def valid_index_records() -> list[dict]:
    """Return SHOW INDEXES-like records matching the retrieval contract."""
    return [
        {
            "name": CHUNK_VECTOR_INDEX,
            "type": "VECTOR",
            "state": "ONLINE",
            "labelsOrTypes": ["Chunk"],
            "properties": ["embedding"],
            "options": {
                "indexConfig": {
                    "vector.dimensions": EMBEDDING_DIMENSIONS,
                    "vector.similarity_function": "cosine",
                }
            },
        },
        {
            "name": CHUNK_FULLTEXT_INDEX,
            "type": "FULLTEXT",
            "state": "ONLINE",
            "labelsOrTypes": ["Chunk"],
            "properties": ["text"],
            "options": {"indexConfig": {}},
        },
    ]


class TestSourceFixtures(unittest.TestCase):
    def test_lite_sample_contains_every_demo_critical_source(self) -> None:
        data_dir = Path(__file__).resolve().parent / "data"
        paths = [
            data_dir / name
            for name in select_lite_files(data_dir, max_docs=30)
        ]
        self.assertEqual(missing_source_fixtures(paths), [])

    def test_missing_source_is_reported_by_filename(self) -> None:
        self.assertIn(
            "hotel-chicago-001.txt",
            missing_source_fixtures([Path("hotel-paris-001.txt")]),
        )


class TestIndexContract(unittest.TestCase):
    def test_expected_indexes_pass(self) -> None:
        self.assertEqual(_index_contract_problems(valid_index_records()), [])

    def test_uppercase_similarity_metadata_passes(self) -> None:
        records = valid_index_records()
        records[0]["options"]["indexConfig"]["vector.similarity_function"] = (
            "COSINE"
        )

        self.assertEqual(_index_contract_problems(records), [])

    def test_wrong_vector_dimensions_fail_clearly(self) -> None:
        records = valid_index_records()
        records[0]["options"]["indexConfig"]["vector.dimensions"] = 1536

        problems = _index_contract_problems(records)

        self.assertTrue(any("1536 dimensions" in problem for problem in problems))

    def test_missing_fulltext_index_fails_clearly(self) -> None:
        problems = _index_contract_problems(valid_index_records()[:1])

        self.assertIn(f"missing index {CHUNK_FULLTEXT_INDEX!r}", problems)


if __name__ == "__main__":
    unittest.main()
