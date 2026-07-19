# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Tag-scoped teardown for the AgentCore workshop (Modules 6 and 7).

Safety contract
---------------
1. **Nothing is ever selected by name prefix.** A resource is deleted only when
   it carries the workshop tag ``WorkshopResource=stop-ai-agent-hallucinations``.
   The single exception is Lambda layer versions, which AWS does not allow to be
   tagged; those are matched by *exact* name and are listed explicitly in
   :data:`UNTAGGABLE_KINDS` so the exception is auditable.
2. **A resource that exists under a workshop name but carries no workshop tag is
   never deleted.** It is reported as ``UNTAGGED_BLOCKED`` and makes the run exit
   non-zero, because it is either someone else's resource or a deployment that
   forgot to tag.
3. **No failure is swallowed.** Every error is recorded and forces a non-zero
   exit. A cleanup script that lies about success is worse than one that crashes.

Usage::

    python workshop_cleanup.py --dry-run    # print the plan, touch nothing
    python workshop_cleanup.py              # execute the plan

Background: an earlier version of this teardown deleted IAM roles by
account-wide name prefix and destroyed five unrelated roles, two of them in a
different region. See ``verify.md`` bug B6.
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

WORKSHOP_TAG_KEY = "WorkshopResource"
WORKSHOP_TAG_VALUE = "stop-ai-agent-hallucinations"

REGION = os.environ.get("AWS_REGION", "us-east-1")

HOTELS_TABLE = "workshop-Hotels"
BOOKINGS_TABLE = "workshop-Bookings"
STEERING_RULES_TABLE = "workshop-SteeringRules"
TABLE_NAMES = [HOTELS_TABLE, BOOKINGS_TABLE, STEERING_RULES_TABLE]

LAMBDA_ROLE_NAME = "workshop-LambdaExecutionRole"
AGENTCORE_ROLE_NAME = "workshop-AgentCoreExecutionRole"
ROLE_NAMES = [LAMBDA_ROLE_NAME, AGENTCORE_ROLE_NAME]

GATEWAY_NAME = "HotelBookingGateway"
RUNTIME_NAME = "HotelBookingAgent"
MEMORY_RUNTIME_NAME = "HotelBookingAgentWithMemory"
RUNTIME_NAMES = [RUNTIME_NAME, MEMORY_RUNTIME_NAME]
MEMORY_NAME = "workshop_HotelBookingMemory"

LAMBDA_TOOLS = [
    "search_available_hotels",
    "book_hotel",
    "get_booking",
    "process_payment",
    "confirm_booking",
    "cancel_booking",
    "validate_booking_rules",
    "query_knowledge_graph",
]
LAMBDA_FUNCTIONS = [f"hotel-booking-{tool}" for tool in LAMBDA_TOOLS]
LAMBDA_LAYER_NAME = "workshop-neo4j-driver"

ECR_REPOS = [f"bedrock-agentcore-{name.lower()}" for name in RUNTIME_NAMES]
CODEBUILD_PROJECTS = [f"{repo}-builder" for repo in ECR_REPOS]

CONFIG_GLOBS = [".bedrock_agentcore*.yaml", "~/.bedrock_agentcore*.yaml"]


class Selection(StrEnum):
    """Why a candidate is or is not going to be deleted."""

    TAGGED = "TAGGED"
    UNTAGGED_BLOCKED = "UNTAGGED_BLOCKED"
    ABSENT = "ABSENT"
    UNTAGGABLE_EXACT_NAME = "UNTAGGABLE_EXACT_NAME"


#: Resource kinds AWS does not support tagging on. Deletion for these falls back
#: to an *exact* name match. Keep this list as short as the API allows; a unit
#: test pins its contents so the exception cannot quietly grow.
UNTAGGABLE_KINDS = frozenset({"lambda-layer-version", "local-config-file"})

#: Selections that authorise a delete call.
DELETABLE = frozenset({Selection.TAGGED, Selection.UNTAGGABLE_EXACT_NAME})


