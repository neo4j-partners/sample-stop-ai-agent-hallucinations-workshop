# Workshop Architecture (PROPOSED DRAFT for review)

> **Status: PROPOSED DRAFT.** This document is offline documentation work only.
> It proposes the architecture visual called for by the v2 plan
> ("Documentation and Delivery" -> "Root documentation") for review before it is
> adopted into the root README or facilitator guide. Nothing here deploys AWS
> resources. Review the diagrams against the frozen contracts in
> `06-agentcore-boto3-demo/CONTRACTS.md` and `06-agentcore-boto3-demo/DEPLOYMENT.md`.

This file contains two views:

1. The **core Demo 06A** view: the pre-provisioned production boundary the
   facilitator invokes, plus the participant hands-on retrieval path and the
   trust boundary between them.
2. A **separate Demo 09 (optional advanced)** view: the Neo4j MCP and controlled
   Text2Cypher alternative. This is deliberately kept out of the core view.

The diagrams follow the frozen contracts exactly: one `HybridCypherRetriever`
retrieval tool, one reservation-request command, one Lambda, no DynamoDB in the
executable path, and no Text2Cypher or MCP in the Demo 06A core path.

## View 1: Core Demo 06A

The shared production boundary is pre-deployed. Only the facilitator invokes it,
using `02_agentcore_walkthrough.ipynb`. The facilitator creates one
`request_id` (a UUID) in the caller and reuses it on retry, so the same value
correlates every downstream log entry.

```
                            FACILITATOR CALLER  (notebook 02, facilitator only)
                            creates request_id = uuid4(), reuses it on every retry
                                             |
                                             |  request_id
                                             v
 +================= AWS SHARED PRODUCTION BOUNDARY  (facilitator-invoked only) ==================+
 |                                                                                               |
 |  +-------------------------------------+           +--------------------------------------+   |
 |  |  Amazon Bedrock                     |<----------|  AgentCore Runtime                   |   |
 |  |  - reasoning model (MODEL_ID)       |  query    |  entry point: booking_agent.py       |   |
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

Key points to verify against the contracts:

- The retrieval tool runs in-process inside Runtime and reads only the
  Runtime-read secret. It has no path to the command secret and cannot invoke
  the Lambda directly.
- The Gateway target set contains exactly one entry,
  `create_reservation_request`. There is one Lambda in the whole design.
- Bedrock supplies both the reasoning model and the Nova query embeddings, which
  use the same pinned model, purpose, and dimensions as the stored hotel chunk
  embeddings.
- `request_id` is the single correlation identifier across Runtime, Gateway,
  Lambda, and Neo4j work. Secrets, prompts, and connection strings are never
  logged.
- DynamoDB does not appear in the executable path. It is only a going-further
  note about persistence behind a real external reservation system.

### Participant hands-on path and trust boundary

Participants run the same retriever contract locally, using
`01_hybrid_retrieval.ipynb`, against their own Aura instance. They never touch
the shared production boundary above.

```
 +---------------------- PARTICIPANT HANDS-ON PATH  (notebook 01, each participant) -----------+
 |                                                                                             |
 |   Participant notebook (HybridCypherRetriever, same contract, NAIVE fusion, top_k=5)        |
 |        |                                                                                    |
 |        |  Nova query embeddings                                                             |
 |        +---------------------------------> Amazon Bedrock                                   |
 |        |                                                                                    |
 |        |  read-only bolt (participant's own env vars:                                       |
 |        |  NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD / NEO4J_DATABASE)                      |
 |        v                                                                                    |
 |   Participant's OWN Neo4j Aura instance (their own hotel_chunk_embeddings                   |
 |   and hotel_chunk_fulltext indexes)                                                         |
 |                                                                                             |
 +---------------------------------------------------------------------------------------------+

   ================================ TRUST BOUNDARY ================================
   * Participant Aura credentials stay in the participant's own environment.
   * They are NEVER sent to the shared Runtime, Gateway, Lambda, or Secrets Manager,
     and never appear in a prompt or tool input to shared infrastructure.
   * Only the facilitator invokes the shared pre-deployed Runtime (View 1).
   * Participants observe the facilitator's shared walkthrough; they do not
     invoke, deploy, or configure any shared resource.
   ===============================================================================
```

## View 2: Demo 09 (optional advanced)

This view is **not** part of the Demo 06A core path. Demo 09 is an optional
advanced module that teaches Neo4j MCP and controlled Text2Cypher as a separate
alternative to Demo 06A's fixed Hybrid-Cypher retrieval. It is shown here only
so the two designs are not confused. The core path in View 1 has no MCP server
and no model-generated Cypher.

```
 +============ Demo 09 (optional advanced): Neo4j MCP + controlled Text2Cypher =============+
 |  Separate from Demo 06A. NOT in the core production path.                                |
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
 |   Contrast: Demo 06A productionizes the fixed Hybrid-Cypher pattern with no MCP          |
 |   and no generated Cypher. Demo 01b teaches the in-notebook library-level                |
 |   Text2Cypher pattern. Demo 09 is the trust-boundary variant with server-side            |
 |   enforcement.                                                                           |
 +==========================================================================================+
```
