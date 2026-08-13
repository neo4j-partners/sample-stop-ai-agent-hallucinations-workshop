# Revised Workshop Outline

All-AWS, all-Neo4j. The workshop teaches Neo4j GraphRAG first, then agents, then production deployment on Amazon Bedrock AgentCore.

## Framing: grounded retrieval to production

The workshop is organized as one continuous path, from raw text to a deployed agent, rather than as a tour of four hallucination categories.

The old framing enumerated failure modes: fabricated statistics, wrong tool selection, business rule violations, and undetected failures. Each demo owned one category, and the demos were independent by design. That framing stops working once the demos become a sequence, because the labs build on each other rather than standing alone.

The new framing is a single claim, demonstrated end to end:

> An agent can only be trusted with a real action if every answer traces back to connected data. This workshop builds that path, from raw documents to a graph, from a graph to grounded retrieval, from retrieval to an agent that uses it, from that agent to a guarded write, and from a working agent to a deployed one on AWS.

Hallucination stays the motivation, but it appears as the thing each lab prevents rather than as the taxonomy the labs are sorted into. Lab 2 shows retrievers that return connected facts instead of loose text, covering fabricated statistics, and closes on the case where the graph cannot answer at all. Lab 4 shows a rule in the graph rejecting a request a prompt alone would allow, covering business rule violations. Two of the four original categories keep a live demonstration. Wrong tool selection goes with `02-semantic-tools-demo`, and undetected failures, where a single agent claims success without validation, goes with Demo 03's swarm.

**Documents this reframing changes.** The root README title line and the "What types of AI agent hallucinations does this repository address?" FAQ answer, which currently promises four categories with four demos. The Module List and Tracks table, which becomes a six-lab sequence with no Core, Audience-dependent, and Optional-advanced split, since only Lab 6 is optional now. The "How Do the Modules Build on Each Other?" section, which becomes the path description above. `images/why-ai-agents-fail-six-demos-progressive-flow.png`, which needed redrawing as the six-lab path and was replaced by a new `images/six-lab-path.svg` rather than edited. `workshop-delivery/architecture.md` and `CLAUDE.md`.

## Why this flow

The workshop answers one question in three moves: where does grounded evidence come from, how does an agent use it, and how does that run in production.

**Neo4j first, because the evidence has to exist before anything can be grounded in it.** Lab 1 builds the knowledge graph and Lab 2 shows what retrieval against it returns. A participant who has watched `VectorRetriever` and `VectorCypherRetriever` answer the same question differently understands why connected data matters, in a way no slide achieves. Putting agents first would invert this. The agent becomes the interesting part and the graph becomes plumbing, which is the opposite of the lesson.

**Agents second, because a tool is more concrete than a framework.** Lab 3 opens the Strands primer with a retriever already in hand from Lab 2. Agents, tools, and hooks arrive as answers to a question the participant already has, which is how the agent gets to use the retriever.

**The agent block is two labs.** Lab 3 is the framework, where the participant gets a working agent that calls the Lab 2 retriever as a tool, and Lab 4 is acting safely, where a rule in the graph stops an action the prompt alone would allow. Splitting them keeps the primer from competing with the write path for attention.

**AgentCore last, because deployment is only meaningful once there is something worth deploying.** Lab 5 takes the exact agent from Lab 4 and hosts it on AWS without changing the retriever. That is the cleanest proof of the partnership in the workshop: the Neo4j retrieval logic is identical, and only the operational surface around it changes.

**The partnership peaks twice, deliberately.** Lab 1 is the first peak, where Bedrock extraction and Neo4j storage sit in the same call path through `SimpleKGPipeline`. Labs 2 through 4 are Neo4j-weighted with Bedrock in a supporting role. Lab 5 is the second and higher peak, wrapping the full AWS operational surface around unchanged Neo4j retrieval. Memory closes as optional material rather than as the finale, so the core path ends on the AWS crescendo.

## How data loads today

- **Nothing is pre-embedded**: only the raw hotel-FAQ text corpus, `hotel-faqs.zip`, is checked into git. The Neo4j graph is a gitignored build artifact that every participant generates.
- **Pre-loading data at an AWS event means the raw zip only**: the EC2 Code Editor pre-extracts `hotel-faqs.zip` so students skip a download step. The graph build and embedding step still run live.
- **`prepare_graph.py` drives `SimpleKGPipeline`**: an idempotent driver script that runs Bedrock LLM extraction and embedding to build the graph, then creates Neo4j's vector and full-text indexes live. It skips work already done and supports `--rebuild` and `--check-only`.
- **Already the target flow**: students run `SimpleKGPipeline` themselves and nothing ships pre-embedded. Lab 1 reuses this as-is.
- **FAISS drops out**: `load_vector_data.py` and `load_vector_data_lite.py` built a separate FAISS index to stand in for plain vector RAG. Neo4j's own vector index does that job, so the standard-RAG-versus-GraphRAG comparison re-points at Neo4j's `VectorRetriever` with no traversal. Same lesson, one less index technology to teach.
- **Build times are confirmed**: 15 minutes for the lite build of 30 documents, 2 hours for the full build of 300. Bedrock concurrency is confirmed working at event scale.

## Step 0: Setup

Aura signup, connection URI and credentials saved to the repo-root `.env`, Bedrock access confirmed. This is a short setup checklist in a README, not a notebook.

**What shipped.** `00-setup/README.md`, four steps and no notebook: get an Aura instance with APOC enabled, write the five repo-root `.env` values, request Bedrock access to both models, then run one verification command. The verification is not the old credential-check cell reused. It is a standalone `uv run --with neo4j --with boto3 --with python-dotenv python -` heredoc that connects to Aura, counts APOC procedures, sends one Bedrock `converse` call, and requests one 1024-dimension Nova embedding, printing three lines. It reads the graph and never writes to it, and it needs no virtual environment. A failure table maps each error message to its fix, including the `NEO4J_USER` versus `NEO4J_USERNAME` mismatch inside Workshop Studio.

