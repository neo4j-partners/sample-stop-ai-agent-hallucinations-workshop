# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Regression guards for the workshop teardown.

The headline test is :meth:`TestTagScoping.test_untagged_unrelated_roles_are_never_selected`,
which pins bug B6: teardown once deleted IAM roles by account-wide name prefix
and destroyed five unrelated ``AmazonBedrockAgentCoreSDKCodeBuild*`` roles, two
of them in a different region. The fixture below reproduces that exact account
shape and asserts none of those roles is selected.

Run with::

    python -m unittest discover -s 08-cleanup -v
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from typing import Any

from botocore.exceptions import ClientError

import workshop_cleanup as wc

TAG = {wc.WORKSHOP_TAG_KEY: wc.WORKSHOP_TAG_VALUE}
TAG_KV = [{"Key": wc.WORKSHOP_TAG_KEY, "Value": wc.WORKSHOP_TAG_VALUE}]

#: Roles that actually existed in the account when B6 fired. None was created by
#: this workshop; two are in a different region entirely. All are untagged.
COLLATERAL_ROLES = [
    "AmazonBedrockAgentCoreSDKCodeBuild-us-east-1-2660eddb3d",
    "AmazonBedrockAgentCoreSDKCodeBuild-us-east-1-3dce273434",
    "AmazonBedrockAgentCoreSDKCodeBuild-us-east-1-c423c61358",
    "AmazonBedrockAgentCoreSDKCodeBuild-us-west-2-7e178ca98a",
    "AmazonBedrockAgentCoreSDKCodeBuild-us-west-2-8556fc4504",
    # Pre-existing, verified live, shares the "workshop" name stem.
    "workshop-studio-execution-role",
]


def not_found(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, "Fake")


