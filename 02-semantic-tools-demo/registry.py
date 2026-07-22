# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Tool Registry: Neo4j vector search over tools.

Tool descriptions are embedded with Amazon Bedrock Nova 2 Multimodal
Embeddings and stored on :Tool nodes in the same Neo4j Aura instance as the
hotel knowledge graph. Selection queries the `tool_description_embeddings`
vector index; tool_graph.py owns the graph schema and index setup.
"""

import json
import os
from typing import Callable, List

import boto3

from tool_graph import build_tool_graph, selection_report, vector_search

_client = None
_tools_by_name: dict[str, Callable] = {}

# --- Amazon Bedrock Nova 2 Embeddings ---
MODEL_ID = "amazon.nova-2-multimodal-embeddings-v1:0"
REGION = os.environ.get("AWS_REGION", "us-east-1")
DIMENSIONS = 1024


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name=REGION)
    return _client


def _embed(texts: List[str]) -> list[list[float]]:
    """Embed texts using Amazon Bedrock Nova 2 Multimodal Embeddings."""
    client = _get_client()
    vectors = []
    for text in texts:
        resp = client.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps({
                "taskType": "SINGLE_EMBEDDING",
                "singleEmbeddingParams": {
                    "embeddingPurpose": "GENERIC_INDEX",
                    "embeddingDimension": DIMENSIONS,
                    "text": {"truncationMode": "END", "value": text},
                },
            }),
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(resp["body"].read())
        vectors.append(result["embeddings"][0]["embedding"])
    return vectors


def build_index(tools: List[Callable]):
    """Build the Neo4j tool graph from tool docstrings using Nova 2 embeddings."""
    global _tools_by_name
    _tools_by_name = {t.__name__: t for t in tools}
    build_tool_graph(tools, _embed)
    print(f"Indexed {len(tools)} tools ({DIMENSIONS} dims, Nova 2 embeddings, Neo4j)")


def search_tools(query: str, top_k: int = 3) -> List[Callable]:
    """Find most relevant tools for a query via the Neo4j vector index."""
    emb = _embed([query])[0]
    hits = vector_search(emb, top_k)
    return [_tools_by_name[hit["name"]] for hit in hits]


def select_tools_with_context(query: str, top_k: int = 3) -> dict:
    """Vector candidates plus workflow-expanded tools, each with an explanation."""
    emb = _embed([query])[0]
    return selection_report(emb, top_k)


def swap_tools(agent, new_tools: List[Callable]):
    """Swap tools in a live agent without losing conversation memory.

    Clears the agent's tool_registry and re-registers only the given tools.
    Since get_all_tools_config() is called each event loop cycle, the agent
    will see the new tools on the next call.
    """
    reg = agent.tool_registry
    reg.registry.clear()
    reg.dynamic_tools.clear()
    for t in new_tools:
        reg.register_tool(t)


def trim_history(agent, max_turns: int = 3) -> int:
    """Bound a live agent's conversation history to the last `max_turns` turns.

    Without this, a long multi-turn run resends the entire transcript on every
    call and token cost grows quadratically — the memory variant ends up far
    more expensive than sending all tools every time.

    Trims only at real user-turn boundaries (a user message carrying text rather
    than a toolResult) so a toolUse/toolResult pair is never split, which the
    Bedrock Converse API rejects. Returns the number of messages dropped.
    """
    messages = agent.messages
    boundaries = [
        i
        for i, m in enumerate(messages)
        if m.get("role") == "user"
        and not any("toolResult" in block for block in m.get("content", []))
    ]
    if len(boundaries) <= max_turns:
        return 0

    cut = boundaries[-max_turns]
    del messages[:cut]
    return cut


_USAGE_KEYS = ("inputTokens", "outputTokens", "totalTokens")


def usage_snapshot(agent) -> dict:
    """Read an agent's lifetime accumulated token usage."""
    metrics = getattr(agent, "event_loop_metrics", None)
    if metrics is None:
        return dict.fromkeys(_USAGE_KEYS, 0)
    usage = metrics.accumulated_usage
    return {k: usage.get(k, 0) for k in _USAGE_KEYS}


def usage_delta(agent, before: dict) -> dict:
    """Token usage for the call that just ran, given a pre-call snapshot.

    `result.metrics.accumulated_usage` is the agent's *lifetime* counter, not a
    per-call figure. A loop that builds a fresh Agent per query reads it as
    per-query by accident; a loop that reuses one agent must difference it, or
    summing across queries yields a triangular number instead of a total.
    """
    after = usage_snapshot(agent)
    return {k: after[k] - before.get(k, 0) for k in _USAGE_KEYS}


def get_scores(query: str, top_k: int = 10) -> List[dict]:
    """Get tool scores for debugging. Scores are cosine similarity in [0, 1]."""
    emb = _embed([query])[0]
    hits = vector_search(emb, min(top_k, len(_tools_by_name)))
    return [
        {
            "name": hit["name"],
            "score": hit["score"],
            "doc": _tools_by_name[hit["name"]].__doc__,
        }
        for hit in hits
    ]