## Lab 1: Neo4j GraphRAG, from text to knowledge graph

**Topic.** No-ETL load, LLM extraction against a pinned schema, embedding, index creation, and fixture seeding. This is the partnership in a single script.

**Neo4j technologies.** Aura, `SimpleKGPipeline` from neo4j-graphrag-python, the pinned schema of `Hotel`, `Room`, `Amenity`, `Policy`, and `Service` with `OFFERS_AMENITY`, `HAS_POLICY`, `HAS_ROOM`, and `PROVIDES_SERVICE`, plus `Document` and `Chunk`, the vector index `hotel_chunk_embeddings`, the full-text index `hotel_chunk_fulltext`, uniqueness constraints, and APOC.

**AWS technologies.** Bedrock Claude Sonnet 5 for entity and relationship extraction, and Amazon Nova 2 Multimodal Embeddings, `amazon.nova-2-multimodal-embeddings-v1:0` at 1024 dimensions, for chunk vectors.

**Notebooks.**
- **`1.1_build_graph.ipynb`**, new. A notebook wrapper around `prepare_graph.py` and `graph_builder.py`: configure the schema, run `SimpleKGPipeline` live, and verify the indexes. The build is CLI-only today, so this is the one genuinely new artifact Lab 1 needs. Shipped at 19 cells in eight sections. Section 4 reports readiness and sets `NEEDS_BUILD`, and a `REBUILD` flag in section 1 is the notebook form of the script's `--rebuild`.
- The notebook must end by calling `apply_demo6_graph()` from `workshop.graph_setup`. That seeds the fixture Hotel, the `max_guests` Rule, and three constraints that Labs 4 and 5 depend on. Without it, Lab 4 opens onto an unprepared graph. Section 7 calls it and then asserts `readiness_problems()` is empty, so a partial seed fails the notebook instead of passing quietly.
- Every live cell is guarded on `BUILD_READY` and prints "Skipping: no Neo4j or AWS configuration." when credentials are absent, so `--labs 1` is green offline. The modules that open a driver, `prepare_graph` included, are imported inside the guarded branch rather than at the top of the notebook, because `workshop.graph_connection` raises at import when `NEO4J_PASSWORD` is unset.

## Lab 2: GraphRAG retrieval patterns

**Topic.** Retriever pairs run side by side on the same question, so the connected-context delta is visible rather than described. The lab closes with the same production retriever run on a question the graph cannot answer.

Split by pair:
- **Vector pair**: `VectorRetriever` for plain semantic similarity, which is also the standard-RAG baseline FAISS used to cover, against `VectorCypherRetriever`, which adds a graph traversal for connected facts.
- **Full-text pair**: `HybridRetriever` fusing vector and full-text with no traversal, against `HybridCypherRetriever`, which adds the one reviewed traversal. This is the production-shaped default that Lab 5 later deploys unchanged.
- **Text2Cypher**: natural language to Cypher for aggregations and counts. It pairs with neither axis, so it stays a separate optional notebook.

**Neo4j technologies.** `VectorRetriever`, `VectorCypherRetriever`, `HybridRetriever`, `HybridCypherRetriever`, and optionally `Text2CypherRetriever`. Lucene full-text scoring, `NAIVE` fusion, `top_k=5`, and a reviewed traversal that returns the stable `hotel_id` with up to 12 amenities.

**AWS technologies.** Bedrock Nova 2 for the query embedding, and Claude Sonnet 5 for answer synthesis and Text2Cypher generation.

**Notebooks.**
- **`2.1_vector_retrievers.ipynb`** reuses the `VectorRetriever` and `VectorCypherRetriever` sections of `01-graphrag-demo/retrieval_patterns.ipynb`, reframed as the standard-RAG-versus-GraphRAG comparison. This replaces the FAISS-based `test_graphrag.ipynb` motivating demo. Shipped at 14 cells.
- **`2.2_fulltext_retrievers.ipynb`** combines the `HybridRetriever` section of `retrieval_patterns.ipynb` with the `HybridCypherRetriever` from `06-agentcore-boto3-demo/01_hybrid_retrieval.ipynb`. These two have never appeared in one notebook, so this one needs assembling from both sources. Shipped at 20 cells. Its first pattern is sharper than a straight reuse: `VectorRetriever` and `HybridRetriever` are run against the same question about the hotel at postal code `60611`, so the full-text arm earns its place on an exact identifier that carries almost no semantic signal. Its second pattern does not build `HybridCypherRetriever` inline. It imports `search_hotel_knowledge` from `workshop.hybrid_retrieval`, which is the same one-field tool Labs 3, 4, and 5 use.
- **`2.3_text2cypher.ipynb`**, optional. Shipped at 10 cells, and authored rather than reused. It pins a hand-written schema and few-shot examples instead of introspecting the graph, so the model can only name labels and properties that exist, and it closes on the trust boundary: a retriever holding database credentials in the notebook process is fine for a notebook and is not what you would ship.
- **All three Lab 2 notebooks open the same way.** Cells 2 through 7 are the shared preamble: connect and verify both Lab 1 indexes, render `GRAPH_SCHEMA` from `workshop.graph_schema`, then construct the embedder from `workshop.bedrock_providers`. The verification and schema cells are duplicated on purpose, because watching them run is what tells a participant whether Lab 1 succeeded. No notebook defines an embedding constant locally.
- **Close `2.2` with one unanswerable question, in three cells.** Carry forward cells 7 through 9 of `01_hybrid_retrieval.ipynb`: the availability question, run on the `HybridCypherRetriever` already constructed earlier in the notebook, returning no context so the agent declines. One markdown cell of framing, then two code cells: the grounded agent and the availability question. One line on what did not happen. The same retriever, on a question the graph cannot answer, returns nothing and the agent says so. Shipped as cells 15 through 17 of `2.2`.
  - **One case, not two.** The out-of-domain alternative in `test_graphrag.ipynb`, "Tell me about hotels in Antarctica," is dropped. It needs its own setup and it is the easy version, since a plain vector index also handles an off-corpus query badly. The availability question is the one participants will hit in production: the graph knows the hotel and does not know this fact.
  - **No `2.4`, and no abstention technique material.** Prompt patterns for refusal, confidence thresholds, and score cutoffs stay out. That material is what turns three minutes into fifteen.