class Recorder:
    """Collects every mutating call so tests can assert nothing was deleted."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def record(self, name: str, **kwargs: Any) -> None:
        self.calls.append((name, kwargs))

    @property
    def names(self) -> list[str]:
        return [name for name, _ in self.calls]


class FakeIam:
    def __init__(self, roles: dict[str, dict[str, str]], recorder: Recorder) -> None:
        # role name -> tags
        self.roles = roles
        self.rec = recorder

    def get_paginator(self, _op: str) -> FakeIam:
        return self

    def paginate(self) -> list[dict[str, Any]]:
        return [
            {
                "Roles": [
                    {"RoleName": name, "Arn": f"arn:aws:iam::123456789012:role/{name}"}
                    for name in self.roles
                ]
            }
        ]

    def list_role_tags(self, RoleName: str) -> dict[str, Any]:
        return {"Tags": [{"Key": k, "Value": v} for k, v in self.roles[RoleName].items()]}

    def get_role(self, RoleName: str) -> dict[str, Any]:
        if RoleName not in self.roles:
            raise not_found("NoSuchEntity")
        return {"Role": {"RoleName": RoleName}}

    def list_attached_role_policies(self, RoleName: str) -> dict[str, Any]:
        return {"AttachedPolicies": []}

    def list_role_policies(self, RoleName: str) -> dict[str, Any]:
        return {"PolicyNames": []}

    def detach_role_policy(self, **kwargs: Any) -> None:
        self.rec.record("detach_role_policy", **kwargs)

    def delete_role_policy(self, **kwargs: Any) -> None:
        self.rec.record("delete_role_policy", **kwargs)

    def delete_role(self, **kwargs: Any) -> None:
        self.rec.record("delete_role", **kwargs)


class FakeAgentCore:
    def __init__(
        self,
        recorder: Recorder,
        memories: list[dict[str, Any]] | None = None,
        tags_by_arn: dict[str, dict[str, str]] | None = None,
        delete_memory_error: Exception | None = None,
    ) -> None:
        self.rec = recorder
        self.memories = memories or []
        self.tags_by_arn = tags_by_arn or {}
        self.delete_memory_error = delete_memory_error

    def list_memories(self) -> dict[str, Any]:
        return {"memories": self.memories}

    def list_agent_runtimes(self) -> dict[str, Any]:
        return {"agentRuntimes": []}

    def list_gateways(self) -> dict[str, Any]:
        return {"items": []}

    def list_tags_for_resource(self, resourceArn: str) -> dict[str, Any]:
        return {"tags": self.tags_by_arn.get(resourceArn, {})}

    def delete_memory(self, **kwargs: Any) -> None:
        self.rec.record("delete_memory", **kwargs)
        if self.delete_memory_error is not None:
            raise self.delete_memory_error


class FakeEmpty:
    """Every lookup reports 'absent'; every mutation is recorded."""

    def __init__(self, recorder: Recorder) -> None:
        self.rec = recorder

    def get_function(self, **_kw: Any) -> dict[str, Any]:
        raise not_found("ResourceNotFoundException")

    def list_layer_versions(self, **_kw: Any) -> dict[str, Any]:
        return {"LayerVersions": []}

    def describe_table(self, **_kw: Any) -> dict[str, Any]:
        raise not_found("ResourceNotFoundException")

    def describe_repositories(self, **_kw: Any) -> dict[str, Any]:
        raise not_found("RepositoryNotFoundException")

    def batch_get_projects(self, **_kw: Any) -> dict[str, Any]:
        return {"projects": []}

    def __getattr__(self, name: str) -> Any:
        def _mutating(**kwargs: Any) -> None:
            self.rec.record(name, **kwargs)

        return _mutating


def make_clients(
    recorder: Recorder,
    *,
    roles: dict[str, dict[str, str]] | None = None,
    agentcore: FakeAgentCore | None = None,
) -> wc.Clients:
    empty = FakeEmpty(recorder)
    return wc.Clients(
        dynamodb=empty,
        iam=FakeIam(roles or {}, recorder),
        lambda_=empty,
        agentcore=agentcore or FakeAgentCore(recorder),
        ecr=empty,
        codebuild=empty,
    )


class TestTagScoping(unittest.TestCase):
    """B6 — deletion must be scoped by tag, never by name prefix."""

    def test_untagged_unrelated_roles_are_never_selected(self) -> None:
        recorder = Recorder()
        clients = make_clients(recorder, roles={name: {} for name in COLLATERAL_ROLES})

        plan = wc.build_plan(clients)
        selected = {c.name for c in plan if c.will_delete}

        for role_name in COLLATERAL_ROLES:
            self.assertNotIn(
                role_name,
                selected,
                msg=f"{role_name} is untagged and unrelated; selecting it is bug B6",
            )

        # And prove it end to end: a real (non-dry) run must issue zero deletes.
        exit_code = wc.run(clients, dry_run=False)
        self.assertNotIn("delete_role", recorder.names)
        self.assertEqual(exit_code, 0, "an account of purely unrelated roles is a clean no-op")

    def test_tagged_role_is_selected_regardless_of_its_name(self) -> None:
        recorder = Recorder()
        clients = make_clients(
            recorder,
            roles={"some-unrelated-name": dict(TAG), **{n: {} for n in COLLATERAL_ROLES}},
        )
        plan = wc.build_plan(clients)
        selected = {c.name for c in plan if c.will_delete}
        self.assertEqual(selected, {"some-unrelated-name"})

        wc.run(clients, dry_run=False)
        self.assertIn(("delete_role", {"RoleName": "some-unrelated-name"}), recorder.calls)

    def test_untagged_workshop_role_blocks_and_exits_nonzero(self) -> None:
        recorder = Recorder()
        clients = make_clients(recorder, roles={wc.LAMBDA_ROLE_NAME: {}})

        plan = wc.build_plan(clients)
        blocked = [c for c in plan if c.selection is wc.Selection.UNTAGGED_BLOCKED]
        self.assertEqual([c.name for c in blocked], [wc.LAMBDA_ROLE_NAME])

        exit_code = wc.run(clients, dry_run=False)
        self.assertEqual(exit_code, 1, "an untagged workshop resource must fail loudly")
        self.assertNotIn("delete_role", recorder.names)

    def test_untaggable_kinds_are_pinned(self) -> None:
        # If this fails, someone widened the tag-gate exemption. Review it.
        self.assertEqual(
            wc.UNTAGGABLE_KINDS,
            frozenset({"lambda-layer-version", "local-config-file"}),
        )

    def test_source_calls_no_prefix_matching_methods(self) -> None:
        """Parse the module and assert no prefix/suffix match is ever *called*.

        An AST walk rather than a text search, so the docstring that quotes the
        old ``startswith`` bug does not trip it.
        """
        tree = ast.parse((Path(__file__).parent / "workshop_cleanup.py").read_text())
        called = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        for banned in ("startswith", "endswith", "removeprefix", "removesuffix"):
            self.assertNotIn(
                banned,
                called,
                msg=f"{banned}() reintroduces name-based matching into the deletion path",
            )

    def test_source_never_lists_roles_by_path_prefix(self) -> None:
        source = (Path(__file__).parent / "workshop_cleanup.py").read_text()
        self.assertNotIn('PathPrefix="/"', source)


class TestMemory(unittest.TestCase):
    """B5 — Memory must be matched on ``id``; there is no ``memoryName``."""

    #: Exactly the keys the live API returned. Any code reading ``memoryName``
    #: raises KeyError against this, which is the bug.
    LIVE_SHAPE = {
        "arn": "arn:aws:bedrock-agentcore:us-east-1:123456789012:memory/workshop_HotelBookingMemory-AbC123",
        "id": "workshop_HotelBookingMemory-AbC123",
        "status": "ACTIVE",
        "createdAt": "2026-07-19",
        "updatedAt": "2026-07-19",
    }

    def test_live_summary_has_no_memory_name_field(self) -> None:
        self.assertNotIn("memoryName", self.LIVE_SHAPE)

    def test_id_matching(self) -> None:
        name = "workshop_HotelBookingMemory"
        self.assertTrue(wc.memory_id_matches_name(f"{name}-AbC123", name))
        self.assertTrue(wc.memory_id_matches_name(name, name))
        # Equality after stripping one suffix, not a prefix test.
        self.assertFalse(wc.memory_id_matches_name(f"{name}Extra-AbC123", name))
        self.assertFalse(wc.memory_id_matches_name("orchestrator_agent_mem-FGnAIw2mUS", name))

    def test_tagged_memory_is_deleted_by_id(self) -> None:
        recorder = Recorder()
        agentcore = FakeAgentCore(
            recorder,
            memories=[self.LIVE_SHAPE],
            tags_by_arn={self.LIVE_SHAPE["arn"]: dict(TAG)},
        )
        clients = make_clients(recorder, agentcore=agentcore)

        exit_code = wc.run(clients, dry_run=False)
        self.assertEqual(exit_code, 0)
        self.assertIn(
            ("delete_memory", {"memoryId": self.LIVE_SHAPE["id"]}), recorder.calls
        )

    def test_unrelated_memory_is_not_touched(self) -> None:
        recorder = Recorder()
        other = {
            "arn": "arn:aws:bedrock-agentcore:us-east-1:123456789012:memory/orchestrator_agent_mem-FGnAIw2mUS",
            "id": "orchestrator_agent_mem-FGnAIw2mUS",
            "status": "ACTIVE",
        }
        clients = make_clients(recorder, agentcore=FakeAgentCore(recorder, memories=[other]))

        wc.run(clients, dry_run=False)
        self.assertNotIn("delete_memory", recorder.names)

    def test_memory_deletion_failure_is_not_swallowed(self) -> None:
        recorder = Recorder()
        agentcore = FakeAgentCore(
            recorder,
            memories=[self.LIVE_SHAPE],
            tags_by_arn={self.LIVE_SHAPE["arn"]: dict(TAG)},
            delete_memory_error=not_found("ThrottlingException"),
        )
        clients = make_clients(recorder, agentcore=agentcore)

        exit_code = wc.run(clients, dry_run=False)
        self.assertEqual(exit_code, 1, "a failed delete must exit non-zero, not report success")


class TestDryRun(unittest.TestCase):
    def test_dry_run_issues_no_mutating_calls(self) -> None:
        recorder = Recorder()
        agentcore = FakeAgentCore(
            recorder,
            memories=[TestMemory.LIVE_SHAPE],
            tags_by_arn={TestMemory.LIVE_SHAPE["arn"]: dict(TAG)},
        )
        clients = make_clients(
            recorder,
            roles={"tagged-role": dict(TAG), **{n: {} for n in COLLATERAL_ROLES}},
            agentcore=agentcore,
        )

        plan = wc.build_plan(clients)
        self.assertTrue([c for c in plan if c.will_delete], "fixture should select something")

        wc.execute_plan(clients, plan, dry_run=True)
        self.assertEqual(recorder.calls, [], "dry run must not call a single mutating API")


if __name__ == "__main__":
    unittest.main()
