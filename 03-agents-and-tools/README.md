[< Back to Main README](../README.md)

# Lab 3: Agents and Tools

Lab 2 produced a retriever that returns connected facts. Lab 3 gives it a caller. One notebook covers the [Strands Agents](https://strandsagents.com) concepts the rest of the workshop depends on: an agent, tools behind the `@tool` decorator, lifecycle hooks that block a tool call the model already decided to make, and a multi-agent swarm. It closes by assembling `hotel_agent`, the one named agent Labs 4 and 5 carry forward.

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://python.org)
[![Strands Agents](https://img.shields.io/badge/Strands_Agents-1.27+-00B4D8.svg?style=flat)](https://strandsagents.com)
[![Amazon Bedrock](https://img.shields.io/badge/Amazon-Bedrock-FF9900.svg?style=flat&logo=amazon-aws)](https://aws.amazon.com/bedrock/)
[![Neo4j](https://img.shields.io/badge/Neo4j-Graph--RAG-4581C3.svg?style=flat&logo=neo4j)](https://neo4j.com)

**At a Glance**
- **Failure it prevents:** an agent that answers about a hotel from its own priors instead of calling a grounded tool.
- **Neo4j:** the Lab 2 `HybridCypherRetriever` reached from inside a Strands `@tool`. No new graph structure is added.
- **AWS:** Bedrock Claude Sonnet 5 runs every agent turn, tool selection, and swarm handoff.
- **You'll build:** small agents for each concept, then `hotel_agent`, carrying the real retriever tool and a hook-guarded booking tool.

> **Where this is going.** Sections 1 through 5 each build a small agent to make one point. Section 6 assembles `hotel_agent` from three of those pieces, and Lab 4 registers the reservation write onto that agent by name.

---

## The one notebook

`3.1_strands_primer.ipynb` has 26 cells. Each teaching section builds its own agent rather than adding tools to a single agent that grows through the notebook, so a section can be read and run on its own. The closing section is the exception: it deliberately takes three pieces from earlier sections and drops the rest. The Summary table is the last cell, after that closing section.

Every agent in the notebook is built with an explicit `model`. Cell 1 binds `MODEL_ID`, which reads the `MODEL_ID` environment variable and defaults to `us.anthropic.claude-sonnet-5`, and each `Agent(...)` passes it. Strands has a default model of its own, so an agent built without `model` runs that one instead, silently and on a different Claude version than the rest of the workshop.

| Section | What it builds | What carries forward |
|---------|----------------|----------------------|
| 1. Creating an Agent | `agent_travel`, a travel assistant with a system prompt and no tools | The `Agent` constructor and the pinned `MODEL_ID` |
| 2. Model Providers | `agent_bedrock`, taking the model id as a string, and `agent_specific`, taking a `BedrockModel` built from the same id | The two ways to pin the model `hotel_agent` uses |
| 3. Creating Tools | `agent_tools`, with three `@tool` functions: `search_hotels`, `book_hotel`, and `search_hotel_knowledge_tool` | `search_hotel_knowledge_tool` |
| 3.5. Token Counting | `agent_metrics`, reading `result.metrics.accumulated_usage` for input, output, and total tokens | Nothing. Useful in any lab where cost matters |
| 4. Lifecycle Hooks | `book_room`, `MaxGuestsHook`, and the pair `agent_no_hook` and `agent_with_hook` | `MaxGuestsHook` and `book_room` |
| 5. Multi-Agent Swarms | `Swarm(nodes=[executor, validator, critic], max_handoffs=5)` over a `lookup_hotel` tool | Nothing. The swarm stays in this notebook |
| 6. Assembling `hotel_agent` | `hotel_agent`, with the retriever tool, `book_room`, and `MaxGuestsHook` attached | Labs 4 and 5 |

---

## One of the three tools is real

Section 3 builds a three-tool agent so the participant can watch tool selection happen. `search_hotels` and `book_hotel` return invented strings, which is all a primer needs to show selection working. The third tool is the Lab 2 hybrid retrieval path behind a `@tool` boundary:

```python
from workshop.hybrid_retrieval import search_hotel_knowledge

@tool
def search_hotel_knowledge_tool(query: str) -> str:
    """Look up amenities, ratings, and policies for a specific named hotel."""
    return json.dumps(search_hotel_knowledge(query), ensure_ascii=False)
```

`search_hotel_knowledge` is the frozen one-field contract from the shared `workshop` package. It runs the `HybridCypherRetriever` over the vector and full-text indexes, applies the one reviewed Cypher traversal, and returns bounded JSON facts rather than prose: chunk evidence, the hybrid score, the query terms found verbatim in that evidence, and the hotel's stable `hotel_id`, name, address, guest rating, and amenities. The tool exposes `query` and nothing else, so the model cannot pick a retriever, a ranker, or a result count.

The three tests in section 3 read as a set. Test 1 asks for hotels in Lisbon under $100 and the agent calls `search_hotels`. Test 2 asks what amenities AnyCompany Cairo Nile View has and the agent calls `search_hotel_knowledge_tool` instead. Test 3 books a room and the agent calls `book_hotel`. Comparing the answers from tests 1 and 2 is the point: one is invented, one came out of the graph.

---

## Where the guest limit lives

Section 4 pairs an unguarded agent against a guarded one. `agent_no_hook` books 15 guests without complaint. `agent_with_hook` cannot, because `MaxGuestsHook` implements `HookProvider`, registers a callback on `BeforeToolCallEvent`, and sets `event.cancel_tool` before `book_room` executes:

```python
def check(self, event: BeforeToolCallEvent) -> None:
    if event.tool_use["name"] == "book_room":
        guests = event.tool_use["input"].get("guests", 1)
        if guests > 10:
            event.cancel_tool = f"BLOCKED: {guests} guests exceeds maximum of 10"
```

The block happens at the framework level, after the model has already decided to call the tool, so the model receives the cancellation message instead of a tool result and cannot argue its way past it. That is a real improvement over the same rule written into a system prompt.

Note where the number is. The limit of 10 is a Python literal inside `MaxGuestsHook`, in the same file as the agent that enforces it. Changing the limit means editing and redeploying agent code, and every other caller of the same business rule keeps its own copy. Lab 4's argument starts from that observation.

---

## Section 6: `hotel_agent`

The closing section assembles the agent the rest of the workshop uses. It takes exactly three pieces from the primer, the real retriever tool from section 3 and the `book_room` tool and the hook from section 4, and leaves the simulated tools and the swarm behind:

```python
hotel_agent = Agent(
    name="hotel_agent",
    model=MODEL_ID,
    tools=[search_hotel_knowledge_tool, book_room],
    hooks=[MaxGuestsHook()],
    system_prompt=(...GROUNDING_INSTRUCTIONS),
)
```

`GROUNDING_INSTRUCTIONS` is imported from `workshop.hybrid_retrieval`, so the abstention wording is the same text Lab 2 used and Lab 5 deploys. It tells the agent to answer only from returned chunk evidence and graph fields, and to decline rather than infer live inventory, guaranteed availability, or a completed booking.

Two questions close the notebook. The first is the workshop's hero question about amenities and guest rating for AnyCompany Cairo Nile View, which the graph can answer. The second asks to book that hotel for 15 guests, which `MaxGuestsHook` cancels before `book_room` runs.

Lab 4 registers `create_reservation_request` onto this same `hotel_agent` by name, which is what makes Labs 3 and 4 one story rather than two.

---

## Running offline

Cell 1 binds `MODEL_ID` and checks the environment once, setting two flags. `AGENT_READY` is true when boto3 finds AWS credentials. `GRAPH_READY` additionally requires `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD`. Every cell that invokes a model is guarded by one of them and prints a skip message instead of raising, so the notebook runs top to bottom with no credentials at all. Sections 1 through 5 still construct their agents while doing so, since constructing an `Agent` makes no service call. Section 6 is the exception: `hotel_agent` is built inside the `AGENT_READY` branch, so with no credentials it is never constructed at all and the two cells that follow skip as well. The two cells that use the real retriever are the ones gated on `GRAPH_READY`.

---

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- AWS credentials with [Amazon Bedrock](https://aws.amazon.com/bedrock/) access and Claude Sonnet 5 enabled in your region
- The graph Lab 1 built, plus the repo-root `.env`, for the two grounded-retrieval cells. See [`00-setup/README.md`](../00-setup/README.md)

### Step 1: Install dependencies

```bash
cd 03-agents-and-tools
uv venv && uv pip install -r requirements.txt
```

`requirements.txt` declares two requirements: `-e ../workshop`, which brings the retriever this lab puts behind `@tool`, and `strands-agents>=1.27.0`. The shared package supplies neo4j, neo4j-graphrag, and boto3.

### Step 2: Confirm the retriever imports

```bash
cd 03-agents-and-tools
uv run python -c "from workshop.hybrid_retrieval import search_hotel_knowledge; print('retriever import OK')"
```

This proves the editable install of the shared package resolved. It opens no connection, so it works with or without credentials.

### Step 3: Run the notebook

Open `3.1_strands_primer.ipynb` in VS Code, Kiro, or any editor with notebook support, and run the cells in order.

This lab has no Python test files. The notebook is registered with the shared acceptance runner as lab 3:

```bash
uv run setup/run_notebooks.py --list
```

Run that from the repository root. The root [README](../README.md) documents how to execute a lab through the runner.

---

## Troubleshooting

**Bedrock access denied, or `AccessDeniedException` on the first agent call:** read the model id in the exception before doing anything else. If it is the id cell 1 printed, enable that model in your region through the [Bedrock Model Access console](https://console.aws.amazon.com/bedrock/home#/modelaccess), and confirm `AWS_REGION` in the repo-root `.env` matches the region where you enabled it. If it is some other Claude id, the agent that raised was built without a `model` argument and fell through to the Strands default, so enabling the workshop model will not clear it: add `model=MODEL_ID` to that `Agent(...)` call. Every section calls a model, so this surfaces on the first agent cell in section 1 rather than partway through.

**The retriever tool returns an empty list, or the agent says it cannot determine the answer for a hotel you know is in the corpus:** the graph is missing or was built with different embedding settings. `search_hotel_knowledge` returns only what is connected in the graph, and an empty result is the honest answer to a query with nothing behind it. Run Lab 1's `1.1_build_graph.ipynb` and then retry section 3's Test 2.

**Cells print `Skipping: needs AWS credentials and the graph Lab 1 built`:** that is `GRAPH_READY` reporting absent configuration rather than an empty graph. Check that `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD` are set in the repo-root `.env`. Inside the hosted Workshop Studio environment, confirm whether `NEO4J_USER` was written instead of `NEO4J_USERNAME`.

**Model alternatives:** set the `MODEL_ID` environment variable, or edit the `MODEL_ID` line in cell 1. Every `Agent` in the notebook passes that one value. See [Strands Model Providers](https://strandsagents.com/docs/user-guide/concepts/model-providers/amazon-bedrock/).

---

## References

- [Strands Agents documentation](https://strandsagents.com)
- [Custom tools](https://strandsagents.com/docs/user-guide/concepts/tools/custom-tools/)
- [Hooks](https://strandsagents.com/docs/user-guide/concepts/agents/hooks/)
- [Multi-agent](https://strandsagents.com/docs/user-guide/concepts/multi-agent/)
- [Agent metrics](https://strandsagents.com/docs/user-guide/concepts/agents/metrics/)

---

## Navigation

- **Previous:** [Lab 2: Retrieval](../02-retrieval/)
- **Next:** [Lab 4: The grounded write](../04-grounded-write/), which registers the idempotent reservation write onto `hotel_agent` and replaces the hook's Python literal with a rule read from the graph.

---

## Contributing

Contributions are welcome. See [CONTRIBUTING](../CONTRIBUTING.md) for more information.

## Security

If you discover a potential security issue in this project, notify AWS/Amazon Security via the [vulnerability reporting page](https://aws.amazon.com/security/vulnerability-reporting/). Please do **not** create a public GitHub issue.

## License

This library is licensed under the MIT-0 License. See the [LICENSE](../LICENSE) file for details.

> Last updated: August 2026 | Strands Agents 1.27+ | Python 3.12+