@dataclass
class Candidate:
    """One resource the teardown considered, and the verdict on it."""

    kind: str
    name: str
    selection: Selection
    identifier: str | None = None
    arn: str | None = None
    tags: dict[str, str] = field(default_factory=dict)
    detail: str = ""

    @property
    def will_delete(self) -> bool:
        return self.selection in DELETABLE

    def describe(self) -> str:
        target = self.identifier or self.name
        reason = {
            Selection.TAGGED: (
                f"tagged {WORKSHOP_TAG_KEY}={WORKSHOP_TAG_VALUE}"
            ),
            Selection.UNTAGGED_BLOCKED: (
                "EXISTS but is NOT tagged — refusing to delete"
            ),
            Selection.ABSENT: "not found",
            Selection.UNTAGGABLE_EXACT_NAME: (
                "exact name match; AWS does not support tags on this kind"
            ),
        }[self.selection]
        line = f"{'DELETE' if self.will_delete else 'SKIP  '}  {self.kind:<24} {target:<52} {reason}"
        return f"{line}\n{'':>10}{self.detail}" if self.detail else line


@dataclass
class Failure:
    kind: str
    name: str
    error: str


def has_workshop_tag(tags: dict[str, str]) -> bool:
    return tags.get(WORKSHOP_TAG_KEY) == WORKSHOP_TAG_VALUE


def _kv_list_to_dict(items: list[dict[str, str]], key: str, value: str) -> dict[str, str]:
    return {item[key]: item[value] for item in items}


def memory_id_matches_name(memory_id: str, memory_name: str) -> bool:
    """AgentCore Memory ids have the form ``<name>-<suffix>``.

    ``list_memories`` returns no name field at all — the ``MemorySummary`` shape
    is ``arn, id, status, createdAt, updatedAt, managedByResourceArn``. Reading
    ``m["memoryName"]`` raises ``KeyError`` on every item, which is bug B5.

    The comparison below strips exactly one trailing ``-<suffix>`` and requires
    the remainder to equal the name. It is an equality test, not a prefix test:
    ``workshop_HotelBookingMemoryExtra-abc`` does not match.
    """
    if memory_id == memory_name:
        return True
    head, sep, _suffix = memory_id.rpartition("-")
    return bool(sep) and head == memory_name


@dataclass
class Clients:
    """The AWS clients the teardown needs, grouped so tests can inject fakes."""

    dynamodb: Any
    iam: Any
    lambda_: Any
    agentcore: Any
    ecr: Any
    codebuild: Any

    @classmethod
    def build(cls, region: str = REGION) -> Clients:
        return cls(
            dynamodb=boto3.client("dynamodb", region_name=region),
            iam=boto3.client("iam"),
            lambda_=boto3.client("lambda", region_name=region),
            agentcore=boto3.client("bedrock-agentcore-control", region_name=region),
            ecr=boto3.client("ecr", region_name=region),
            codebuild=boto3.client("codebuild", region_name=region),
        )


def _absent(error: ClientError, *codes: str) -> bool:
    return error.response.get("Error", {}).get("Code") in codes


# --------------------------------------------------------------------------
# Discovery — every function below returns candidates without deleting anything
# --------------------------------------------------------------------------


def discover_memories(clients: Clients) -> Iterator[Candidate]:
    memories = clients.agentcore.list_memories().get("memories", [])
    matches = [m for m in memories if memory_id_matches_name(m["id"], MEMORY_NAME)]
    if not matches:
        yield Candidate("agentcore-memory", MEMORY_NAME, Selection.ABSENT)
        return
    for memory in matches:
        tags = clients.agentcore.list_tags_for_resource(
            resourceArn=memory["arn"]
        ).get("tags", {})
        yield Candidate(
            kind="agentcore-memory",
            name=MEMORY_NAME,
            selection=Selection.TAGGED if has_workshop_tag(tags) else Selection.UNTAGGED_BLOCKED,
            identifier=memory["id"],
            arn=memory["arn"],
            tags=tags,
            detail=f"id {memory['id']} -> name {memory['id'].rpartition('-')[0]}",
        )


def discover_runtimes(clients: Clients) -> Iterator[Candidate]:
    runtimes = clients.agentcore.list_agent_runtimes().get("agentRuntimes", [])
    by_name = {rt.get("agentRuntimeName"): rt for rt in runtimes}
    for name in RUNTIME_NAMES:
        runtime = by_name.get(name)
        if runtime is None:
            yield Candidate("agentcore-runtime", name, Selection.ABSENT)
            continue
        tags = clients.agentcore.list_tags_for_resource(
            resourceArn=runtime["agentRuntimeArn"]
        ).get("tags", {})
        yield Candidate(
            kind="agentcore-runtime",
            name=name,
            selection=Selection.TAGGED if has_workshop_tag(tags) else Selection.UNTAGGED_BLOCKED,
            identifier=runtime["agentRuntimeId"],
            arn=runtime["agentRuntimeArn"],
            tags=tags,
        )