- **State the mechanism in one sentence at the end.** Vector search finds candidates, traversal finds what is connected.

## Lab 3: Agents and tools

**Topic.** The Strands primer covering agents, tools, lifecycle hooks, and swarms, with the Lab 2 retriever as one of the agent's tools.

**Neo4j technologies.** The Lab 2 `HybridCypherRetriever` reached from inside a Strands `@tool`. No new graph structure.

**AWS technologies.** Bedrock Claude Sonnet 5 through the Strands `BedrockModel`, the Converse API, the `@tool` boundary, and lifecycle hooks.

**Notebooks.**
- **`3.1_strands_primer.ipynb`** reuses the five teaching sections of `00-getting-started/getting_started_strands.ipynb` unchanged, with one substitution: the Lab 2 retriever replaces `get_weather` in the section 3 toolset, so the primer builds on what participants already have.
- **The primer is not five independent agents by the end.** Its sections each build their own agent: section 3 has a three-tool agent, section 4 has the hook pair, section 5 has a swarm. The lab closes with a new sixth section that assembles one named `hotel_agent` carrying the retriever tool and the hook-guarded booking tool. That named agent is what Lab 4 registers the write onto, so the two labs read as one story rather than two.
- **The names in the shipped notebook are the primer's own.** The hook is `MaxGuestsHook` and the booking tool is `book_room`, both defined in section 4. `BookingGuardrailsHook` and `book_hotel` have no referent here: `book_hotel` is one of section 3's simulated tools, and the guardrails name was a holdover from the deleted steering demo. Section 6 takes exactly two pieces forward, `search_hotel_knowledge_tool` from section 3 and `MaxGuestsHook` from section 4, then asks one question the graph answers and one booking the hook stops.
- **The notebook shipped at 26 cells, six sections.** Guards went on the ten cells that invoke a model, so `--labs 3` is green offline. Agent and swarm construction needs no credentials, so the teaching code stayed unindented and readable. Section 3.5's `AgentResult.metrics` agent was renamed `agent_metrics`, because reusing the name `agent` silently rebound the three-tool agent for any cell run after it.
- **One notebook, not two.** Semantic tool selection is dropped, so nothing follows the primer inside this lab. Lab 3 hands the participant a working agent and Lab 4 gives it something consequential to do.

## Lab 4: The grounded write

**Topic.** The idempotent reservation write, with a rule that lives in the graph rejecting a request the prompt alone would have allowed.

**Neo4j technologies.** The `Rule` node `demo-06-maximum-guests` with its limit of 10, read from the graph rather than asserted in the prompt. The `ReservationRequest` node and its `FOR_HOTEL` relationship, `MERGE` idempotency keyed on a caller-supplied `request_id`, uniqueness constraints, and parameterized Cypher only, with no model-generated queries.

**AWS technologies.** Bedrock Claude Sonnet 5 reasoning over the tool result, the Strands tool boundary, lifecycle hooks, and closed input-schema validation.

**Notebooks.**
- **`4.1_reservation_write.ipynb`**, new. Wraps `workshop.reservation_command`, `workshop.contracts`, and `workshop.graph_setup`: an accepted write, a duplicate retry that stays idempotent, a `max_guests_exceeded` rejection, and an unknown-hotel rejection. No new backend code is needed. The command and its contracts already exist, covered by 29 tests across `test_reservation_command.py`, which holds 22, and `test_contracts.py`, which holds 7. Lab 4's whole suite is 56 tests: those 29 plus 12 in `test_graph_setup.py`, 12 in `test_hybrid_retrieval.py`, and 3 in `test_demo_guest_consistency.py`.
- Open by registering `create_reservation_request` on the `hotel_agent` that Lab 3's closing section built, so the two labs read as one story rather than two.
- This is where the Demo 04 lesson survives. The rule comes from Neo4j rather than from a Python fixture, which is the stronger version of the same point.
- **`MaxGuestsHook` comes off the agent here, which is the point of the lab.** The retrieval tool and the write tool stay. The hook goes, because the rule it enforced now lives in the graph and the command reads it inside the write transaction.
- **The notebook creates the `request_id` rather than letting the model invent one.** A model-invented UUID makes idempotence untestable, so the notebook generates it, prints it, and passes it in the user turn. No field was added to the frozen contract and no second write path exists. Shipped at 21 cells, each of the four cases carrying its own assertion instead of leaving the reader to read printed JSON.
- **`test_demo_guest_consistency.py` grew from one test to three.** Two source-level tests compare `contracts.py` against `graph_setup.py`, and a third, `SeededRuleTests`, reads the seeded `Rule` node and self-skips when credentials are absent. It calls `load_dotenv()` in `setUp`, because participants keep credentials in the repo-root `.env` rather than exported.

## Lab 5: Deploy to AgentCore

**Topic.** Containerize the agent from Labs 3 and 4, launch the AgentCore Runtime, expose the reservation write through Gateway to Lambda, correlate one request end to end, then tag and tear down.

