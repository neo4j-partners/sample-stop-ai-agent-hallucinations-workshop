# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Focused offline tests for the Demo 06 reservation command."""

import importlib.util
import json
import os
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from neo4j.exceptions import AuthError, ConstraintError, ServiceUnavailable

import contracts
import reservation_command

REQUEST_ID = "1f90b477-12a4-4654-8321-c3db6af26d4e"
HOTEL_ID = "81393d51-1df3-4f53-b58e-e4cda9736fd7"
TODAY = date(2026, 7, 21)


class FakeResult:
    def __init__(self, record):
        self.record = record

    def single(self):
        return self.record


class FakeTransaction:
    def __init__(self, *, existing=None, targets=None, created=None):
        self.existing = existing
        self.targets = targets
        self.created = created
        self.calls = []

    def run(self, query, **parameters):
        self.calls.append((query, parameters))
        if query == reservation_command.READ_EXISTING_QUERY:
            return FakeResult(self.existing)
        if query == reservation_command.READ_TARGETS_QUERY:
            return FakeResult(self.targets)
        if query == reservation_command.CREATE_REQUEST_QUERY:
            return FakeResult(self.created)
        raise AssertionError(f"Unexpected Cypher: {query}")


class FakeSession:
    def __init__(self, driver):
        self.driver = driver

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute_write(self, callback, *arguments):
        if self.driver.write_error is not None:
            raise self.driver.write_error
        return callback(self.driver.write_transaction, *arguments)

    def execute_read(self, callback, command):
        if self.driver.read_error is not None:
            raise self.driver.read_error
        return callback(self.driver.read_transaction, command)


class FakeDriver:
    def __init__(
        self,
        *,
        write_transaction=None,
        read_transaction=None,
        write_error=None,
        read_error=None,
    ):
        self.write_transaction = write_transaction or FakeTransaction()
        self.read_transaction = read_transaction or FakeTransaction()
        self.write_error = write_error
        self.read_error = read_error
        self.databases = []

    def session(self, *, database):
        self.databases.append(database)
        return FakeSession(self)


def command(*, guests=2, **changes):
    payload = {
        "request_id": REQUEST_ID,
        "hotel_id": HOTEL_ID,
        "check_in": "2026-08-20",
        "check_out": "2026-08-23",
        "guests": guests,
    }
    payload.update(changes)
    return payload


def ready_targets():
    return {
        "rule_count": 1,
        "max_guests": contracts.MAX_GUESTS,
        "rejection_message": "Reservation requests are limited to 10 guests.",
        "hotel_count": 1,
        "hotel_id": HOTEL_ID,
    }


