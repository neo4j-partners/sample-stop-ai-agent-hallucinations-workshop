# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Neo4j tool graph for semantic tool selection.

Stores each Strands tool as a ``:Tool`` node carrying its description and
description embedding, links tools to the ``:Concept`` nodes they require or
produce, groups tools into ``:Domain`` nodes, and serves two query shapes:

1. Vector search over ``tool_description_embeddings`` for candidate tools.
2. Workflow expansion from those candidates to the tools that consume what a
   candidate produces, or produce what a candidate requires.

Graph shape:
    (:Tool)-[:IN_DOMAIN]->(:Domain)
    (:Tool)-[:REQUIRES]->(:Concept)
    (:Tool)-[:PRODUCES]->(:Concept)

Every node written here carries the workshop ownership property so scoped
cleanup can remove the tool graph without touching the hotel domain graph.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Callable

from neo4j import Driver, GraphDatabase
from neo4j.exceptions import DriverError, Neo4jError

# Reuse the Demo 01 connection settings so the tool graph lands in the same
# Aura instance as the hotel knowledge graph.
_GRAPH_TOOLS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "01-graphrag-demo", "tools")
)
if _GRAPH_TOOLS_DIR not in sys.path:
    sys.path.append(_GRAPH_TOOLS_DIR)

TOOL_VECTOR_INDEX = "tool_description_embeddings"
EMBEDDING_DIMENSIONS = 1024
WORKSHOP_OWNER = "stop-ai-agent-hallucinations"

PREPARATION_HINT = (
    "Neo4j is required for Demo 02. Check the credentials in "
    "01-graphrag-demo/.env and prepare the graph with: "
    "uv run 01-graphrag-demo/prepare_graph.py"
)


@dataclass(frozen=True)
class ToolProfile:
    """Domain and workflow metadata for one tool."""

    domain: str
    requires: tuple[str, ...] = ()
    produces: tuple[str, ...] = ()