**Neo4j technologies.** Aura reached from inside AWS, the Runtime-read and Lambda-command credential split, the secret JSON shape of `uri`, `username`, `password`, and `database`, and the same `HybridCypherRetriever` from Lab 2 running unchanged.

**AWS technologies.** The `bedrock-agentcore-starter-toolkit` `Runtime.configure` and `Runtime.launch` calls, AgentCore Runtime on ARM64, AgentCore Gateway with one Lambda target, ECR, CodeBuild, AWS Lambda, IAM with three least-privilege roles, Secrets Manager, CloudWatch and AgentCore observability correlated by `request_id`, `setup/provision_agentcore.py`, and tag-scoped teardown.

**Notebooks.**
- **`5.1_agentcore_deploy.ipynb`**, authored fresh around the four proven cells of `deploy_agentcore.ipynb`, recovered from git commit `861ec06^` and now back in the working tree at `05-agentcore-deploy/deploy_agentcore.ipynb`. Those four are the pre-flight toolkit cleanup, the `Runtime.configure` and `Runtime.launch` pair, and the tagging header and tagging code. `launch()` builds the ARM64 image through CodeBuild, creates the ECR repository, pushes, and creates the Runtime. That mechanism carries over; the rest is retargeted.
- **`5.1` shipped at 19 cells in six steps:** the provisioning gate that reads `AGENTCORE_GATEWAY_URL`, `AGENTCORE_RUNTIME_ROLE_ARN`, and `NEO4J_COMMAND_SECRET_ID` from the repo-root `.env` and sets `DEPLOY_READY`; the wheel build; the pre-flight cleanup and `chdir`; configure and launch; tagging; then the four smoke tests and a closing note on where the `request_id` went. Every step after the gate is guarded on `DEPLOY_READY`, so `--labs 5 --include-deploy` skips rather than fails when the infrastructure is absent.
- **`5.2_teardown.ipynb`**, built on `workshop_cleanup.py`, which moved into `05-agentcore-deploy/` along with `test_workshop_cleanup.py` and its 20 tests. Teardown is its own notebook rather than a closing section, because the acceptance runner gates per notebook: `deploys_resources` and `deletes_resources` are `NotebookSpec` fields and a section cannot hold a gate. Shipped at 11 cells: a dry run, a review of the `DELETE` lines, execution, then a verification pass that re-plans and raises if anything is still present, because a success message is a claim rather than evidence.
- **`5.3_agentcore_walkthrough.ipynb`**, optional, 13 cells. Reuses `advanced-deployment/02_agentcore_walkthrough.ipynb`, which invokes the deployed Runtime and correlates AgentCore and CloudWatch logs by request ID. It reads `AGENT_RUNTIME_ARN`, which `5.1` produces.
- **Teardown is part of this lab, not an afterthought.** Lab 5 creates real billable resources. The tagging cell carried over from the restored notebook is what makes `workshop_cleanup.py` able to delete the ECR repository, the CodeBuild project, and the Runtime. Skipping it leaves infrastructure running. Every target in that cell is addressed by exact name or by ARN; nothing is enumerated or prefix-matched, and the toolkit's shared `AmazonBedrockAgentCoreSDKCodeBuild-*` IAM role is deliberately left untagged so it stays ineligible for deletion.

### Packaging the shared package into the Runtime image

`booking_agent.py` imports `search_hotel_knowledge` from `workshop.hybrid_retrieval`, which is the whole claim of the lab: the retrieval tool Lab 2 built is imported rather than reimplemented. That import has to keep working inside the container, and the package lives at the repository root, outside the build context. A container build cannot reach up out of its own context, so:

- `5.1` runs `uv build --wheel --out-dir vendor ../../workshop` on every deploy, writing into `05-agentcore-deploy/deployment-tools/vendor/`. Stale wheels are deleted first, so a previous version cannot satisfy the requirement and ship code that is no longer in front of you.
- `agent_requirements.txt` pins that wheel by exact filename, `./vendor/workshop-0.1.0-py3-none-any.whl`, rather than by the bare name `workshop`, which a resolver would try to satisfy from PyPI.
- `deployment-tools/Dockerfile` does `COPY vendor/ vendor/` before its install line. The wheel is gitignored and the directory is tracked, because `COPY` against a missing directory fails the image build.
- `5.1` chdirs into `deployment-tools/` before configuring, because the starter toolkit treats the current directory as the build root. Run from `05-agentcore-deploy/` instead and the toolkit generates its own Dockerfile, ignores the hand-written one, and ships the whole lab folder.

### Teardown is two halves with two owner tags

Neither half deletes the other's resources, and either one alone leaves the other billing.

| Half | Owner tag | What it deletes |
|---|---|---|
| `5.2_teardown.ipynb` and `workshop_cleanup.py` | `WorkshopResource=stop-ai-agent-hallucinations` | The ECR repository, the CodeBuild project, and the AgentCore Runtime that `5.1` created through the starter toolkit, plus the local `.bedrock_agentcore.yaml` |
| `setup/provision_agentcore.py teardown` | `demo06-agentcore=true` | The Gateway and its target, the reservation Lambda, the Neo4j command secret, and the `demo06-*` IAM roles |

`workshop_cleanup.py` deletes only tagged resources and reports an untagged workshop resource as `UNTAGGED_BLOCKED`, which makes the run exit nonzero rather than leave a failed teardown looking like a successful one. `CONFIG_FILES` is now a single entry, `05-agentcore-deploy/deployment-tools/.bedrock_agentcore.yaml`.

### Retarget work for the restored notebook

