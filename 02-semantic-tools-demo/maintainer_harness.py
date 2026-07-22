#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "strands-agents>=1.27.0",
#     "boto3>=1.35.0",
#     "neo4j>=5.28.0",
#     "python-dotenv>=1.0.1",
# ]
# ///
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Maintainer validation harness for Demo 02 semantic tool selection.

MAINTAINER-ONLY. This is not part of the live workshop path. The notebook
`token_efficiency_analysis.ipynb` shows three representative questions; this
script runs the full 24-query evaluation that produces the measured figures
quoted there and in the README.

It builds the Neo4j tool graph, runs all 24 queries through three variants,
and scores tool selection against ground truth:

    Traditional       all 31 tools sent on every call
    Semantic          top 3 tools from the Neo4j vector index
    Semantic+Memory   top 3 tools, one reused agent, history bounded to 3 turns

Each query is a live Bedrock agent call, so a full run makes roughly 72 agent
invocations and takes several minutes. Requires AWS credentials for Bedrock
and the Neo4j connection configured in ../01-graphrag-demo/.env.

Usage:
    uv run maintainer_harness.py             # full 24-query run (default)
    uv run maintainer_harness.py --limit 3   # smoke run on the first 3 queries

Read the accuracy result carefully. The headline result is the token
reduction, which is large and reproducible. Accuracy is measured because it
is what a cost optimization is most likely to damage, not because filtering
is expected to improve it. Across runs so far the accuracy difference between
Traditional and Semantic has landed within a single query out of 24, which is
too small a sample to call a difference in either direction. This script
prints whatever it measures, including a decrease, and it should be left that
way. Do not adjust the query set until the number flatters the technique.
"""

from __future__ import annotations

import argparse

from strands import Agent

from enhanced_tools import ALL_TOOLS
from registry import (
    build_index,
    search_tools,
    swap_tools,
    trim_history,
    usage_delta,
    usage_snapshot,
)

# Conversation turns the memory agent retains. Unbounded history makes token
# cost grow quadratically across a 24-query run and lose to the baseline.
MEMORY_MAX_TURNS = 3

PROMPT = "You are a travel assistant. Use the correct tool to answer questions."

# Ground truth: (query, tool the query asks for). Two queries name tools that
# do not exist in ALL_TOOLS (confirm_booking, cancel_booking), so they fail in
# every variant and cap accuracy at 22/24. They are kept because they hit all
# three variants equally and because the figures quoted in the README were
# measured against exactly this list. Do not edit the list without
# re-measuring and updating every quoted number.
TESTS = [
    # Hotel queries - semantic filtering helps agent focus
    ("Search hotels in Barcelona", "search_hotels"),
    ("Find real hotels in France", "search_real_hotels"),
    ("Show me top rated hotels worldwide", "get_top_hotels"),
    ("What's the price for Grand Hotel Paris?", "get_hotel_pricing"),
    ("What amenities does the Hilton have?", "get_hotel_details"),
    ("Read reviews for Marriott Downtown", "search_hotel_reviews"),
    ("Is the Sheraton available tomorrow?", "check_hotel_availability"),
    ("Check availability March 15 to March 18", "check_hotel_availability_dates"),
    ("Compare hotel prices in Lisbon for next week", "compare_hotel_prices"),
    # Flight queries - similar tool names cause confusion with all 31 tools
    ("Find flights from NYC to Tokyo", "search_flights"),
    ("How much do flights to Paris cost?", "search_flight_prices"),
    ("Show me flight details for AA123", "get_flight_details"),
    ("Is flight BA456 on time?", "get_flight_status"),
    ("How many seats left on United 789?", "check_flight_availability"),
    # Booking workflow - semantic approach surfaces right tool sequence
    ("Book AnyCompany Hotel for John Smith", "book_hotel"),
    ("Book flight AA123 for Jane Doe", "book_flight"),
    ("Process payment of $500", "process_payment"),
    ("Confirm my booking BK-12345", "confirm_booking"),
    ("Cancel reservation BK-67890", "cancel_booking"),
    # Travel utilities - clear intent, semantic finds exact match
    ("Convert 500 USD to EUR", "get_currency_exchange"),
    ("Do I need a visa for Spain from USA?", "get_travel_documents"),
    ("What's the weather in Tokyo?", "get_weather"),
    ("Show me weather forecast for London", "get_weather_forecast"),
    ("Any weather alerts in Miami?", "get_weather_alerts"),
]


def run_and_capture_with_tokens(agent: Agent, query: str) -> tuple[list[str], dict]:
    """Run the agent and capture tool calls plus this call's token usage.

    accumulated_usage is the agent's lifetime counter, so it is differenced
    against a pre-call snapshot. Reading it directly would make the reused
    memory agent report a running total and sum to a triangular number.
    """
    before = usage_snapshot(agent)
    result = agent(query)

    tools = list(result.metrics.tool_metrics.keys()) if result.metrics else []

    tokens = {"input": 0, "output": 0, "total": 0}
    if result.metrics:
        used = usage_delta(agent, before)
        tokens["input"] = used["inputTokens"]
        tokens["output"] = used["outputTokens"]
        tokens["total"] = used["totalTokens"]

    return tools, tokens


def run_traditional(tests: list[tuple[str, str]]) -> list[dict]:
    """Fresh agent per query, all tools sent every call."""
    print("=" * 80)
    print(f"TEST 1: TRADITIONAL - {len(ALL_TOOLS)} tools every query")
    print("=" * 80)

    results = []
    for query, expected in tests:
        agent = Agent(tools=ALL_TOOLS, system_prompt=PROMPT)
        tools, tokens = run_and_capture_with_tokens(agent, query)
        results.append(
            {
                "query": query,
                "expected": expected,
                "selected": None,
                "actual": tools,
                "correct": expected in tools,
                "tokens": tokens,
            }
        )
    return results


def run_semantic(tests: list[tuple[str, str]]) -> list[dict]:
    """Fresh agent per query, top-3 tools from the Neo4j vector index."""
    print("=" * 80)
    print("TEST 2: SEMANTIC - Top-3 tools per query")
    print("=" * 80)

    results = []
    for query, expected in tests:
        selected = search_tools(query, top_k=3)
        agent = Agent(tools=selected, system_prompt=PROMPT)
        tools, tokens = run_and_capture_with_tokens(agent, query)
        results.append(
            {
                "query": query,
                "expected": expected,
                "selected": [t.__name__ for t in selected],
                "actual": tools,
                "correct": expected in tools,
                "tokens": tokens,
            }
        )
    return results


def run_memory(tests: list[tuple[str, str]]) -> tuple[list[dict], Agent]:
    """One reused agent, tools swapped per query, history bounded."""
    print("=" * 80)
    print("TEST 3: SEMANTIC + MEMORY - Single agent, dynamic tool swapping,")
    print(f"        conversation history bounded to {MEMORY_MAX_TURNS} turns")
    print("=" * 80)

    initial_tools = search_tools(tests[0][0], top_k=3)
    memory_agent = Agent(tools=initial_tools, system_prompt=PROMPT)

    results = []
    for query, expected in tests:
        selected = search_tools(query, top_k=3)
        swap_tools(memory_agent, selected)
        trim_history(memory_agent, max_turns=MEMORY_MAX_TURNS)
        tools, tokens = run_and_capture_with_tokens(memory_agent, query)
        results.append(
            {
                "query": query,
                "expected": expected,
                "selected": [t.__name__ for t in selected],
                "actual": tools,
                "correct": expected in tools,
                "tokens": tokens,
                "messages": len(memory_agent.messages),
            }
        )
    return results, memory_agent


def print_result_table(title: str, results: list[dict]) -> None:
    """Print the per-query summary table for one variant."""
    correct = sum(r["correct"] for r in results)
    total_tokens = sum(r["tokens"]["total"] for r in results)

    print()
    print("=" * 80)
    print(f"{title} SUMMARY TABLE")
    print("=" * 80)
    header = (
        f"{'#':>3} {'Query':<45} {'Expected':<20} "
        f"{'Called':<20} {'Result':>6} {'Tokens':>7}"
    )
    print(f"\n{header}")
    print("-" * 80)

    for i, r in enumerate(results, 1):
        status = "OK" if r["correct"] else "MISS"
        query_short = r["query"][:44]
        expected = r["expected"][:19]
        actual = ", ".join(r["actual"][:2])[:19] if r["actual"] else "NO TOOL"
        tokens = r["tokens"]["total"]
        print(
            f"{i:3} {query_short:<45} {expected:<20} "
            f"{actual:<20} {status:>6} {tokens:7,}"
        )
        if not r["correct"] and r["selected"] is not None:
            print(f"    Available tools: [{', '.join(r['selected'])}]")
            if r["expected"] not in r["selected"]:
                print("    Correct tool NOT in top-3 (vector filtering issue)")

    print("-" * 80)
    print(
        f"Total: {correct}/{len(results)} correct "
        f"({100 * correct / len(results):.1f}%), {total_tokens:,} tokens"
    )


def print_comparison(
    trad: list[dict], sem: list[dict], mem: list[dict], memory_agent: Agent
) -> None:
    """Print the accuracy and token comparison across the three variants."""
    n = len(trad)
    trad_correct = sum(r["correct"] for r in trad)
    sem_correct = sum(r["correct"] for r in sem)
    mem_correct = sum(r["correct"] for r in mem)
    trad_tokens = sum(r["tokens"]["total"] for r in trad)
    sem_tokens = sum(r["tokens"]["total"] for r in sem)
    mem_tokens = sum(r["tokens"]["total"] for r in mem)

    print()
    print("=" * 80)
    print("COMPARATIVE ANALYSIS")
    print("=" * 80)

    print("\nAccuracy Comparison:")
    print(f"   Traditional:      {trad_correct}/{n} ({100 * trad_correct / n:.1f}%)")
    print(f"   Semantic:         {sem_correct}/{n} ({100 * sem_correct / n:.1f}%)")
    print(f"   Semantic+Memory:  {mem_correct}/{n} ({100 * mem_correct / n:.1f}%)")

    # Print the measured accuracy gap and its sample size together. A gap of
    # one or two queries out of 24 is not a result in either direction, and
    # saying so here is what stops the token reduction from being read as an
    # accuracy claim too.
    gap = sem_correct - trad_correct
    if gap == 0:
        print("   Same accuracy as Traditional")
    else:
        direction = "above" if gap > 0 else "below"
        plural = "y" if abs(gap) == 1 else "ies"
        print(
            f"   Semantic scored {abs(gap)} quer{plural} "
            f"{direction} Traditional, out of {n}."
        )
        if abs(gap) <= 2:
            print(f"   Within noise at n={n}. Not evidence that filtering")
            print("   helps or hurts accuracy. The token reduction below is the")
            print("   result this harness establishes.")

    print("\nToken Consumption:")
    print(f"   Traditional:      {trad_tokens:,} tokens ({trad_tokens / n:.0f} avg)")
    print(f"   Semantic:         {sem_tokens:,} tokens ({sem_tokens / n:.0f} avg)")
    print(f"   Semantic+Memory:  {mem_tokens:,} tokens ({mem_tokens / n:.0f} avg)")

    if trad_tokens > 0:
        sem_savings = trad_tokens - sem_tokens
        mem_savings = trad_tokens - mem_tokens

        def verdict(saved: int) -> str:
            pct = 100 * saved / trad_tokens
            word = "reduction" if saved > 0 else "INCREASE"
            return f"{abs(saved):,} tokens ({abs(pct):.1f}% {word})"

        print("\nToken Savings (measured this run, not a cited figure):")
        print(f"   Semantic vs Traditional:  {verdict(sem_savings)}")
        print(f"   Memory vs Traditional:    {verdict(mem_savings)}")
        if mem_savings <= 0:
            print("   Memory loses to the baseline even with bounded history:")
            print("   conversation context outweighs the tool-schema saving here.")
        if mem_tokens > sem_tokens:
            overhead = mem_tokens - sem_tokens
            print(
                f"   Memory overhead:          +{overhead:,} tokens "
                "(conversation history)"
            )

    print(
        f"\n   Memory agent finished with {len(memory_agent.messages)} messages "
        f"(bounded to {MEMORY_MAX_TURNS} turns, "
        f"peak {max(r['messages'] for r in mem)})"
    )

    print("\nPer-Query Token Breakdown:")
    print(f"\n{'Query':<50} {'Trad':>8} {'Sem':>8} {'Mem':>8} {'Saved':>8}")
    print("-" * 80)
    for i in range(n):
        query = trad[i]["query"][:49]
        t = trad[i]["tokens"]["total"]
        s = sem[i]["tokens"]["total"]
        m = mem[i]["tokens"]["total"]
        print(f"{query:<50} {t:8} {s:8} {m:8} {t - s:8}")


def print_error_analysis(trad: list[dict], sem: list[dict], mem: list[dict]) -> None:
    """Print every miss, labeling the ones the top-3 cut caused."""
    print()
    print("=" * 80)
    print("ERROR ANALYSIS")
    print("=" * 80)

    for title, results in (
        ("Traditional", trad),
        ("Semantic", sem),
        ("Semantic+Memory", mem),
    ):
        print(f"\n{title} Errors:")
        errors = [r for r in results if not r["correct"]]
        if not errors:
            print("   No errors")
            continue
        for r in errors:
            print(f"   MISS '{r['query'][:60]}'")
            print(f"      Expected: {r['expected']}, Got: {r['actual']}")
            if r["selected"] is not None:
                print(f"      Available: {r['selected']}")
                if r["expected"] not in r["selected"]:
                    print("      Correct tool NOT in top-3 (vector filtering issue)")


def main() -> int:
    """Build the tool graph, run the three variants, and print the analysis."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Run only the first N queries (smoke run). "
            "The default is the full 24-query evaluation."
        ),
    )
    args = parser.parse_args()

    tests = TESTS if args.limit is None else TESTS[: args.limit]
    if not tests:
        parser.error("--limit must be at least 1")

    print("=" * 80)
    print("DEMO 02 MAINTAINER HARNESS (not part of the live workshop path)")
    print(f"Queries: {len(tests)} of {len(TESTS)}, tool pool: {len(ALL_TOOLS)}")
    print("Goal: measure the token/accuracy tradeoff, not assume filtering")
    print("      improves accuracy")
    print("=" * 80)
    print()

    build_index(ALL_TOOLS)
    print()

    trad = run_traditional(tests)
    print_result_table("TEST 1 (TRADITIONAL)", trad)

    print()
    sem = run_semantic(tests)
    print_result_table("TEST 2 (SEMANTIC)", sem)

    print()
    mem, memory_agent = run_memory(tests)
    print_result_table("TEST 3 (SEMANTIC+MEMORY)", mem)

    print_comparison(trad, sem, mem, memory_agent)
    print_error_analysis(trad, sem, mem)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
