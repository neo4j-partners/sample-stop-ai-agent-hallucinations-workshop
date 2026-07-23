# Workshop Architecture (PROPOSED DRAFT for review)

> **Status: PROPOSED DRAFT.** This document is offline documentation work only.
> It proposes the architecture visual called for by the v2 plan
> ("Documentation and Delivery" -> "Root documentation") for review before it is
> adopted into the root README or facilitator guide. Nothing here deploys AWS
> resources. Review the diagrams against the frozen contracts in
> `06-agentcore-boto3-demo/CONTRACTS.md` and
> `06-agentcore-boto3-demo/deployment-deferred/DEPLOYMENT.md`.

This file contains two views:

1. The **core Demo 06** view: the local in-process path the single participant
   notebook executes on the participant's own laptop, followed by the deferred
   AWS deployment that would host the same boundary as a managed service.
2. A **separate Demo 09 (optional advanced)** view: the Neo4j MCP and controlled
   Text2Cypher alternative. This is deliberately kept out of the core view.

The diagrams follow the frozen contracts exactly: one `HybridCypherRetriever`
retrieval tool, one reservation-request command, one Lambda, no DynamoDB in the
executable path, and no Text2Cypher or MCP in the Demo 06 core path.

## View 1: Core Demo 06

The workshop runs the single self-contained notebook,
`06-agentcore-boto3-demo/01_hybrid_retrieval.ipynb`, entirely in-process on the
participant's own laptop against their own Neo4j Aura and Amazon Bedrock. It
creates no AWS resources. The notebook calls the retrieval function and
`reservation_command.create_reservation_request(...)` directly against the Neo4j
Python driver. There is no AWS-hosted Runtime, Gateway, or Lambda in this path.
The notebook creates one `request_id` UUID in the caller and reuses it on retry,
so the same value correlates the retrieval, the rule check, and the idempotent
write.

```
 +----------------- CORE DEMO 06 : LOCAL IN-PROCESS PATH  (notebook 01, each participant) ------------+
 |                                                                                                    |
 |   Participant laptop: 01_hybrid_retrieval.ipynb                                                     |
 |   creates request_id = uuid4(), reuses it on every retry                                           |
 |        |                                                                                            |
 |        |  RETRIEVAL: called directly, in-process                                                    |
 |        |    HybridCypherRetriever, NAIVE fusion, top_k=5, one reviewed Cypher traversal             |
 |        |        |                                                                                   |
 |        |        |  Nova 2 query embeddings, 1024 dim, GENERIC_INDEX purpose                         |
 |        |        +---------------------------------------------> Amazon Bedrock                      |
 |        |        |                                                                                   |
 |        |        |  read via participant env vars                                                    |
 |        |        |    NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD / NEO4J_DATABASE                    |
 |        |        v                                                                                   |
 |        |   structured evidence -> grounded local agent, abstains when the graph does not support     |
 |        |                                                                                            |
 |        |  RESERVATION: called directly, in-process                                                   |
 |        |    reservation_command.create_reservation_request(...)                                     |
 |        |    enforces full closed schema, canonical UUID, ISO date checks, positive guest count      |
 |        |    loads + enforces the Neo4j maximum-guests rule at the data boundary                     |
 |        |        |                                                                                   |
 |        |        |  same participant env vars, Neo4j Python driver                                   |
 |        v        v                                                                                   |
 |   Participant's OWN Neo4j Aura instance                                                             |
 |     Hotel knowledge graph:   Document --> Chunk --> Hotel --> Amenity                               |
 |     Retrieval indexes:       hotel_chunk_embeddings vector, hotel_chunk_fulltext full-text          |
 |     Demo 06 Rule node:       max 10 guests per request, workshop_owner = neo4j-ftw-demo-6           |
 |     Workshop writes:         ReservationRequest nodes + FOR_HOTEL relationships, idempotent          |
 |                                                                                                    |
 +----------------------------------------------------------------------------------------------------+
```

Key points to verify against the contracts:

- Retrieval and the reservation command both run in-process. The notebook calls
  them directly against the Neo4j Python driver, with no AWS-hosted Runtime,
  Gateway, or Lambda in the executable path.
- The retrieval tool is one `HybridCypherRetriever` with NAIVE fusion and
  `top_k=5` over the participant's own indexes.
- A 15-guest request is rejected with `reason_code=max_guests_exceeded` and no
  write, because the Neo4j maximum-guests rule caps a request at 10. A corrected
  request within the limit records one `ReservationRequest` linked by
  `FOR_HOTEL`, and re-delivering the same `request_id` returns `duplicate=true`
  with no second node.
