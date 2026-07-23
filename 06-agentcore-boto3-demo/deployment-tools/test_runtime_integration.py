# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Focused offline tests for the Demo 06 Runtime and Gateway boundary."""

import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import booking_agent
import contracts

DEMO_DIR = Path(__file__).parent


class RuntimeIntegrationTests(unittest.TestCase):
    def test_runtime_exposes_one_local_and_one_gateway_tool(self) -> None:
        self.assertEqual(
            booking_agent.search_hotel_knowledge.tool_name,
            "search_hotel_knowledge",
        )
        self.assertEqual(
            booking_agent.GATEWAY_COMMAND_TOOL,
            "demo06-reservation-request___create_reservation_request",
        )

    def test_gateway_manifest_has_only_the_reservation_command(self) -> None:
        path = DEMO_DIR / "gateway_target.json"
        target = json.loads(path.read_text(encoding="utf-8"))
        tools = target["targetConfiguration"]["mcp"]["lambda"][
            "toolSchema"
        ]["inlinePayload"]

        self.assertEqual(len(tools), 1)
        self.assertEqual(target["name"], booking_agent.GATEWAY_TARGET_NAME)
        self.assertEqual(tools[0]["name"], "create_reservation_request")
        self.assertEqual(
            tools[0]["inputSchema"],
            contracts.gateway_reservation_input_schema(),
        )
        full_schema = contracts.reservation_input_schema()
        self.assertIn("additionalProperties", full_schema)
        self.assertNotIn("additionalProperties", tools[0]["inputSchema"])
        serialized = json.dumps(target).casefold()
        for forbidden in (
            "dynamodb",
            "book_hotel",
            "payment",
            "confirmation",
            "cancellation",
            "query_knowledge_graph",
            "validate_booking_rules",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_gateway_discovery_fails_closed(self) -> None:
        expected = Mock(tool_name=booking_agent.GATEWAY_COMMAND_TOOL)
        client = Mock()
        client.list_tools_sync.return_value = [expected]

        self.assertEqual(
            booking_agent._validated_command_tools(client),
            [expected],
        )
        client.list_tools_sync.assert_called_once_with()

        client.list_tools_sync.return_value = [
            expected,
            Mock(tool_name="process_payment"),
        ]
        with self.assertRaisesRegex(RuntimeError, "must expose only"):
            booking_agent._validated_command_tools(client)

    def test_payload_uses_only_a_caller_created_canonical_uuid(self) -> None:
        request_id = "a8b3c4d5-1234-4abc-8def-0123456789ab"
        self.assertEqual(
            booking_agent._prompt(
                {"prompt": "Create the request", "request_id": request_id}
            ),
            ("Create the request", request_id),
        )
        with self.assertRaisesRegex(ValueError, "canonical UUID"):
            booking_agent._prompt(
                {
                    "prompt": "Create the request",
                    "request_id": request_id.upper(),
                }
            )
        with self.assertRaisesRegex(ValueError, "non-empty prompt"):
            booking_agent._prompt({"prompt": " "})

    def test_command_guard_requires_and_preserves_caller_request_id(self) -> None:
        request_id = "a8b3c4d5-1234-4abc-8def-0123456789ab"

        missing = SimpleNamespace(
            tool_use={
                "name": booking_agent.GATEWAY_COMMAND_TOOL,
                "input": {"request_id": request_id},
            },
            cancel_tool=None,
        )
        booking_agent.ReservationRequestGuard(None)._validate(missing)
        self.assertIn("caller-provided request_id", missing.cancel_tool)

        mismatch = SimpleNamespace(
            tool_use={
                "name": booking_agent.GATEWAY_COMMAND_TOOL,
                "input": {"request_id": "other"},
            },
            cancel_tool=None,
        )
        booking_agent.ReservationRequestGuard(request_id)._validate(mismatch)
        self.assertIn("unchanged", mismatch.cancel_tool)

        matching = SimpleNamespace(
            tool_use={
                "name": booking_agent.GATEWAY_COMMAND_TOOL,
                "input": {"request_id": request_id},
            },
            cancel_tool=None,
        )
        booking_agent.ReservationRequestGuard(request_id)._validate(matching)
        self.assertIsNone(matching.cancel_tool)

    def test_local_tool_returns_bounded_retrieval_as_json(self) -> None:
        evidence = [{"hotel_id": "fixture-id", "chunk_evidence": "grounded"}]
        with patch.object(
            booking_agent,
            "_search_hotel_knowledge",
            return_value=evidence,
        ) as search:
            result = booking_agent.search_hotel_knowledge(query="Cairo")

        self.assertEqual(json.loads(result), evidence)
        search.assert_called_once_with("Cairo")

    def test_prompt_requires_grounding_and_visible_rejection(self) -> None:
        prompt = booking_agent.SYSTEM_PROMPT.casefold()
        normalized = " ".join(prompt.split())
        self.assertIn("use search_hotel_knowledge before", normalized)
        self.assertIn("stable hotel id returned by that search", normalized)
        self.assertIn("never silently reduce the guest count", normalized)
        self.assertIn("make every policy rejection visible", normalized)
        for forbidden in (
            "take payment",
            "confirm a booking",
            "silently reduce",
        ):
            self.assertIn(forbidden, normalized)

    def test_deployed_read_configuration_uses_only_read_secret(self) -> None:
        with patch.dict(
            os.environ,
            {contracts.READ_SECRET_ID_ENV: "demo/read"},
            clear=True,
        ):
            self.assertEqual(
                os.environ[contracts.READ_SECRET_ID_ENV],
                "demo/read",
            )
            self.assertNotIn(contracts.COMMAND_SECRET_ID_ENV, os.environ)

        deployment = (
            DEMO_DIR.parent / "advanced-deployment" / "DEPLOYMENT.md"
        ).read_text(encoding="utf-8")
        self.assertIn(contracts.READ_SECRET_ID_ENV, deployment)
        self.assertIn(contracts.COMMAND_SECRET_ID_ENV, deployment)
        self.assertIn("separate Neo4j users", deployment)

    def test_runtime_image_excludes_lambda_and_legacy_notebooks(self) -> None:
        dockerignore = (DEMO_DIR / ".dockerignore").read_text(encoding="utf-8")
        self.assertIn("lambda_tools/", dockerignore)
        self.assertIn("*.ipynb", dockerignore)
        self.assertIn("reservation_command.py", dockerignore)


if __name__ == "__main__":
    unittest.main()