**This is not the path that was taken, and the table below is kept as the record of the decision.** Retargeting the restored notebook in place meant deleting roughly 28 of its 43 cells and inheriting DynamoDB-shaped recovery scaffolding at cell 5, a "Module 6 Deployment Complete" banner at cell 40, and "Save Variables for Module 7" at cells 41 and 42. The proven mechanism is four cells out of 43, so `5.1` was authored fresh around those four instead, with the restored notebook open beside it as reference. The restored notebook stays in the tree at `05-agentcore-deploy/deploy_agentcore.ipynb`, 43 cells, unregistered in the runner.

The deploy mechanism is intact. The deploy target changed, so the deletions and repointings the table names are what `5.1` accomplishes by other means.

| Restored step | Action |
|---|---|
| Steps 1 through 3: DynamoDB hotels, bookings, and steering-rule tables and seeds | Delete. That data lives in Neo4j after Lab 1, and DynamoDB is outside the core path |
| Step 4: IAM roles | Delete. Already reimplemented as three least-privilege roles in `setup/provision_agentcore.py` |
| Step 5: six booking-lifecycle Lambdas plus a VPC Neo4j query Lambda | Replace with the single `create_reservation_request` Lambda in `deployment-tools/lambda_tools/`, already provisioned |
| Steps 6 and 7: Gateway and targets | Delete. Already in `provision_agentcore.py` using `gateway_target.json` |
| Step 8: Runtime configure and launch | Keep. Swap `env_vars` from `BOOKINGS_TABLE` to the `GATEWAY_URL`, `MODEL_ID`, and `NEO4J_*` values `booking_agent.py` reads. `entrypoint` and `requirements_file` end up as the bare names `booking_agent.py` and `agent_requirements.txt`, not folder-prefixed paths, because `5.1` chdirs into `deployment-tools/` first |
| Tagging cell | Keep as-is. Cleanup refuses to delete untagged toolkit resources |
| Step 9: eight booking-lifecycle tests | Replace with four: the hero question, the abstention, the `max_guests` rejection, and the idempotent retry |

Path references still pointing at the pre-move layout: `booking_agent.py`, `agent_requirements.txt`, and `lambda_tools/query_knowledge_graph/lambda_function.py`. The first two moved to `deployment-tools/`. The third is gone and its work is covered by in-process retrieval. `tool_schemas/tools.json` moved with the rest of the deployment surface and now sits at `05-agentcore-deploy/tool_schemas/tools.json`; its contents needed no change, but `04-grounded-write/test_contracts.py` reads it across the folder boundary and had to be repointed at `../05-agentcore-deploy/`.

## Lab 6: Neo4j agent memory, optional

**Topic.** Explicit, graph-native memory with provenance and actor isolation, and when to prefer it over a managed store.

**Neo4j technologies.** Memory graph nodes and relationships, the full provenance path, actor isolation, and run-scoped cleanup tagging.

**AWS technologies.** Bedrock for memory read and write reasoning, with AgentCore Memory as the managed contrast.

**Notebooks.**
- **`6.1_neo4j_agent_memory.ipynb`** reuses `08-neo4j-memory-demo/inspectable_memory.ipynb`, 15 cells. "As-is" did not survive the renumber: the notebook opened as "Module 8" and told the reader to run "Module 1," so six prose references across six cells now name labs. Nothing in code changed. The `demo08-` identifier prefix stays exactly as it is, because `cleanup_memory.py` matches on it.
- Add a one-paragraph callout explaining why the workshop uses Neo4j memory instead of AgentCore Memory. Dropping Demo 07 removes a comparison the README Platform Responsibilities table still makes, and a paragraph is enough to keep it. Shipped as an argument rather than a disclaimer: it says what the managed service gives you, then names the one thing it does not, which is the last section of this notebook, where a preference is traversed back to the message that produced it and forward to the `Hotel` it describes.
- `test_memory_helpers.py` carries the lab's 22 tests, unchanged in behavior by the move.

## What gets removed

- **FAISS**: `load_vector_data.py`, `load_vector_data_lite.py`, and the `faqs_docs.json` (2.2 MB) and `faqs_vector.index` (1.2 MB) they produce. Both artifacts are gitignored at `.gitignore:88-89`, so they were never in the repository, only in a working tree that had run the loader. Neo4j's vector index covers plain vector RAG.
- **`01-graphrag-demo/travel_agent_demo.py` and `01-graphrag-demo/tools/graph_tool.py`**: a standalone graph-backed agent demo, superseded by Lab 3. `graph_tool.py` has no consumer other than `travel_agent_demo.py`, and neither is referenced by any notebook in the six-lab path. Only `01-graphrag-demo/README.md`, itself being rewritten, mentions them.
- **`01-graphrag-demo/test_graphrag.ipynb` and its two executed copies**, `test_graphrag-executed.ipynb` and `test_graphrag-executed-lite.ipynb`. Lab 2's vector notebook takes over its role as the motivating demo, under a `N.M_` name rather than the misleading `test_` prefix.
- **02-semantic-tools-demo**: semantic tool selection over `:Tool` nodes, the `tool_description_embeddings` index, the derived workflow edge, and the token-cost comparison between the naive toolset and the graph-filtered one. Wrong tool selection loses its live demonstration. So does the only place where the graph shaped the agent's control flow rather than its evidence, and the only second graph living in the same Aura instance as the hotel graph.
- **03-multiagent-demo**: graph-backed domain validation via agent swarm. Undetected failures lose their demonstration with it.
- **04-neurosymbolic-demo**: dropped as a standalone lab. Its lesson, the one enabled `max_guests` rule, survives in Lab 4 and reads more strongly there, because the rule comes from the graph rather than from a Python fixture.
- **05-steering-demo**: Agent Control steering.
- **07-agentcore-memory-demo**: managed AgentCore memory, superseded by Lab 6 plus the contrast callout.
- **09-neo4j-mcp-demo**: MCP and controlled Text2Cypher.
- **10-cleanup** as a standalone module. The teardown itself is not removed. It becomes `5.2_teardown.ipynb` inside Lab 5, where the resources are created. It stays a notebook rather than a section so it can keep its own `deletes_resources` gate.

