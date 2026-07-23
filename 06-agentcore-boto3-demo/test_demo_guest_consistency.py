# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Prove the shared guest-limit scenario without coupling demo outcomes."""

import ast
import importlib.util
import unittest
from pathlib import Path

import contracts

ROOT = Path(__file__).resolve().parent.parent


def _load_demo04_rules():
    path = ROOT / "04-neurosymbolic-demo" / "rules.py"
    spec = importlib.util.spec_from_file_location("demo04_rules", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assignment(path: Path, name: str) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, int):
                return node.value.value
    raise AssertionError(f"Integer assignment {name} not found in {path}")


class CrossDemoGuestConsistencyTests(unittest.TestCase):
    def test_demos_share_limit_and_over_limit_scenario(self):
        demo04_rules = _load_demo04_rules()
        demo04_scenarios = (
            ROOT / "04-neurosymbolic-demo" / "demo_neurosymbolic_hooks.py"
        ).read_text(encoding="utf-8")
        demo05_path = ROOT / "05-steering-demo" / "demo_hooks_vs_control.py"

        self.assertTrue(demo04_rules.max_guests_check({"guests": 10}))
        self.assertFalse(demo04_rules.max_guests_check({"guests": 11}))
        self.assertIn("for 15 people", demo04_scenarios)

        self.assertEqual(_assignment(demo05_path, "GUESTS"), 15)
        demo05_source = demo05_path.read_text(encoding="utf-8")
        self.assertIn("if guests > 10:", demo05_source)

        self.assertEqual(contracts.MAX_GUESTS, 10)
        self.assertEqual(contracts.OVER_LIMIT_GUESTS, 15)

        # Outcomes intentionally differ: Demo 04 blocks, Demo 05 can steer,
        # and Demo 06 returns a visible policy rejection. This test couples
        # only their common policy input and threshold.


if __name__ == "__main__":
    unittest.main()
