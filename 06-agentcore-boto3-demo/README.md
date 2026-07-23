[< Back to Main README](../README.md)

# Demo 06: Grounded Hotel Retrieval and Safe Reservations

Take the anti-hallucination techniques from the earlier demos (01-05) into a self-contained agent you run on your own laptop against [Neo4j AuraDB](https://neo4j.com/cloud/aura-free/) and [Amazon Bedrock](https://aws.amazon.com/bedrock/). The agent grounds every answer in a reviewed hybrid graph retrieval and can take exactly one safe, idempotent action: create a reservation request. The full Amazon Bedrock AgentCore deployment that hosts this same boundary as a managed service has its live source in [`deployment-tools/`](deployment-tools/) and its reference walkthrough in [`advanced-deployment/`](advanced-deployment/).

[![Python](https://img.shields.io/badge/Python-3.11-green.svg?style=flat)](https://python.org)
[![AgentCore](https://img.shields.io/badge/Bedrock-AgentCore-orange.svg?style=flat&logo=amazon-aws)](https://aws.amazon.com/bedrock/agentcore/)
[![Lambda](https://img.shields.io/badge/AWS-Lambda-orange.svg?style=flat&logo=aws-lambda)](https://aws.amazon.com/lambda/)
[![Neo4j](https://img.shields.io/badge/Neo4j-AuraDB-blue.svg?style=flat)](https://neo4j.com/cloud/aura-free/)

This demo uses [Strands Agents](https://github.com/strands-agents/sdk-python) with [Amazon Bedrock](https://aws.amazon.com/bedrock/). The same boundary applies with other agent frameworks that support AgentCore Runtime.

**At a Glance**
- **Failure it stops:** carrying the grounded techniques into a real action path without losing them.
- **Neo4j:** Aura holds the hotel graph, the retrieval indexes, and the reservation rule.
- **AWS:** Amazon Bedrock reasons over the evidence and embeds the query. AgentCore, Gateway, and Lambda host the same boundary as a managed service in the deferred deployment.
- **You'll build:** a grounded retrieval path plus one protected reservation-request action, run locally.

---

## What This Demo Shows

Demos 01-05 build techniques that reduce hallucination. Demo 06 shows the production shape of three of them, all runnable from one notebook against your own Aura instance:

| Technique (from demos) | Production shape here |
|------------------------|-----------------------|
| **Graph-RAG** (demo 01) | A fixed `HybridCypherRetriever` over Neo4j: vector index plus full-text index, one reviewed Cypher traversal, structured evidence the agent must cite |
| **Grounded abstention** (demos 02-04) | The agent answers only from returned evidence and abstains when the graph does not support a claim, including live availability |
| **Guardrails that cannot be argued away** (demos 04-05) | One idempotent reservation command enforces a Neo4j guest-limit rule at the data boundary, not in the prompt |

The retrieval tool accepts only a `query`. The reservation command accepts only `request_id`, `hotel_id`, `check_in`, `check_out`, and `guests`. Callers cannot pick a retriever, a ranker, a weight, a result count, or an actor identity. The frozen contracts are documented in [CONTRACTS.md](CONTRACTS.md).

---

## One Notebook

`01_hybrid_retrieval.ipynb` runs the full local story end to end against your own Neo4j Aura and Amazon Bedrock. It creates no AWS resources.

| Section | What it proves |
|---------|----------------|
| Hybrid retrieval | A hero question is grounded in vector plus full-text evidence and one reviewed Cypher traversal. |
| Abstention | An availability question the graph cannot answer forces the agent to decline instead of inventing a claim. |
| Rule rejection | A 15-guest request is rejected with `reason_code=max_guests_exceeded` and no write, because the Neo4j maximum-guests rule caps a request at 10. |
| Safe write | A corrected request within the limit records one `ReservationRequest` linked by `FOR_HOTEL`, and re-delivering the same `request_id` returns `duplicate=true` with no second node. |
| Graph inspection | The stored request is read back by its stable `request_id`. |

Live cells self-skip when credentials are absent, so the notebook parses and runs cleanly in CI. The reservation cells need only your Aura connection; they derive the hero `hotel_id` from the local fixture manifest and never depend on a live retrieval result.

---

## Architecture

```
Local path (Notebook)
  query -> HybridCypherRetriever -> Neo4j Aura -> structured evidence -> grounded local agent
  reservation payload -> create_reservation_request -> Neo4j Aura (rule check + idempotent write)
```

The same boundary, hosted as a managed AWS service, has its live source in `deployment-tools/` and its reference walkthrough in `advanced-deployment/`:

```
Deployment (deferred)
  caller (request_id) -> AgentCore Runtime (search_hotel_knowledge, in-process)
                                     |
                                     +-> AgentCore Gateway -> create_reservation_request Lambda -> Neo4j Aura
```

- **`create_reservation_request`** enforces the full closed schema, canonical UUID, strict dates, positive guest count, and the Neo4j maximum-guests rule at the command boundary. The notebook calls it directly; the deferred Lambda wraps the same function.
- **Neo4j AuraDB** holds the prepared hotel knowledge graph, the maximum-guests rule, and workshop-owned reservation requests.

---

## The Hybrid Retriever

The retrieval tool always uses the same configuration. Callers cannot change it:

- `HybridCypherRetriever` from `neo4j-graphrag`
- vector index `hotel_chunk_embeddings` and full-text index `hotel_chunk_fulltext`
- Amazon Nova 2 embeddings, 1,024 dimensions, `GENERIC_INDEX` purpose
- explicit `NAIVE` fusion with `top_k=5`
- one reviewed, parameterized Cypher traversal from chunk to hotel and amenity

Each result returns chunk evidence, the hybrid score, the query terms found verbatim in that evidence, and hotel facts (ID, name, address, guest rating, amenities). Missing facts come back as null or an empty list. Hotel IDs are null for non-fixture hotels, so those hotels cannot be sent to the reservation command. The retriever never claims live inventory or guaranteed availability, which is why the agent abstains on availability questions.

---

## The Reservation Command

The command is idempotent by a caller-created `request_id` UUID. The same ID is reused on retries.

| Outcome | `status` | `reason_code` | Write behavior |
|---------|----------|---------------|----------------|
| Accepted | `accepted` | omitted | One request plus one `FOR_HOTEL` relationship |
| Duplicate delivery | `accepted` | omitted | Returns the existing request with `duplicate=true` |
| Policy rejection | `rejected` | `max_guests_exceeded` | No write |
| Unknown hotel | `rejected` | `unknown_hotel` | No write |
| Invalid dates | `rejected` | `invalid_dates` | No write |

A 15-guest request is rejected with no write because the enabled Neo4j rule caps a request at 10 guests. The correction is a new command from the caller, not a silent adjustment inside the model. Reusing a request ID with different input returns `service_error` and never changes the stored request.

---

## Quick Start

### Prerequisites

- **[Python](https://python.org/downloads) 3.11+**
- **[uv](https://docs.astral.sh/uv/)** package manager ([installation guide](https://docs.astral.sh/uv/getting-started/installation/))
- A **Neo4j AuraDB** instance with the prepared Demo 06 graph (see [Neo4j Setup](#neo4j-setup))
- **Amazon Bedrock access** for the query embedding (Amazon Nova 2) and the grounded agent

### Step 1: Install dependencies

```bash
cd 06-agentcore-boto3-demo
uv venv && uv pip install -r requirements.txt
```

### Step 2: Configure your Neo4j connection

Set these in your environment or `.env`:

```bash
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j
```

### Step 3: Run the notebook

```bash
code 01_hybrid_retrieval.ipynb
```

The notebook confirms your Aura connection and prepared indexes, runs the hero question through hybrid retrieval, demonstrates abstention on a question the graph cannot answer, rejects a 15-guest request, records and re-delivers a valid request idempotently, and reads the stored request back. If Neo4j or Bedrock is not configured, the affected live cells self-skip and the notebook still runs top to bottom.

The repository acceptance path runs the same notebook:

```bash
python setup/run_notebooks.py --labs 6
```

This executes the notebook without creating AWS resources.

---

## Deployment (deferred, see `deployment-tools/` and `advanced-deployment/`)

The full Amazon Bedrock AgentCore deployment is staged intact and is not run in this workshop pass. Its live source lives in [`deployment-tools/`](deployment-tools/): the Runtime entry point (`booking_agent.py`), the Gateway target manifest (`gateway_target.json`), the reservation Lambda, and the container `Dockerfile`. Its reference material lives in [`advanced-deployment/`](advanced-deployment/): the second facilitator notebook (`02_agentcore_walkthrough.ipynb`) and the Secrets Manager and IAM boundary described in [`advanced-deployment/DEPLOYMENT.md`](advanced-deployment/DEPLOYMENT.md). See each folder's `README.md` for what is staged and why.

### Two credentials, two secrets (deferred boundary)

When deployed, the Runtime and command use separate identities and never share a credential:

- **Runtime-read**: reads chunk search indexes and traverses to hotel and amenity data. No write privileges.
- **Lambda-command**: reads the maximum-guests rule and fixture hotel identity, and creates workshop-owned `ReservationRequest` nodes and `FOR_HOTEL` relationships. Cannot update or delete canonical hotel, chunk, document, amenity, or rule data.

Deployed code reads `NEO4J_READ_SECRET_ID` and `NEO4J_COMMAND_SECRET_ID` from Secrets Manager. Each secret contains `uri`, `username`, `password`, and `database`. The local notebook reads `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, and `NEO4J_DATABASE`. Passwords, secret values, and full connection strings must never appear in a deployment package, a prompt, or a log.

---

## Neo4j Setup

### Create a free Neo4j AuraDB instance

1. Go to [console.neo4j.io](https://console.neo4j.io) and create a free account.
2. Click **New Instance**, then **AuraDB Free**.
3. Download the credentials file when prompted. It contains your URI, username, and password.

### Prepare the Demo 06 graph

The retrieval and command paths expect the prepared graph: hotel documents and chunks, the `hotel_chunk_embeddings` and `hotel_chunk_fulltext` indexes, the maximum-guests rule, and the fixture hotel identities in `fixtures/hotel_ids.json`. `graph_setup.py` applies this preparation, and the notebook reports any missing pieces before it runs.

Run the one-time readiness check before an event to confirm every dependency is in place:

```bash
python graph_setup.py --check-only
```

It reads your `NEO4J_*` environment values and reports one corrective action per missing dependency (absent env vars, missing or offline indexes, missing constraints, unresolved fixtures, or the missing rule), exiting non-zero until the graph is ready. Drop `--check-only` to apply the idempotent Demo 06 graph preparation.

---

## File Structure

```
06-agentcore-boto3-demo/
├── 01_hybrid_retrieval.ipynb        # The self-contained local notebook
├── CONTRACTS.md                     # Frozen retrieval and command contracts
├── contracts.py                     # Shared schema and contract helpers
├── graph_setup.py                   # Prepare and verify the Demo 06 graph
├── hybrid_retrieval.py              # HybridCypherRetriever configuration and tool
├── reservation_command.py           # Reservation command logic (called locally)
├── requirements.txt                 # Local dependencies (notebook)
├── conftest.py                      # Keeps the local test run out of the deployment dirs
├── fixtures/
│   └── hotel_ids.json               # Committed fixture hotel identities
├── tool_schemas/
│   └── tools.json                   # Tool definitions
├── deployment-tools/                # Live deployment source, not run in this pass
│   ├── README.md                    # What the live source is and how it is used
│   ├── booking_agent.py             # AgentCore Runtime entry point (Strands)
│   ├── Dockerfile                   # Runtime container image
│   ├── .dockerignore
│   ├── agent_requirements.txt       # Runtime dependencies (deployed to AgentCore)
│   ├── gateway_target.json          # The single Gateway target manifest
│   ├── lambda_tools/
│   │   └── create_reservation_request/  # The one reservation Lambda
│   └── test_runtime_integration.py  # Deployment tests (run in the deployment env)
└── advanced-deployment/             # Reference only, nothing automated reads it
    ├── README.md                    # What is kept here and why
    ├── 02_agentcore_walkthrough.ipynb  # Facilitator: pre-deployed Runtime + command
    └── DEPLOYMENT.md                # The production-hardening boundary reference
```

---

## Cleanup

The notebook creates no AWS resources, so there is nothing to clean up from running it. If a facilitator later deploys the staged AgentCore boundary, tear it down with the workshop cleanup in [Demo 10](../10-cleanup/).

> Skip cleanup if you are using an AWS-provided workshop account. It is cleaned up automatically.

---

## Navigation

- **Previous:** [Demo 05: Agent Control Steering](../05-steering-demo/)
- **Start from the beginning:** [Demo 01: Graph-RAG vs RAG](../01-graphrag-demo/)

---

## Contributing

Contributions are welcome. See [CONTRIBUTING](../CONTRIBUTING.md) for more information.

---

## Security

If you discover a potential security issue in this project, notify AWS/Amazon Security via the [vulnerability reporting page](https://aws.amazon.com/security/vulnerability-reporting/). Please do **not** create a public GitHub issue.

---

## License

This library is licensed under the MIT-0 License. See the [LICENSE](../LICENSE) file for details.

> Last updated: July 2026 | Strands Agents 1.27+ | Python 3.11+ | Amazon Bedrock AgentCore
