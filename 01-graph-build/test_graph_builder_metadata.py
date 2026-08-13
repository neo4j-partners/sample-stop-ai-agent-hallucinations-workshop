# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Regression test for source identity passed into graph extraction."""

import asyncio
import os
import unittest
from pathlib import Path

os.environ.setdefault("NEO4J_PASSWORD", "test-only")

from graph_builder import ingest  # noqa: E402


class RecordingPipeline:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def run_async(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


class GraphBuilderMetadataTests(unittest.TestCase):
    def test_ingest_preserves_source_filename_on_document(self) -> None:
        pipeline = RecordingPipeline()
        source = Path("data/hotel-cairo-001.txt")

        errors = asyncio.run(ingest(pipeline, [source]))  # type: ignore[arg-type]

        self.assertEqual(errors, 0)
        self.assertEqual(len(pipeline.calls), 1)
        self.assertEqual(pipeline.calls[0]["file_path"], source.name)
        self.assertEqual(
            pipeline.calls[0]["document_metadata"],
            {"source_filename": source.name},
        )
        self.assertIn("AnyCompany Cairo Nile View", pipeline.calls[0]["text"])


if __name__ == "__main__":
    unittest.main()