# Workflow metadata for every tool in enhanced_tools.ALL_TOOLS. A concept a
# tool PRODUCES that another tool REQUIRES is a workflow edge: booking flows
# into payment, payment into refund, availability into booking.
TOOL_PROFILES: dict[str, ToolProfile] = {
    # Hotel tools
    "search_real_hotels": ToolProfile("hotels", ("destination",), ("hotel",)),
    "get_top_hotels": ToolProfile("hotels", (), ("hotel",)),
    "search_hotels": ToolProfile("hotels", ("destination",), ("hotel",)),
    "search_hotel_reviews": ToolProfile("hotels", ("hotel",), ("hotel_reviews",)),
    "get_hotel_details": ToolProfile("hotels", ("hotel",), ("hotel_amenities",)),
    "get_hotel_pricing": ToolProfile("hotels", ("hotel",), ("price_quote",)),
    "check_hotel_availability": ToolProfile(
        "hotels", ("hotel", "dates"), ("hotel_availability",)
    ),
    "check_hotel_availability_dates": ToolProfile(
        "hotels", ("hotel", "dates"), ("hotel_availability", "price_quote")
    ),
    "book_hotel": ToolProfile(
        "hotels", ("hotel", "guest", "hotel_availability"), ("booking",)
    ),
    "compare_hotel_prices": ToolProfile(
        "hotels", ("destination", "dates"), ("price_quote",)
    ),
    # Flight tools
    "search_flights": ToolProfile("flights", ("destination",), ("flight",)),
    "search_flight_prices": ToolProfile("flights", ("destination",), ("price_quote",)),
    "get_flight_details": ToolProfile("flights", ("flight",), ("flight_details",)),
    "get_flight_status": ToolProfile("flights", ("flight",), ("flight_status",)),
    "check_flight_availability": ToolProfile(
        "flights", ("flight",), ("flight_availability",)
    ),
    "book_flight": ToolProfile(
        "flights", ("flight", "passenger", "flight_availability"), ("booking",)
    ),
    # Weather tools
    "get_weather": ToolProfile("weather", ("destination",), ("weather_report",)),
    "get_weather_forecast": ToolProfile(
        "weather", ("destination",), ("weather_forecast",)
    ),
    "get_weather_alerts": ToolProfile(
        "weather", ("destination",), ("weather_alerts",)
    ),
    # Payment tools
    "process_payment": ToolProfile("payments", ("booking",), ("payment",)),
    "check_payment": ToolProfile("payments", ("payment",), ("payment_status",)),
    "refund_payment": ToolProfile(
        "payments", ("payment", "cancellation"), ("refund",)
    ),
    # Travel utilities
    "get_currency_exchange": ToolProfile(
        "travel-utilities", ("currency_amount",), ("currency_conversion",)
    ),
    "get_travel_documents": ToolProfile(
        "travel-utilities", ("destination",), ("visa_requirements",)
    ),
    # Generic fallback tools
    "search": ToolProfile("generic", (), ("generic_results",)),
    "check": ToolProfile("generic", (), ("generic_status",)),
    "get_details": ToolProfile("generic", (), ("generic_details",)),
    "get_status": ToolProfile("generic", (), ("generic_status",)),
    "get_info": ToolProfile("generic", (), ("generic_details",)),
    "book": ToolProfile("generic", ("guest",), ("booking",)),
    "cancel": ToolProfile("generic", ("booking",), ("cancellation",)),
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


def build_tool_graph(
    tools: list[Callable],
    embed: Callable[[list[str]], list[list[float]]],
) -> None:
    """Write the tool graph idempotently and ensure the vector index is online.

    Re-running replaces each tool's metadata and relationships, removes tools
    that are no longer in the given list, and prunes orphaned concepts, so the
    graph always mirrors exactly the tools passed in.
    """
    missing = sorted(t.__name__ for t in tools if t.__name__ not in TOOL_PROFILES)
    if missing:
        raise ValueError(
            f"TOOL_PROFILES has no entry for: {', '.join(missing)}. "
            "Add domain and concept metadata for every tool before building "
            "the tool graph."
        )

    texts = [f"{t.__name__}: {t.__doc__}" for t in tools]
    embeddings = embed(texts)

    tool_rows = []
    requires_rows = []
    produces_rows = []
    for tool, embedding in zip(tools, embeddings):
        profile = TOOL_PROFILES[tool.__name__]
        tool_rows.append(
            {
                "name": tool.__name__,
                "description": tool.__doc__ or "",
                "embedding": list(embedding),
                "domain": profile.domain,
            }
        )
        requires_rows.extend(
            {"tool": tool.__name__, "concept": concept}
            for concept in profile.requires
        )
        produces_rows.extend(
            {"tool": tool.__name__, "concept": concept}
            for concept in profile.produces
        )

    driver = _get_driver()
    with driver.session() as session:
        session.run(
            """
            UNWIND $rows AS row
            MERGE (t:Tool {name: row.name})
            SET t.description = row.description,
                t.embedding = row.embedding,
                t.domain = row.domain,
                t.workshop = $owner
            MERGE (d:Domain {name: row.domain})
            SET d.workshop = $owner
            MERGE (t)-[:IN_DOMAIN]->(d)
            """,
            rows=tool_rows,
            owner=WORKSHOP_OWNER,
        ).consume()
        session.run(
            """
            MATCH (t:Tool {workshop: $owner})
            WHERE NOT t.name IN $names
            DETACH DELETE t
            """,
            names=[row["name"] for row in tool_rows],
            owner=WORKSHOP_OWNER,
        ).consume()
        session.run(
            """
            MATCH (t:Tool {workshop: $owner})-[r:REQUIRES|PRODUCES]->(:Concept)
            DELETE r
            """,
            owner=WORKSHOP_OWNER,
        ).consume()
        for rows, relationship in (
            (requires_rows, "REQUIRES"),
            (produces_rows, "PRODUCES"),
        ):
            session.run(
                f"""
                UNWIND $rows AS row
                MATCH (t:Tool {{name: row.tool}})
                MERGE (c:Concept {{name: row.concept}})
                SET c.workshop = $owner
                MERGE (t)-[:{relationship}]->(c)
                """,
                rows=rows,
                owner=WORKSHOP_OWNER,
            ).consume()
        session.run(
            """
            MATCH (c:Concept {workshop: $owner})
            WHERE NOT (c)<-[:REQUIRES|PRODUCES]-(:Tool)
            DELETE c
            """,
            owner=WORKSHOP_OWNER,
        ).consume()

    _ensure_tool_vector_index(driver)


def _ensure_tool_vector_index(driver: Driver) -> None:
    """Create the tool vector index idempotently and wait until it is online."""
    with driver.session() as session:
        session.run(
            f"""
            CREATE VECTOR INDEX {TOOL_VECTOR_INDEX} IF NOT EXISTS
            FOR (t:Tool) ON (t.embedding)
            OPTIONS {{indexConfig: {{
                `vector.dimensions`: {EMBEDDING_DIMENSIONS},
                `vector.similarity_function`: 'cosine'
            }}}}
            """
        ).consume()
        session.run(
            "CALL db.awaitIndexes($timeout_seconds)", timeout_seconds=300
        ).consume()
        record = session.run(
            """
            SHOW INDEXES YIELD name, state
            WHERE name = $name
            RETURN state
            """,
            name=TOOL_VECTOR_INDEX,
        ).single()
    if record is None or record["state"] != "ONLINE":
        state = "missing" if record is None else record["state"]
        raise RuntimeError(
            f"Vector index {TOOL_VECTOR_INDEX!r} is {state}, not ONLINE. "
            f"{PREPARATION_HINT}"
        )


def vector_search(query_embedding: list[float], top_k: int) -> list[dict]:
    """Return the top-k tools by cosine similarity to the query embedding."""
    driver = _get_driver()
    with driver.session() as session:
        records = session.run(
            """
            CALL db.index.vector.queryNodes($index, $top_k, $embedding)
            YIELD node, score
            RETURN node.name AS name, score
            ORDER BY score DESC
            """,
            index=TOOL_VECTOR_INDEX,
            top_k=top_k,
            embedding=query_embedding,
        )
        return [{"name": record["name"], "score": record["score"]} for record in records]


def expand_candidates(candidate_names: list[str]) -> list[dict]:
    """Return workflow-related tools reachable from the candidate tools.

    Downstream tools consume a concept a candidate produces; upstream tools
    produce a concept a candidate requires. Each row carries the relationship
    that caused the inclusion so the selection stays explainable.
    """
    driver = _get_driver()
    with driver.session() as session:
        records = session.run(
            """
            MATCH (seed:Tool)-[:PRODUCES]->(c:Concept)<-[:REQUIRES]-(next:Tool)
            WHERE seed.name IN $candidates AND NOT next.name IN $candidates
            RETURN DISTINCT next.name AS name, 'downstream' AS direction,
                   c.name AS concept, seed.name AS via
            UNION
            MATCH (seed:Tool)-[:REQUIRES]->(c:Concept)<-[:PRODUCES]-(prev:Tool)
            WHERE seed.name IN $candidates AND NOT prev.name IN $candidates
            RETURN DISTINCT prev.name AS name, 'upstream' AS direction,
                   c.name AS concept, seed.name AS via
            """,
            candidates=candidate_names,
        )
        expanded = []
        for record in records:
            if record["direction"] == "downstream":
                reason = (
                    f"consumes '{record['concept']}', which "
                    f"{record['via']} produces (next workflow step)"
                )
            else:
                reason = (
                    f"produces '{record['concept']}', which "
                    f"{record['via']} requires (prerequisite)"
                )
            expanded.append(
                {
                    "name": record["name"],
                    "direction": record["direction"],
                    "concept": record["concept"],
                    "via": record["via"],
                    "reason": reason,
                }
            )
        return expanded


def selection_report(query_embedding: list[float], top_k: int = 3) -> dict:
    """Return vector candidates with scores plus workflow-expanded tools.

    The candidates carry the similarity signal; the expanded tools carry the
    graph relationship that caused their inclusion.
    """
    candidates = vector_search(query_embedding, top_k)
    expanded = expand_candidates([candidate["name"] for candidate in candidates])
    for candidate in candidates:
        candidate["reason"] = f"vector similarity {candidate['score']:.3f} to the query"
    return {"candidates": candidates, "expanded": expanded}
