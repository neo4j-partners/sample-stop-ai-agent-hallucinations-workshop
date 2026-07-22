# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Graph-backed domain validation for the multi-agent demo.

`oracle.py` validates transactional figures against exact tool output. This
module grounds the other kind of claim: static domain facts such as whether a
hotel exists, whether it offers an amenity, and whether a guest rating is
stored. Those facts live in the Neo4j knowledge graph, and the validator gets
one read-only tool to look them up.

The demo's AnyCompany hotels are fictional, so they are seeded here as
workshop-owned ``:Hotel`` fixtures in the same Aura instance as the Demo 01
corpus. Every node this module writes carries the workshop ownership property
and is matched on it, so the real hotel corpus is never touched and scoped
cleanup can remove the fixtures cleanly.

Deliberately absent: a stored guest rating. No booking tool returns a rating
and the graph stores none, so any rating figure remains invention, and the
graph record says so explicitly.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Mapping

from neo4j import Driver, GraphDatabase
from neo4j.exceptions import DriverError, Neo4jError
from strands import tool

# Reuse the Demo 01 connection settings so the fixtures land in the same Aura
# instance as the hotel knowledge graph.
_GRAPH_TOOLS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "01-graphrag-demo", "tools")
)
if _GRAPH_TOOLS_DIR not in sys.path:
    sys.path.append(_GRAPH_TOOLS_DIR)

WORKSHOP_OWNER = "stop-ai-agent-hallucinations"

PREPARATION_HINT = (
    "Neo4j is required for the Demo 03 domain validator. Check the "
    "credentials in 01-graphrag-demo/.env and prepare the graph with: "
    "uv run 01-graphrag-demo/prepare_graph.py"
)

# The graph-side ground truth for the fictional AnyCompany properties. The
# amenity lists are deliberately small and contain no spa anywhere: the
# fabricated_amenity_fee scenario depends on the graph having no supporting
# relationship for a spa claim.
DOMAIN_FIXTURES: dict[str, dict[str, Any]] = {
    "anycompany_lisbon": {
        "name": "AnyCompany Lisbon Resort",
        "amenities": ("Outdoor Pool", "Free WiFi"),
    },
    "anycompany_paris": {
        "name": "AnyCompany Paris City Hotel",
        "amenities": ("Free WiFi", "Breakfast Buffet"),
    },
    "anycompany_rome": {
        "name": "AnyCompany Rome City Hotel",
        "amenities": ("Free WiFi",),
    },
    "anycompany_porto_partner": {
        "name": "AnyCompany Porto",
        "amenities": (),
    },
}

_driver: Driver | None = None


def _get_driver() -> Driver:
    """Return a cached driver, loading credentials and verifying on first use.

    The graph_tool import is deferred so importing this module never reads
    credentials; a missing password surfaces here with the preparation hint.
    """
    global _driver
    if _driver is None:
        # graph_tool's own find_dotenv falls back to the process working
        # directory inside a Jupyter kernel, so load the Demo 01 .env by
        # explicit path first. Existing environment variables win.
        from dotenv import load_dotenv

        load_dotenv(os.path.join(_GRAPH_TOOLS_DIR, "..", ".env"))
        try:
            from graph_tool import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USERNAME
        except RuntimeError as exc:
            raise RuntimeError(PREPARATION_HINT) from exc
        driver = GraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )
        try:
            driver.verify_connectivity()
        except (DriverError, Neo4jError, OSError) as exc:
            driver.close()
            raise RuntimeError(PREPARATION_HINT) from exc
        _driver = driver
    return _driver


def seed_domain_fixtures() -> None:
    """Write the AnyCompany domain fixtures idempotently.

    Matches and merges only on the workshop ownership property, so corpus
    hotels and amenities with similar names are never touched. Re-running
    replaces each fixture's amenity relationships in place.
    """
    rows = [
        {
            "hotel_id": hotel_id,
            "name": fixture["name"],
            "amenities": list(fixture["amenities"]),
        }
        for hotel_id, fixture in DOMAIN_FIXTURES.items()
    ]
    driver = _get_driver()
    with driver.session() as session:
        session.run(
            """
            UNWIND $rows AS row
            MERGE (h:Hotel {hotel_id: row.hotel_id, workshop: $owner})
            SET h.name = row.name
            """,
            rows=rows,
            owner=WORKSHOP_OWNER,
        ).consume()
        session.run(
            """
            MATCH (h:Hotel {workshop: $owner})-[r:OFFERS_AMENITY]->(:Amenity)
            DELETE r
            """,
            owner=WORKSHOP_OWNER,
        ).consume()
        session.run(
            """
            UNWIND $rows AS row
            MATCH (h:Hotel {hotel_id: row.hotel_id, workshop: $owner})
            UNWIND row.amenities AS amenity
            MERGE (a:Amenity {name: amenity, workshop: $owner})
            MERGE (h)-[:OFFERS_AMENITY]->(a)
            """,
            rows=rows,
            owner=WORKSHOP_OWNER,
        ).consume()
        session.run(
            """
            MATCH (a:Amenity {workshop: $owner})
            WHERE NOT (a)<-[:OFFERS_AMENITY]-(:Hotel)
            DELETE a
            """,
            owner=WORKSHOP_OWNER,
        ).consume()


def format_domain_record(query: str, record: Mapping[str, Any] | None) -> str:
    """Render one graph lookup result as validator-facing evidence text.

    Pure function so the wording, which the validator reasons over, can be
    unit tested without a database.
    """
    if record is None:
        known = ", ".join(sorted(DOMAIN_FIXTURES))
        return (
            f"NO SUPPORTING NODE: the knowledge graph contains no hotel "
            f"matching '{query}'. A claim about this hotel has no graph "
            f"support. Hotels in the graph: {known}."
        )
    amenities = record.get("amenities") or []
    amenity_text = (
        ", ".join(sorted(amenities))
        if amenities
        else "NONE recorded in the graph"
    )
    return (
        f"Hotel {record['hotel_id']} ({record['name']}) exists in the "
        f"knowledge graph. OFFERS_AMENITY: {amenity_text}. An amenity not in "
        f"this list has no supporting relationship in the graph. "
        f"guest_rating: NOT STORED, so any rating figure is unsupported."
    )


def _lookup_hotel(query: str) -> Mapping[str, Any] | None:
    """Fetch one workshop-owned hotel by id or name fragment."""
    driver = _get_driver()
    with driver.session() as session:
        record = session.run(
            """
            MATCH (h:Hotel {workshop: $owner})
            WHERE h.hotel_id = $lookup
               OR toLower(h.name) CONTAINS toLower($lookup)
            OPTIONAL MATCH (h)-[:OFFERS_AMENITY]->(a:Amenity)
            RETURN h.hotel_id AS hotel_id, h.name AS name,
                   collect(a.name) AS amenities
            LIMIT 1
            """,
            lookup=query,
            owner=WORKSHOP_OWNER,
        ).single()
    return record.data() if record is not None else None


@tool
def get_hotel_domain_record(hotel: str) -> str:
    """Look up a hotel in the knowledge graph by id or name. Returns whether the hotel exists, the exact amenities it offers, and whether a guest rating is stored. Use this to verify static domain claims: a hotel's existence, an amenity, or a rating. Read-only.

    Args:
        hotel: Hotel id (for example anycompany_lisbon) or hotel name.
    """
    return format_domain_record(hotel, _lookup_hotel(hotel))
