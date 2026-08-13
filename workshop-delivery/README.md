# Facilitator Delivery Guide

Joint Neo4j and AWS workshop: "How to Stop AI Agent Hallucinations, plus Production on Amazon Bedrock AgentCore."

This guide covers what to schedule, in what order, what to verify before an event, and what to cut when time runs short.

The story is one sentence: Neo4j owns the connected data and AWS owns the reasoning and the hosting. Neo4j holds the hotel knowledge graph, the retrieval indexes, the production rule, the reservation requests, and the optional inspectable memory. AWS supplies Bedrock models and embeddings, AgentCore Runtime and Gateway, Secrets Manager, IAM, Lambda, and CloudWatch observability.

The repository is one sequential path of six labs, not a set of independent demos. Each lab consumes what the previous one produced, so the delivery order is fixed. The scheduling decisions left to you are how much of Lab 1's corpus to build, which optional notebooks to include, and whether Lab 5 is hands-on or facilitator-led.

**The partnership peaks twice, and saying so is part of the delivery.** Lab 1 is the first peak, where Bedrock extraction and Neo4j storage sit in the same call path through `SimpleKGPipeline`. Labs 2 through 4 are Neo4j-weighted with Bedrock in a supporting role. Lab 5 is the second and higher peak, wrapping the full AWS operational surface around unchanged Neo4j retrieval. Name the peak at Lab 1 and name it again at Lab 5.

Why the split matters: an agent that cannot trace its answer to connected data cannot be trusted in front of a guest. Neo4j makes the relationships traversable and AWS supplies the reasoning, so every answer is grounded in evidence the graph can defend.

Reference documents:

- The root [`README.md`](../README.md) is the source of truth for the lab table, the Platform Responsibilities and Data Ownership tables, and the two hero questions.
- [`architecture.md`](architecture.md) in this folder holds the architecture visual.
- [`04-grounded-write/CONTRACTS.md`](../04-grounded-write/CONTRACTS.md) holds the frozen retrieval and reservation-command contracts. It predates the six-lab renumbering and still says "Demo 06"; `workshop/src/workshop/contracts.py` is the authority on values.
- [`05-agentcore-deploy/advanced-deployment/DEPLOYMENT.md`](../05-agentcore-deploy/advanced-deployment/DEPLOYMENT.md) holds the Runtime, Gateway, and Lambda boundary, including the two-secret and two-Neo4j-user split.
- [`05-agentcore-deploy/CLEANUP.md`](../05-agentcore-deploy/CLEANUP.md) is the detailed teardown reference.

---

## What to schedule

| Lab | Folder | Notebooks | Delivery role |
|:-:|---|---|---|
| 0 | [`00-setup/`](../00-setup/) | None. A credential checklist | Done before the room sits down. Ends in one verification command that proves Aura and Bedrock both work |
| 1 | [`01-graph-build/`](../01-graph-build/) | `1.1_build_graph.ipynb` | The first partnership peak. Bedrock extracts entities and relationships against a pinned schema and Neo4j stores them with the vector and full-text indexes. Also the longest wall-clock lab |
| 2 | [`02-retrieval/`](../02-retrieval/) | `2.1_vector_retrievers.ipynb`, `2.2_fulltext_retrievers.ipynb`, `2.3_text2cypher.ipynb` | The lesson the room remembers. Four retrievers on the same questions, closing on a question the graph cannot answer |
| 3 | [`03-agents-and-tools/`](../03-agents-and-tools/) | `3.1_strands_primer.ipynb` | Strands Agents concepts with a retriever already in hand: agents, tools, lifecycle hooks, swarms. Section 6 assembles `hotel_agent` |
| 4 | [`04-grounded-write/`](../04-grounded-write/) | `4.1_reservation_write.ipynb` | The safety beat. A rule read from the graph rejects a 15-guest request inside the write transaction, and a retry stays idempotent |
| 5 | [`05-agentcore-deploy/`](../05-agentcore-deploy/) | `5.1_agentcore_deploy.ipynb`, `5.2_teardown.ipynb`, `5.3_agentcore_walkthrough.ipynb` | The second peak, and the only billable lab. The Lab 4 agent hosted on AgentCore Runtime with the retriever unchanged, then torn down by tag |
| 6 | [`06-memory/`](../06-memory/) | `6.1_neo4j_agent_memory.ipynb` | Optional closing material. Graph-native memory with provenance and actor isolation |