- Bedrock supplies both the reasoning model and the Nova query embeddings, which
  use the same pinned model, purpose, and dimensions as the stored hotel chunk
  embeddings.
- `request_id` is the single correlation identifier across retrieval, rule check,
  and write. Secrets, prompts, and connection strings are never logged.
- Participant Aura credentials stay in the participant's own environment, read
  from `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, and `NEO4J_DATABASE`.
- DynamoDB does not appear in the executable path. It is only a going-further
  note about persistence behind a real external reservation system.

### Deferred deployment path

The same boundary, hosted as a managed AWS service, is staged in
`06-agentcore-boto3-demo/deployment-deferred/` and is not run in this workshop
pass. It holds the facilitator notebook
`06-agentcore-boto3-demo/deployment-deferred/02_agentcore_walkthrough.ipynb`, the
Runtime entry point
`06-agentcore-boto3-demo/deployment-deferred/booking_agent.py`, the single
Gateway target, the one reservation Lambda, and the Secrets Manager and IAM
boundary described in
`06-agentcore-boto3-demo/deployment-deferred/DEPLOYMENT.md`. Deploying it would
provision the architecture below. The facilitator, not the participant, would
create one `request_id` UUID in the caller and reuse it on retry, so the same
value correlates every downstream log entry.

```
                            FACILITATOR CALLER  (deployment-deferred/02_agentcore_walkthrough.ipynb)
                            creates request_id = uuid4(), reuses it on every retry
                                             |
                                             |  request_id
                                             v
 +================= AWS DEFERRED DEPLOYMENT BOUNDARY  (staged, not run in this pass) =============+
 |                                                                                               |
 |  +-------------------------------------+           +--------------------------------------+   |
 |  |  Amazon Bedrock                     |<----------|  AgentCore Runtime                   |   |
 |  |  - reasoning model (MODEL_ID)       |  query    |  entry point in deployment-deferred/ |   |
 |  |  - Nova 2 query embeddings          |  text     |                                      |   |
 |  |    1024 dim, GENERIC_INDEX purpose  |---------->|  Tool 1 (in-process):                |   |
 |  |    (pinned Nova embedding contract) |  vectors  |    search_hotel_knowledge            |   |
 |  +-------------------------------------+           |    HybridCypherRetriever             |   |
 |                                                    |    NAIVE fusion, top_k=5             |   |
 |                                                    |    one reviewed Cypher traversal     |   |
 |                                                    |    reads NEO4J_READ_SECRET_ID        |   |
 |                                                    |                                      |   |
 |                                                    |  Tool 2 (discovered via Gateway):    |   |
 |                                                    |    create_reservation_request        |   |
 |                                                    +------------------+-------------------+   |
 |                                                                       |  request_id           |
 |                                                                       v                       |
 |                                                    +--------------------------------------+   |
 |                                                    |  AgentCore Gateway                   |   |
 |                                                    |  single target:                      |   |
 |                                                    |    create_reservation_request        |   |
 |                                                    |  JSON Schema subset projection       |   |
 |                                                    +------------------+-------------------+   |
 |                                                                       |  invoke via           |
 |                                                                       |  Gateway IAM role     |
 |                                                                       v                       |
 |                                                    +--------------------------------------+   |
 |                                                    |  Reservation-request Lambda  (ONE)   |   |
 |                                                    |  enforces full closed schema,        |   |
 |                                                    |    canonical UUID, ISO date checks,  |   |
 |                                                    |    positive guest count              |   |
 |                                                    |  loads + enforces max-guests rule    |   |
 |                                                    |  reads NEO4J_COMMAND_SECRET_ID       |   |
 |                                                    +------------------+-------------------+   |
 |                                                                       |                       |
 |  +------------------------------+   +-----------------------------+   |                       |
 |  |  AWS Secrets Manager         |   |  IAM                        |   |                       |
 |  |  - Runtime-read secret       |   |  - Runtime role             |   |                       |
 |  |    {uri,username,            |   |    (Bedrock + read secret   |   |                       |
 |  |     password,database}       |   |     + invoke Gateway)       |   |                       |
 |  |  - Lambda-command secret     |   |  - Gateway role             |   |                       |
 |  |    {uri,username,            |   |    (invoke the one Lambda)  |   |                       |
 |  |     password,database}       |   |  - Lambda role              |   |                       |
 |  |  two separate secret IDs     |   |    (read command secret)    |   |                       |
 |  +------------------------------+   |  least privilege on each    |   |                       |
 |                                     +-----------------------------+   |                       |
 |                                                                       |                       |
 |  +-----------------------------------------------------------------+  |                       |
 |  |  CloudWatch / AgentCore observability                           |  |                       |
 |  |  request_id correlates:                                         |  |                       |
 |  |    Runtime retrieval -> Gateway -> Lambda -> Neo4j work         |  |                       |
 |  |  never logs prompts, credentials, secret values, or full URIs   |  |                       |
 |  +-----------------------------------------------------------------+  |                       |
 +=======================================================================|=======================+
                    read-only bolt  |                    command bolt     |
                    (Runtime-read   |                    (Lambda-command  |
                     secret)        v                     secret)         v
      +======================= Neo4j Aura : CANONICAL EVENT GRAPH ==========================+
      |                                                                                     |
      |   Hotel knowledge graph:   Document --> Chunk --> Hotel --> Amenity                 |
      |                                                                                     |
      |   Retrieval indexes:       hotel_chunk_embeddings   (vector)                        |
      |                            hotel_chunk_fulltext     (full-text)                     |
      |                                                                                     |
      |   Demo 06 Rule node:       max 10 guests per request                               |
      |                            workshop_owner = neo4j-ftw-demo-6                        |
      |                                                                                     |
      |   Workshop writes:         ReservationRequest nodes + FOR_HOTEL relationships       |
      |                            (workshop-owned; status, dates, guests, created_at)      |
      +=====================================================================================+
