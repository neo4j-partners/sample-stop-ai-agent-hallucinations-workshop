#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "boto3>=1.43.0",
# ]
# ///
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Stand-alone pre-provisioning for the Lab 5 AgentCore deploy.

This script creates, inspects, and tears down the slow, privileged
infrastructure that ``05-agentcore-deploy/5.1_agentcore_deploy.ipynb``
depends on, mirroring what Workshop Studio pre-provisions for hosted
participants:

* a Secrets Manager secret holding the Neo4j command credential,
* three least-privilege IAM roles (reservation Lambda, Gateway, Runtime),
* the reservation Lambda behind the Gateway,
* the AgentCore Gateway and its single reservation-request target.

The dependency arrow points one way. This script reads Lab 5 files to package
the Lambda and the shared package to know the contracts; the labs never read
anything under ``setup/``. Everything that crosses back to the notebook is
written to the repo-root ``.env`` as a handful of identifiers, nothing more.

Usage:
    uv run setup/provision_agentcore.py provision
    uv run setup/provision_agentcore.py status
    uv run setup/provision_agentcore.py teardown [--yes]
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import subprocess
import tempfile
import time
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

REPO_ROOT = Path(__file__).resolve().parent.parent
DEPLOY_DIR = REPO_ROOT / "05-agentcore-deploy"
WRITE_PATH_DIR = REPO_ROOT / "04-grounded-write"
DEPLOY_TOOLS = DEPLOY_DIR / "deployment-tools"
LAMBDA_SRC = DEPLOY_TOOLS / "lambda_tools" / "create_reservation_request"
GATEWAY_MANIFEST = DEPLOY_TOOLS / "gateway_target.json"
ENV_FILE = REPO_ROOT / ".env"

# Shared modules the Lambda wrapper imports at run time. They live in the lab
# root, not next to the wrapper, so the packaging step copies them in.
SHARED_MODULES = ("reservation_command.py", "contracts.py")

PREFIX = os.environ.get("DEMO06_PREFIX", "demo06")
TAG_KEY = f"{PREFIX}-agentcore"
TAG_VALUE = "true"

DEFAULT_MODEL_ID = "us.anthropic.claude-sonnet-4-6"
LAMBDA_RUNTIME = "python3.12"
LAMBDA_ARCH = "arm64"  # Match the ARM64 AgentCore Runtime; Graviton price/perf.
LAMBDA_HANDLER = "lambda_function.handler"
LAMBDA_TIMEOUT_SECONDS = 30
LAMBDA_MEMORY_MB = 256

# The AgentCore service principal, used as the trust principal for both the
# Gateway role and the Runtime role, per the AgentCore IAM documentation.
AGENTCORE_PRINCIPAL = "bedrock-agentcore.amazonaws.com"

# .env keys written by `provision` and cleared by `teardown`. There is no read
# secret: the deployed Runtime reads Neo4j from environment variables (D2), and
# the stand-alone path uses one Neo4j user (D4).
ENV_GATEWAY_URL = "AGENTCORE_GATEWAY_URL"
ENV_RUNTIME_ROLE_ARN = "AGENTCORE_RUNTIME_ROLE_ARN"
ENV_COMMAND_SECRET_ID = "NEO4J_COMMAND_SECRET_ID"
MANAGED_ENV_KEYS = (ENV_GATEWAY_URL, ENV_RUNTIME_ROLE_ARN, ENV_COMMAND_SECRET_ID)
ENV_HEADER = "# --- Demo 06 AgentCore deploy (written by setup/provision_agentcore.py) ---"


# --------------------------------------------------------------------------- #
# Configuration and .env handling
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Neo4jValues:
    """The Neo4j connection values that back the command secret."""

    uri: str
    username: str
    password: str
    database: str

    def as_secret_json(self) -> str:
        """Render the SECRET_FIELDS JSON the reservation Lambda expects."""
        return json.dumps(
            {
                "uri": self.uri,
                "username": self.username,
                "password": self.password,
                "database": self.database,
            }
        )


