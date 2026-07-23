[< Back to Main README](../README.md)

# Demo 06A: Production Grounded Agent on Amazon Bedrock AgentCore

Take the anti-hallucination techniques from the earlier demos (01-05) into a production shape on [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/), [AWS Lambda](https://aws.amazon.com/lambda/), and [Neo4j AuraDB](https://neo4j.com/cloud/aura-free/). The agent grounds every answer in a reviewed hybrid graph retrieval and can take exactly one safe, idempotent action: create a reservation request.

[![Python](https://img.shields.io/badge/Python-3.11-green.svg?style=flat)](https://python.org)
[![AgentCore](https://img.shields.io/badge/Bedrock-AgentCore-orange.svg?style=flat&logo=amazon-aws)](https://aws.amazon.com/bedrock/agentcore/)
[![Lambda](https://img.shields.io/badge/AWS-Lambda-orange.svg?style=flat&logo=aws-lambda)](https://aws.amazon.com/lambda/)
[![Neo4j](https://img.shields.io/badge/Neo4j-AuraDB-blue.svg?style=flat)](https://neo4j.com/cloud/aura-free/)

This demo uses [Strands Agents](https://github.com/strands-agents/sdk-python) with [Amazon Bedrock](https://aws.amazon.com/bedrock/). The same boundary applies with other agent frameworks that support AgentCore Runtime.

**At a Glance**
- **Failure it stops:** carrying the grounded techniques into production without losing them.
- **Neo4j:** Aura holds the hotel graph, the retrieval indexes, and the reservation rule.
- **AWS:** AgentCore hosts the agent, Lambda performs the one safe action, Bedrock reasons.
- **You'll build:** a grounded retrieval path plus one protected reservation-request action.

---

## What This Demo Shows

Demos 01-05 build techniques that reduce hallucination. Demo 06A shows the production shape of two of them:

| Technique (from demos) | Production shape here |
|------------------------|-----------------------|
| **Graph-RAG** (demo 01) | A fixed `HybridCypherRetriever` over Neo4j: vector index plus full-text index, one reviewed Cypher traversal, structured evidence the agent must cite |
| **Grounded abstention** (demos 02-04) | The agent answers only from returned evidence and abstains when the graph does not support a claim, including live availability |
| **Guardrails that cannot be argued away** (demos 04-05) | One idempotent reservation command enforces a Neo4j guest-limit rule at the data boundary, not in the prompt |

The retrieval tool accepts only a `query`. The reservation command accepts only `request_id`, `hotel_id`, `check_in`, `check_out`, and `guests`. Callers cannot pick a retriever, a ranker, a weight, a result count, or an actor identity. The frozen contracts are documented in [CONTRACTS.md](CONTRACTS.md).

---

## Two Notebooks

This demo is split by what each notebook can prove, not by workstream.

| Notebook | Audience | What it proves | AWS resources |
|----------|----------|----------------|---------------|
| [`01_hybrid_retrieval.ipynb`](01_hybrid_retrieval.ipynb) | Participant | Hybrid graph retrieval grounds a hero question and forces abstention on an unanswerable one. Runs against your own Neo4j Aura, offline of AWS. | None created |
| [`02_agentcore_walkthrough.ipynb`](02_agentcore_walkthrough.ipynb) | Facilitator | The pre-deployed Runtime, Gateway, and reservation Lambda reject a 15-guest request with no write, record a corrected request, and correlate by request ID. | None created; invokes an existing deployment |

Both notebooks self-skip their live cells when credentials are absent, so they parse and run cleanly in CI. Neither notebook creates AWS resources. The deployable boundary they exercise is described in [DEPLOYMENT.md](DEPLOYMENT.md).

---

## Architecture

```
Participant path (Notebook 1)
  query -> HybridCypherRetriever -> Neo4j Aura -> structured evidence -> grounded local agent

Facilitator path (Notebook 2), pre-deployed
  caller (request_id) -> AgentCore Runtime (search_hotel_knowledge, in-process)
                                     |
                                     +-> AgentCore Gateway -> create_reservation_request Lambda -> Neo4j Aura
```

- **AgentCore Runtime** hosts `booking_agent.py`. It runs the retrieval tool in-process and discovers exactly one command through the Gateway.
- **AgentCore Gateway** exposes only `create_reservation_request`, defined by `deployment/gateway_target.json`.
- **The reservation Lambda** enforces the full closed schema, canonical UUID, strict dates, positive guest count, and the Neo4j maximum-guests rule at the command boundary.
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

## Quick Start (Participant Path)

### Prerequisites

- **[Python](https://python.org/downloads) 3.11+**
- **[uv](https://docs.astral.sh/uv/)** package manager ([installation guide](https://docs.astral.sh/uv/getting-started/installation/))
- A **Neo4j AuraDB** instance with the prepared Demo 06 graph (see [Neo4j Setup](#neo4j-setup))
- **Amazon Bedrock access** to Amazon Nova 2 embeddings for the retrieval query

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

### Step 3: Run Notebook 1

```bash
code 01_hybrid_retrieval.ipynb
```

The notebook confirms your Aura connection and prepared indexes, runs the hero question through hybrid retrieval, shows the structured evidence, and demonstrates abstention on a question the graph cannot answer. If Neo4j or Bedrock is not configured, the live cells self-skip and the notebook still runs top to bottom.

The repository acceptance path runs the same notebook:

```bash
python setup/run_notebooks.py --labs 6
```

This executes Notebook 1 and parses Notebook 2 without creating AWS resources.

---

## Facilitator Path (Notebook 2)

`02_agentcore_walkthrough.ipynb` drives an existing deployment. Set `AGENT_RUNTIME_ARN` for the pre-deployed AgentCore Runtime, then walk through:

1. One caller-created request ID, reused on retries.
2. A 15-guest request rejected with no write.
3. A corrected request within the limit, recorded with a Neo4j `created_at`.
4. Graph inspection of the resulting `ReservationRequest` and its `FOR_HOTEL` relationship.
5. Correlation of AgentCore and CloudWatch by the same request ID.

Every live cell self-skips when the Runtime or Neo4j is not configured. The notebook creates no AWS resources; deploying the boundary is a separate facilitator step described in [DEPLOYMENT.md](DEPLOYMENT.md).

---

## Neo4j Setup

### Create a free Neo4j AuraDB instance

1. Go to [console.neo4j.io](https://console.neo4j.io) and create a free account.
2. Click **New Instance**, then **AuraDB Free**.
3. Download the credentials file when prompted. It contains your URI, username, and password.

### Prepare the Demo 06 graph

The retrieval and command paths expect the prepared graph: hotel documents and chunks, the `hotel_chunk_embeddings` and `hotel_chunk_fulltext` indexes, the maximum-guests rule, and the fixture hotel identities in `fixtures/hotel_ids.json`. `graph_setup.py` applies this preparation, and Notebook 1 reports any missing pieces before it runs.

Run the one-time readiness check before an event to confirm every dependency is in place:

```bash
python graph_setup.py --check-only
```

It reads your `NEO4J_*` environment values and reports one corrective action per missing dependency (absent env vars, missing or offline indexes, missing constraints, unresolved fixtures, or the missing rule), exiting non-zero until the graph is ready. Drop `--check-only` to apply the idempotent Demo 06 graph preparation.

### Two credentials, two secrets (deployed boundary)

The deployed Runtime and command use separate identities and never share a credential:

- **Runtime-read**: reads chunk search indexes and traverses to hotel and amenity data. No write privileges.
- **Lambda-command**: reads the maximum-guests rule and fixture hotel identity, and creates workshop-owned `ReservationRequest` nodes and `FOR_HOTEL` relationships. Cannot update or delete canonical hotel, chunk, document, amenity, or rule data.

Deployed code reads `NEO4J_READ_SECRET_ID` and `NEO4J_COMMAND_SECRET_ID` from Secrets Manager. Each secret contains `uri`, `username`, `password`, and `database`. Local notebooks read `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, and `NEO4J_DATABASE`. Passwords, secret values, and full connection strings must never appear in a deployment package, a prompt, or a log.

---

## File Structure

```
06-agentcore-boto3-demo/
├── 01_hybrid_retrieval.ipynb        # Participant: hybrid retrieval, offline of AWS
├── 02_agentcore_walkthrough.ipynb   # Facilitator: pre-deployed Runtime + command
├── CONTRACTS.md                     # Frozen retrieval and command contracts
├── DEPLOYMENT.md                    # The deployable boundary (Runtime, Gateway, Lambda)
├── contracts.py                     # Shared schema and contract helpers
├── graph_setup.py                   # Prepare and verify the Demo 06 graph
├── hybrid_retrieval.py              # HybridCypherRetriever configuration and tool
├── reservation_command.py           # Reservation command logic
├── booking_agent.py                 # AgentCore Runtime entry point (Strands)
├── agent_requirements.txt           # Runtime dependencies (deployed to AgentCore)
├── requirements.txt                 # Local dependencies (notebooks)
├── fixtures/
│   └── hotel_ids.json               # Committed fixture hotel identities
├── deployment/
│   └── gateway_target.json          # The single Gateway target manifest
├── lambda_tools/
│   └── create_reservation_request/  # The one reservation Lambda
└── tool_schemas/
    └── tools.json                   # Tool definitions
```

---

## Cleanup

Notebooks 1 and 2 create no AWS resources, so there is nothing to clean up from running them. If a facilitator deployed the AgentCore boundary, tear it down with the workshop cleanup in [Demo 10](../10-cleanup/).

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