def discover_gateways(clients: Clients) -> Iterator[Candidate]:
    gateways = clients.agentcore.list_gateways().get("items", [])
    match = next((g for g in gateways if g.get("name") == GATEWAY_NAME), None)
    if match is None:
        yield Candidate("agentcore-gateway", GATEWAY_NAME, Selection.ABSENT)
        return
    # GatewaySummary carries no arn, so the arn has to be fetched before tags
    # can be read.
    arn = clients.agentcore.get_gateway(gatewayIdentifier=match["gatewayId"])["gatewayArn"]
    tags = clients.agentcore.list_tags_for_resource(resourceArn=arn).get("tags", {})
    yield Candidate(
        kind="agentcore-gateway",
        name=GATEWAY_NAME,
        selection=Selection.TAGGED if has_workshop_tag(tags) else Selection.UNTAGGED_BLOCKED,
        identifier=match["gatewayId"],
        arn=arn,
        tags=tags,
    )


def discover_lambda_functions(clients: Clients) -> Iterator[Candidate]:
    for name in LAMBDA_FUNCTIONS:
        try:
            response = clients.lambda_.get_function(FunctionName=name)
        except ClientError as exc:
            if _absent(exc, "ResourceNotFoundException"):
                yield Candidate("lambda-function", name, Selection.ABSENT)
                continue
            raise
        tags = response.get("Tags", {}) or {}
        yield Candidate(
            kind="lambda-function",
            name=name,
            selection=Selection.TAGGED if has_workshop_tag(tags) else Selection.UNTAGGED_BLOCKED,
            arn=response["Configuration"]["FunctionArn"],
            tags=tags,
        )


def discover_lambda_layers(clients: Clients) -> Iterator[Candidate]:
    try:
        versions = clients.lambda_.list_layer_versions(
            LayerName=LAMBDA_LAYER_NAME
        ).get("LayerVersions", [])
    except ClientError as exc:
        if _absent(exc, "ResourceNotFoundException"):
            versions = []
        else:
            raise
    if not versions:
        yield Candidate("lambda-layer-version", LAMBDA_LAYER_NAME, Selection.ABSENT)
        return
    for version in versions:
        yield Candidate(
            kind="lambda-layer-version",
            name=LAMBDA_LAYER_NAME,
            selection=Selection.UNTAGGABLE_EXACT_NAME,
            identifier=str(version["Version"]),
            detail="Lambda layer versions cannot carry tags; exact name match only",
        )


def discover_tables(clients: Clients) -> Iterator[Candidate]:
    for name in TABLE_NAMES:
        try:
            arn = clients.dynamodb.describe_table(TableName=name)["Table"]["TableArn"]
        except ClientError as exc:
            if _absent(exc, "ResourceNotFoundException"):
                yield Candidate("dynamodb-table", name, Selection.ABSENT)
                continue
            raise
        tags = _kv_list_to_dict(
            clients.dynamodb.list_tags_of_resource(ResourceArn=arn).get("Tags", []),
            "Key",
            "Value",
        )
        yield Candidate(
            kind="dynamodb-table",
            name=name,
            selection=Selection.TAGGED if has_workshop_tag(tags) else Selection.UNTAGGED_BLOCKED,
            arn=arn,
            tags=tags,
        )


def discover_roles(clients: Clients) -> Iterator[Candidate]:
    """Select IAM roles **purely by tag**.

    This is the B6 fix. The old code did
    ``if role["RoleName"].startswith("AmazonBedrockAgentCoreSDKCodeBuild")``
    over every role in the account, which is global and reached other regions.
    Nothing here looks at name shape when deciding to delete; the workshop's own
    role names are only used to *warn* about an untagged leftover.
    """
    seen: set[str] = set()
    paginator = clients.iam.get_paginator("list_roles")
    for page in paginator.paginate():
        for role in page.get("Roles", []):
            role_name = role["RoleName"]
            tags = _kv_list_to_dict(
                clients.iam.list_role_tags(RoleName=role_name).get("Tags", []),
                "Key",
                "Value",
            )
            if not has_workshop_tag(tags):
                continue
            seen.add(role_name)
            yield Candidate(
                kind="iam-role",
                name=role_name,
                selection=Selection.TAGGED,
                arn=role.get("Arn"),
                tags=tags,
            )

    for role_name in ROLE_NAMES:
        if role_name in seen:
            continue
        try:
            clients.iam.get_role(RoleName=role_name)
        except ClientError as exc:
            if _absent(exc, "NoSuchEntity", "NoSuchEntityException"):
                yield Candidate("iam-role", role_name, Selection.ABSENT)
                continue
            raise
        yield Candidate(
            kind="iam-role",
            name=role_name,
            selection=Selection.UNTAGGED_BLOCKED,
            detail="workshop role name but no workshop tag — tag it at creation or remove it by hand",
        )


