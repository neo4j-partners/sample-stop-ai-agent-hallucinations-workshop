# Facilitator Delivery Guide

Joint Neo4j and AWS workshop: "How to Stop AI Agent Hallucinations, plus Production on Amazon Bedrock AgentCore."

This guide helps a facilitator choose a track for the audience in the room, confirm the environment is ready, and deliver the opening grounded-retrieval demonstration with confidence. It covers audience profiles, selectable tracks built from the module list, per-module timing estimates, readiness steps, and the opening hero demonstration.

The central story is one sentence: Neo4j holds connected hotel knowledge, retrieval indexes, tool metadata, production rules, and optional inspectable memory, while AWS supplies Bedrock models and embeddings, AgentCore hosting and tool exposure, Secrets Manager, IAM, Lambda integration, and observability. Demo 06A is the bounded 30 to 45 minute production demonstration that anchors the workshop.

For the deployable service boundary and the frozen retrieval and command contracts, see `06-agentcore-boto3-demo/CONTRACTS.md` and `06-agentcore-boto3-demo/DEPLOYMENT.md`. For the architecture visual, see `workshop-delivery/architecture.md`, which is owned separately. For the pre-delivery environment checklist, see `workshop-delivery/readiness-checklist.md` in this directory.

---

## How to use this guide

1. Read the audience profiles and pick the profile closest to the room.
2. Choose a track: the core track always runs, and optional modules attach to it based on audience and available time.
3. Two working days before the event, walk the readiness checklist and record any gaps.
4. Rehearse Demo 06A end to end and record its actual duration in the timing table below.
5. Deliver the opening hero demonstration exactly as scripted so the grounding and abstention behaviors land.

---

## Audience profiles

Most rooms are a mix. Identify the dominant profile, then add optional modules that serve the secondary profiles present.

### Developers and agent builders

What they care about: the code they can run themselves, the retrieval contract, tool schemas and docstrings, idempotency, and how grounding and abstention actually work in a running agent.

Serve them with: Demo 00 (Strands primer), Demo 01 and optional Demo 01b (retrieval patterns), Demo 02 (semantic tool selection), Demo 04 and Demo 05 (guardrails and steering), and the participant hands-on notebook in Demo 06A, which they run against their own Aura instance.

### Architects and platform engineers

What they care about: the service boundary, trust boundaries, separation of read and command credentials, Secrets Manager, IAM, the Runtime, Gateway, and Lambda layout, and request-ID-correlated observability across AgentCore and CloudWatch.

Serve them with: the Demo 06A facilitator walkthrough (Notebook 2), the data-ownership and platform-responsibility summaries in the root README, Demo 09 (the MCP trust boundary) where an MCP endpoint exists, and Demo 06B as a going-further conversation, since it is deferred and not deliverable in the current pass.

### Technical decision-makers and leaders

What they care about: why grounding and deterministic guardrails reduce hallucination risk, the cost and accuracy tradeoffs, and the production-readiness narrative. They want the story, not a code walk.

Serve them with: the Demo 01 findings table, the measured token and accuracy figures in Demo 02 and Demo 03, the opening hero demonstration, and a facilitator-driven view of the Demo 06A walkthrough. Keep hands-on setup light for this group.

### Data and graph practitioners

What they care about: the graph model, retrieval index design, provenance, and how connected data changes retrieval quality.

Serve them with: Demo 01 and Demo 01b, Demo 03 (graph-backed domain validation), Demo 08 (inspectable Neo4j memory), and Demo 09.

---

## Selectable tracks

### Core track

The core track always runs and tells the full story on its own: Demo 00, Demo 01, Demo 04, Demo 05, Demo 06A, and Demo 10.

| Module | Role in the core story |
|---|---|
| Demo 00 | Confirm access and start from known-good infrastructure |
| Demo 01 | Show why connected data reduces hallucination before comparing implementations |
| Demo 04 | A Python hook blocks an invalid operation deterministically |
| Demo 05 | Agent Control steers the same invalid request toward safe behavior |
| Demo 06A | The pre-provisioned production grounded agent on AgentCore, the anchor demonstration |
| Demo 10 | Scoped, tag-gated AWS cleanup |

Demo 06A stays a bounded 30 to 45 minute module regardless of which optional modules are added around it.

### Optional modules and when to include each

