#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Validate the workshop inventory against the runner, disk, and lab READMEs."""

from __future__ import annotations

import ast
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INVENTORY_PATH = REPO_ROOT / "workshop-inventory.json"
RUNNER_PATH = REPO_ROOT / "setup" / "run_notebooks.py"


def _path_parts(node: ast.expr) -> list[str]:
    """Read a ``REPO_ROOT / "folder" / "file"`` expression safely."""
    if isinstance(node, ast.Name) and node.id == "REPO_ROOT":
        return []
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        if not isinstance(node.right, ast.Constant) or not isinstance(
            node.right.value, str
        ):
            raise ValueError("runner paths must use string literals")
        return [*_path_parts(node.left), node.right.value]
    raise ValueError("runner paths must start at REPO_ROOT")


def load_runner_registry() -> list[tuple[str, str]]:
    """Parse the runner registry without importing its third-party packages."""
    tree = ast.parse(RUNNER_PATH.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "NOTEBOOKS"
            for target in node.targets
        ):
            continue
        if not isinstance(node.value, ast.Tuple):
            raise ValueError("NOTEBOOKS must be a tuple")
        registry = []
        for entry in node.value.elts:
            if not isinstance(entry, ast.Call) or len(entry.args) < 2:
                raise ValueError("NOTEBOOKS entries must call Notebook")
            lab = ast.literal_eval(entry.args[0])
            relative_path = str(Path(*_path_parts(entry.args[1])))
            registry.append((lab, relative_path))
        return registry
    raise ValueError("NOTEBOOKS registry not found")


def main() -> int:
    """Return zero when every inventory representation agrees."""
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    labs = inventory["labs"]
    problems: list[str] = []

    numbers = [lab["number"] for lab in labs]
    if numbers != [str(number) for number in range(7)]:
        problems.append(f"lab numbers must be 0 through 6 in order, found {numbers}")

    expected_registry: list[tuple[str, str]] = []
    all_notebooks: list[str] = []
    all_hero_questions: list[str] = []
    for lab in labs:
        folder = REPO_ROOT / lab["folder"]
        readme = folder / "README.md"
        if not folder.is_dir():
            problems.append(f"missing lab folder: {lab['folder']}")
            continue
        if not readme.is_file():
            problems.append(f"missing lab README: {readme.relative_to(REPO_ROOT)}")
            continue

        readme_text = readme.read_text(encoding="utf-8")
        if not isinstance(lab.get("optional"), bool):
            problems.append(f"lab {lab['number']} optional must be a boolean")
        if not lab.get("title") or not lab.get("topics"):
            problems.append(f"lab {lab['number']} needs a title and topics")

        inventory_files = [entry["file"] for entry in lab["notebooks"]]
        all_notebooks.extend(inventory_files)
        for filename in inventory_files:
            path = folder / filename
            if not path.is_file():
                relative_path = path.relative_to(REPO_ROOT)
                problems.append(f"inventory notebook is missing: {relative_path}")
            if filename not in readme_text:
                problems.append(
                    f"{readme.relative_to(REPO_ROOT)} does not name {filename}"
                )
            expected_registry.append((lab["number"], str(path.relative_to(REPO_ROOT))))

        for question in lab.get("hero_questions", []):
            if question not in all_hero_questions:
                all_hero_questions.append(question)
            question_forms = (
                question,
                question.replace(
                    "AnyCompany Cairo Nile View",
                    "{HERO_NAME}",
                ),
            )
            if inventory_files and not any(
                any(
                    form in (folder / filename).read_text(encoding="utf-8")
                    for form in question_forms
                )
                for filename in inventory_files
            ):
                problems.append(
                    f"lab {lab['number']} notebooks do not contain hero question: "
                    f"{question}"
                )

        shipping_on_disk = sorted(
            path.name for path in folder.glob(f"{lab['number']}.*_*.ipynb")
        )
        if sorted(inventory_files) != shipping_on_disk:
            problems.append(
                f"shipping notebooks in {lab['folder']} differ: "
                f"inventory={sorted(inventory_files)}, disk={shipping_on_disk}"
            )

    actual_registry = load_runner_registry()
    if expected_registry != actual_registry:
        problems.append(
            "runner registry differs from workshop-inventory.json: "
            f"expected={expected_registry}, actual={actual_registry}"
        )

    for target in inventory.get("documentation_targets", []):
        target_path = REPO_ROOT / target["file"]
        if not target_path.is_file():
            problems.append(f"missing documentation target: {target['file']}")
            continue
        target_text = target_path.read_text(encoding="utf-8")
        required = []
        if target.get("all_notebooks"):
            required.extend(all_notebooks)
        if target.get("all_hero_questions"):
            required.extend(all_hero_questions)
        missing = [value for value in required if value not in target_text]
        if missing:
            problems.append(
                f"{target['file']} is missing inventory values: {missing}"
            )

    if problems:
        print("Workshop inventory check failed:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print(
        f"Workshop inventory is consistent: {len(labs)} labs and "
        f"{len(expected_registry)} notebooks."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