@dataclass(frozen=True)
class Config:
    """Resolved run configuration."""

    region: str
    account_id: str
    neo4j: Neo4jValues
    model_id: str

    @property
    def secret_name(self) -> str:
        return f"{PREFIX}/neo4j-command"

    @property
    def lambda_role_name(self) -> str:
        return f"{PREFIX}-reservation-lambda-role"

    @property
    def gateway_role_name(self) -> str:
        return f"{PREFIX}-gateway-role"

    @property
    def runtime_role_name(self) -> str:
        return f"{PREFIX}-runtime-role"

    @property
    def lambda_function_name(self) -> str:
        return f"{PREFIX}-reservation-request"

    @property
    def gateway_name(self) -> str:
        return f"{PREFIX}-gateway"

    @property
    def lambda_arn(self) -> str:
        return (
            f"arn:aws:lambda:{self.region}:{self.account_id}:"
            f"function:{self.lambda_function_name}"
        )

    def role_arn(self, role_name: str) -> str:
        return f"arn:aws:iam::{self.account_id}:role/{role_name}"


def load_env_file(path: Path) -> None:
    """Populate os.environ from a .env file without overriding real env vars.

    Mirrors python-dotenv's ``load_dotenv(override=False)`` so the script sees
    the same Neo4j values the notebooks do, while still letting a caller export
    an override (for example a CI-injected AWS_REGION).
    """
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def resolve_config() -> Config:
    """Read Neo4j and AWS values, refusing to run if Neo4j is missing."""
    load_env_file(ENV_FILE)
    missing = [
        name
        for name in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "NEO4J_DATABASE")
        if not os.environ.get(name)
    ]
    if missing:
        names = ", ".join(missing)
        raise SystemExit(
            f"Refusing to run: missing Neo4j values in {ENV_FILE} or the "
            f"environment: {names}"
        )
    region = (
        os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "us-east-1"
    )
    sts = boto3.client("sts", region_name=region)
    account_id = sts.get_caller_identity()["Account"]
    return Config(
        region=region,
        account_id=account_id,
        neo4j=Neo4jValues(
            uri=os.environ["NEO4J_URI"],
            username=os.environ["NEO4J_USERNAME"],
            password=os.environ["NEO4J_PASSWORD"],
            database=os.environ["NEO4J_DATABASE"],
        ),
        model_id=os.environ.get("MODEL_ID", DEFAULT_MODEL_ID),
    )


def upsert_env(path: Path, values: dict[str, str]) -> None:
    """Write or replace the managed keys in .env, preserving everything else.

    A commented placeholder (``# KEY=...``) is replaced by the live value so a
    repeated ``provision`` stays idempotent instead of appending duplicates.
    """
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = existing.splitlines()
    remaining = dict(values)
    patterns = {
        key: re.compile(rf"^\s*#?\s*{re.escape(key)}\s*=") for key in values
    }
    for index, line in enumerate(lines):
        for key, pattern in patterns.items():
            if key in remaining and pattern.match(line):
                lines[index] = f"{key}={remaining.pop(key)}"
                break
    if remaining:
        if ENV_HEADER not in lines:
            if lines and lines[-1].strip():
                lines.append("")
            lines.append(ENV_HEADER)
        for key, value in remaining.items():
            lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def clear_env(path: Path, keys: tuple[str, ...]) -> None:
    """Comment out managed keys on teardown so nothing stale points at AWS."""
    if not path.exists():
        return
    patterns = {key: re.compile(rf"^\s*{re.escape(key)}\s*=") for key in keys}
    kept = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() == ENV_HEADER:
            continue
        if any(pattern.match(line) for pattern in patterns.values()):
            continue
        kept.append(line)
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# AWS clients
# --------------------------------------------------------------------------- #


@dataclass
class Clients:
    """The boto3 clients the provisioner uses."""

    iam: Any
    secrets: Any
    awslambda: Any
    agentcore: Any

    @classmethod
    def build(cls, region: str) -> "Clients":
        cfg = BotoConfig(retries={"max_attempts": 5, "mode": "standard"})
        return cls(
            iam=boto3.client("iam", region_name=region, config=cfg),
            secrets=boto3.client("secretsmanager", region_name=region, config=cfg),
            awslambda=boto3.client("lambda", region_name=region, config=cfg),
            agentcore=boto3.client(
                "bedrock-agentcore-control", region_name=region, config=cfg
            ),
        )


