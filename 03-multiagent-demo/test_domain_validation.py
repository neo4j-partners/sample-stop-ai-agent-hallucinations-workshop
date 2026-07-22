# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Unit tests for the graph-backed domain evidence wording. No database calls.

The validator reasons over the exact text `format_domain_record` produces, so
its wording is pinned against fixed inputs here, the same way `test_oracle.py`
pins the figure scorer. The Cypher lookup itself is exercised by the live demo
run, not here.

Run with:  uv run --python 3.12 python test_domain_validation.py
       or:  uv run --with pytest pytest test_domain_validation.py
"""
import unittest

from domain_validation import DOMAIN_FIXTURES, format_domain_record


class TestMissingHotel(unittest.TestCase):
    def test_states_no_supporting_node(self) -> None:
        text = format_domain_record("anycompany_barcelona", None)
        self.assertIn("NO SUPPORTING NODE", text)
        self.assertIn("anycompany_barcelona", text)

    def test_lists_the_hotels_that_do_exist(self) -> None:
        text = format_domain_record("anycompany_barcelona", None)
        for hotel_id in DOMAIN_FIXTURES:
            self.assertIn(hotel_id, text)


class TestExistingHotel(unittest.TestCase):
    def test_reports_identity_and_amenities(self) -> None:
        record = {
            "hotel_id": "anycompany_lisbon",
            "name": "AnyCompany Lisbon Resort",
            "amenities": ["Outdoor Pool", "Free WiFi"],
        }
        text = format_domain_record("anycompany_lisbon", record)
        self.assertIn("anycompany_lisbon", text)
        self.assertIn("AnyCompany Lisbon Resort", text)
        self.assertIn("Free WiFi, Outdoor Pool", text)

    def test_states_that_an_unlisted_amenity_is_unsupported(self) -> None:
        record = {
            "hotel_id": "anycompany_lisbon",
            "name": "AnyCompany Lisbon Resort",
            "amenities": ["Outdoor Pool"],
        }
        text = format_domain_record("anycompany_lisbon", record)
        self.assertIn("no supporting relationship", text)
        self.assertNotIn("spa", text.lower())

    def test_empty_amenity_list_is_explicit(self) -> None:
        record = {
            "hotel_id": "anycompany_porto_partner",
            "name": "AnyCompany Porto",
            "amenities": [],
        }
        text = format_domain_record("anycompany_porto_partner", record)
        self.assertIn("NONE recorded in the graph", text)

    def test_rating_is_always_reported_as_not_stored(self) -> None:
        record = {
            "hotel_id": "anycompany_lisbon",
            "name": "AnyCompany Lisbon Resort",
            "amenities": ["Outdoor Pool"],
        }
        text = format_domain_record("anycompany_lisbon", record)
        self.assertIn("guest_rating: NOT STORED", text)


class TestFixtureInvariants(unittest.TestCase):
    def test_no_fixture_offers_a_spa(self) -> None:
        """fabricated_amenity_fee depends on no seeded hotel having a spa."""
        for hotel_id, fixture in DOMAIN_FIXTURES.items():
            joined = " ".join(fixture["amenities"]).lower()
            self.assertNotIn("spa", joined, f"{hotel_id} must not offer a spa")

    def test_every_booking_hotel_has_a_fixture(self) -> None:
        """Each hotel the booking tools know must exist in the graph fixtures."""
        from tools import HOTELS, PARTNER_PROPERTIES

        for hotel_id in list(HOTELS) + list(PARTNER_PROPERTIES):
            self.assertIn(hotel_id, DOMAIN_FIXTURES)


if __name__ == "__main__":
    unittest.main()
