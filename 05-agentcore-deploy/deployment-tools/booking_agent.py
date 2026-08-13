# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Demo 06 AgentCore Runtime entry point.

The Runtime exposes one in-process, read-only retrieval tool and discovers one
reservation-request command from its pre-provisioned AgentCore Gateway. This
module defines no AWS resource creation or deployment behavior.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any
from uuid import UUID

from bedrock_agentcore import BedrockAgentCoreApp
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent, tool
from strands.hooks.events import BeforeToolCallEvent
from strands.hooks.registry import HookProvider, HookRegistry
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient

from workshop.hybrid_retrieval import (
    GROUNDING_INSTRUCTIONS,
    search_hotel_knowledge as _search_hotel_knowledge,
)

LOGGER = logging.getLogger(__name__)

DEFAULT_MODEL_ID = "us.anthropic.claude-sonnet-5"
GATEWAY_TARGET_NAME = "demo06-reservation-request"
GATEWAY_SCHEMA_TOOL = "create_reservation_request"
GATEWAY_COMMAND_TOOL = f"{GATEWAY_TARGET_NAME}___{GATEWAY_SCHEMA_TOOL}"

SYSTEM_PROMPT = f"""
You are a grounded hotel-information and reservation-request assistant.

You have exactly two logical tools:
- search_hotel_knowledge searches hotel evidence and returns a stable hotel ID.
- {GATEWAY_COMMAND_TOOL} is the Gateway form of create_reservation_request. It
  validates policy and records a request. It does not reserve inventory, take
  payment, or confirm a booking.

Rules:
- Use search_hotel_knowledge before creating any reservation request.
- Pass only a stable hotel ID returned by that search to the command.
- Use the caller-provided request ID exactly. Never invent or alter one.
- Never silently reduce the guest count or change dates. Make every policy
  rejection visible and ask the caller for a corrected request.
- Never claim that availability is guaranteed or that a booking is complete.

{GROUNDING_INSTRUCTIONS}
""".strip()

app = BedrockAgentCoreApp()


class ReservationRequestGuard(HookProvider):
    """Bind reservation tool calls to the caller's correlation UUID."""

    def __init__(self, request_id: str | None) -> None:
        self.request_id = request_id

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeToolCallEvent, self._validate)

    def _validate(self, event: BeforeToolCallEvent) -> None:
        tool_use = event.tool_use
        if tool_use.get("name") != GATEWAY_COMMAND_TOOL:
            return
        parameters = tool_use.get("input") or {}
        if self.request_id is None:
            event.cancel_tool = (
                "BLOCKED: A caller-provided request_id is required for the "
                "reservation command."
            )
        elif parameters.get("request_id") != self.request_id:
            event.cancel_tool = (
                "BLOCKED: The reservation command must use the caller-provided "
                "request_id unchanged."
            )


@tool
def search_hotel_knowledge(query: str) -> str:
    """Search bounded hotel evidence and graph-enriched facts.

    Use this before answering hotel questions or creating a reservation
    request. The returned hotel_id is the only hotel identity accepted by the
    reservation command. Results do not represent live room availability.

    Args:
        query: Natural-language hotel question.

    Returns:
        JSON containing at most five grounded hotel evidence records.
    """
    return json.dumps(_search_hotel_knowledge(query), ensure_ascii=False)


def _runtime_region() -> str:
    return os.environ.get(
        "AWS_REGION",
        os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )


def _gateway_url() -> str:
    value = os.environ.get("GATEWAY_URL", "").strip()
    if not value:
        raise ValueError("GATEWAY_URL is required for the deployed Runtime")
    return value


def _request_id(payload: dict[str, Any]) -> str | None:
    value = payload.get("request_id")
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("request_id must be a UUID string")
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise ValueError("request_id must be a valid UUID") from error
    if str(parsed) != value:
        raise ValueError("request_id must use canonical UUID format")
    return str(parsed)


def _prompt(payload: str | dict[str, Any]) -> tuple[str, str | None]:
    if isinstance(payload, str):
        prompt = payload.strip()
        request_id = None
    elif isinstance(payload, dict):
        raw_prompt = payload.get("prompt")
        prompt = raw_prompt.strip() if isinstance(raw_prompt, str) else ""
        request_id = _request_id(payload)
    else:
        raise ValueError("payload must be a prompt string or object")

    if not prompt:
        raise ValueError("payload must include a non-empty prompt")
    return prompt, request_id


def _tool_name(gateway_tool: Any) -> str | None:
    return getattr(
        gateway_tool,
        "tool_name",
        getattr(gateway_tool, "name", None),
    )


def _validated_command_tools(gateway_client: MCPClient) -> list[Any]:
    tools = list(gateway_client.list_tools_sync())
    names = [_tool_name(candidate) for candidate in tools]
    if names != [GATEWAY_COMMAND_TOOL]:
        raise RuntimeError(
            f"Gateway must expose only {GATEWAY_COMMAND_TOOL}; "
            f"discovered {names!r}"
        )
    return tools


def _tools_used(result: Any) -> list[str]:
    metrics = getattr(result, "metrics", None)
    tool_metrics = getattr(metrics, "tool_metrics", None)
    return list(tool_metrics) if isinstance(tool_metrics, dict) else []


@app.entrypoint
def invoke(
    payload: str | dict[str, Any],
    context: Any | None = None,
) -> dict[str, Any]:
    """Handle one isolated Runtime invocation.

    ``request_id`` is optional for retrieval-only questions and required by the
    Gateway command schema when the agent creates a reservation request.
    """
    del context
    prompt, request_id = _prompt(payload)
    correlation_id = request_id or "retrieval-only"
    LOGGER.info("runtime_invocation_started request_id=%s", correlation_id)

    gateway_client = MCPClient(
        lambda: streamablehttp_client(_gateway_url()),
    )
    try:
        with gateway_client:
            command_tools = _validated_command_tools(gateway_client)
            model = BedrockModel(
                model_id=os.environ.get("MODEL_ID", DEFAULT_MODEL_ID),
                region_name=_runtime_region(),
            )
            agent = Agent(
                model=model,
                tools=[search_hotel_knowledge, *command_tools],
                system_prompt=SYSTEM_PROMPT,
                hooks=[ReservationRequestGuard(request_id)],
            )
            caller_context = (
                f"\n\nCaller request ID: {request_id}"
                if request_id is not None
                else ""
            )
            result = agent(f"{prompt}{caller_context}")
    except Exception as error:
        LOGGER.error(
            "runtime_invocation_failed request_id=%s error_type=%s",
            correlation_id,
            type(error).__name__,
        )
        raise

    tools_used = _tools_used(result)
    LOGGER.info(
        "runtime_invocation_completed request_id=%s tools_used=%s",
        correlation_id,
        ",".join(tools_used) or "none",
    )
    return {
        "response": str(result),
        "request_id": request_id,
        "tools_used": tools_used,
    }


if __name__ == "__main__":
    app.run()