def _tags_list() -> list[dict[str, str]]:
    return [{"Key": TAG_KEY, "Value": TAG_VALUE}]


def _error_code(error: ClientError) -> str:
    return error.response.get("Error", {}).get("Code", "")


def _error_message(error: ClientError) -> str:
    return error.response.get("Error", {}).get("Message", "")


def log(message: str) -> None:
    print(message, flush=True)


# --------------------------------------------------------------------------- #
# A1: the Neo4j command secret
# --------------------------------------------------------------------------- #


def provision_secret(clients: Clients, config: Config) -> str:
    """Create or update the command secret and return its ARN."""
    payload = config.neo4j.as_secret_json()
    try:
        response = clients.secrets.create_secret(
            Name=config.secret_name,
            Description="Demo 06 Neo4j command credential for the reservation Lambda.",
            SecretString=payload,
            Tags=_tags_list(),
        )
        log(f"  created secret {config.secret_name}")
        return response["ARN"]
    except ClientError as error:
        if _error_code(error) != "ResourceExistsException":
            raise
    clients.secrets.put_secret_value(
        SecretId=config.secret_name, SecretString=payload
    )
    described = clients.secrets.describe_secret(SecretId=config.secret_name)
    log(f"  updated secret {config.secret_name}")
    return described["ARN"]


# --------------------------------------------------------------------------- #
# A2: the IAM roles
# --------------------------------------------------------------------------- #


def _service_trust_policy(service: str, account_id: str | None = None) -> str:
    statement: dict[str, object] = {
        "Effect": "Allow",
        "Principal": {"Service": service},
        "Action": "sts:AssumeRole",
    }
    if account_id is not None:
        statement["Condition"] = {"StringEquals": {"aws:SourceAccount": account_id}}
    return json.dumps({"Version": "2012-10-17", "Statement": [statement]})


def _ensure_role(clients: Clients, name: str, trust_policy: str) -> str:
    """Create the role if absent, refresh its trust policy if present."""
    try:
        response = clients.iam.create_role(
            RoleName=name,
            AssumeRolePolicyDocument=trust_policy,
            Description=f"Demo 06 AgentCore role ({name}).",
            Tags=_tags_list(),
        )
        log(f"  created role {name}")
        return response["Role"]["Arn"]
    except ClientError as error:
        if _error_code(error) != "EntityAlreadyExists":
            raise
    clients.iam.update_assume_role_policy(
        RoleName=name, PolicyDocument=trust_policy
    )
    described = clients.iam.get_role(RoleName=name)
    log(f"  reused role {name}")
    return described["Role"]["Arn"]


def _put_inline_policy(
    clients: Clients, role_name: str, policy_name: str, document: dict[str, object]
) -> None:
    clients.iam.put_role_policy(
        RoleName=role_name,
        PolicyName=policy_name,
        PolicyDocument=json.dumps(document),
    )


def provision_lambda_role(clients: Clients, config: Config, secret_arn: str) -> str:
    """Role for the reservation Lambda: write logs, open only its own secret."""
    role_arn = _ensure_role(
        clients,
        config.lambda_role_name,
        _service_trust_policy("lambda.amazonaws.com"),
    )
    log_group = (
        f"arn:aws:logs:{config.region}:{config.account_id}:"
        f"log-group:/aws/lambda/{config.lambda_function_name}:*"
    )
    _put_inline_policy(
        clients,
        config.lambda_role_name,
        f"{PREFIX}-reservation-lambda-policy",
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "Logs",
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                    ],
                    "Resource": log_group,
                },
                {
                    "Sid": "ReadCommandSecret",
                    "Effect": "Allow",
                    "Action": ["secretsmanager:GetSecretValue"],
                    "Resource": secret_arn,
                },
            ],
        },
    )
    return role_arn