def discover_ecr_repos(clients: Clients) -> Iterator[Candidate]:
    for name in ECR_REPOS:
        try:
            repo = clients.ecr.describe_repositories(repositoryNames=[name])["repositories"][0]
        except ClientError as exc:
            if _absent(exc, "RepositoryNotFoundException"):
                yield Candidate("ecr-repository", name, Selection.ABSENT)
                continue
            raise
        tags = _kv_list_to_dict(
            clients.ecr.list_tags_for_resource(
                resourceArn=repo["repositoryArn"]
            ).get("tags", []),
            "Key",
            "Value",
        )
        yield Candidate(
            kind="ecr-repository",
            name=name,
            selection=Selection.TAGGED if has_workshop_tag(tags) else Selection.UNTAGGED_BLOCKED,
            arn=repo["repositoryArn"],
            tags=tags,
        )


def discover_codebuild_projects(clients: Clients) -> Iterator[Candidate]:
    found = {
        project["name"]: project
        for project in clients.codebuild.batch_get_projects(
            names=CODEBUILD_PROJECTS
        ).get("projects", [])
    }
    for name in CODEBUILD_PROJECTS:
        project = found.get(name)
        if project is None:
            # delete_project is idempotent and returns success for projects that
            # never existed, which is how the old code produced false
            # "Deleted ..." lines. Report absence instead of calling it.
            yield Candidate("codebuild-project", name, Selection.ABSENT)
            continue
        tags = _kv_list_to_dict(project.get("tags", []), "key", "value")
        yield Candidate(
            kind="codebuild-project",
            name=name,
            selection=Selection.TAGGED if has_workshop_tag(tags) else Selection.UNTAGGED_BLOCKED,
            arn=project.get("arn"),
            tags=tags,
        )


def discover_local_config(_clients: Clients) -> Iterator[Candidate]:
    paths = [
        path
        for pattern in CONFIG_GLOBS
        for path in glob.glob(os.path.expanduser(pattern))
    ]
    if not paths:
        yield Candidate("local-config-file", CONFIG_GLOBS[0], Selection.ABSENT)
        return
    for path in paths:
        yield Candidate(
            kind="local-config-file",
            name=path,
            selection=Selection.UNTAGGABLE_EXACT_NAME,
            detail="local file, not an AWS resource",
        )


DISCOVERERS = (
    discover_memories,
    discover_runtimes,
    discover_gateways,
    discover_lambda_functions,
    discover_lambda_layers,
    discover_tables,
    discover_roles,
    discover_ecr_repos,
    discover_codebuild_projects,
    discover_local_config,
)


def build_plan(clients: Clients) -> list[Candidate]:
    """Enumerate every candidate. Read-only: this never deletes anything."""
    return [candidate for discover in DISCOVERERS for candidate in discover(clients)]


# --------------------------------------------------------------------------
# Execution
# --------------------------------------------------------------------------


def _delete_role(clients: Clients, role_name: str) -> None:
    attached = clients.iam.list_attached_role_policies(RoleName=role_name)
    for policy in attached.get("AttachedPolicies", []):
        clients.iam.detach_role_policy(RoleName=role_name, PolicyArn=policy["PolicyArn"])
    inline = clients.iam.list_role_policies(RoleName=role_name)
    for policy_name in inline.get("PolicyNames", []):
        clients.iam.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
    clients.iam.delete_role(RoleName=role_name)


def _delete_gateway(clients: Clients, gateway_id: str) -> None:
    targets = clients.agentcore.list_gateway_targets(
        gatewayIdentifier=gateway_id
    ).get("items", [])
    for target in targets:
        clients.agentcore.delete_gateway_target(
            gatewayIdentifier=gateway_id, targetId=target["targetId"]
        )
    clients.agentcore.delete_gateway(gatewayIdentifier=gateway_id)


