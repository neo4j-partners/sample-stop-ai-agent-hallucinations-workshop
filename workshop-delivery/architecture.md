# Workshop Architecture, DRAFT under review

> **Status: DRAFT under review.** This document is offline documentation only.
> Nothing here provisions or deletes an AWS resource. It describes the six-lab
> layout as the repository now stands, and it is reviewed against the root
> `README.md`, the seven per-lab READMEs, `04-grounded-write/CONTRACTS.md`, and
> `05-agentcore-deploy/README.md`. Where a claim could not be checked against a
> file in the tree, it is marked **unverified** rather than stated as fact. The
> list of those claims is at the bottom.

The repository is one sequential path of six labs sharing one installable
package. Three views follow:

1. **The six-lab path**, from raw documents through a deployed agent, and what
   each lab hands the next.
2. **The Lab 5 deployed boundary**, the AWS resources that host the Lab 4 agent
   and the two teardown paths that remove them.
3. **The shared `workshop/` package**, the structural change from the older
   self-contained-demo layout.

---

## View 1: The six-lab path

Lab 0 is a credential checklist with no notebook. Labs 1 through 4 create no AWS
resources beyond Bedrock inference calls. Lab 5 is the only lab that creates
billable infrastructure. Lab 6 is optional.

```
 +--------------------------------------------------------------------------------------+
 |  LAB 0  00-setup/            README only, no notebook                                |
 |    One repo-root .env: NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD,                    |
 |      NEO4J_DATABASE, AWS_REGION                                                      |
 |    One Aura instance. Bedrock model access.                                          |
 +--------------------------------------------------------------------------------------+
                                        |
                                        v
 +--------------------------------------------------------------------------------------+
 |  LAB 1  01-graph-build/      1.1_build_graph.ipynb                                   |
 |                                                                                      |
 |    hotel-faqs.zip  ---> SimpleKGPipeline ---> Neo4j Aura                             |
 |      300 .txt docs         |                                                         |
 |      lite build takes 30   +--> Bedrock reasoning: entity extraction                 |
 |                            +--> Bedrock embeddings: chunk vectors                    |
 |                            schema=GRAPH_SCHEMA, from_pdf=False,                      |
 |                            perform_entity_resolution=True,                           |
 |                            FixedSizeSplitter chunk_size=12000, overlap=0             |
 |                                                                                      |
 |    Pinned extraction schema, workshop.graph_schema.GRAPH_SCHEMA:                     |
 |      Hotel -HAS_ROOM->         Room                                                  |
 |      Hotel -OFFERS_AMENITY->   Amenity                                               |
 |      Hotel -HAS_POLICY->       Policy                                                |
 |      Hotel -PROVIDES_SERVICE-> Service                                               |
 |      additional_node_types / additional_relationship_types /                         |
 |      additional_patterns all false, so anything off-contract is refused.             |
 |      OFF_SCHEMA_LABELS lists 11 labels earlier unpinned runs produced;               |
 |      their presence after a build means the schema did not hold.                     |
 |                                                                                      |
 |    Document and Chunk come from the pipeline, not from extraction:                   |
 |      Hotel -FROM_CHUNK-> Chunk -FROM_DOCUMENT-> Document                             |
 |      Every pipeline node also carries the __KGBuilder__ label                        |
 |                                                                                      |
 |    Indexes created: hotel_chunk_embeddings  vector on Chunk.embedding,               |
 |                                             1024 dim, cosine                         |
 |                    hotel_chunk_fulltext    full-text on Chunk.text                   |
 |    Then db.awaitIndexes, then a contract check on type, ONLINE state,                |
 |    labels, properties, dimensions, and similarity function.                          |
 |                                                                                      |
 |    Closing cell stamps fixture hotel_ids from the manifest, creates three            |
 |    uniqueness constraints, and seeds the Rule node the Lab 4 write reads:            |
 |      Rule {rule_id: 'demo-06-maximum-guests', rule_type: 'MAXIMUM_GUESTS',           |
 |             max_guests: 10, enabled: true, rejection_message,                        |
 |             steering_message, workshop_owner: 'neo4j-ftw-demo-6',                    |
 |             schema_version: 1}                                                       |
 +--------------------------------------------------------------------------------------+
                                        |  the graph, the two indexes, the Rule node
                                        v
 +--------------------------------------------------------------------------------------+
 |  LAB 2  02-retrieval/        2.1_vector_retrievers.ipynb                             |
 |                              2.2_fulltext_retrievers.ipynb                           |
 |                              2.3_text2cypher.ipynb          optional                 |
 |                                                                                      |
 |    2.1  VectorRetriever, then VectorCypherRetriever                                  |
 |    2.2  VectorRetriever and HybridRetriever inline for comparison, then the          |
 |         production HybridCypherRetriever imported rather than rebuilt                |
 |    2.3  Text2CypherRetriever, optional. Nothing later depends on it.                 |
 |                                                                                      |
 |    2.2 closes on abstention. The availability hero question has no answer in         |
 |    the graph, so the correct behavior is to decline.                                 |
 |                                                                                      |
 |    The survivor is workshop.hybrid_retrieval.search_hotel_knowledge:                 |
 |      HybridCypherRetriever over both indexes                                         |
 |      HybridSearchRanker.NAIVE, top_k 5, one reviewed static Cypher traversal         |
 |      returns chunk_evidence capped at 1200 chars, combined_score, exact_terms        |
 |        capped at 20, hotel_id, hotel_name, address, guest_rating, and                |
 |        amenities sorted and capped at 12                                             |
 |      hotel_id is null for any hotel outside the fixture set, which is what           |
 |        keeps the Lab 4 write to hotels the graph can identify                        |
 |                                                                                      |
 |    2.2's inline comparison uses ranker "linear", alpha 0.2. That is the              |
 |    teaching configuration, not the production one.                                   |
 +--------------------------------------------------------------------------------------+
                                        |  one retrieval function, importable
                                        v
 +--------------------------------------------------------------------------------------+
 |  LAB 3  03-agents-and-tools/ 3.1_strands_primer.ipynb                                |
 |                                                                                      |
 |    Five teaching sections: agents, model providers, @tool, token metrics,            |
 |    lifecycle hooks, and a Swarm. Then a sixth that assembles one agent:              |
 |                                                                                      |
 |      hotel_agent = Agent(                                                            |
 |          name="hotel_agent",                                                         |
 |          model="us.anthropic.claude-sonnet-5",                                       |
 |          tools=[search_hotel_knowledge_tool, book_room],                             |
 |          hooks=[MaxGuestsHook()],                                                    |
 |          system_prompt=... + GROUNDING_INSTRUCTIONS,                                 |
 |      )                                                                               |
 |                                                                                      |
 |    search_hotel_knowledge_tool is a @tool wrapper over the Lab 2 function.           |
 |    MaxGuestsHook is a BeforeToolCallEvent hook that cancels a call above a           |
 |    Python literal of 10. That literal is the fixture version, and it is the          |
 |    thing Lab 4 replaces.                                                             |
 +--------------------------------------------------------------------------------------+
                                        |  hotel_agent
                                        v
 +--------------------------------------------------------------------------------------+
 |  LAB 4  04-grounded-write/   4.1_reservation_write.ipynb                             |
 |                                                                                      |
 |    The write goes onto hotel_agent and MaxGuestsHook comes off, because the          |
 |    rule now lives in the graph and the command reads it at the data boundary.        |
 |                                                                                      |
 |    workshop.reservation_command.create_reservation_request                           |
 |    Five fields and no more, additionalProperties false:                              |
 |      request_id, hotel_id, check_in, check_out, guests                               |
 |    status:      accepted | rejected | error                                          |
 |    reason_code: max_guests_exceeded, unknown_hotel, invalid_dates,                   |
 |                 unauthorized, service_error                                          |
 |                                                                                      |
 |    One session.execute_write transaction does all of it:                             |
 |      1. read the existing request by request_id, for idempotency                     |
 |      2. read the enabled Rule node for max_guests                                    |
 |      3. CREATE (:ReservationRequest)-[:FOR_HOTEL]->(:Hotel), re-checking             |
 |         guests <= max_guests inside the write itself                                 |
 |    Fail-closed: a missing or disabled Rule raises rather than defaulting.            |
 |    request_id is the caller's canonical UUID and the idempotency key, backed         |
 |    by the demo06_reservation_request_id uniqueness constraint.                       |
 |                                                                                      |
 |    Frozen contract. 04-grounded-write/CONTRACTS.md is the authority.                 |
 +--------------------------------------------------------------------------------------+
                                        |  the agent, unchanged
                                        v
 +--------------------------------------------------------------------------------------+
 |  LAB 5  05-agentcore-deploy/ 5.1_agentcore_deploy.ipynb        gated: deploy         |
 |                              5.2_teardown.ipynb                gated: cleanup        |
 |                              5.3_agentcore_walkthrough.ipynb   optional, gated       |
 |                                                                                      |
 |    The same agent on AgentCore Runtime. See View 2.                                  |
 |    The retrieval tool does not change: deployment-tools/booking_agent.py             |
 |    imports search_hotel_knowledge from workshop.hybrid_retrieval, the same           |
 |    module Labs 2, 3, and 4 import.                                                   |
 +--------------------------------------------------------------------------------------+
                                        |
                                        v
 +--------------------------------------------------------------------------------------+
 |  LAB 6  06-memory/           6.1_neo4j_agent_memory.ipynb      OPTIONAL              |
 |                                                                                      |
 |    Inspectable Neo4j memory with provenance and actor isolation, weighed             |
 |    against AgentCore Memory as the managed alternative.                              |
 |                                                                                      |
 |    Library-owned:   User -HAS_PREFERENCE-> Preference                                |
 |                     Conversation -HAS_MESSAGE-> Message                              |
 |    Workshop-owned:  Preference -DERIVED_FROM-> Message                               |
 |                     Preference -ABOUT_HOTEL->  Hotel                                 |
 |                                                                                      |
 |    That last edge is the argument for graph memory: a preference traverses           |
 |    back to the message that produced it and forward to the real Lab 1 Hotel.         |
 |    No property is added to Hotel and no Entity label is introduced.                  |
 |                                                                                      |
 |    Its own embedding contract, separate from Labs 1-5. See below.                    |
 |    Identifier prefix demo08-, workshop_owner neo4j-ftw-demo-8. Both are live         |
 |    strings that cleanup_memory.py matches on, not leftover numbering.                |
 +--------------------------------------------------------------------------------------+
```

