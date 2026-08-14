# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Lab 5 AgentCore Runtime entry point.

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
from strands.hooks.events import AfterToolCallEvent, BeforeToolCallEvent
from strands.hooks.registry import HookProvider, HookRegistry
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient

from workshop.bedrock_providers import default_model_id
from workshop.hybrid_retrieval import (
    GROUNDING_INSTRUCTIONS,
    search_hotel_knowledge as _search_hotel_knowledge,
)

LOGGER = logging.getLogger(__name__)

# `demo06` is a real provisioned identifier, not a stale label for Lab 5.
# `setup/provision_agentcore.py` names the Gateway target
# `<prefix>-reservation-request`, and AgentCore Gateway derives the MCP tool
# name by joining the target name and the schema tool name with three
# underscores. A facilitator giving each participant their own `DEMO06_PREFIX`
# therefore gets a different target name, so the name is read from the
# environment: `5.1_agentcore_deploy.ipynb` passes it to the container the same
# way it passes `GATEWAY_URL`. Without that, an overridden prefix provisions
# cleanly and then fails the discovery check below on every invocation.
DEFAULT_GATEWAY_TARGET_NAME = "demo06-reservation-request"
GATEWAY_TARGET_NAME = (
    os.environ.get("GATEWAY_TARGET_NAME", "").strip() or DEFAULT_GATEWAY_TARGET_NAME
)
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
- Treat the tool's grounding_result as binding. When answerable is false,
  explain the missing fact and do not infer an answer from related evidence.
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


def _command_verdict(result: Any) -> dict[str, Any]:
    """Parse the reservation command's own JSON response out of a tool result.

    `workshop.reservation_command` computes the verdict inside the Lambda and
    returns it as JSON: `status`, `reason_code`, `duplicate`, and the rest of
    the frozen response contract. The Gateway hands that back as tool-result
    content. A result that does not parse is returned as the raw text it was,
    never reshaped into something that reads like a verdict, because the two
    outcomes this has to tell apart are "the rule in the graph refused it" and
    "something broke between the agent and the graph."
    """
    blocks = result.get("content") or [] if isinstance(result, dict) else []
    texts = [
        block["text"]
        for block in blocks
        if isinstance(block, dict) and isinstance(block.get("text"), str)
    ]
    for text in texts:
        try:
            parsed = json.loads(text)
        except ValueError:
            continue
        if isinstance(parsed, dict) and "status" in parsed:
            return parsed
    return {
        "tool_status": result.get("status") if isinstance(result, dict) else None,
        "content": texts,
    }


class CommandResultRecorder(HookProvider):
    """Keep the reservation command's verdict so `invoke` can return it.

    Without this, the verdict is computed in the Lambda, read by the model, and
    then leaves the Runtime only as prose. `tools_used` records that a call was
    *attempted*, so a cancelled call, a Lambda that failed on auth, and a
    Gateway 5xx all look identical from outside. This is the key that separates
    them.
    """

    def __init__(self) -> None:
        self.last_result: dict[str, Any] | None = None

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(AfterToolCallEvent, self._record)

    def _record(self, event: AfterToolCallEvent) -> None:
        tool_use = event.tool_use or {}
        if tool_use.get("name") != GATEWAY_COMMAND_TOOL:
            return
        self.last_result = _command_verdict(event.result)


