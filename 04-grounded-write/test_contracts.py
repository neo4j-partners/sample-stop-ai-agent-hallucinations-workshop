# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Contract tests for the bounded Demo 06 service boundary."""

import json
import unittest
from pathlib import Path
from typing import get_type_hints

from workshop import contracts


class Demo06ContractTests(unittest.TestCase):
    def test_retrieval_contract_is_fixed_and_bounded(self) -> None:
        schema = contracts.retrieval_input_schema()

        self.assertEqual(schema["required"], ["query"])
        self.assertEqual(set(schema["properties"]), {"query"})
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(contracts.HYBRID_RANKER, "NAIVE")
        self.assertEqual(contracts.HYBRID_TOP_K, 5)
        self.assertEqual(contracts.MAX_AMENITIES, 12)

    def test_reservation_contract_has_no_actor_or_booking_lifecycle(self) -> None:
        schema = contracts.reservation_input_schema()

        self.assertEqual(
            set(schema["properties"]),
            {"request_id", "hotel_id", "check_in", "check_out", "guests"},
        )
        self.assertFalse(schema["additionalProperties"])
        serialized = json.dumps(schema).lower()
        for forbidden in ("actor", "payment", "confirmation", "cancellation"):
            self.assertNotIn(forbidden, serialized)

    def test_committed_tool_schemas_match_python_contracts(self) -> None:
        # The schemas ship with the deployment, which lives in Lab 5, while the
        # Python contracts they must match live here in Lab 4. The two labs came
        # out of one folder, so this assertion now crosses a folder boundary.
        schema_path = (
            Path(__file__).resolve().parent.parent
            / "05-agentcore-deploy"
            / "tool_schemas"
            / "tools.json"
        )
        tools = json.loads(schema_path.read_text(encoding="utf-8"))

        self.assertEqual(
            [tool["name"] for tool in tools],
            ["search_hotel_knowledge", "create_reservation_request"],
        )
        self.assertEqual(tools[0]["input_schema"], contracts.retrieval_input_schema())
        self.assertEqual(tools[1]["input_schema"], contracts.reservation_input_schema())

    def test_separate_credentials_share_only_secret_shape(self) -> None:
        self.assertNotEqual(
            contracts.READ_SECRET_ID_ENV,
            contracts.COMMAND_SECRET_ID_ENV,
        )
        self.assertEqual(
            contracts.SECRET_FIELDS,
            ("uri", "username", "password", "database"),
        )

    def test_gateway_schema_is_a_supported_projection(self) -> None:
        schema = contracts.gateway_reservation_input_schema()

        self.assertEqual(
            set(schema),
            {"type", "properties", "required"},
        )
        for definition in schema["properties"].values():
            self.assertLessEqual(
                set(definition),
                {"type", "description", "items"},
            )

    def test_response_reason_codes_cover_frozen_outcomes(self) -> None:
        self.assertEqual(
            {reason.value for reason in contracts.ReservationReason},
            {
                "max_guests_exceeded",
                "unknown_hotel",
                "invalid_dates",
                "unauthorized",
                "service_error",
            },
        )

    def test_response_contract_requires_common_correlation_fields(self) -> None:
        hints = get_type_hints(contracts.ReservationCommandResponse)

        self.assertEqual(
            contracts.ReservationCommandResponse.__required_keys__,
            {"status", "request_id", "hotel_id", "duplicate", "message"},
        )
        self.assertEqual(
            contracts.ReservationCommandResponse.__optional_keys__,
            {"reason_code", "max_guests", "created_at"},
        )
        self.assertIn("Literal", str(hints["status"]))


if __name__ == "__main__":
    unittest.main()
