# Facilitator Delivery Guide

Joint Neo4j and AWS workshop: "How to Stop AI Agent Hallucinations, plus Production on Amazon Bedrock AgentCore."

This guide lists the workshop modules, the prerequisites to confirm before an event, and suggested module selections by audience and time.

The central story is one sentence: Neo4j holds connected hotel knowledge, retrieval indexes, tool metadata, production rules, and optional inspectable memory, while AWS supplies Bedrock models and embeddings, AgentCore hosting and tool exposure, Secrets Manager, IAM, Lambda integration, and observability. Demo 06 is the bounded 30 to 45 minute grounded-retrieval and safe-reservation demonstration that anchors the workshop, run locally on the participant's own Aura and Bedrock. The full AWS deployment of that same boundary is staged as the deferred deployment path in `06-agentcore-boto3-demo/deployment-deferred/`.

Why this split matters: an agent that cannot trace its answer to connected data cannot be trusted in front of a guest. Neo4j makes the relationships traversable and AWS supplies the reasoning, so every answer is grounded in evidence the graph can defend.

For the frozen retrieval and command contracts, see `06-agentcore-boto3-demo/CONTRACTS.md`. For the deferred deployment boundary, see `06-agentcore-boto3-demo/deployment-deferred/DEPLOYMENT.md`. For the architecture visual, see `workshop-delivery/architecture.md`.

---

## Modules

### Core track

The core track always runs and tells the full story on its own: Demo 00, Demo 01, Demo 04, Demo 05, Demo 06, and Demo 10.

| Module | Role in the core story |
|---|---|
| Demo 00 | Strands Agents primer covering the core concepts every later demo uses |
| Demo 01 | Show why connected data reduces hallucination before comparing implementations |
| Demo 04 | A Python hook blocks an invalid operation deterministically |
| Demo 05 | Agent Control steers the same invalid request toward safe behavior |
| Demo 06 | The grounded retrieval and safe-reservation agent, run locally, the anchor demonstration |
| Demo 10 | Scoped, tag-gated AWS cleanup |

Demo 06 stays a bounded 30 to 45 minute module regardless of which optional modules are added around it.

### Optional modules and when to include each

| Module | Classification | Include when | Prerequisite beyond the core |
|---|---|---|---|
| Demo 01b | Optional | The audience wants retrieval-pattern depth: vector, hybrid, Vector-Cypher, and library Text2Cypher. Best for developers and data practitioners. | None beyond the prepared indexes |
| Demo 02 | Audience-dependent | The audience runs agents with many similar tools and cares about token cost and tool-selection accuracy. | None beyond Aura and Bedrock |
| Demo 03 | Audience-dependent | The audience worries about fabricated answers in generative output and wants multi-agent validation. | None beyond Aura and Bedrock |
| Deferred deployment path | Deferred, optional advanced | Do not schedule as a live module in this pass. Use only as a going-further discussion of the deployment boundary staged in `06-agentcore-boto3-demo/deployment-deferred/`. | Not run in the current implementation pass |
| Demo 07 | Optional managed-memory reference | The environment already has the pre-provisioned multi-table booking deployment this reference reuses. | A pre-provisioned booking agent deployment must already exist |
| Demo 08 | Optional advanced | The audience leans toward Neo4j and wants inspectable memory with provenance and actor isolation. Runs independently of Demo 07. | Aura and Bedrock embeddings |
| Demo 09 | Optional advanced | The audience wants the governed MCP and controlled Text2Cypher trust boundary. | A pre-deployed read-only Neo4j MCP endpoint |

Every optional module is independently removable and does not change Demo 06. Demo 07 carries a hard dependency: it connects to a pre-provisioned booking deployment that the core path does not create, so run it only where that deployment already exists.

### Suggested track shapes

- Developer half-day: Core track plus Demo 01b and Demo 02.
- Architect half-day: Core track plus Demo 09, with the deferred deployment path as a closing discussion.
- Leadership briefing: Core track delivered facilitator-first, plus the Demo 02 and Demo 03 findings, with light hands-on.
- Full-day deep dive: Core track plus Demo 01b, Demo 02, Demo 03, and one memory module (Demo 08 preferred for a Neo4j-forward audience).

---

## Prerequisites

Before the event, confirm:

- AWS access and Bedrock model access, including Amazon Nova 2 embeddings for retrieval query embeddings.
- Aura connectivity. Participants use their own Aura instance for the hands-on retrieval path through Demo 06.
- Secrets, for the deferred deployment path only. That boundary uses separate Runtime-read and Lambda-command secrets in Secrets Manager, each holding URI, username, password, and database fields. A shared Runtime or Lambda never accepts participant database credentials as prompt or tool input. Demo 06 in this pass runs locally and reads standard `NEO4J_*` environment values.
- Graph fixtures and indexes. Run `python graph_setup.py --check-only` in `06-agentcore-boto3-demo/` to confirm the `hotel_chunk_embeddings` and `hotel_chunk_fulltext` indexes, the uniqueness constraints, the fixture hotel identities, and the maximum-guests rule.
- The pre-deployed AgentCore Runtime, reservation Gateway target, and reservation Lambda apply only to the deferred deployment path staged in `06-agentcore-boto3-demo/deployment-deferred/` and are not required in this pass. Demo 06 runs locally with no Runtime.
- The Agent Control server for Demo 05, which is a separate product and is not bundled with the workshop.
- The Neo4j MCP endpoint only when Demo 09 is selected.

Keep event setup within 30 minutes and avoid graph extraction or infrastructure deployment during the main path.
