# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Prove the guest limit has exactly one source of truth.

`contracts.MAX_GUESTS` is the limit the reservation command enforces, the
rule the graph is seeded with, and the rule the readiness check validates
against. Those three must agree, and the way they agree is that
`graph_setup.py` refers to the constant instead of repeating the number.
A literal `10` in the seeding call would pass every other test in this lab
and still leave a participant's graph disagreeing with the command.

This reads the source rather than the running module because a literal and a
constant reference evaluate to the same `10` at runtime. Only the source
distinguishes them, and only the source drifts.

Source agreement is not the whole story, though: a participant whose graph was
seeded by an older version of this code has a `Rule` node the source can say
nothing about. `SeededRuleTests` makes that check against a live graph, and
skips when there is no graph to check.
"""

import ast
import os
import unittest
from pathlib import Path

from workshop import contracts, graph_setup

# Located through the imported module rather than by a relative path, so this
# keeps working wherever the shared package is installed from.
GRAPH_SETUP = Path(graph_setup.__file__).resolve()

CONTRACT_REFERENCE = "contracts.MAX_GUESTS"


def _max_guests_bindings(source: str, filename: str) -> list[ast.expr]:
    """Return every expression bound to a `max_guests` name in `source`.

    Covers both spellings `graph_setup.py` uses: the `max_guests=` keyword
    argument on the rule-seeding query, and the `"max_guests"` key of the
    expected-value mapping the readiness check compares against.
    """
    bindings: list[ast.expr] = []
    for node in ast.walk(ast.parse(source, filename=filename)):
        if isinstance(node, ast.Call):
            bindings.extend(
                keyword.value
                for keyword in node.keywords
                if keyword.arg == "max_guests"
            )
        elif isinstance(node, ast.Dict):
            bindings.extend(
                value
                for key, value in zip(node.keys, node.values)
                if isinstance(key, ast.Constant) and key.value == "max_guests"
            )
    return bindings


class GuestLimitConsistencyTests(unittest.TestCase):
    def test_over_limit_scenario_exceeds_the_limit(self):
        self.assertEqual(contracts.MAX_GUESTS, 10)
        self.assertEqual(contracts.OVER_LIMIT_GUESTS, 15)
        self.assertGreater(contracts.OVER_LIMIT_GUESTS, contracts.MAX_GUESTS)

    def test_graph_setup_seeds_the_rule_from_the_contract(self):
        source = GRAPH_SETUP.read_text(encoding="utf-8")
        bindings = _max_guests_bindings(source, str(GRAPH_SETUP))

        self.assertTrue(
            bindings,
            f"No max_guests binding found in {GRAPH_SETUP.name}. The rule is "
            "either no longer seeded or is spelled a third way.",
        )
        for binding in bindings:
            self.assertEqual(
                ast.unparse(binding),
                CONTRACT_REFERENCE,
                f"{GRAPH_SETUP.name} line {binding.lineno} binds max_guests to "
                f"{ast.unparse(binding)!r} instead of {CONTRACT_REFERENCE}. A "
                "literal here lets the seeded rule drift from the limit the "
                "reservation command enforces.",
            )


class SeededRuleTests(unittest.TestCase):
    """The `Rule` node in a live graph must carry the contract's limit.

    This is the failure the source check cannot see. A graph seeded before the
    limit last changed keeps the old `max_guests`, and the command reads the
    graph, so the participant's rejection threshold silently stops matching the
    constant every other test agrees on.

    Skips without Neo4j credentials, which is how the offline suite stays green.
    """

    def setUp(self) -> None:
        # Participants keep their credentials in the repo-root `.env` rather
        # than exported, so without this the test would skip on every machine
        # that actually has a graph to check.
        from dotenv import load_dotenv

        load_dotenv()
        if not all(
            os.getenv(name)
            for name in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD")
        ):
            self.skipTest("Neo4j is not configured")

    def test_seeded_rule_matches_the_contract(self) -> None:
        from neo4j import GraphDatabase

        from workshop.hybrid_retrieval import Neo4jConfig

        config = Neo4jConfig.from_environment()
        with GraphDatabase.driver(
            config.uri, auth=(config.username, config.password)
        ) as driver:
            with driver.session(database=config.database) as session:
                record = session.run(
                    graph_setup.RULE_QUERY,
                    rule_id=contracts.MAX_GUESTS_RULE_ID,
                ).single()

        self.assertEqual(
            record["rule_count"],
            1,
            f"Expected exactly one {contracts.MAX_GUESTS_RULE_ID} rule node. "
            "Run 01-graph-build/1.1_build_graph.ipynb to seed it.",
        )
        self.assertEqual(
            record["max_guests"],
            contracts.MAX_GUESTS,
            f"The seeded rule allows {record['max_guests']} guests but "
            f"contracts.MAX_GUESTS is {contracts.MAX_GUESTS}. The graph is what "
            "the reservation command reads, so it is the one that wins; re-seed "
            "it rather than changing the constant to match.",
        )
        self.assertTrue(
            record["enabled"],
            "The seeded rule is disabled, so the command would accept an "
            "over-limit request.",
        )


if __name__ == "__main__":
    unittest.main()