def _delete(clients: Clients, candidate: Candidate) -> None:
    match candidate.kind:
        case "agentcore-memory":
            clients.agentcore.delete_memory(memoryId=candidate.identifier)
        case "agentcore-runtime":
            clients.agentcore.delete_agent_runtime(agentRuntimeId=candidate.identifier)
        case "agentcore-gateway":
            _delete_gateway(clients, candidate.identifier)
        case "lambda-function":
            clients.lambda_.delete_function(FunctionName=candidate.name)
        case "lambda-layer-version":
            clients.lambda_.delete_layer_version(
                LayerName=candidate.name, VersionNumber=int(candidate.identifier)
            )
        case "dynamodb-table":
            clients.dynamodb.delete_table(TableName=candidate.name)
        case "iam-role":
            _delete_role(clients, candidate.name)
        case "ecr-repository":
            clients.ecr.delete_repository(repositoryName=candidate.name, force=True)
        case "codebuild-project":
            clients.codebuild.delete_project(name=candidate.name)
        case "local-config-file":
            Path(candidate.name).unlink(missing_ok=True)
        case unknown:
            raise ValueError(f"no delete handler for kind {unknown!r}")


def execute_plan(
    clients: Clients, plan: list[Candidate], *, dry_run: bool
) -> list[Failure]:
    """Delete every selected candidate. Errors are collected, never swallowed."""
    failures: list[Failure] = []
    for candidate in plan:
        if not candidate.will_delete:
            continue
        if dry_run:
            continue
        try:
            _delete(clients, candidate)
        except (ClientError, BotoCoreError, OSError, ValueError) as exc:
            failures.append(Failure(candidate.kind, candidate.name, str(exc)))
            print(f"  FAILED  {candidate.kind} {candidate.name}: {exc}", file=sys.stderr)
        else:
            print(f"  deleted {candidate.kind} {candidate.identifier or candidate.name}")
    return failures


def wait_for_tables_gone(clients: Clients, plan: list[Candidate], timeout: float = 300.0) -> None:
    """Block until deleted tables are actually gone, so teardown is verifiable."""
    names = [c.name for c in plan if c.kind == "dynamodb-table" and c.will_delete]
    deadline = time.monotonic() + timeout
    for name in names:
        while time.monotonic() < deadline:
            try:
                clients.dynamodb.describe_table(TableName=name)
            except ClientError as exc:
                if _absent(exc, "ResourceNotFoundException"):
                    break
                raise
            time.sleep(5)


def print_plan(plan: list[Candidate], *, dry_run: bool) -> None:
    header = "DRY RUN — nothing will be deleted" if dry_run else "TEARDOWN PLAN"
    print("=" * 100)
    print(f"{header}   region={REGION}   gate={WORKSHOP_TAG_KEY}={WORKSHOP_TAG_VALUE}")
    print("=" * 100)
    for candidate in plan:
        print(candidate.describe())
    selected = [c for c in plan if c.will_delete]
    blocked = [c for c in plan if c.selection is Selection.UNTAGGED_BLOCKED]
    print("-" * 100)
    print(f"selected for deletion: {len(selected)}")
    print(f"blocked (present, untagged): {len(blocked)}")
    print(f"absent: {sum(1 for c in plan if c.selection is Selection.ABSENT)}")


def run(clients: Clients, *, dry_run: bool) -> int:
    plan = build_plan(clients)
    print_plan(plan, dry_run=dry_run)

    failures: list[Failure] = []
    if not dry_run:
        print("\nexecuting...")
        failures = execute_plan(clients, plan, dry_run=False)
        wait_for_tables_gone(clients, plan)

    blocked = [c for c in plan if c.selection is Selection.UNTAGGED_BLOCKED]
    if blocked:
        print("\nBLOCKED — these exist under workshop names but carry no workshop tag:", file=sys.stderr)
        for candidate in blocked:
            print(f"  {candidate.kind} {candidate.name}", file=sys.stderr)
        print(
            "Refusing to delete untagged resources. Tag them at creation time with "
            f"{WORKSHOP_TAG_KEY}={WORKSHOP_TAG_VALUE}, or remove them by hand after "
            "confirming they are yours.",
            file=sys.stderr,
        )
    if failures:
        print("\nFAILURES:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure.kind} {failure.name}: {failure.error}", file=sys.stderr)

    if blocked or failures:
        print("\nCLEANUP INCOMPLETE", file=sys.stderr)
        return 1
    print("\nCLEANUP COMPLETE")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print exactly what would be deleted and why, then exit without deleting",
    )
    parser.add_argument("--region", default=REGION, help=f"AWS region (default {REGION})")
    args = parser.parse_args(argv)
    return run(Clients.build(args.region), dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