### One definition of the models, for Labs 1 through 5

Both models used by the core path have a single definition, in
`workshop.bedrock_providers`:

| Role | Model |
|---|---|
| Reasoning | `us.anthropic.claude-sonnet-5` |
| Embeddings | `amazon.nova-2-multimodal-embeddings-v1:0`, purpose `GENERIC_INDEX`, 1024 dimensions |

Lab 6 is the exception, and deliberately so. Its memory store is driven by
`neo4j-agent-memory` rather than by the shared package, it embeds with
`amazon.titan-embed-text-v2:0`, and it writes to its own
`message_embedding_idx` and `preference_embedding_idx` indexes. Those
dimensions are pinned to 1024 in the notebook because the library's
`EmbeddingConfig` otherwise defaults to 1536. Lab 6's indexes and Lab 1's
`hotel_chunk_embeddings` are separate, so the two embedding contracts do not
have to agree.

`workshop.retrieval_contract` holds the five constants that have to agree
between the lab that writes the graph and the labs that read it:
`EMBEDDING_MODEL_ID`, `EMBEDDING_PURPOSE`, `EMBEDDING_DIMENSIONS`,
`CHUNK_VECTOR_INDEX`, and `CHUNK_FULLTEXT_INDEX`. A mismatch in the three
embedding constants returns wrong results with no error, which is why there is
one definition rather than one per lab.