def _grounding_result(
    query: str,
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """Describe whether bounded hotel evidence can answer the question."""
    normalized_query = query.casefold()
    asks_for_live_availability = any(
        term in normalized_query
        for term in (
            "availability",
            "available",
            "vacancy",
            "vacancies",
            "inventory",
        )
    )
    evidence_ids = list(
        dict.fromkeys(
            item["hotel_id"]
            for item in evidence
            if isinstance(item.get("hotel_id"), str) and item["hotel_id"]
        )
    )
    supported_facts = [
        fact
        for fact, field in (
            ("hotel_identity", "hotel_id"),
            ("hotel_address", "address"),
            ("guest_rating", "guest_rating"),
            ("amenities", "amenities"),
        )
        if any(item.get(field) not in (None, "", []) for item in evidence)
    ]

    if asks_for_live_availability:
        answerable = False
        missing_fact = "live_room_availability"
    else:
        answerable = bool(evidence)
        missing_fact = None if answerable else "matching_hotel_evidence"

    return {
        "answerable": answerable,
        "supported_facts": supported_facts,
        "missing_fact": missing_fact,
        "evidence_ids": evidence_ids,
    }


def _grounding_verdict(result: Any) -> dict[str, Any] | None:
    """Read the structured grounding verdict from a retrieval tool result."""
    blocks = result.get("content") or [] if isinstance(result, dict) else []
    for block in blocks:
        text = block.get("text") if isinstance(block, dict) else None
        if not isinstance(text, str):
            continue
        try:
            payload = json.loads(text)
        except ValueError:
            continue
        verdict = (
            payload.get("grounding_result") if isinstance(payload, dict) else None
        )
        if isinstance(verdict, dict) and isinstance(verdict.get("answerable"), bool):
            return verdict
    return None


class GroundingResultRecorder(HookProvider):
    """Keep the retrieval verdict so callers can assert on it directly."""

    def __init__(self) -> None:
        self.last_result: dict[str, Any] | None = None

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(AfterToolCallEvent, self._record)

    def _record(self, event: AfterToolCallEvent) -> None:
        tool_use = event.tool_use or {}
        if tool_use.get("name") != "search_hotel_knowledge":
            return
        self.last_result = _grounding_verdict(event.result)


@tool
def search_hotel_knowledge(query: str) -> str:
    """Search bounded hotel evidence and graph-enriched facts.

    Use this before answering hotel questions or creating a reservation
    request. The returned hotel_id is the only hotel identity accepted by the
    reservation command. Results do not represent live room availability.

    Args:
        query: Natural-language hotel question.

    Returns:
        JSON containing the unchanged bounded evidence records and a structured
        answerability verdict.
    """
    evidence = _search_hotel_knowledge(query)
    return json.dumps(
        {
            "evidence": evidence,
            "grounding_result": _grounding_result(query, evidence),
        },
        ensure_ascii=False,
    )


def _runtime_region() -> str:
    # Same resolution order as setup/provision_agentcore.py: AWS_REGION, then
    # AWS_DEFAULT_REGION, then us-east-1. The `or` chain matters, because an
    # empty AWS_REGION has to fall through rather than be taken as the answer.
    return (
        os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "us-east-1"
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

    The returned ``grounding_result`` and ``command_result`` are the tools' own
    structured verdicts. They let a caller assert on evidence and graph behavior
    rather than on the model's prose.
    """
    del context
    prompt, request_id = _prompt(payload)
    correlation_id = request_id or "retrieval-only"
    LOGGER.info("runtime_invocation_started request_id=%s", correlation_id)

    gateway_client = MCPClient(
        lambda: streamablehttp_client(_gateway_url()),
    )
    command_recorder = CommandResultRecorder()
    grounding_recorder = GroundingResultRecorder()
    try:
        with gateway_client:
            command_tools = _validated_command_tools(gateway_client)
            # One definition of the model id, in the shared package, applying
            # the same MODEL_ID override every lab honors. The image carries
            # that package as a wheel, so there is no second literal here.
            model = BedrockModel(
                model_id=default_model_id(),
                region_name=_runtime_region(),
            )
            # Same name Lab 3 gave it and Lab 4 carried forward. The agent is
            # the constant across the workshop; only where it runs changes.
            hotel_agent = Agent(
                name="hotel_agent",
                model=model,
                tools=[search_hotel_knowledge, *command_tools],
                system_prompt=SYSTEM_PROMPT,
                hooks=[
                    ReservationRequestGuard(request_id),
                    grounding_recorder,
                    command_recorder,
                ],
            )
            caller_context = (
                f"\n\nCaller request ID: {request_id}"
                if request_id is not None
                else ""
            )
            result = hotel_agent(f"{prompt}{caller_context}")
    except Exception as error:
        LOGGER.error(
            "runtime_invocation_failed request_id=%s error_type=%s",
            correlation_id,
            type(error).__name__,
        )
        raise

    tools_used = _tools_used(result)
    grounding_result = grounding_recorder.last_result
    command_result = command_recorder.last_result
    LOGGER.info(
        "runtime_invocation_completed request_id=%s tools_used=%s command_status=%s",
        correlation_id,
        ",".join(tools_used) or "none",
        (command_result or {}).get("status", "none"),
    )
    return {
        "response": str(result),
        "request_id": request_id,
        "tools_used": tools_used,
        "grounding_result": grounding_result,
        "command_result": command_result,
    }


if __name__ == "__main__":
    app.run()
