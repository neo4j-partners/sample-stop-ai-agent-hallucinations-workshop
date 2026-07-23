[< Back to Main README](../README.md)

# Semantic Tool Selection: Reducing Agent Hallucinations

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://python.org)
[![Strands Agents](https://img.shields.io/badge/Strands_Agents-1.27+-00B4D8.svg?style=flat)](https://strandsagents.com)
[![Neo4j](https://img.shields.io/badge/Neo4j-Tool_Graph-blue.svg?style=flat)](https://neo4j.com)

**AI agents with many similar tools waste tokens sending every schema on every call. This demo builds a travel agent with Strands Agents, stores the 31 tools as a graph in Neo4j, and uses Neo4j vector search to filter them down to the top 3 most relevant. The notebook runs three live questions and explains each selection with both the similarity scores and the graph relationships.**

**At a Glance**
- **Failure it stops:** wrong tool picks and wasted tokens when an agent carries many similar tools.
- **Neo4j:** stores the 31 tools as a graph and ranks them by vector similarity and workflow links.
- **AWS:** Amazon Bedrock runs the travel agent and embeds the tool descriptions.
- **You'll build:** a travel agent that filters its toolset down to the top 3 relevant tools per question.

Based on research: ["Internal Representations as Indicators of Hallucinations in Agent Tool Selection"](https://arxiv.org/abs/2601.05214)

## The Problem

Research ([Internal Representations, 2025](https://arxiv.org/abs/2601.05214)) identifies 5 critical agent failure modes when tools scale:

1. **Function selection errors** - Calling non-existent tools
2. **Function appropriateness errors** - Choosing semantically wrong tools
3. **Parameter errors** - Malformed or invalid arguments
4. **Completeness errors** - Missing required parameters
5. **Tool bypass behavior** - Generating outputs instead of calling tools

**The dual problem**:
- ❌ **Hallucination risk**: More tools = more inappropriate selections
- ❌ **Token waste**: Sending all tool descriptions on every call. The live token comparison below shows the traditional approach spending several thousand tokens per query, counting the tool schemas plus system prompt, user turn, tool results, and model output.

## The Solution

Semantic tool selection filters tools **before** the agent sees them:

![Semantic tool selection flow diagram](images/semantic-tool-selection.png)

**Measured result: a 61.5% token reduction over three live queries.** See [Verify Token Savings](#verify-token-savings) for the full figures and how to read them.

### Why Strands Agents Supports This at Scale

Strands Agents provides native capabilities that enable semantic tool selection in deployed applications (handling dynamic tools, preserving state, and managing concurrent requests):

**1. Dynamic Tool Swapping**
```python
# Add/remove tools at runtime without recreating the agent
agent.tool_registry.register_tool(new_tool)
agent.tool_registry.unregister_tool(old_tool)
```

**2. Conversation Memory Preservation**
```python
# Swap tools between queries while keeping conversation history
swap_tools(agent, new_tools)  # agent.messages preserved
```

**3. Runtime Tool Discovery**
- Agent picks up tool changes automatically at each event loop
- No manual refresh needed—just modify `tool_registry`
- Zero-downtime tool updates in production

Traditional frameworks require agent recreation to change tools, losing conversation state. Strands maintains memory while tools change dynamically.

Learn more: [Strands Tool Registry](https://strandsagents.com/docs/user-guide/concepts/tools/custom-tools/)

## Setup

### Prerequisites

- Python 3.9+
- [Strands Agents](https://strandsagents.com) — AI agent framework
- Neo4j connection from `../01-graphrag-demo` — the tool graph and the real hotel data live in the same Aura instance as Demo 01

### Model

This demo uses Amazon Bedrock by default (requires AWS credentials). Strands Agents uses Bedrock when no model is specified.

You can swap the model for any provider supported by Strands — Amazon Bedrock, Anthropic, Ollama, etc. See [Strands Model Providers](https://strandsagents.com/docs/user-guide/concepts/model-providers/amazon-bedrock/) for configuration.

### Configure Credentials

This demo needs AWS credentials for Bedrock and the Neo4j connection configured for Demo 01 in `../01-graphrag-demo/.env`. If the graph is not prepared yet, run `uv run ../01-graphrag-demo/prepare_graph.py` first. No API keys from any other provider are required.

### Install

```bash
uv venv && uv pip install -r requirements.txt
```

## Files

| File | Purpose |
|------|---------|
| `token_efficiency_analysis.ipynb` | **Main demo, the live path** - Three representative questions, each explained with similarity scores and graph relationships, plus one bounded agent call |
| `token_comparison_app.py` | **Token savings verification** - Standalone script to measure token reduction over 3 queries |
| `enhanced_tools.py` | The 31 travel agent tools, 2 of which read real Neo4j hotel data |
| `registry.py` | Semantic tool filtering backed by the Neo4j vector index |
| `tool_graph.py` | Tool graph schema, idempotent build, vector search, and workflow expansion |

## Run the Demo

Open `token_efficiency_analysis.ipynb` in your IDE (VS Code, Kiro, or any editor with notebook support).

**What it does**:
1. Builds the Neo4j tool graph and its vector index (idempotent)
2. Runs three representative questions: a hotel search, a booking, and a cancellation
3. For each question, prints the top-3 vector candidates with similarity scores and the graph-expanded tools with the relationship that caused each inclusion
4. Ends with one live agent call using only the 3 selected tools

The three questions were chosen because their top-3 candidates are stable across repeated runs against the live graph, so they are safe to run in front of an audience.

## Verify Token Savings

Run the standalone token comparison script for a live 3-query measurement:

```bash
uv run token_comparison_app.py
```

**What it measures**:
- Compares 3 approaches: Traditional, Semantic, Semantic+Memory
- Shows actual token usage per query
- Demonstrates memory accumulation cost
- Verifies `swap_tools()` preserves conversation history

**Measured output**, real stdout from `token_comparison_app.py` over 3 queries:

```
Total tokens:
  Traditional:      17182 tokens
  Semantic:          6614 tokens (+61.5%)
  Semantic+Memory:   8170 tokens (+52.5%)

Query                                             Trad      Sem      Mem    Saved
----------------------------------------------------------------------
What's the weather in Paris?                      6803     1737     1720     5083
Find flights from NYC to London                   7001     1953     2317     4684
Book a hotel in Rome for John                     3378     2924     4133     -755
```

**These numbers are LLM output and vary between runs.** Expect roughly 60-75% reduction for the semantic approach depending on query mix and turn count, not a single fixed figure.

**Where the savings come from**: the tool schemas are the only part of the prompt that semantic filtering removes. Dropping 31 schemas to 3 is the constant-size win. System prompt, user turn, tool results, and model output are unaffected and are included in the figures above, which is why the measured reduction is below what a schema-only calculation predicts.

**Bounded conversation history**: the memory variant trims to the last 3 turns via `trim_history()`. Without a bound, the full transcript is resent on every call, cost grows quadratically with turn count, and the memory variant becomes more expensive than sending all 31 tools every time.

**A note on accuracy**: this demo measures token cost, not tool-selection accuracy. Filtering can only help when the correct tool survives the top-3 cut; when vector search ranks the right tool fourth or lower, the agent never sees it and cannot recover. That makes `top_k` the parameter to tune against your own tool set and query mix. The token reduction is the result this demo supports; treat accuracy as something to evaluate separately on your own tools.

## How It Works

### Traditional Approach (Baseline)
```python
# Agent sees ALL 31 tools on every query
agent = Agent(tools=ALL_TOOLS, model=model)
agent("How much does Hotel Marriott cost?")
# ~6,800 tokens/query for the weather query in the token comparison run
# Risk: Picks wrong tool from 31 options
```

### Semantic Approach (Optimized)
```python
# 1. Build the Neo4j tool graph once (idempotent)
build_index(ALL_TOOLS)

# 2. Filter tools per query
query = "How much does Hotel Marriott cost?"
relevant_tools = search_tools(query, top_k=3)
# Returns: [get_hotel_pricing, get_hotel_details, search_hotels]

# 3. Agent sees only 3 relevant tools
agent = Agent(tools=relevant_tools, model=model)
agent(query)
# ~1,700 tokens/query with the top-3 filter
# Risk: Picks correct tool from 3 focused options
```

### Production Pattern: Preserving Conversation Memory

For multi-turn conversations, use Strands' native tool swapping to maintain conversation history:

```python
def swap_tools(agent, new_tools):
    """Swap agent's tools without losing conversation memory"""
    agent.tool_registry.registry.clear()
    agent.tool_registry.dynamic_tools.clear()
    for tool in new_tools:
        agent.tool_registry.register_tool(tool)

# Create agent once
agent = Agent(tools=initial_tools, model=model)

# Multi-turn conversation with dynamic tool filtering
for query in queries:
    selected = search_tools(query, top_k=3)
    swap_tools(agent, selected)  # Tools change, agent.messages preserved
    agent(query)  # Full conversation history intact
```

**Why this works**: Strands calls `tool_registry.get_all_tools_config()` at each event loop cycle, automatically picking up runtime changes. No agent recreation needed.

**Key advantages**:
- Zero conversation loss across tool swaps
- Same agent instance handles all queries
- Add/remove tools between any two queries
- Production-ready for long conversations

Learn more: [Strands Agent Architecture](https://strandsagents.com/docs/user-guide/concepts/agents/agent-loop/)

- [Search for tools in your Amazon Bedrock AgentCore gateway with a natural language query](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-using-mcp-semantic-search.html?trk=87c4c426-cddf-4799-a299-273337552ad8&sc_channel=el)

## The Neo4j Tool Graph

The tools live in the same Aura instance as the Demo 01 hotel knowledge graph:

```
(:Tool {name, description, embedding, domain, workshop})
(:Tool)-[:IN_DOMAIN]->(:Domain)
(:Tool)-[:REQUIRES]->(:Concept)
(:Tool)-[:PRODUCES]->(:Concept)
```

- **Vector search.** The `tool_description_embeddings` index (1024 dimensions, cosine, Nova 2 embeddings) serves the top-k candidate selection used by all three tests.
- **Workflow expansion.** A concept one tool `PRODUCES` and another tool `REQUIRES` is a workflow edge: `book_hotel` produces a `booking`, `process_payment` requires one. The notebook's three live questions walk these relationships from the vector candidates and report, for each expanded tool, the relationship that caused its inclusion.
- **Ownership.** Every tool-graph node carries `workshop: 'stop-ai-agent-hallucinations'`, so scoped cleanup can remove the tool graph without touching the hotel domain graph.
- **Idempotent build.** `build_index(ALL_TOOLS)` re-embeds and replaces the tool graph in place, removes tools no longer in the list, and verifies the vector index is online.

## Enhanced Tools with Real Data

Two of the 31 tools are connected to the Neo4j hotel database:

```python
@tool
def search_real_hotels(country: str, min_rating: float = 0.0) -> str:
    """Search real hotels in a specific country from our database."""
    # Executes Cypher query on Neo4j

@tool
def get_top_hotels(limit: int = 5) -> str:
    """Get top-rated hotels globally."""
    # Real aggregation from graph database
```

These tools return real graph data, so the agent's hotel answers are grounded in the knowledge graph rather than invented.

## Research Background

This demo implements findings from:
- [Internal Representations as Indicators of Hallucinations](https://arxiv.org/abs/2601.05214) - Tool selection hallucinations increase with tool count
- Production systems report 89% token reduction ([rconnect.tech](https://www.rconnect.tech/blog/semantic-tool-selection-guide))

## Frequently Asked Questions

### How much does semantic tool selection reduce token usage?

**Measured in this demo: 61.5% over three live queries (`token_comparison_app.py`).** This figure is LLM output and moves between runs, so treat 60-75% as the range this demo reproduces rather than a fixed number.

Neo4j vector filtering sends the top 3 tool schemas instead of all 31. That saving is constant per query, but it applies only to the schema portion of the prompt. System prompt, user turn, tool results, and model output are unchanged, which is why the end-to-end reduction lands below a schema-only estimate.

A separate published figure of **89%** comes from a third-party writeup, [rconnect.tech](https://www.rconnect.tech/blog/semantic-tool-selection-guide). It is a citation from someone else's production system, not a result this demo produces.

### Does filtering tools break conversation memory?

No. Strands Agents' `swap_tools()` function changes the available tools at runtime without recreating the agent, preserving conversation history in `agent.messages`. This is a key production advantage over frameworks that require agent recreation to change tools.

Preserved history is not free. It is resent on every call, so an unbounded transcript grows cost quadratically with turn count and will overtake the saving from filtering tools. This demo bounds history to the last 3 turns with `trim_history()`. In the three-query comparison, the bounded memory variant uses 8,170 tokens against a 17,182-token traditional baseline, a 52.5% reduction. It costs more than stateless semantic filtering at 6,614 tokens, which is the price of keeping the conversation.

### Does semantic filtering improve tool selection accuracy?

**This demo does not measure accuracy; it measures token cost.** Filtering can only help if the correct tool survives the top-3 cut, so accuracy depends on your own tool set and query mix. If the correct tool falls outside the top 3, the agent cannot call it at all, which makes `top_k` the parameter to tune. The reason to adopt semantic filtering here is the token reduction, which is large and reproduces across runs; treat accuracy as something to evaluate separately on your own tools.

### Can I use semantic tool selection with other agent frameworks?

Yes. The core pattern, embedding tool descriptions into a vector index and filtering by cosine similarity before the LLM sees them, is framework-agnostic. You can implement it in LangGraph, CrewAI, AutoGen, or any framework. Amazon Bedrock AgentCore Gateway also provides built-in [MCP semantic routing](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-using-mcp-semantic-search.html?trk=87c4c426-cddf-4799-a299-273337552ad8&sc_channel=el) for production workloads.

---

## Navigation

- **Previous:** [Demo 01 - Graph-RAG vs RAG](../01-graphrag-demo/)
- **Next:** [Demo 03 - Multi-Agent Validation](../03-multiagent-demo/) — Cross-validate tool selections with Executor → Validator → Critic

---

## Security

If you discover a potential security issue in this project, notify AWS/Amazon Security via the [vulnerability reporting page](https://aws.amazon.com/security/vulnerability-reporting/?trk=87c4c426-cddf-4799-a299-273337552ad8&sc_channel=el). Please do **not** create a public GitHub issue.

---

## License

This library is licensed under the MIT-0 License. See the [LICENSE](../LICENSE) file for details.