`workshop.contracts` re-exports those five and adds the write-path constants,
including `HYBRID_RANKER = "NAIVE"`, `HYBRID_TOP_K = 5`, `MAX_GUESTS = 10`,
`OVER_LIMIT_GUESTS = 15`, `MAX_GUESTS_RULE_ID = "demo-06-maximum-guests"`, and
`WORKSHOP_OWNER = "neo4j-ftw-demo-6"`. The `demo-06` and `demo-6` strings are
live identifiers in code rather than leftover labels from the old numbering.

### The acceptance runner

`setup/run_notebooks.py` registers ten notebooks across labs 1 through 6. Lab 0
has no notebook, so it has no registry entry. Two flags gate Lab 5, because those
notebooks touch real AWS resources:

```bash
uv run setup/run_notebooks.py --list                       # the registry
uv run setup/run_notebooks.py                              # labs 1-4 and 6
uv run setup/run_notebooks.py --labs 5 --include-deploy     # 5.1 and 5.3
uv run setup/run_notebooks.py --labs 5 --include-cleanup    # 5.2
```

Every live cell self-skips when Neo4j or Bedrock credentials are absent, so the
default run is green offline. A clean run proves only that no cell raised.

---

## View 2: The Lab 5 deployed boundary

Two creation paths stand this up, in order. `setup/provision_agentcore.py`
creates the privileged infrastructure from a terminal.
`5.1_agentcore_deploy.ipynb` then builds and launches the Runtime through the
`bedrock-agentcore-starter-toolkit`.

