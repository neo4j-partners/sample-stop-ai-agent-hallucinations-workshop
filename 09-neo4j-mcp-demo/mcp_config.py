# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Configuration helpers for Demo 09: Neo4j MCP and controlled Text2Cypher.

The notebook must run end to end even when no MCP endpoint is configured,
so this module only reads environment variables and shapes tool results.
It never opens a network connection, at import time or otherwise.

Two spellings are accepted for each setting because the operator's validated
AgentCore deployment publishes ``MCP_GATEWAY_URL`` and ``MCP_ACCESS_TOKEN``,
while this repository's demos read ``NEO4J_*`` names from ``.env`` files.
The ``NEO4J_MCP_*`` names win when both are set.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

URL_VARS = ("NEO4J_MCP_URL", "MCP_GATEWAY_URL")
TOKEN_VARS = ("NEO4J_MCP_TOKEN", "MCP_ACCESS_TOKEN")
REQUIRED_TOOL_NAMES = frozenset({"get_neo4j_schema", "read_neo4j_cypher"})

SKIP_MESSAGE = (
    "No Neo4j MCP endpoint is configured, so every live cell in this "
    "notebook will skip cleanly.\n"
    "To run the live path, set NEO4J_MCP_URL (plus NEO4J_MCP_TOKEN when the "
    "endpoint requires a bearer token) in your environment or .env file.\n"
    "See this demo's README.md for the operator-provided endpoint and for "
    "running the official mcp-neo4j-cypher server locally against your own "
    "Aura instance."
)


@dataclass(frozen=True)
class McpSettings:
    """Resolved MCP endpoint configuration for one notebook session."""

    url: str | None
    token: str | None

    @property
    def configured(self) -> bool:
        """Return True when an MCP endpoint URL is available."""
        return bool(self.url)

    def headers(self) -> dict[str, str]:
        """Return the HTTP headers for the endpoint, empty when tokenless."""
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}


def _first_set(env: Mapping[str, str], names: tuple[str, ...]) -> str | None:
    """Return the first non-blank value among `names`, or None."""
    for name in names:
        value = env.get(name, "").strip()
        if value:
            return value
    return None


def load_mcp_settings(env: Mapping[str, str] | None = None) -> McpSettings:
    """Read the MCP endpoint settings from `env` or the process environment."""
    if env is None:
        import os

        env = os.environ
    return McpSettings(
        url=_first_set(env, URL_VARS),
        token=_first_set(env, TOKEN_VARS),
    )


def tool_result_text(result: Mapping[str, Any]) -> str:
    """Join the text blocks of a Strands MCPClient.call_tool_sync result.

    Strands returns tool results in the Bedrock converse shape:
    ``{"toolUseId": ..., "status": ..., "content": [{"text": ...}, ...]}``.
    Non-text blocks are ignored.
    """
    blocks = result.get("content") or []
    texts = [
        block["text"]
        for block in blocks
        if isinstance(block, Mapping) and isinstance(block.get("text"), str)
    ]
    return "\n".join(texts)


def require_read_tools(tools: Sequence[Any]) -> list[Any]:
    """Return the exact two approved read tools or fail closed.

    Tool wrappers are intentionally typed as ``Any`` because Strands does not
    expose a stable public protocol for them. Each wrapper must provide a
    string ``tool_name`` attribute.
    """
    named_tools = [
        tool
        for tool in tools
        if isinstance(getattr(tool, "tool_name", None), str)
    ]
    by_name = {tool.tool_name: tool for tool in named_tools}
    discovered = set(by_name)
    if discovered != REQUIRED_TOOL_NAMES or len(named_tools) != len(by_name):
        missing = sorted(REQUIRED_TOOL_NAMES - discovered)
        unexpected = sorted(discovered - REQUIRED_TOOL_NAMES)
        details = []
        if missing:
            details.append(f"missing {missing}")
        if unexpected:
            details.append(f"unexpected {unexpected}")
        if len(named_tools) != len(by_name):
            details.append("duplicate tool names")
        raise ValueError(
            "Neo4j MCP tool surface is not the approved read-only set: "
            + "; ".join(details)
        )
    return [by_name[name] for name in sorted(REQUIRED_TOOL_NAMES)]


def tool_result_records(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Validate one successful MCP result and decode its JSON row list."""
    status = result.get("status")
    if status != "success":
        detail = tool_result_text(result) or "no error detail returned"
        raise ValueError(f"MCP tool returned {status!r}: {detail}")

    raw = tool_result_text(result)
    if not raw:
        raise ValueError("MCP tool returned success with no text content")
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("MCP tool returned non-JSON text") from exc
    if not isinstance(decoded, list) or not all(
        isinstance(record, dict) for record in decoded
    ):
        raise ValueError("MCP tool result must be a JSON list of objects")
    return decoded