| Module | Classification | Include when | Prerequisite beyond the core |
|---|---|---|---|
| Demo 01b | Optional | The audience wants retrieval-pattern depth: vector, hybrid, Vector-Cypher, and library Text2Cypher. Best for developers and data practitioners. | None beyond the prepared indexes |
| Demo 02 | Audience-dependent | The audience runs agents with many similar tools and cares about token cost and tool-selection accuracy. | None beyond Aura and Bedrock |
| Demo 03 | Audience-dependent | The audience worries about fabricated answers in generative output and wants multi-agent validation. | None beyond Aura and Bedrock |
| Demo 06B | Deferred, optional advanced | Do not schedule as a live module in this pass. Use only as a going-further discussion of the deployment boundary. | Not deliverable in the current implementation pass |
| Demo 07 | Optional managed-memory reference | The environment already has the pre-provisioned multi-table booking deployment this reference reuses. | A pre-provisioned booking agent deployment must already exist |
| Demo 08 | Optional advanced | The audience leans toward Neo4j and wants inspectable memory with provenance and actor isolation. Runs independently of Demo 07. | Aura and Bedrock embeddings |
| Demo 09 | Optional advanced | The audience wants the governed MCP and controlled Text2Cypher trust boundary. | A pre-deployed read-only Neo4j MCP endpoint, verified in Demo 00 |

Every optional module is independently removable and does not change Demo 06A. Demo 07 carries a hard dependency: it connects to a pre-provisioned booking deployment that the core path does not create, so run it only where that deployment already exists.

### Suggested track shapes

- Developer half-day: Core track plus Demo 01b and Demo 02.
- Architect half-day: Core track plus Demo 09, with Demo 06B as a closing discussion.
- Leadership briefing: Core track delivered facilitator-first, plus the Demo 02 and Demo 03 findings, with light hands-on.
- Full-day deep dive: Core track plus Demo 01b, Demo 02, Demo 03, and one memory module (Demo 08 preferred for a Neo4j-forward audience).

---

## Module timing estimates

Two timing sources exist. Notebook execution time is grounded in the repository. Facilitated delivery time is a planning estimate that includes narration, questions, and transitions, and it must be confirmed during operator rehearsal. The overall track timings and the actual Demo 06A duration are rehearsal outputs, per the v2 plan's Phase 7 item "Rehearse selected audience tracks and record timings."

| Module | Track | Notebook execution (grounded) | Facilitated delivery (planning estimate) | Status |
|---|---|---|---|---|
| Demo 00 | Core | Setup targeted within 30 minutes | 20 to 30 minutes | Estimate; confirm at rehearsal |
| Demo 01 | Core | Comparison notebook runs quickly; graph build is a readiness step, not live | 15 to 20 minutes | Estimate; confirm at rehearsal |
| Demo 01b | Optional | Runs on the prepared lite graph | 15 to 20 minutes | Estimate; confirm at rehearsal |
| Demo 02 | Optional | Under 5 minutes | 15 to 20 minutes | Estimate; confirm at rehearsal |
| Demo 03 | Optional | Under 5 minutes | 15 to 20 minutes | Estimate; confirm at rehearsal |
| Demo 04 | Core | Under 5 minutes | 10 to 15 minutes | Estimate; confirm at rehearsal |
| Demo 05 | Core | Under 5 minutes, once the Agent Control server is running | 15 to 20 minutes, plus server setup time | Estimate; confirm at rehearsal |
| Demo 06A | Core | Notebook 1 runs against participant Aura; Notebook 2 is facilitator-only | Target window 30 to 45 minutes | TBD: confirm actual duration during operator rehearsal |
| Demo 06B | Deferred | Not deliverable in this pass | Not scheduled | Deferred future work |
| Demo 07 | Optional | Requires a pre-provisioned booking deployment; asynchronous extraction wait applies | TBD: confirm during operator rehearsal | Credential- and deployment-gated |
| Demo 08 | Optional | Runs on Aura with Bedrock embeddings | TBD: confirm during operator rehearsal | Live Aura and Bedrock validation pending |
| Demo 09 | Optional | Requires a pre-deployed MCP endpoint | TBD: confirm during operator rehearsal | Live endpoint validation pending |
| Demo 10 | Core | Dry run by default; deletion only with an explicit flag | 5 to 10 minutes | Estimate; confirm at rehearsal |

Demo 06A's actual duration is the single most important timing to capture. The v2 plan's Facilitator material checklist calls for rehearsing Demo 06A independently and recording its actual duration, so leave that cell as TBD until a real rehearsal produces the number. Do not publish an invented figure.

Notes on grounded execution times:

- Demos 02 through 05 execute in under 5 minutes according to the root README.
- Demo 01's knowledge graph is built during readiness, not live. The lite graph is roughly 15 minutes to build and the full graph roughly 2 hours, so build it well before the event.
- Demo 00 setup is targeted to complete within 30 minutes.
- Demo 05 needs a separate Agent Control server that is not bundled with the workshop. Budget setup time for it, and note that only the hooks half of Demo 05 runs without the server.