```
   CALLER: 5.1 smoke tests, or 5.3_agentcore_walkthrough.ipynb
   creates request_id = uuid4(), reuses it on every delivery
                     |
                     |  {prompt, request_id}
                     v
 +====================== AWS, one region =========================================+
 |                                                                                |
 |  +----------------------------+        +----------------------------------+    |
 |  |  Amazon Bedrock            |<-------|  AgentCore Runtime, ARM64        |    |
 |  |  us.anthropic.             | query  |  booking_agent.py                |    |
 |  |    claude-sonnet-5         | text   |  image pulled from ECR           |    |
 |  |  amazon.nova-2-            |------->|                                  |    |
 |  |    multimodal-             |vectors |  Tool 1, in-process:             |    |
 |  |    embeddings-v1:0         |        |    search_hotel_knowledge        |    |
 |  |    GENERIC_INDEX, 1024     |        |    workshop.hybrid_retrieval     |    |
 |  +----------------------------+        |    READ ONLY                     |    |
 |                                        |    Neo4j from container env vars |    |
 |                                        |                                  |    |
 |                                        |  Tool 2, discovered over MCP:    |    |
 |                                        |    demo06-reservation-request    |    |
 |                                        |      ___create_reservation_      |    |
 |                                        |      request                     |    |
 |                                        |                                  |    |
 |                                        |  ReservationRequestGuard, a      |    |
 |                                        |  BeforeToolCallEvent hook, binds |    |
 |                                        |  the call to the caller's        |    |
 |                                        |  request_id or cancels it        |    |
 |                                        +----------------+-----------------+    |
 |                                                         |  request_id          |
 |                                                         v                      |
 |                                        +----------------------------------+    |
 |                                        |  AgentCore Gateway               |    |
 |                                        |  demo06-gateway, NONE auth, MCP  |    |
 |                                        |  exactly one target:             |    |
 |                                        |    demo06-reservation-request     |   |
 |                                        |  Gateway-subset JSON Schema       |   |
 |                                        |  projection of the five fields   |    |
 |                                        +----------------+-----------------+    |
 |                                                         |  Gateway IAM role    |
 |                                                         v                      |
 |                                        +----------------------------------+    |
 |                                        |  Reservation Lambda, ONE         |    |
 |                                        |  demo06-reservation-request      |    |
 |                                        |  python3.12, arm64, 30s, 256 MB  |    |
 |                                        |  wraps workshop.                 |    |
 |                                        |    reservation_command           |    |
 |                                        |  reads the max_guests Rule from  |    |
 |                                        |    the graph, then writes        |    |
 |                                        |  THE ONLY GRAPH WRITER           |    |
 |                                        |  reads NEO4J_COMMAND_SECRET_ID   |    |
 |                                        +----------------+-----------------+    |
 |                                                         |                      |
 |  +-------------------------------+  +------------------+ |                     |
 |  |  AWS Secrets Manager          |  |  IAM, three      | |                     |
 |  |  demo06/neo4j-command         |  |  least-privilege | |                     |
 |  |  {uri, username, password,    |  |  roles           | |                     |
 |  |   database}                    |  |                  | |                    |
 |  |  ONE secret. The Lambda reads |  |  demo06-         | |                     |
 |  |  it. The Runtime has no path  |  |   reservation-   | |                     |
 |  |  to it.                        |  |   lambda-role    | |                    |
 |  +-------------------------------+  |  demo06-gateway- | |                     |
 |                                     |   role           | |                     |
 |  +-------------------------------+  |  demo06-runtime- | |                     |
 |  |  CloudWatch and AgentCore     |  |   role           | |                     |
 |  |  observability                |  |                  | |                     |
 |  |  request_id correlates        |  |  The Runtime role| |                     |
 |  |    Runtime -> Gateway ->      |  |  grants NO       | |                     |
 |  |    Lambda -> graph write      |  |  Secrets Manager | |                     |
 |  |  Logs never carry prompts,    |  |  access          | |                     |
 |  |  credentials, secret values,  |  +------------------+ |                     |
 |  |  or connection strings        |                       |                     |
 |  |  /aws/bedrock-agentcore/      |                       |                     |
 |  |    runtimes/                  |                       |                     |
 |  +-------------------------------+                       |                     |
 +==========================================================|=====================+
        read-only, container env vars   |                    |  command credential,
        NEO4J_URI / NEO4J_USERNAME /    |                    |  demo06/neo4j-command
        NEO4J_PASSWORD / NEO4J_DATABASE v                    v
      +========================= Neo4j Aura ==================================+
      |                                                                       |
      |   Hotel -HAS_ROOM-> Room, -OFFERS_AMENITY-> Amenity,                  |
      |         -HAS_POLICY-> Policy, -PROVIDES_SERVICE-> Service             |
      |   Hotel -FROM_CHUNK-> Chunk -FROM_DOCUMENT-> Document                 |
      |                                                                       |
      |   Indexes:  hotel_chunk_embeddings  vector on Chunk.embedding,        |
      |                                     1024 dim, cosine                  |
      |             hotel_chunk_fulltext    full-text on Chunk.text           |
      |                                                                       |
      |   Constraints, all UNIQUENESS:  demo06_fixture_hotel_id               |
      |                                 demo06_reservation_request_id         |
      |                                 demo06_rule_id                        |
      |                                                                       |
      |   Rule node:  demo-06-maximum-guests, max_guests 10, enabled,         |
      |               workshop_owner = neo4j-ftw-demo-6                       |
      |                                                                       |
      |   Workshop writes:  ReservationRequest -FOR_HOTEL-> Hotel             |
      +=======================================================================+
```