Only Lab 6 is optional. `2.3_text2cypher.ipynb` and `5.3_agentcore_walkthrough.ipynb` are optional notebooks inside required labs.

Lab 6 is optional but not standalone. It requires the hero `Hotel` that Lab 1 creates, and it stops with a `RuntimeError` naming the missing hotel rather than writing partial memory.

## The four beats to land

Everything else is scaffolding around these.

1. **Lab 1: the graph is built live, not shipped.** Only the raw corpus `01-graph-build/hotel-faqs.zip` is in git. Every participant generates the graph, which is what makes the Bedrock-plus-Neo4j call path concrete rather than described.
2. **Lab 2, hero question one:** *"What amenities and guest rating does AnyCompany Cairo Nile View have?"* It arrives in `2.2` and it makes every arm earn its place. The exact hotel name is what the full-text arm is for, the paraphrased wording is what the vector arm is for, and the rating and the amenity list are in neither matched chunk. The traversal is what produces them. The `2.1` pair sets this up on a different question: both retrievers find the same chunks, and only the one with the traversal returns the rating as a named field and the amenities as a list.
3. **Lab 2, hero question two:** *"Does AnyCompany Cairo Nile View guarantee room availability next weekend?"* The agent abstains, because the graph holds no live availability. The abstention is the point of the lab. Both hero questions return in Lab 3 inside an agent and again in Lab 5 against the deployed Runtime.
4. **Lab 4: the rule moves out of the prompt.** Lab 3 blocks a 15-guest booking with `MaxGuestsHook`, where `10` is a Python literal in one notebook next to one agent. Lab 4 reads the same limit from a `Rule` node inside the write transaction and rejects the same request with nothing written.

## Cutting for time

| Lever | What it costs |
|---|---|
| Build Lab 1's lite 30-document corpus rather than the full 300 | Roughly 15 minutes instead of roughly 2 hours. `MODE` is already `"lite"` in step 1 of the notebook. Every later lab works against the lite graph |
| Build the graph before the session | Nothing. `prepare_graph.py` is idempotent, so a graph that already reports ready is verified rather than rebuilt |
| Skip `2.3_text2cypher.ipynb` | The one demonstration that Neo4j computes a count over the whole matching set, which top-k retrieval cannot do. Nothing later in the workshop depends on it |
| Skim Lab 3 sections 1 through 5 for a Strands-fluent room | Little, if you still run section 6. That section assembles `hotel_agent`, which Labs 4 and 5 carry forward by name |
| Run Lab 5 as a facilitator demonstration rather than hands-on | Participant muscle memory, and it saves every participant's AWS spend and every participant's teardown |
| Skip `5.3_agentcore_walkthrough.ipynb` | The `request_id` correlation across AgentCore and CloudWatch traces. It depends on `5.1` and reads `AGENT_RUNTIME_ARN`, which `5.1` produces at launch |
| Drop Lab 6 | The graph-memory argument and the AgentCore Memory comparison. It is the only fully optional lab |

**Never cut Lab 5's teardown.** `5.2_teardown.ipynb` is a numbered notebook in the lab for that reason. If Lab 5 ran, teardown runs.

A rehearsed per-lab time budget is still outstanding. The two wall-clock numbers that are measured: Lab 1's lite build takes roughly 15 minutes, and the AgentCore Runtime launch in `5.1` takes three to five minutes.

## Suggested track shapes