## Renumbering plan

Everything is renumbered. Six labs, one setup folder, and folder names that match lab numbers exactly.

| New folder | Lab | Built from |
|---|---|---|
| `00-setup/` | Step 0, README only | Authored fresh against the credential steps of `00-getting-started/README.md` and `01-graphrag-demo/README.md`, with a new standalone verification script rather than a reused notebook cell |
| `01-graph-build/` | Lab 1 | `01-graphrag-demo/` build path: `prepare_graph.py`, `graph_builder.py`, `build_graph.py`, `build_graph_lite.py`, the build-only remainder of `graph_config.py`, `data/`, `hotel-faqs.zip`, `images/`, `test_graph_builder_metadata.py`, `test_retrieval_setup.py` |
| `02-retrieval/` | Lab 2 | `01-graphrag-demo/retrieval_patterns.ipynb` plus the `HybridCypherRetriever` and abstention cells from `06-agentcore-boto3-demo/01_hybrid_retrieval.ipynb` |
| `03-agents-and-tools/` | Lab 3 | `00-getting-started/getting_started_strands.ipynb` plus a new closing section that assembles `hotel_agent` |
| `04-grounded-write/` | Lab 4 | The write path from `06-agentcore-boto3-demo/`: cells 10 through 15 of `01_hybrid_retrieval.ipynb`, over `reservation_command.py`, `contracts.py`, `graph_setup.py` and their tests |
| `05-agentcore-deploy/` | Lab 5 | `06-agentcore-boto3-demo/deploy_agentcore.ipynb`, `deployment-tools/`, `tool_schemas/`, `advanced-deployment/02_agentcore_walkthrough.ipynb`, and `workshop_cleanup.py` with `test_workshop_cleanup.py` from `10-cleanup/` |
| `06-memory/` | Lab 6, optional | `08-neo4j-memory-demo/` |

Drop the `-demo` suffix. These are labs in a sequence now, not independent demos, and the rename makes that visible in the tree.

**Four source notebooks stayed in the tree beside their replacements,** unregistered in the runner and reachable only by opening them: `02-retrieval/retrieval_patterns.ipynb`, `04-grounded-write/01_hybrid_retrieval.ipynb`, `05-agentcore-deploy/deploy_agentcore.ipynb`, and `05-agentcore-deploy/advanced-deployment/02_agentcore_walkthrough.ipynb`. They were the authoring references, and nothing in the six-lab path points at them.

**Notebooks are never named `test_*`.** Every notebook in the new tree is named `N.M_<topic>.ipynb`. The `test_` prefix belongs to Python test modules that `pytest` collects, and today `01-graphrag-demo/` holds `test_graphrag.ipynb` next to `test_bedrock_providers.py`, so the prefix reads as "this is a test" when the notebook is teaching material and reads as "pytest will collect this" when it will not. Both readings are wrong. The three `test_graphrag*.ipynb` files are being deleted anyway, and no notebook that replaces them takes the prefix back. Held: no notebook anywhere in the tree carries the prefix now, outside `backups/` and the run artifacts under `setup/notebook-output/`.

**Add one shared `workshop/` package.** This is the part that matters more than the numbering. Nine modules are used by more than one lab, and they come from both sides of the current split, not just from Demo 06.

It shipped as a `src` layout, `workshop/pyproject.toml` over `workshop/src/workshop/`, built by hatchling, and it declares `requires-python = ">=3.12"`. Every lab installs it, so 3.12 is the workshop's real floor, matching the `python3.12` Lambda runtime and the `python3.12` container base image. Six documents still say 3.9+ and are stale: the root README in three places, `00-setup/README.md`, and the Lab 2, Lab 3, Lab 4, and Lab 6 READMEs. Its dependencies are the union of what the nine modules import: `boto3`, `neo4j`, `neo4j-graphrag`, and `python-dotenv`.

| Module in `workshop/` | Comes from | Labs that need it |
|---|---|---|
| `retrieval_contract.py` | `01-graphrag-demo/` | 1, 2, 4, 5 |
| `bedrock_providers.py` | `01-graphrag-demo/` | 1, 2 |
| `retrieval_setup.py` | `01-graphrag-demo/` | 1, 2 |
| `graph_connection.py` | split out of `01-graphrag-demo/graph_config.py` | 1, 2, 4, 5 |
| `graph_schema.py` | split out of `01-graphrag-demo/graph_config.py` | 1, 2 |
| `contracts.py` | `06-agentcore-boto3-demo/` | 2, 4, 5 |
| `graph_setup.py` | `06-agentcore-boto3-demo/` | 1, 4 |
| `hybrid_retrieval.py` | `06-agentcore-boto3-demo/` | 2, 3, 4, 5 |
| `reservation_command.py` | `06-agentcore-boto3-demo/` | 4, 5 |

The Lab 1 side is the half that is easy to miss. `retrieval_patterns.ipynb` imports `bedrock_providers`, `graph_config`, `retrieval_contract`, and `retrieval_setup`, and it only resolves them today because it sits inside `01-graphrag-demo/`. Once that notebook becomes `02-retrieval/2.1_vector_retrievers.ipynb`, all four are in a sibling folder with no import path.