The retrieval traversal reads `(node:Chunk)<-[:FROM_CHUNK]-(candidate:Hotel)`,
so vector and full-text search find the chunk and the traversal finds the hotel
connected to it. One hotel is chosen deterministically, tie-broken on `hotel_id`
then `name`, so the same query returns the same hotel identity on every run.

### The security boundary worth stating

The Runtime and the Lambda reach the same Aura instance by different means, and
that asymmetry is the point.

- The Runtime's retrieval path is read-only, and it takes Neo4j from container
  environment variables set at launch. Its execution role grants no Secrets
  Manager access at all, so the container cannot read the command credential
  even if the model asks it to.
- **What makes that path read-only is worth stating precisely.** The Cypher in
  `workshop.hybrid_retrieval` is reviewed and static. No query text is
  interpolated and no model writes or generates any part of it, and the query
  contains no write clause. The module does not open the session in a read-only
  access mode, and in the executable one-user form the Neo4j credential itself
  carries write privileges. So read-only here is a property of the query and of
  code review, not of the connection. The two-user form in `DEPLOYMENT.md` is
  what turns it into a property of the credential.
- The one path that writes to the graph is the reservation Lambda, and it reads
  its credential from `demo06/neo4j-command`, a secret the Runtime cannot see.
  `workshop.reservation_command.handler` picks its source by looking for
  `NEO4J_COMMAND_SECRET_ID`. When that variable is set it reads the secret
  through Secrets Manager, and otherwise it falls back to the four local
  `NEO4J_*` variables. Setting the variable is what moves the Lambda from the
  local form to the deployed one.