def provision_gateway_role(clients: Clients, config: Config) -> str:
    """Role the Gateway assumes to invoke only the one reservation Lambda."""
    role_arn = _ensure_role(
        clients,
        config.gateway_role_name,
        _service_trust_policy(AGENTCORE_PRINCIPAL, config.account_id),
    )
    _put_inline_policy(
        clients,
        config.gateway_role_name,
        f"{PREFIX}-gateway-policy",
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "InvokeReservationLambda",
                    "Effect": "Allow",
                    "Action": ["lambda:InvokeFunction"],
                    "Resource": config.lambda_arn,
                }
            ],
        },
    )
    return role_arn


def provision_runtime_role(clients: Clients, config: Config) -> str:
    """Runtime execution role, per the AgentCore Runtime IAM documentation.

    The role grants ECR image pulls, the AgentCore runtime log groups, X-Ray,
    the bedrock-agentcore workload-identity tokens, and Bedrock model
    invocation. It grants no secret access: the deployed Runtime reads Neo4j
    from environment variables (decision D2).

    Bedrock invoke is scoped to ``foundation-model/*`` plus the account-scoped
    ``bedrock:<region>:<account>:*`` rather than a single model ARN. This is
    the documented scope, and it is what lets the cross-region inference
    profile ``us.anthropic.claude-sonnet-4-6`` work: that profile fans out to
    several foundation-model ARNs across regions, so pinning one ARN would
    break invocation.
    """
    trust = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AssumeRolePolicy",
                    "Effect": "Allow",
                    "Principal": {"Service": AGENTCORE_PRINCIPAL},
                    "Action": "sts:AssumeRole",
                    "Condition": {
                        "StringEquals": {"aws:SourceAccount": config.account_id},
                        "ArnLike": {
                            "aws:SourceArn": (
                                f"arn:aws:bedrock-agentcore:{config.region}:"
                                f"{config.account_id}:*"
                            )
                        },
                    },
                }
            ],
        }
    )
    role_arn = _ensure_role(clients, config.runtime_role_name, trust)
    region, account = config.region, config.account_id
    runtime_logs = (
        f"arn:aws:logs:{region}:{account}:log-group:/aws/bedrock-agentcore/runtimes/"
    )
    _put_inline_policy(
        clients,
        config.runtime_role_name,
        f"{PREFIX}-runtime-policy",
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "ECRImageAccess",
                    "Effect": "Allow",
                    "Action": ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
                    "Resource": f"arn:aws:ecr:{region}:{account}:repository/*",
                },
                {
                    "Sid": "ECRTokenAccess",
                    "Effect": "Allow",
                    "Action": ["ecr:GetAuthorizationToken"],
                    "Resource": "*",
                },
                {
                    "Sid": "RuntimeLogs",
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                        "logs:DescribeLogStreams",
                        "logs:PutResourcePolicy",
                    ],
                    "Resource": f"{runtime_logs}*",
                },
                {
                    "Sid": "DescribeLogGroups",
                    "Effect": "Allow",
                    "Action": ["logs:DescribeLogGroups"],
                    "Resource": f"arn:aws:logs:{region}:{account}:log-group:*",
                },
                {
                    "Sid": "XRay",
                    "Effect": "Allow",
                    "Action": [
                        "xray:PutTraceSegments",
                        "xray:PutTelemetryRecords",
                        "xray:GetSamplingRules",
                        "xray:GetSamplingTargets",
                    ],
                    "Resource": "*",
                },
                {
                    "Sid": "CloudWatchMetrics",
                    "Effect": "Allow",
                    "Action": "cloudwatch:PutMetricData",
                    "Resource": "*",
                    "Condition": {
                        "StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}
                    },
                },
                {
                    "Sid": "GetAgentAccessToken",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:GetWorkloadAccessToken",
                        "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                        "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
                    ],
                    "Resource": [
                        f"arn:aws:bedrock-agentcore:{region}:{account}:"
                        "workload-identity-directory/default",
                        f"arn:aws:bedrock-agentcore:{region}:{account}:"
                        "workload-identity-directory/default/workload-identity/*",
                    ],
                },
                {
                    "Sid": "BedrockModelInvocation",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock:InvokeModel",
                        "bedrock:InvokeModelWithResponseStream",
                    ],
                    "Resource": [
                        "arn:aws:bedrock:*::foundation-model/*",
                        f"arn:aws:bedrock:{region}:{account}:*",
                    ],
                },
            ],
        },
    )
    return role_arn


