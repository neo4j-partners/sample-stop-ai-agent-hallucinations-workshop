# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Unit tests for the pure configuration and MCP-boundary helpers."""

from dataclasses import dataclass

import pytest

from mcp_config import (
    McpSettings,
    load_mcp_settings,
    require_read_tools,
    tool_result_records,
    tool_result_text,
)


@dataclass
class FakeTool:
    tool_name: str


def test_unconfigured_environment_is_not_configured() -> None:
    settings = load_mcp_settings({})
    assert settings.url is None
    assert settings.token is None
    assert not settings.configured
    assert settings.headers() == {}


def test_blank_values_are_treated_as_unset() -> None:
    settings = load_mcp_settings({"NEO4J_MCP_URL": "  ", "NEO4J_MCP_TOKEN": ""})
    assert not settings.configured


def test_neo4j_mcp_url_configures_the_endpoint() -> None:
    settings = load_mcp_settings(
        {"NEO4J_MCP_URL": "http://127.0.0.1:8000/mcp/"}
    )
    assert settings.configured
    assert settings.url == "http://127.0.0.1:8000/mcp/"
    assert settings.headers() == {}


def test_operator_gateway_spelling_is_accepted() -> None:
    settings = load_mcp_settings(
        {
            "MCP_GATEWAY_URL": "https://gateway.example/mcp",
            "MCP_ACCESS_TOKEN": "abc123",
        }
    )
    assert settings.url == "https://gateway.example/mcp"
    assert settings.headers() == {"Authorization": "Bearer abc123"}


def test_neo4j_mcp_names_win_over_gateway_names() -> None:
    settings = load_mcp_settings(
        {
            "NEO4J_MCP_URL": "http://localhost:8000/mcp/",
            "MCP_GATEWAY_URL": "https://gateway.example/mcp",
            "NEO4J_MCP_TOKEN": "local-token",
            "MCP_ACCESS_TOKEN": "gateway-token",
        }
    )
    assert settings.url == "http://localhost:8000/mcp/"
    assert settings.token == "local-token"


def test_headers_include_bearer_token_only_when_set() -> None:
    tokenless = McpSettings(url="http://localhost:8000/mcp/", token=None)
    assert tokenless.headers() == {}
    with_token = McpSettings(url="http://localhost:8000/mcp/", token="t")
    assert with_token.headers() == {"Authorization": "Bearer t"}


def test_tool_result_text_joins_text_blocks() -> None:
    result = {
        "toolUseId": "template-1",
        "status": "success",
        "content": [{"text": "line one"}, {"json": {"x": 1}}, {"text": "line two"}],
    }
    assert tool_result_text(result) == "line one\nline two"


def test_tool_result_text_handles_missing_content() -> None:
    assert tool_result_text({"status": "error"}) == ""
    assert tool_result_text({"content": None}) == ""
    assert tool_result_text({"content": [{"text": 42}]}) == ""


def test_exact_read_tool_surface_is_accepted_and_sorted() -> None:
    tools = [FakeTool("read_neo4j_cypher"), FakeTool("get_neo4j_schema")]
    selected = require_read_tools(tools)
    assert [tool.tool_name for tool in selected] == [
        "get_neo4j_schema",
        "read_neo4j_cypher",
    ]


@pytest.mark.parametrize(
    "tools",
    [
        [FakeTool("get_neo4j_schema")],
        [
            FakeTool("get_neo4j_schema"),
            FakeTool("read_neo4j_cypher"),
            FakeTool("write_neo4j_cypher"),
        ],
        [
            FakeTool("get_neo4j_schema"),
            FakeTool("read_neo4j_cypher"),
            FakeTool("read_neo4j_cypher"),
        ],
    ],
)
def test_tool_surface_fails_closed(tools: list[FakeTool]) -> None:
    with pytest.raises(ValueError, match="approved read-only set"):
        require_read_tools(tools)


def test_tool_result_records_decodes_rows() -> None:
    result = {
        "status": "success",
        "content": [{"text": '[{"hotel": "Cairo"}]'}],
    }
    assert tool_result_records(result) == [{"hotel": "Cairo"}]


@pytest.mark.parametrize(
    ("result", "message"),
    [
        ({"status": "error", "content": [{"text": "timed out"}]}, "timed out"),
        ({"status": "success", "content": []}, "no text content"),
        ({"status": "success", "content": [{"text": "not json"}]}, "non-JSON"),
        (
            {"status": "success", "content": [{"text": '{"hotel": "Cairo"}'}]},
            "list of objects",
        ),
    ],
)
def test_tool_result_records_rejects_bad_results(
    result: dict, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        tool_result_records(result)