- The Gateway's target set holds exactly one entry. `booking_agent.py` calls
  `list_tools_sync()` at startup and raises if the discovered list is anything
  other than `demo06-reservation-request___create_reservation_request`, so a
  Gateway that has grown a second target fails loudly rather than handing the
  model a wider surface.
- `request_id` is the caller's UUID and the single correlation identifier across
  Runtime logs, Gateway, Lambda logs, and the stored `ReservationRequest` node.
  It is also the idempotency key, so re-delivering the same value returns the
  existing record rather than writing a second one.
- **The Gateway schema is narrower than the enforcement.**
  `deployment-tools/gateway_target.json` carries the output of
  `contracts.gateway_reservation_input_schema()`, which projects the closed
  five-field schema onto the subset AgentCore accepts. It keeps only `type`,
  `description`, and `items` per property and drops `additionalProperties`. Full
  validation stays in the Lambda, where `_validate_command` rejects any payload
  whose key set is not exactly the five fields. A schema the platform will accept
  is therefore not the security boundary, and the Lambda is.
- The Lambda wrapper holds no logic of its own. It is 13 lines that do
  `from workshop.reservation_command import handler`, configured as
  `lambda_function.handler`, so the deployed command is the same code Lab 4 ran.
- Secret values never appear in a deployment package, a Gateway schema, a
  prompt, or a log.

The stronger form of this boundary, two Neo4j identities on two secrets, is
documented as the production-hardening step in
`05-agentcore-deploy/advanced-deployment/DEPLOYMENT.md`. The executable path is
the one-user form: one secret for the Lambda, environment variables for the
Runtime, and no `NEO4J_READ_SECRET_ID`.

### Why the shared package is shipped as a wheel

`booking_agent.py` imports `workshop.hybrid_retrieval` directly, which is what
makes the retrieval logic the same code Lab 2 ran rather than a second copy. The
package lives at `workshop/` in the repository root, outside the
`deployment-tools/` container build context, and a build cannot reach up out of
its own context. So `5.1_agentcore_deploy.ipynb` builds it into a wheel
immediately before launch:

```bash
uv build --wheel --out-dir vendor ../../workshop
```

`agent_requirements.txt` pins that exact filename, `./vendor/workshop-0.1.0-py3-none-any.whl`,
rather than requesting a package named `workshop`, which would let the resolver
reach PyPI for something unrelated. The `Dockerfile` copies `vendor/` before the
install line runs. The wheel is gitignored build output and the directory itself
is tracked, because a `COPY vendor/ vendor/` against a missing directory fails
the image build.

### Two teardown paths, because there were two creation paths

Neither half removes the other, and either one alone leaves the other still
billing.

| Tag | Applied by | Removed by |
|---|---|---|
| `WorkshopResource=stop-ai-agent-hallucinations` | The tagging cell in `5.1_agentcore_deploy.ipynb` | `5.2_teardown.ipynb`, which runs `workshop_cleanup.py` |
| `demo06-agentcore=true` | `setup/provision_agentcore.py provision` | `setup/provision_agentcore.py teardown` |

The starter toolkit creates the ECR repository, the CodeBuild project, and the
Runtime itself, and it does not forward tags, which is why `5.1` tags those three
immediately after launch and reads the Runtime tag back to verify it stuck.
Skipping that cell makes `workshop_cleanup.py` report them as
`UNTAGGED_BLOCKED`, refuse to delete them, and exit non-zero.