class ReservationCommandTests(unittest.TestCase):
    def test_gateway_and_body_event_envelopes_extract_command(self):
        payload = command()

        self.assertEqual(
            reservation_command._extract_payload({"parameters": payload}),
            payload,
        )
        self.assertEqual(
            reservation_command._extract_payload({"body": payload}),
            payload,
        )
        self.assertEqual(
            reservation_command._extract_payload(
                {"body": json.dumps(payload)}
            ),
            payload,
        )

    def test_lambda_handler_executes_gateway_command_envelope(self):
        payload = command(
            check_in="2099-08-20",
            check_out="2099-08-23",
        )
        transaction = FakeTransaction(
            targets=ready_targets(),
            created={
                "request_id": REQUEST_ID,
                "hotel_id": HOTEL_ID,
                "created_at": "2026-07-21T12:34:56Z",
            },
        )
        driver = FakeDriver(write_transaction=transaction)
        config = reservation_command.Neo4jCommandConfig(
            uri="neo4j+s://example.test",
            username="command",
            password="secret",
            database="neo4j",
        )

        with (
            patch.dict(
                os.environ,
                {contracts.COMMAND_SECRET_ID_ENV: "demo/command"},
                clear=True,
            ),
            patch.object(
                reservation_command.Neo4jCommandConfig,
                "from_secret",
                return_value=config,
            ) as from_secret,
            patch.object(
                reservation_command,
                "_get_driver",
                return_value=driver,
            ),
        ):
            response = reservation_command.handler(
                {"parameters": payload},
                None,
            )

        self.assertEqual(response["status"], "accepted")
        from_secret.assert_called_once_with("demo/command")

    def test_lambda_handler_rejects_malformed_body(self):
        response = reservation_command.handler({"body": "not-json"}, None)

        self.assertEqual(response["status"], "error")
        self.assertEqual(response["reason_code"], "service_error")

    def test_configuration_failure_logs_only_safe_correlation_id(self):
        with (
            patch.dict(
                os.environ,
                {contracts.COMMAND_SECRET_ID_ENV: "demo/command"},
                clear=True,
            ),
            patch.object(
                reservation_command.Neo4jCommandConfig,
                "from_secret",
                side_effect=ValueError("password=do-not-log"),
            ),
            self.assertLogs(reservation_command.LOGGER, level="ERROR") as logs,
        ):
            response = reservation_command.handler(
                {
                    "parameters": command(
                        request_id="bad\npassword=also-do-not-log"
                    )
                },
                None,
            )

        self.assertEqual(response["status"], "error")
        rendered = " ".join(logs.output)
        self.assertIn("request_id=invalid", rendered)
        self.assertNotIn("do-not-log", rendered)

    def test_packaged_lambda_entrypoint_resolves_shared_handler(self):
        path = (
            Path(__file__).parent
            / "deployment-deferred"
            / "lambda_tools"
            / "create_reservation_request"
            / "lambda_function.py"
        )
        spec = importlib.util.spec_from_file_location(
            "demo06_reservation_lambda",
            path,
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.assertIs(module.handler, reservation_command.handler)

    def test_log_correlation_id_never_returns_untrusted_text(self):
        self.assertEqual(
            reservation_command._safe_correlation_id(
                {"request_id": f"{REQUEST_ID}\npassword=secret"}
            ),
            "invalid",
        )
        self.assertEqual(
            reservation_command._safe_correlation_id(
                {"request_id": REQUEST_ID}
            ),
            REQUEST_ID,
        )

    def test_valid_request_creates_one_request_and_relationship(self):
        transaction = FakeTransaction(
            targets=ready_targets(),
            created={
                "request_id": REQUEST_ID,
                "hotel_id": HOTEL_ID,
                "created_at": "2026-07-21T12:34:56Z",
            },
        )
        driver = FakeDriver(write_transaction=transaction)

        response = reservation_command.create_reservation_request(
            command(),
            driver=driver,
            database="neo4j",
            today=TODAY,
        )

        self.assertEqual(response["status"], "accepted")
        self.assertFalse(response["duplicate"])
        self.assertEqual(response["created_at"], "2026-07-21T12:34:56Z")
        self.assertEqual(driver.databases, ["neo4j"])
        self.assertEqual(
            [query for query, _ in transaction.calls],
            [
                reservation_command.READ_EXISTING_QUERY,
                reservation_command.READ_TARGETS_QUERY,
                reservation_command.CREATE_REQUEST_QUERY,
            ],
        )
        write_parameters = transaction.calls[-1][1]
        self.assertEqual(write_parameters["workshop_owner"], contracts.WORKSHOP_OWNER)
        self.assertNotIn("actor_id", write_parameters)

    def test_malformed_dates_are_rejected_without_opening_a_session(self):
        driver = FakeDriver()

        for payload in (
            command(check_in="07/20/2026"),
            command(check_in="20260820"),
            command(check_in="2026-W34-4"),
            command(check_in="2026-08-20", check_out="2026-08-20"),
        ):
            with self.subTest(payload=payload):
                response = reservation_command.create_reservation_request(
                    payload,
                    driver=driver,
                    database="neo4j",
                    today=TODAY,
                )
                self.assertEqual(response["status"], "rejected")
                self.assertEqual(response["reason_code"], "invalid_dates")

        self.assertEqual(driver.databases, [])

    def test_new_past_request_is_rejected_after_idempotency_read(self):
        transaction = FakeTransaction()
        driver = FakeDriver(write_transaction=transaction)

        response = reservation_command.create_reservation_request(
            command(check_in="2026-07-20", check_out="2026-07-22"),
            driver=driver,
            database="neo4j",
            today=TODAY,
        )

        self.assertEqual(response["status"], "rejected")
        self.assertEqual(response["reason_code"], "invalid_dates")
        self.assertEqual(
            [query for query, _ in transaction.calls],
            [reservation_command.READ_EXISTING_QUERY],
        )

    def test_duplicate_returns_existing_hotel_without_writing(self):
        existing_hotel_id = "0d82c2e5-9db8-49a5-8c22-7d8ec209453a"
        transaction = FakeTransaction(
            existing={
                "workshop_owner": contracts.WORKSHOP_OWNER,
                "status": "accepted",
                "check_in": "2026-08-20",
                "check_out": "2026-08-23",
                "guests": 2,
                "created_at": "2026-07-21T12:34:56Z",
                "relationship_count": 1,
                "hotel_ids": [existing_hotel_id],
            }
        )
        driver = FakeDriver(write_transaction=transaction)

        response = reservation_command.create_reservation_request(
            command(hotel_id=existing_hotel_id),
            driver=driver,
            database="neo4j",
            today=TODAY,
        )

        self.assertEqual(response["status"], "accepted")
        self.assertTrue(response["duplicate"])
        self.assertEqual(response["hotel_id"], existing_hotel_id)
        self.assertEqual(response["created_at"], "2026-07-21T12:34:56Z")
        self.assertEqual(len(transaction.calls), 1)

    def test_exact_duplicate_remains_idempotent_after_check_in(self):
        transaction = FakeTransaction(
            existing={
                "workshop_owner": contracts.WORKSHOP_OWNER,
                "status": "accepted",
                "check_in": "2026-08-20",
                "check_out": "2026-08-23",
                "guests": 2,
                "created_at": "2026-07-21T12:34:56Z",
                "relationship_count": 1,
                "hotel_ids": [HOTEL_ID],
            }
        )
        driver = FakeDriver(write_transaction=transaction)

        response = reservation_command.create_reservation_request(
            command(),
            driver=driver,
            database="neo4j",
            today=date(2026, 8, 21),
        )

        self.assertEqual(response["status"], "accepted")
        self.assertTrue(response["duplicate"])
        self.assertEqual(len(transaction.calls), 1)

    def test_noncanonical_uuid_is_rejected_before_database_access(self):
        driver = FakeDriver()

        response = reservation_command.create_reservation_request(
            command(request_id=REQUEST_ID.upper()),
            driver=driver,
            database="neo4j",
            today=TODAY,
        )

        self.assertEqual(response["status"], "error")
        self.assertEqual(response["reason_code"], "service_error")
        self.assertEqual(driver.databases, [])

    def test_conflicting_duplicate_returns_service_error_without_write(self):
        transaction = FakeTransaction(
            existing={
                "workshop_owner": contracts.WORKSHOP_OWNER,
                "status": "accepted",
                "check_in": "2026-08-20",
                "check_out": "2026-08-23",
                "guests": 3,
                "created_at": "2026-07-21T12:34:56Z",
                "relationship_count": 1,
                "hotel_ids": [HOTEL_ID],
            }
        )
        driver = FakeDriver(write_transaction=transaction)

        response = reservation_command.create_reservation_request(
            command(guests=2),
            driver=driver,
            database="neo4j",
            today=TODAY,
        )

        self.assertEqual(response["status"], "error")
        self.assertEqual(response["reason_code"], "service_error")
        self.assertIn("already used", response["message"])
        self.assertEqual(len(transaction.calls), 1)

    def test_unknown_hotel_is_rejected_without_writing(self):
        targets = ready_targets() | {"hotel_count": 0, "hotel_id": None}
        transaction = FakeTransaction(targets=targets)
        driver = FakeDriver(write_transaction=transaction)

        response = reservation_command.create_reservation_request(
            command(),
            driver=driver,
            database="neo4j",
            today=TODAY,
        )

        self.assertEqual(response["status"], "rejected")
        self.assertEqual(response["reason_code"], "unknown_hotel")
        self.assertNotIn(
            reservation_command.CREATE_REQUEST_QUERY,
            [query for query, _ in transaction.calls],
        )

    def test_missing_or_duplicate_enabled_rule_fails_without_write(self):
        for rule_count in (0, 2):
            with self.subTest(rule_count=rule_count):
                targets = ready_targets() | {"rule_count": rule_count}
                transaction = FakeTransaction(targets=targets)
                driver = FakeDriver(write_transaction=transaction)

                response = reservation_command.create_reservation_request(
                    command(),
                    driver=driver,
                    database="neo4j",
                    today=TODAY,
                )

                self.assertEqual(response["status"], "error")
                self.assertEqual(response["reason_code"], "service_error")
                self.assertNotIn(
                    reservation_command.CREATE_REQUEST_QUERY,
                    [query for query, _ in transaction.calls],
                )

    def test_invalid_rule_values_fail_closed_without_write(self):
        invalid_targets = (
            ready_targets() | {"max_guests": 0},
            ready_targets() | {"max_guests": -1},
            ready_targets() | {"max_guests": True},
            ready_targets() | {"max_guests": "10"},
            ready_targets() | {"rejection_message": ""},
            ready_targets() | {"rejection_message": 10},
        )
        for targets in invalid_targets:
            with self.subTest(targets=targets):
                transaction = FakeTransaction(targets=targets)
                driver = FakeDriver(write_transaction=transaction)

                response = reservation_command.create_reservation_request(
                    command(),
                    driver=driver,
                    database="neo4j",
                    today=TODAY,
                )

                self.assertEqual(response["status"], "error")
                self.assertEqual(response["reason_code"], "service_error")
                self.assertNotIn(
                    reservation_command.CREATE_REQUEST_QUERY,
                    [query for query, _ in transaction.calls],
                )

    def test_over_limit_request_is_rejected_before_write(self):
        transaction = FakeTransaction(targets=ready_targets())
        driver = FakeDriver(write_transaction=transaction)

        response = reservation_command.create_reservation_request(
            command(guests=contracts.OVER_LIMIT_GUESTS),
            driver=driver,
            database="neo4j",
            today=TODAY,
        )

        self.assertEqual(response["status"], "rejected")
        self.assertEqual(response["reason_code"], "max_guests_exceeded")
        self.assertEqual(response["max_guests"], contracts.MAX_GUESTS)
        self.assertNotIn(
            reservation_command.CREATE_REQUEST_QUERY,
            [query for query, _ in transaction.calls],
        )

    def test_unauthorized_database_error_has_stable_response(self):
        driver = FakeDriver(write_error=AuthError("credentials rejected"))

        response = reservation_command.create_reservation_request(
            command(),
            driver=driver,
            database="neo4j",
            today=TODAY,
        )

        self.assertEqual(response["status"], "error")
        self.assertEqual(response["reason_code"], "unauthorized")
        self.assertNotIn("credentials", response["message"])

    def test_service_failure_has_stable_response(self):
        driver = FakeDriver(write_error=ServiceUnavailable("bolt unavailable"))

        response = reservation_command.create_reservation_request(
            command(),
            driver=driver,
            database="neo4j",
            today=TODAY,
        )

        self.assertEqual(response["status"], "error")
        self.assertEqual(response["reason_code"], "service_error")
        self.assertNotIn("bolt", response["message"])

    def test_concurrent_retry_reads_winner_without_second_write(self):
        winner = FakeTransaction(
            existing={
                "workshop_owner": contracts.WORKSHOP_OWNER,
                "status": "accepted",
                "check_in": "2026-08-20",
                "check_out": "2026-08-23",
                "guests": 2,
                "created_at": "2026-07-21T12:34:56Z",
                "relationship_count": 1,
                "hotel_ids": [HOTEL_ID],
            }
        )
        driver = FakeDriver(
            write_error=ConstraintError("request_id already exists"),
            read_transaction=winner,
        )

        response = reservation_command.create_reservation_request(
            command(),
            driver=driver,
            database="neo4j",
            today=TODAY,
        )

        self.assertEqual(response["status"], "accepted")
        self.assertTrue(response["duplicate"])
        self.assertEqual(driver.databases, ["neo4j", "neo4j"])
        self.assertEqual(len(winner.calls), 1)

    def test_cypher_cannot_modify_canonical_hotel_data(self):
        normalized = " ".join(reservation_command.CREATE_REQUEST_QUERY.split())

        self.assertIn("MATCH (hotel:Hotel {hotel_id: $hotel_id})", normalized)
        self.assertIn("WHERE hotel.demo6_fixture = true", normalized)
        self.assertIn("CREATE (request)-[:FOR_HOTEL]->(hotel)", normalized)
        self.assertIn("status: 'accepted'", normalized)
        self.assertIn("created_at: datetime()", normalized)
        self.assertNotIn("SET hotel", normalized)
        self.assertNotIn("DELETE", normalized)
        self.assertNotIn("actor", normalized.casefold())

    def test_command_secret_has_the_frozen_shape(self):
        secret = {
            "uri": "neo4j+s://example.databases.neo4j.io",
            "username": "demo06-command",
            "password": "secret",
            "database": "neo4j",
        }

        class SecretsClient:
            def get_secret_value(self, *, SecretId):
                self.secret_id = SecretId
                return {"SecretString": json.dumps(secret)}

        client = SecretsClient()
        config = reservation_command.Neo4jCommandConfig.from_secret(
            "demo06/command",
            secrets_client=client,
        )

        self.assertEqual(client.secret_id, "demo06/command")
        self.assertEqual(config.username, "demo06-command")


if __name__ == "__main__":
    unittest.main()