`graph_config.py` splits rather than moving whole. The connection helpers `NEO4J_URI` and `neo4j_auth()` become `workshop/graph_connection.py`, and `GRAPH_SCHEMA`, `SCHEMA_NODE_LABELS`, and `OFF_SCHEMA_LABELS` become `workshop/graph_schema.py`, because `retrieval_setup.py` imports `SCHEMA_NODE_LABELS` and Lab 2 renders `GRAPH_SCHEMA`. The build-only remainder, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `EXTRACTION_MAX_TOKENS`, `REQUIRED_CITIES`, and `select_lite_files()`, stays in `01-graph-build/graph_config.py`. Only Lab 1 reads it, and a shared package should not carry lite-versus-full corpus selection.

The remainder imports nothing from the package, which is the opposite of what this spec first said. Its docstring says so explicitly and names where each moved thing went, so there is one obvious place each name comes from and no re-export chain to follow. Callers import from `workshop` directly.

**One shared module needed its data file to travel with it.** `graph_setup.MANIFEST_PATH` resolves as `Path(__file__).parent / "fixtures" / "hotel_ids.json"`, so moving the module alone broke three Lab 4 tests with `FileNotFoundError`. The manifest now lives inside the package and ships through a hatch `force-include` entry. Any future module that reads a file relative to itself needs the same treatment.

Copying any of these into three lab folders guarantees drift. The duplication has already started: all five of `EMBEDDING_MODEL_ID`, `EMBEDDING_PURPOSE`, `EMBEDDING_DIMENSIONS`, `CHUNK_VECTOR_INDEX`, and `CHUNK_FULLTEXT_INDEX` are defined verbatim in both `01-graphrag-demo/retrieval_contract.py` and `06-agentcore-boto3-demo/contracts.py`, and they have to agree for Lab 2 to read the graph Lab 1 built.

This breaks the current one-venv-per-demo convention on purpose. That convention was built for demos that ran independently and in any order. Once the labs share a graph, a contract, and a retriever, the convention costs more than it saves. Keep per-lab `requirements.txt` files, and have each one install the shared package in editable mode. All six shipped with `-e ../workshop` as their first line. Two folders had no requirements file at all after the rename, `02-retrieval/` and `05-agentcore-deploy/`, because each was carved out of a folder whose requirements file went to the other half of the split; both were written when the labs were pointed at the package.

Three consumers beyond the labs had to learn the package too:
- `setup/run_notebooks.py` is a PEP 723 script with its own dependency list, so no notebook importing `workshop.*` could run under it until `"workshop"` plus a `[tool.uv.sources]` entry pointing at `../workshop` as an editable install were added to the inline block.
- The reservation Lambda's build directory gets `pip install --no-deps` of the package rather than a flat copy of named files, which removed the hardcoded `SHARED_MODULES` list. `--no-deps` is what keeps the zip at roughly 865 KB: the package declares `neo4j-graphrag`, tens of megabytes the reservation handler never touches, and `neo4j` is resolved from the Lambda's own `requirements.txt`. If a future change makes `reservation_command` import outside that set, the zip will build and fail only at Lambda runtime.
- The Runtime container reaches the package through a wheel built into `deployment-tools/vendor/`, described under Lab 5 above. `COPY . .` from a build context below the package cannot see it.

The convention is already partly abandoned: `06-agentcore-boto3-demo/test_demo_guest_consistency.py` reads source files out of `04-neurosymbolic-demo/` and `05-steering-demo/`. It now lives at `04-grounded-write/test_demo_guest_consistency.py` and reaches across a folder boundary for a different reason: `test_contracts.py` reads `../05-agentcore-deploy/tool_schemas/tools.json`, and `test_reservation_command.py` loads the Lambda entrypoint from the same sibling lab.

**Do the rename as pure `git mv` operations in one commit,** with no content edits mixed in, so file history survives and the follow-up content commits stay reviewable.

**Files that hardcode the current folder names and must change with it:**

- `setup/run_notebooks.py`, the `NOTEBOOKS` registry. `5.1_agentcore_deploy.ipynb` keeps `deploys_resources=True` behind `--include-deploy`, and `5.2_teardown.ipynb` carries `deletes_resources=True` behind `--include-cleanup`. The runner already skips a registered notebook whose file is missing, and a `SKIP` does not affect the exit code, so the registry can be populated ahead of the content with no runner change. Shipped as ten notebooks across labels 1 through 6, not 0 through 6: Lab 0 has no notebook, so it has no registry entry, and the module docstring says so rather than leaving a reader to wonder where lab 0 went. `5.3_agentcore_walkthrough.ipynb` also carries the deploy gate, because it invokes a Runtime that only a deploy can have created.
- `setup/run_notebooks.py` also carried three stale strings independent of the registry: `--include-deploy`'s help text read "Run lab 7," `--include-cleanup`'s read "Run lab 10," and the module docstring claimed "The default run covers demos 00 through 05" with `--labs 2-5` and `--labs 6` examples that change meaning under the new numbering. All three now name lab 5 and the new numbering, and the docstring reads "The default run covers labs 1 through 4 and lab 6."
- `10-cleanup/workshop_cleanup.py`, which points `CONFIG_FILES` at `:99-100` at `.bedrock_agentcore.yaml` under `06-agentcore-boto3-demo/` and `07-agentcore-memory-demo/`. The whole script moved into `05-agentcore-deploy/`, and `CONFIG_FILES` is now a single entry at `05-agentcore-deploy/deployment-tools/.bedrock_agentcore.yaml`. The comment in `discover_local_config` that explained the old 06-versus-07 case was rewritten to stop naming deleted labs.
- `06-agentcore-boto3-demo/test_demo_guest_consistency.py`, whose single test asserts the guest limit agrees across Demos 04, 05, and 06. Two of its three sources are being removed, so it narrows to `contracts.py` against `graph_setup.py`, then gains an assertion against the seeded `Rule` node. It shipped at `04-grounded-write/` as three tests rather than one: the constants check and the source check were split, because they fail for different reasons and the old single test reported them as one, and the live `Rule`-node check is a third in its own class.
- `01-graphrag-demo/test_bedrock_providers.py`, which names folders in docstrings and path logic. It moved to `01-graph-build/` with the rest of Lab 1's tests. `01-graphrag-demo/tools/graph_tool.py` and `05-steering-demo/test_score_ledger.py` are deleted rather than repointed.
- `01-graphrag-demo/.env`, which is gitignored at `.gitignore:46` and therefore invisible to `git mv`. A demo-local `.env` takes precedence over the root one, so a copy stranded at a deleted path is a silent credential bug. Deleted by hand. No lab folder carries a local `.env` now; every lab reads the repo-root file.
- Every per-lab `README.md`, the root `README.md` module table, `CLAUDE.md`, and `workshop-delivery/architecture.md`. The root README, `CLAUDE.md`, all seven lab READMEs, and `workshop-delivery/architecture.md` are rewritten. `architecture.md` also carries its own audit of stale references it noticed and deliberately did not change; that list is the shortest route to what documentation work is left. `05-agentcore-deploy/deployment-tools/README.md` is rewritten too, as "Lab 5 deployment source." One document is not: `workshop-delivery/README.md`, the facilitator delivery guide, still describes the eleven-demo layout with a Core track of Demo 00, 01, 04, 05, 06, and 10. See Open items.