Deletion is scoped by tag and never by name prefix. `CLEANUP.md` records the
incident that settled this: an earlier version selected IAM roles by name prefix,
IAM is global, and the sweep destroyed five roles the workshop never created.

Aura is not an AWS resource in the account, so nothing in Lab 5 can reach it.
The instance is terminated from the Aura console.

---

## View 3: The shared `workshop/` package

This is the structural change from the older layout, where each demo folder
carried its own copy of the code more than one demo needed.

```
 workshop/
   pyproject.toml          name "workshop", version 0.1.0, hatchling,
                           src-layout, requires-python >=3.12
   src/workshop/
     retrieval_contract.py   the five embedding and index constants
     contracts.py            re-exports those five, adds the write-path constants,
                             the TypedDicts, and the closed JSON schemas.
                             Opens no client, so the Lambda can import it
     bedrock_providers.py    the one definition of both models
     graph_schema.py         the pinned extraction schema
     graph_connection.py     Neo4j connection values from the environment
     retrieval_setup.py      index creation and verification
     graph_setup.py          fixtures, the Rule node, readiness checks
     hybrid_retrieval.py     search_hotel_knowledge, the retriever Labs 2-5 share
     reservation_command.py  the grounded write
     fixtures/hotel_ids.json shipped as package data through a hatch
                             force-include entry
```

| Module | Labs that import it |
|---|---|
| `retrieval_contract.py` | 1, 2, 4, 5 |
| `bedrock_providers.py` | 1, 2 |
| `retrieval_setup.py` | 1, 2 |
| `graph_connection.py` | 1, 2, 4, 5 |
| `graph_schema.py` | 1, 2 |
| `contracts.py` | 2, 4, 5 |
| `graph_setup.py` | 1, 4 |
| `hybrid_retrieval.py` | 2, 3, 4, 5 |
| `reservation_command.py` | 4, 5 |

Each lab keeps its own `requirements.txt` and its own `.venv`, and each one
installs the package in editable mode with `-e ../workshop`. Three consumers
outside the labs install it differently, and the difference matters:

- `setup/run_notebooks.py` is a PEP 723 script that lists `workshop` in its
  inline dependency block with a `[tool.uv.sources]` entry pointing at
  `../workshop` as an editable install. Without that, no notebook importing
  `workshop.*` runs under the acceptance runner.
- The reservation Lambda's deployment package installs the shared package with
  `--no-deps` and resolves `neo4j` from the Lambda's own `requirements.txt`. The
  package declares `neo4j-graphrag`, which the reservation handler never touches
  and which would add tens of megabytes to the zip. A future change that makes
  `reservation_command` import something outside that narrow set builds fine and
  fails at Lambda runtime.
- The Runtime image installs the wheel described in View 2.

`workshop/__init__.py` deliberately re-exports nothing. `graph_connection` raises
at import when `NEO4J_PASSWORD` is unset, and `bedrock_providers`, `graph_setup`,
`hybrid_retrieval`, and `reservation_command` all build AWS or Neo4j clients. A
convenience re-export would drag every one of those into a bare
`import workshop`, and `contracts` promises the Lambda that it can be imported
without touching credentials or the network.

---

## Trust boundary, in words

```
 ============================== TRUST BOUNDARY ==============================
 * Labs 1 through 4 and Lab 6 run in the participant's own notebook kernel
   against the participant's own Aura instance and Bedrock. They create no AWS
   resources beyond inference calls.
 * Aura credentials stay in the participant's own environment, read from
   NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, and NEO4J_DATABASE in the
   repo-root .env. They are never placed in a prompt or a tool input.
 * workshop.graph_connection raises at import when NEO4J_PASSWORD is unset.
   There is no default password, so a missing credential fails loudly instead
   of sending a bad one. Notebooks import connecting modules inside a guarded
   branch for exactly that reason, which is also what lets every live cell
   self-skip offline.
 * Lab 5 moves that same boundary into AWS. The Runtime gets Neo4j from
   container environment variables and no Secrets Manager access. The
   reservation Lambda gets the write credential from one secret the Runtime
   cannot read.
 * Three least-privilege IAM roles rather than one shared role. The Runtime can
   invoke the model and pull its image. The Gateway can invoke one Lambda. The
   Lambda can read one secret and write one log group.
 * The five-field reservation contract is closed. additionalProperties is false,
   and no second write path exists.
 * Lab 6's actor isolation is not authorization. Recall is actor-anchored
   Cypher rooted at (:User {identifier}), and multi_tenant=True makes an
   unattributed write raise. The library's embedding search is store-wide with
   no owner filter, which is why the notebook does not use it as the boundary.
   Authenticating the actor and authorizing the session ID stays the
   application's job.
 ===========================================================================
```