```

Key points for the deferred deployment, to verify against the contracts:

- The retrieval tool runs in-process inside Runtime and reads only the
  Runtime-read secret. It has no path to the command secret and cannot invoke
  the Lambda directly.
- The Gateway target set contains exactly one entry,
  `create_reservation_request`. There is one Lambda in the whole design.
- `request_id` is the single correlation identifier across Runtime, Gateway,
  Lambda, and Neo4j work. Secrets, prompts, and connection strings are never
  logged.

### Trust boundary

The core in-process path keeps participant credentials on the participant's own
laptop. The deferred deployment, once a facilitator provisions it, reads its own
Neo4j credentials from Secrets Manager and keeps its read and command identities
on separate secrets.

```
   ================================ TRUST BOUNDARY ================================
   * Participant Aura credentials stay in the participant's own environment,
     read from NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD / NEO4J_DATABASE.
   * The core in-process path sends those credentials only to the participant's
     own Neo4j Aura, and never places them in a prompt or a tool input.
   * The deferred deployment reads two separate Secrets Manager secrets, one
     read-only and one command, and keeps each credential to its own identity.
   * If a facilitator later deploys the staged boundary, participants observe
     the walkthrough; they do not deploy or configure any shared resource.
   ===============================================================================
```

## View 2: Demo 09 (optional advanced)

This view is **not** part of the Demo 06 core path. Demo 09 is an optional
advanced module that teaches Neo4j MCP and controlled Text2Cypher as a separate
alternative to Demo 06's fixed Hybrid-Cypher retrieval. It is shown here only
so the two designs are not confused. The core path in View 1 has no MCP server
and no model-generated Cypher.

```
 +============ Demo 09 (optional advanced): Neo4j MCP + controlled Text2Cypher =============+
 |  Separate from Demo 06. NOT in the core production path.                                 |
 |                                                                                          |
 |   Agent / caller                                                                         |
 |        |                                                                                 |
 |        v                                                                                 |
 |   Pre-deployed read-only Neo4j MCP server                                                |
 |     exactly two discovered tools:                                                        |
 |       - get_neo4j_schema                                                                 |
 |       - read_neo4j_cypher                                                                 |
 |     server-side enforcement: read-only DB role, query classification,                    |
 |       timeout, response truncation, fail-closed on unexpected tools                      |
 |        |                                                                                 |
 |        +----(optional) Amazon Bedrock: controlled Text2Cypher generation                 |
 |        |                                                                                 |
 |        v                                                                                 |
 |   Neo4j Aura  (read-only)                                                                 |
 |                                                                                          |
 |   Contrast: Demo 06 productionizes the fixed Hybrid-Cypher pattern with no MCP           |
 |   and no generated Cypher. Demo 01b teaches the in-notebook library-level                |
 |   Text2Cypher pattern. Demo 09 is the trust-boundary variant with server-side            |
 |   enforcement.                                                                           |
 +==========================================================================================+
```