- **Developer half-day:** Labs 0 through 4, with `2.3` included. Pre-build the lite graph before the room sits down and treat Lab 5 as a walkthrough of `5.1` on the facilitator's screen.
- **Architect half-day:** Labs 0 through 5 hands-on, with `2.3` cut and `5.3` kept. `5.3` is the trace correlation an architect audience asks for, and `DEPLOYMENT.md` is the going-further read.
- **Leadership briefing:** Labs 1, 2, and 4 delivered facilitator-first with light hands-on, closing on the Lab 4 rejection. Land the two hero questions and the Platform Responsibilities table; skip Lab 3's primer and Lab 5's infrastructure.
- **Full-day deep dive:** All six labs hands-on, every optional notebook included, full 300-document build started before the first session or overnight.

---

## Prerequisites to confirm before the event

- **Bedrock model access,** granted in the exact region named by `AWS_REGION`. Three models, and access to one proves nothing about the others: `us.anthropic.claude-sonnet-5` for Lab 1 extraction and all later agent reasoning, `amazon.nova-2-multimodal-embeddings-v1:0` for Lab 1 chunk embeddings and every Lab 2 query embedding at 1024 dimensions, and `amazon.titan-embed-text-v2:0` for Lab 6's memory embeddings, also at 1024 dimensions. The third is needed only if you are running Lab 6, and Lab 6 is the only optional lab. Access is per region, so enabling a model in one region does nothing for another. The `us.` prefix marks a cross-region inference profile, so pair it with a US region such as `us-east-1`.
- **One Neo4j Aura instance per participant.** APOC Core is preinstalled on every Aura instance, so there is no plugin to enable. Lab 1's graph build uses it and finds it already there; a self-hosted Neo4j is the only case that needs the plugin installed by hand. A single instance serves all six labs: retrieval, the production rule, the reservation requests, and the optional memory graph. At a hosted event the instance is provided and the URI, username, and password come from the event materials.
- **One repo-root `.env`,** copied from `.env.example` and holding `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`, and `AWS_REGION`. A `.env` inside a lab folder overrides the root one, so keep a single file at the root.
- **The Workshop Studio username variable.** The hosted CloudFormation environment writes `NEO4J_USER`, and every lab in this repository reads `NEO4J_USERNAME`. If authentication fails only inside the hosted workshop, this mismatch is the first thing to check.
- **Python 3.12 or newer, and [uv](https://docs.astral.sh/uv/).** The shared `workshop` package declares `requires-python = ">=3.12"` in `workshop/pyproject.toml`, and every lab installs it in editable mode with `-e ../workshop` at the top of its `requirements.txt`.
- **The AgentCore infrastructure, for Lab 5 only.** Labs 1 through 4 and Lab 6 create no AWS resources beyond Bedrock inference calls. Lab 5 needs `uv run setup/provision_agentcore.py provision` to have run first. It stands up the Neo4j command secret, three least-privilege IAM roles, the reservation Lambda, and the AgentCore Gateway with its single target, then writes the resulting identifiers into the repo-root `.env` for `5.1_agentcore_deploy.ipynb` to read. It is idempotent, and `status` reports what exists.
- **Two Secrets Manager secrets for the deployed path,** one Runtime-read and one Lambda-command, each holding `uri`, `username`, `password`, and `database`. Use separate Neo4j users where the Aura tier supports fine-grained privileges. No Runtime or Lambda ever accepts database credentials as prompt or tool input. Labs 1 through 4 and Lab 6 run locally against the standard `NEO4J_*` values.

Keep participant setup inside 30 minutes. The way to hit that is to finish Lab 0 before the session and to have the graph already built, because Lab 1's build is deliberately live and takes as long as it takes.

## Pre-delivery rehearsal

Run these from the repository root, in order, on the machine and account you will deliver from.

1. **Both credentials.** Run the verification script in [`00-setup/README.md`](../00-setup/README.md) step 4. It connects to Aura, counts APOC procedures, sends one short Bedrock prompt, and requests one embedding. Three OK lines mean Lab 0 is done. The embedding must report 1024 dimensions, because that is the width Lab 1 writes into the vector index and Lab 2 queries against.
2. **Graph and index readiness.**

   ```bash
   cd 01-graph-build
   uv run prepare_graph.py --check-only
   ```

   Read-only. It verifies the `hotel_chunk_embeddings` vector index and the `hotel_chunk_fulltext` full-text index, reports document and chunk counts against the selected mode, and names any missing demo-critical source file. It exits nonzero when the graph is not ready. Drop `--check-only` and pass `--mode lite` to build what is missing.
3. **The seeded rule, the fixture identities, and the constraints.** Step 7 of `1.1_build_graph.ipynb` calls `apply_lab4_fixtures` from `workshop.graph_setup`, which seeds the fixture hotel IDs, the `demo-06-maximum-guests` `Rule` node, and three uniqueness constraints, then asserts readiness. This is graph-owned data rather than extracted data, and it is `MERGE` and `SET` throughout, so running it twice changes nothing. Without it Lab 4 opens onto an unprepared graph. Confirm it with Lab 4's suite:

   ```bash
   cd 04-grounded-write
   uv run --with pytest --with-requirements requirements.txt -m pytest
   ```

   56 tests. `SeededRuleTests` in `test_demo_guest_consistency.py` reads the `Rule` node live and skips when credentials are absent, so check that it ran rather than skipped.
4. **The notebook gate.**

   ```bash
   uv run setup/run_notebooks.py
   ```

   Covers Labs 1 through 4 and Lab 6. It executes copies and never modifies the originals, and every live cell self-skips without credentials, so the default run is green offline and creates no AWS resources. With credentials present, Lab 1 performs a real build and takes as long as that build does, so run it once, alone, on a machine that stays awake. A clean run proves cells did not raise; it does not validate narrative or model-quality claims. See [`setup/README.md`](../setup/README.md) for the full command reference.
5. **Lab 5, if it is in the plan.** Rehearse the deploy and the teardown as one sitting, in a disposable account:

   ```bash
   uv run setup/run_notebooks.py --labs 5 --include-deploy
   uv run setup/run_notebooks.py --labs 5 --include-cleanup
   ```

   Both flags touch real, billable AWS resources. The tagging step in `5.1_agentcore_deploy.ipynb` is what makes teardown possible, because the starter toolkit creates the ECR repository, the CodeBuild project, and the Runtime without forwarding tags. Skipping it makes `workshop_cleanup.py` report them as `UNTAGGED_BLOCKED` and exit nonzero while the infrastructure keeps billing.

Two notes on running from a fresh clone. Register the `nbstripout` git filter once, with `pip install nbstripout && nbstripout --install` from the repository root, or every `.ipynb` checkout runs against an undefined filter. And run only one Lab 1 build at a time: each build clears the graph before it starts, so two overlapping builds wipe each other mid-flight and the document-count assertion fails with a count that keeps changing. On macOS, wrap a long build in `caffeinate -i -s`, because sleep kills it and closing the lid still sleeps the machine.

## Cost and teardown

Lab 5 is the only lab that creates billable AWS resources: an AgentCore Runtime, an AgentCore Gateway with one target, an ECR repository holding a container image, a CodeBuild project, a Lambda function, a Secrets Manager secret, and three IAM roles. They bill until they are deleted.

Teardown is two halves, tagged differently. Each one leaves the other billing if run alone, so run both.

| Tag | Created by | Deleted by |
|---|---|---|
| `WorkshopResource=stop-ai-agent-hallucinations` | The tagging step in `5.1_agentcore_deploy.ipynb` | `5.2_teardown.ipynb` and `05-agentcore-deploy/workshop_cleanup.py` |
| `demo06-agentcore=true` | `uv run setup/provision_agentcore.py provision` | `uv run setup/provision_agentcore.py teardown` |

Cleanup is tag-scoped and refuses to guess. An untagged resource under a workshop-looking name is reported as `UNTAGGED_BLOCKED` and the run fails rather than deleting it. Treat both halves as destructive and confirm scope before running either outside a disposable sandbox account.

The Neo4j database is terminated separately. Aura is not an AWS resource in the account, so nothing in the repository can reach it. Delete the instance from the Aura console when the event is over.