# --------------------------------------------------------------------------- #
# A3: the reservation Lambda
# --------------------------------------------------------------------------- #


def build_lambda_zip(build_dir: Path) -> bytes:
    """Build the reservation Lambda deployment package.

    Why a platform-targeted install and not a bare ``pip install -t`` on the
    dev machine:

    * The provisioning host may be macOS/arm64, but the Lambda runs on Amazon
      Linux. Installing without a platform target would resolve wheels for the
      *build* platform, which fail to import at Lambda cold start. We therefore
      force Linux wheels for the Lambda architecture with
      ``--python-platform`` / ``--python-version`` / ``--only-binary``.
    * ``neo4j`` is the only third-party dependency, and its base driver is pure
      Python, so a platform-targeted wheel install is reliable. We deliberately
      do not pull the optional native ``neo4j-rust-ext`` package, which would
      reintroduce a compiled artifact and the cross-platform problem above.
    * ``boto3``/``botocore`` are intentionally NOT vendored: they are already
      present in the Lambda Python runtime, so bundling them only bloats the
      package.

    The three first-party source files (the wrapper plus the shared
    ``reservation_command.py`` and ``contracts.py``) are copied in at the zip
    root so ``lambda_function.handler`` resolves its imports.
    """
    platform_tag = (
        "aarch64-manylinux2014" if LAMBDA_ARCH == "arm64" else "x86_64-manylinux2014"
    )
    package_dir = build_dir / "package"
    package_dir.mkdir(parents=True, exist_ok=True)
    log(f"  installing Lambda dependencies for {platform_tag}")
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python-platform",
            platform_tag,
            "--python-version",
            "3.12",
            "--only-binary",
            ":all:",
            "--target",
            str(package_dir),
            "--requirement",
            str(LAMBDA_SRC / "requirements.txt"),
        ],
        check=True,
    )

    # Copy first-party sources to the package root next to the dependencies.
    (package_dir / "lambda_function.py").write_bytes(
        (LAMBDA_SRC / "lambda_function.py").read_bytes()
    )
    for module in SHARED_MODULES:
        (package_dir / module).write_bytes((WRITE_PATH_DIR / module).read_bytes())

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(package_dir.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            if path.name == ".lock":  # uv coordination file; not part of the package
                continue
            archive.write(path, path.relative_to(package_dir).as_posix())
    return buffer.getvalue()


def _create_function_with_retry(
    clients: Clients, *, attempts: int = 12, delay: float = 5.0, **kwargs: Any
) -> dict[str, Any]:
    """Call ``create_function``, retrying the IAM eventual-consistency race.

    The Lambda execution role is created moments before this call, and IAM is
    eventually consistent: the role is not yet globally visible to the Lambda
    control plane, which surfaces as ``InvalidParameterValueException`` with the
    message "The role defined for the function cannot be assumed by Lambda."
    That specific error is transient, so we back off and retry. Any other error
    is re-raised immediately.
    """
    for attempt in range(1, attempts + 1):
        try:
            return clients.awslambda.create_function(**kwargs)
        except ClientError as error:
            transient = (
                _error_code(error) == "InvalidParameterValueException"
                and "cannot be assumed by Lambda" in _error_message(error)
            )
            if not transient or attempt == attempts:
                raise
            log(
                "  role not yet assumable by Lambda (IAM propagation); "
                f"retrying {attempt}/{attempts - 1}"
            )
            time.sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover


def provision_lambda(
    clients: Clients, config: Config, role_arn: str, secret_arn: str, zip_bytes: bytes
) -> str:
    """Create or update the reservation Lambda and return its ARN."""
    environment = {"Variables": {ENV_COMMAND_SECRET_ID: secret_arn}}
    try:
        response = _create_function_with_retry(
            clients,
            FunctionName=config.lambda_function_name,
            Runtime=LAMBDA_RUNTIME,
            Role=role_arn,
            Handler=LAMBDA_HANDLER,
            Code={"ZipFile": zip_bytes},
            Timeout=LAMBDA_TIMEOUT_SECONDS,
            MemorySize=LAMBDA_MEMORY_MB,
            Architectures=[LAMBDA_ARCH],
            Environment=environment,
            Description="Demo 06 reservation-request command behind the Gateway.",
            Tags={TAG_KEY: TAG_VALUE},
        )
        log(f"  created function {config.lambda_function_name}")
        arn = response["FunctionArn"]
    except ClientError as error:
        if _error_code(error) != "ResourceConflictException":
            raise
        clients.awslambda.update_function_code(
            FunctionName=config.lambda_function_name, ZipFile=zip_bytes
        )
        clients.awslambda.get_waiter("function_updated_v2").wait(
            FunctionName=config.lambda_function_name
        )
        clients.awslambda.update_function_configuration(
            FunctionName=config.lambda_function_name,
            Role=role_arn,
            Handler=LAMBDA_HANDLER,
            Runtime=LAMBDA_RUNTIME,
            Timeout=LAMBDA_TIMEOUT_SECONDS,
            MemorySize=LAMBDA_MEMORY_MB,
            Environment=environment,
        )
        described = clients.awslambda.get_function(
            FunctionName=config.lambda_function_name
        )
        log(f"  updated function {config.lambda_function_name}")
        arn = described["Configuration"]["FunctionArn"]
    clients.awslambda.get_waiter("function_active_v2").wait(
        FunctionName=config.lambda_function_name
    )
    return arn


# --------------------------------------------------------------------------- #
# A4: the Gateway and its one target
# --------------------------------------------------------------------------- #


def _find_gateway(clients: Clients, name: str) -> dict[str, object] | None:
    paginator = clients.agentcore.get_paginator("list_gateways")
    for page in paginator.paginate():
        for item in page.get("items", []):
            if item.get("name") == name:
                return item
    return None


def _wait_gateway_ready(clients: Clients, gateway_id: str) -> dict[str, object]:
    for _ in range(60):
        gateway = clients.agentcore.get_gateway(gatewayIdentifier=gateway_id)
        status = gateway.get("status", "")
        if status == "READY":
            return gateway
        if "FAIL" in status.upper():
            reasons = gateway.get("statusReasons") or []
            raise SystemExit(f"Gateway {gateway_id} failed: {status} {reasons}")
        time.sleep(5)
    raise SystemExit(f"Gateway {gateway_id} did not become READY in time")


def provision_gateway(clients: Clients, config: Config, gateway_role_arn: str) -> dict:
    """Create or reuse the NONE-auth MCP Gateway; return id and url."""
    existing = _find_gateway(clients, config.gateway_name)
    if existing is None:
        created = clients.agentcore.create_gateway(
            name=config.gateway_name,
            roleArn=gateway_role_arn,
            protocolType="MCP",
            authorizerType="NONE",
            description="Demo 06 Gateway exposing the sole reservation target.",
            tags={TAG_KEY: TAG_VALUE},
        )
        gateway_id = created["gatewayId"]
        log(f"  created gateway {config.gateway_name}")
    else:
        gateway_id = str(existing["gatewayId"])
        log(f"  reused gateway {config.gateway_name}")
    gateway = _wait_gateway_ready(clients, gateway_id)
    return {"id": gateway_id, "url": gateway["gatewayUrl"]}


def _load_target_manifest(lambda_arn: str) -> dict[str, object]:
    raw = GATEWAY_MANIFEST.read_text(encoding="utf-8")
    raw = raw.replace("${RESERVATION_LAMBDA_ARN}", lambda_arn)
    return json.loads(raw)


def _find_target(clients: Clients, gateway_id: str, name: str) -> str | None:
    paginator = clients.agentcore.get_paginator("list_gateway_targets")
    for page in paginator.paginate(gatewayIdentifier=gateway_id):
        for item in page.get("items", []):
            if item.get("name") == name:
                return str(item.get("targetId"))
    return None


def _wait_target_deleted(clients: Clients, gateway_id: str, name: str) -> None:
    """Wait for a deleted target to disappear before deleting the gateway.

    ``delete_gateway_target`` returns before the association is torn down, and
    ``delete_gateway`` then fails with ValidationException "has targets
    associated with it." Poll until the target is no longer listed.
    """
    for _ in range(60):
        if _find_target(clients, gateway_id, name) is None:
            return
        time.sleep(5)
    raise SystemExit(f"Gateway target {name} was not deleted in time")


def provision_target(clients: Clients, gateway_id: str, lambda_arn: str) -> None:
    """Create or update the single reservation-request Gateway target."""
    manifest = _load_target_manifest(lambda_arn)
    name = str(manifest["name"])
    kwargs = {
        "name": name,
        "description": manifest.get("description", ""),
        "targetConfiguration": manifest["targetConfiguration"],
        "credentialProviderConfigurations": manifest[
            "credentialProviderConfigurations"
        ],
    }
    target_id = _find_target(clients, gateway_id, name)
    if target_id is None:
        clients.agentcore.create_gateway_target(gatewayIdentifier=gateway_id, **kwargs)
        log(f"  created gateway target {name}")
    else:
        clients.agentcore.update_gateway_target(
            gatewayIdentifier=gateway_id, targetId=target_id, **kwargs
        )
        log(f"  updated gateway target {name}")


def provision_lambda_permission(
    clients: Clients, config: Config, gateway_role_arn: str
) -> None:
    """Allow the Gateway role to invoke the Lambda (resource-based policy)."""
    statement_id = f"{PREFIX}-gateway-invoke"
    try:
        clients.awslambda.add_permission(
            FunctionName=config.lambda_function_name,
            StatementId=statement_id,
            Action="lambda:InvokeFunction",
            Principal=gateway_role_arn,
        )
        log("  added Lambda invoke permission for the Gateway role")
    except ClientError as error:
        if _error_code(error) != "ResourceConflictException":
            raise
        log("  Lambda invoke permission already present")


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #


def cmd_provision(clients: Clients, config: Config) -> int:
    """Create every resource in dependency order and hand off via .env."""
    log(f"Provisioning Demo 06 AgentCore infrastructure in {config.region}")
    log("A1: Neo4j command secret")
    secret_arn = provision_secret(clients, config)

    log("A2: IAM roles")
    provision_lambda_role(clients, config, secret_arn)
    gateway_role_arn = provision_gateway_role(clients, config)
    runtime_role_arn = provision_runtime_role(clients, config)

    log("A3: reservation Lambda")
    with build_workspace() as build_dir:
        zip_bytes = build_lambda_zip(build_dir)
    provision_lambda(
        clients,
        config,
        config.role_arn(config.lambda_role_name),
        secret_arn,
        zip_bytes,
    )

    log("A4: Gateway and target")
    gateway = provision_gateway(clients, config, gateway_role_arn)
    provision_lambda_permission(clients, config, gateway_role_arn)
    provision_target(clients, str(gateway["id"]), config.lambda_arn)

    log("A5: config handoff to .env")
    upsert_env(
        ENV_FILE,
        {
            ENV_GATEWAY_URL: str(gateway["url"]),
            ENV_RUNTIME_ROLE_ARN: runtime_role_arn,
            ENV_COMMAND_SECRET_ID: secret_arn,
        },
    )
    log(f"  wrote {', '.join(MANAGED_ENV_KEYS)} to {ENV_FILE}")
    log("Provision complete.")
    return 0


def cmd_status(clients: Clients, config: Config) -> int:
    """Report presence of each resource without changing anything."""
    log(f"Demo 06 AgentCore status in {config.region}")

    def report(label: str, present: bool, detail: str = "") -> None:
        mark = "present" if present else "absent "
        suffix = f"  {detail}" if detail else ""
        log(f"  [{mark}] {label}{suffix}")

    try:
        clients.secrets.describe_secret(SecretId=config.secret_name)
        report("secret", True, config.secret_name)
    except ClientError:
        report("secret", False, config.secret_name)

    for role in (
        config.lambda_role_name,
        config.gateway_role_name,
        config.runtime_role_name,
    ):
        try:
            clients.iam.get_role(RoleName=role)
            report("role", True, role)
        except ClientError:
            report("role", False, role)

    try:
        clients.awslambda.get_function(FunctionName=config.lambda_function_name)
        report("lambda", True, config.lambda_function_name)
    except ClientError:
        report("lambda", False, config.lambda_function_name)

    gateway = _find_gateway(clients, config.gateway_name)
    if gateway is None:
        report("gateway", False, config.gateway_name)
    else:
        gateway_id = str(gateway["gatewayId"])
        report("gateway", True, f"{config.gateway_name} ({gateway.get('status')})")
        target_id = _find_target(clients, gateway_id, "demo06-reservation-request")
        report("target", target_id is not None, "demo06-reservation-request")
    return 0


def _delete_role(clients: Clients, name: str) -> None:
    try:
        policies = clients.iam.list_role_policies(RoleName=name)["PolicyNames"]
    except ClientError as error:
        if _error_code(error) == "NoSuchEntity":
            return
        raise
    for policy in policies:
        clients.iam.delete_role_policy(RoleName=name, PolicyName=policy)
    attached = clients.iam.list_attached_role_policies(RoleName=name)[
        "AttachedPolicies"
    ]
    for policy in attached:
        clients.iam.detach_role_policy(RoleName=name, PolicyArn=policy["PolicyArn"])
    clients.iam.delete_role(RoleName=name)
    log(f"  deleted role {name}")


def cmd_teardown(clients: Clients, config: Config, assume_yes: bool) -> int:
    """Delete every resource in reverse dependency order."""
    if not assume_yes:
        answer = input(
            f"Delete all Demo 06 AgentCore resources in {config.region}? [y/N] "
        )
        if answer.strip().lower() not in {"y", "yes"}:
            log("Aborted.")
            return 1

    log("Tearing down Demo 06 AgentCore infrastructure")
    gateway = _find_gateway(clients, config.gateway_name)
    if gateway is not None:
        gateway_id = str(gateway["gatewayId"])
        target_id = _find_target(clients, gateway_id, "demo06-reservation-request")
        if target_id is not None:
            clients.agentcore.delete_gateway_target(
                gatewayIdentifier=gateway_id, targetId=target_id
            )
            _wait_target_deleted(clients, gateway_id, "demo06-reservation-request")
            log("  deleted gateway target")
        clients.agentcore.delete_gateway(gatewayIdentifier=gateway_id)
        log("  deleted gateway")

    try:
        clients.awslambda.delete_function(FunctionName=config.lambda_function_name)
        log(f"  deleted function {config.lambda_function_name}")
    except ClientError as error:
        if _error_code(error) != "ResourceNotFoundException":
            raise

    for role in (
        config.lambda_role_name,
        config.gateway_role_name,
        config.runtime_role_name,
    ):
        _delete_role(clients, role)

    try:
        clients.secrets.delete_secret(
            SecretId=config.secret_name, ForceDeleteWithoutRecovery=True
        )
        log(f"  deleted secret {config.secret_name}")
    except ClientError as error:
        if _error_code(error) != "ResourceNotFoundException":
            raise

    clear_env(ENV_FILE, MANAGED_ENV_KEYS)
    log(f"  cleared {', '.join(MANAGED_ENV_KEYS)} from {ENV_FILE}")
    log("Teardown complete.")
    return 0


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


@contextlib.contextmanager
def build_workspace() -> Iterator[Path]:
    """Yield a temporary directory for the Lambda build, cleaned up on exit."""
    with tempfile.TemporaryDirectory(prefix="demo06-lambda-") as name:
        yield Path(name)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("provision", help="Create every resource in dependency order.")
    sub.add_parser("status", help="Report the presence of each resource.")
    teardown = sub.add_parser("teardown", help="Delete every resource.")
    teardown.add_argument(
        "--yes", action="store_true", help="Skip the confirmation prompt."
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = resolve_config()
    clients = Clients.build(config.region)
    if args.command == "provision":
        return cmd_provision(clients, config)
    if args.command == "status":
        return cmd_status(clients, config)
    if args.command == "teardown":
        return cmd_teardown(clients, config, assume_yes=args.yes)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