---

## Opening hero demonstration

The opening demonstration is the participant hands-on retrieval notebook, `06-agentcore-boto3-demo/01_hybrid_retrieval.ipynb`. Run it against a prepared Aura instance so the room sees grounding and abstention in one sitting.

### Step 1: the grounded question

Ask the named-hotel hero question:

> What amenities and guest rating does AnyCompany Cairo Nile View have?

Show the fused hybrid score, the exact matched terms found verbatim in the evidence, the chunk evidence itself, and the reviewed graph enrichment: the connected hotel, up to 12 amenities, the guest rating, and the stable fixture `hotel_id`.

Why this question works: the exact hotel name benefits from the full-text arm, the request for amenities and ratings benefits from semantic matching, and the reviewed Cypher traversal adds the structured graph context. The returned `hotel_id`, not the hotel name, becomes the reservation-command identity later in the facilitator walkthrough. Present the result as top-k grounded retrieval, not as an exhaustive database scan of every matching hotel.

### Step 2: the abstention

Ask the unsupported availability question:

> Does AnyCompany Cairo Nile View guarantee room availability next weekend?

Show the agent abstaining because the returned graph evidence contains no live inventory or availability data. Do not add a score threshold and do not switch to another retriever. The abstention is the point: the agent answers only from evidence and declines when the graph does not support the claim.

### Handoff to the facilitator walkthrough

After the hero and abstention land, move to the facilitator-only notebook, `06-agentcore-boto3-demo/02_agentcore_walkthrough.ipynb`, which only the facilitator runs against the shared pre-deployed Runtime and canonical event graph. There the facilitator submits a 15-guest request that is rejected with no write, submits a corrected request within the 10-guest limit that is written idempotently, and inspects the request-to-hotel relationship and the request-ID-correlated AgentCore and CloudWatch entries. Participants observe this walkthrough. They never invoke the shared Runtime and never send their own Neo4j credentials into shared infrastructure.

---

## Readiness before delivery

The full step-by-step checklist lives in `workshop-delivery/readiness-checklist.md`. It cross-references Demo 00, which is the in-workshop readiness module. In summary, confirm before the event:

- AWS access and Bedrock model access, including Amazon Nova 2 embeddings for retrieval query embeddings.
- Aura connectivity. Participants use their own Aura instance for the hands-on retrieval path through Demo 06A.
- Secrets. The deployed boundary uses separate Runtime-read and Lambda-command secrets in Secrets Manager, each holding URI, username, password, and database fields. A shared Runtime or Lambda never accepts participant database credentials as prompt or tool input.
- Graph fixtures and indexes. Run `python graph_setup.py --check-only` in `06-agentcore-boto3-demo/` to confirm the `hotel_chunk_embeddings` and `hotel_chunk_fulltext` indexes, the uniqueness constraints, the fixture hotel identities, and the maximum-guests rule.
- The pre-deployed AgentCore Runtime, reservation Gateway target, and reservation Lambda for the facilitator walkthrough. Set `AGENT_RUNTIME_ARN` for Notebook 2.
- The Agent Control server for Demo 05, which is a separate product and is not bundled with the workshop.
- The Neo4j MCP endpoint only when Demo 09 is selected. Verify it in Demo 00 rather than during the live module.

Demo 00 produces a single readiness report that identifies every required dependency and gives a precise corrective action for anything missing. Keep event setup within 30 minutes and avoid graph extraction or infrastructure deployment during the main path.

---

## What stays out of this repository guide

Sales targeting, calls to action, and survey routing stay in internal enablement material and are deliberately absent from this repository guide. Keep them in the enablement channel rather than adding them here.

Long harnesses and repeated model evaluations remain maintainer pre-event checks, not attendee exercises. The Demo 02 24-query cost and accuracy harness and the Demo 03 repeated multi-agent evaluation runs are maintainer validation. Run them as pre-event smoke checks and present only the summarized measured figures during delivery.

Live event deployment, shared-environment invocation, and timing rehearsal are operator tasks outside the repository-validation pass. The repository acceptance path is `setup/run_notebooks.py --labs 6`, which creates no AWS resources.

---

## Open items for the operator to fill during rehearsal

- Demo 06A actual duration, currently the target window of 30 to 45 minutes. Record the measured number.
- Facilitated delivery times for every module, which are planning estimates until rehearsal confirms them.
- Overall track timings for each suggested track shape.
- Demo 07, Demo 08, and Demo 09 live timings, which are credential- and deployment-gated.
</content>
</invoke>