---

## Claims marked unverified

These appear in the repository's documentation and are carried here as claims
rather than as confirmed facts, because nothing in the tree settles them and
this document was written without running a notebook, a deploy, or a Cypher
query.

- **Live behavior of any lab.** Nothing here was executed. `run_notebooks.py
  --list` was run to confirm the registry, and no notebook was run. The claim
  that Lab 5 deploys, answers its four smoke questions, and tears down cleanly
  is the plan's Phase 8 validation step, and `new-content-plan.md` still records
  Phase 8 as pending.
- **The four-hour delivery budget and any per-lab timing.** `new-content-plan.md`
  records Phase 0, the timing probe, and Phase 11, the rehearsal, as both
  pending. The 15-minute lite build and 2-hour full build figures come from the
  root README and the plan's assumptions, not from a measured run recorded in
  the tree.
- **The 73% hallucination-reduction figure** in the root README's Graph-RAG
  comparison table is cited to arXiv 2503.13514. The citation was not checked.
- **`5.3_agentcore_walkthrough.ipynb` reading `AGENT_RUNTIME_ARN`.** The file is
  present and the READMEs describe the handoff, but no run has confirmed the
  Runtime ARN flows from `5.1` to `5.3`.
- **Whether the deployed Lambda imports the shared package cleanly.** The plan
  flags this as the first real test of the packaging change and records it as
  outstanding.
- **CloudWatch log group paths and AgentCore trace contents.** Taken from
  `05-agentcore-deploy/README.md` and `5.1_agentcore_deploy.ipynb` prose, not
  observed.

### Stale references noticed elsewhere, since resolved

An earlier revision of this section listed eleven-demo names, module numbers, and
paths that survived the renumbering in other files. Every item has been fixed:
`workshop-delivery/README.md` now describes the six-lab path, the two build-status
notes in `README.md` and `05-agentcore-deploy/README.md` match what is on disk,
`deployment-tools/README.md` and `CLEANUP.md` speak of labs, the `MODEL_ID`
default reads `us.anthropic.claude-sonnet-5` everywhere, `6.1`'s comparison table
no longer cites a Module 7, and `build_graph.py` points its docstring at
`workshop.graph_schema.GRAPH_SCHEMA`.

The Python floor is now stated one way. `workshop/pyproject.toml` sets
`requires-python = ">=3.12"` and every lab installs that package with
`-e ../workshop`, so 3.12+ is the binding floor. The 3.9+ and 3.11+ badges are
gone from all seven lab READMEs and the root README, because the install commands
those files document fail on anything older.

One item on the earlier list was wrong rather than stale.
`01-graph-build/README.md` says "Nine code cells" and `1.1_build_graph.ipynb` has
exactly nine, so nothing needed changing.

### What this document deliberately dropped

The previous revision carried a second architecture view for Demo 09, the Neo4j
MCP server and controlled Text2Cypher trust boundary, plus references to Demo
01b and a deferred `06-agentcore-boto3-demo/advanced-deployment/` deployment
path. Demo 09 and Demo 01b no longer exist in the tree, and the deployment that
was deferred is now Lab 5 and part of the required path. Controlled Text2Cypher
survives only as the optional `2.3_text2cypher.ipynb`, which uses
`Text2CypherRetriever` with a hand-written schema, two examples, and a custom
prompt constraining it to reads. There is no MCP server anywhere in the
repository, and nothing in the six-lab path lets a model generate Cypher that
reaches the graph unreviewed.