## Settled

- **Framing** is "grounded retrieval to production." See the section at the top for the documents it changes.
- **Semantic tool selection is dropped.** `02-semantic-tools-demo` does not become a lab. Lab 3 is the Strands primer alone.
- **Renumbering** is a full renumber to `00-setup/` through `06-memory/`, with a shared `workshop/` package of nine modules drawn from both `01-graphrag-demo/` and `06-agentcore-boto3-demo/`.
- **Lab 3 closes with one assembled `hotel_agent`,** carrying the Lab 2 retriever and the hook-guarded booking tool. Lab 4 registers the write onto that agent by name.
- **`graph_config.py` splits** rather than moving whole into the shared package.
- **`travel_agent_demo.py` and `tools/graph_tool.py` are deleted** along with the FAISS path.
- **Notebooks are never named `test_*`.** The prefix is reserved for Python test modules. Every notebook in the new tree is `N.M_<topic>.ipynb`.
- **Lab 1 build times are confirmed**: 15 minutes lite, 2 hours full. Bedrock concurrency is confirmed working at event scale.
- **The stale claim in `deployment-tools/README.md`** is fixed twice over. The pre-rebuild fix pointed it at `provision_agentcore.py` for the infrastructure and at the deploy notebook for the Runtime launch. The rebuild then made it stale again, since it still said "Demo 06 Deployment Tools" and still described the Lambda and Runtime importing `reservation_command.py` and `contracts.py` from "the demo root one level up," which the shared package ended. It is now rewritten as "Lab 5 deployment source": it points at `../5.1_agentcore_deploy.ipynb`, explains why `5.1` changes directory into the folder, and describes the wheel in `vendor/` and the `workshop` package at the repository root.
- **The deploy notebook** is restored from commit `861ec06^`, 43 cells, output-stripped. It now sits at `05-agentcore-deploy/deploy_agentcore.ipynb` and stays in the tree as reference, unregistered in the runner.
- **The model ID is standardized on `us.anthropic.claude-sonnet-5`,** defined once as the default in `workshop.bedrock_providers`. The carried-forward Lab 2 and Lab 4 cells had defaulted `MODEL_ID` to `us.anthropic.claude-sonnet-4-6`, which would have put the notebooks on a different model from the shared embedder module. Seven files changed. One straggler survives: `04-grounded-write/README.md` still tells the reader the notebook defaults to Sonnet 4-6, where the notebook defaults to Sonnet 5.
- **Test counts, measured.** 12 in Lab 1, 56 in Lab 4, 20 in Lab 5, 22 in Lab 6. The write path is 29 of Lab 4's 56. The often-quoted 54 was every test in the old Demo 06, and the number moved twice as `test_demo_guest_consistency.py` went from one test to two and then to three.

## Open items

- ~~**The flow diagram.**~~ Closed. `images/six-lab-path.svg` is drawn and the root README renders it at line 35. The old `images/why-ai-agents-fail-six-demos-progressive-flow.png` stays in the tree and is now referenced by nothing.
- **Timing budget per lab.** Six labs need a rehearsed per-lab time budget, especially Lab 5, which the current README scopes at 30 to 45 minutes on its own.
- **Documentation that the rebuild left behind.** `workshop-delivery/README.md`, the facilitator delivery guide, still lists eleven demos, tracks by audience, and paths under `06-agentcore-boto3-demo/`. The Python floor is stated three ways: the shared package requires 3.12+, the Lambda runtime and the container base image are 3.12, and the root README badge plus `00-setup/README.md`, `02-retrieval/README.md`, `03-agents-and-tools/README.md`, `04-grounded-write/README.md`, and `06-memory/README.md` all still say 3.9+. `04-grounded-write/README.md:241` still tells the reader the notebook defaults to `us.anthropic.claude-sonnet-4-6`. The root README's build-status note at line 49 still says `5.1_agentcore_deploy.ipynb` and `5.3_agentcore_walkthrough.ipynb` are being authored, where both are complete at 19 and 13 cells and registered in the runner. `workshop-delivery/architecture.md` carries its own audit of these and a few more, which is the shortest route to the remaining list.
- **Whether Lab 3 still earns a folder.** It is one reused notebook plus one new closing section. Folding the primer into the top of Lab 4 would give five labs and one less context switch, at the cost of mixing the framework tour with the write path. Left as six labs here, since only the tool-selection content was cut. Revisit if the rehearsal comes in over budget.
