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

The notebook adds the check this cannot make: an assertion against the `Rule`
node in a live graph, which is the only thing that catches a graph seeded by
an older version of this code.
"""

import ast
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


if __name__ == "__main__":
    unittest.main()
