# Pre-Delivery Readiness Checklist

Work this checklist two working days before the event, then again the morning of delivery. It cross-references Demo 00, the in-workshop readiness module, which produces a single readiness report with a precise corrective action for anything missing. See `00-getting-started/README.md` and, for Demo 06A specifics, `06-agentcore-boto3-demo/README.md`.

Keep event setup within 30 minutes for participants, and avoid graph extraction or infrastructure deployment during the main path. Build any large graph well ahead of time.

---

## 1. AWS access and Bedrock

- [ ] AWS credentials are configured. At an AWS event they are pre-configured; self-paced facilitators run `aws configure` or set the environment variables.
- [ ] Bedrock model access is enabled for the workshop model, for example `us.anthropic.claude-sonnet-5` or the equivalent, in the Bedrock Model Access console.
- [ ] Amazon Nova 2 embeddings are available for retrieval query embeddings, at 1,024 dimensions with the `GENERIC_INDEX` purpose, matching the pinned chunk embedding contract.

## 2. Neo4j Aura connectivity

- [ ] Each participant has an Aura instance for the hands-on retrieval path through Demo 06A. Participants use their own Aura instance for hands-on retrieval.
- [ ] The canonical event graph exists on the Aura instance the facilitator uses for the pre-deployed walkthrough.
- [ ] Local connection values are set: `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, and `NEO4J_DATABASE`.

## 3. Graph fixtures and indexes

Run the one-time readiness check in `06-agentcore-boto3-demo/`:

```bash
python graph_setup.py --check-only
```

- [ ] The `hotel_chunk_embeddings` vector index is online and matches the pinned embedding contract.
- [ ] The `hotel_chunk_fulltext` full-text index is online over chunk text.
- [ ] Ordinary Cypher 25 uniqueness constraints exist for fixture hotel IDs and reservation request IDs.
- [ ] The fixture hotel identities in `fixtures/hotel_ids.json` resolve, including the hero hotel `AnyCompany Cairo Nile View`.
- [ ] The maximum-10-guests Rule node exists with its rejection and steering messages.

The check reports one corrective action per missing dependency and exits non-zero until the graph is ready.

## 4. Secrets and credential separation

- [ ] The deployed Runtime-read secret exists in Secrets Manager with `uri`, `username`, `password`, and `database`, and grants read-only privileges.
- [ ] The Lambda-command secret exists separately and grants only the required rule reads and workshop-owned request writes. It cannot update or delete canonical hotel, chunk, document, amenity, or rule data.
- [ ] No participant Neo4j credential is ever accepted by a shared Runtime or Lambda as prompt or tool input. Participant credentials stay in participant-local configuration only.
- [ ] Passwords, secret values, and full connection strings never appear in a deployment package, a prompt, or a log.

## 5. Pre-deployed AgentCore boundary for the facilitator walkthrough

The core live flow requires only reservation-request creation. Inspect and cancel actions are not Demo 06A acceptance criteria.

- [ ] The AgentCore Runtime hosting `booking_agent.py` is deployed and reachable.
- [ ] The AgentCore Gateway exposes exactly one target, `create_reservation_request`, per `deployment/gateway_target.json`.
- [ ] The single reservation Lambda under `lambda_tools/create_reservation_request/` is deployed and enforces the closed schema, the canonical UUID, strict dates, a positive guest count, and the Neo4j maximum-guests rule at the command boundary.
- [ ] `AGENT_RUNTIME_ARN` is set for Notebook 2 so its live cells run rather than self-skip.
- [ ] A rehearsal confirms the 15-guest rejection with no write, the corrected in-limit request written idempotently, and request-ID correlation across Runtime retrieval, Gateway, the reservation Lambda, and Neo4j work in AgentCore and CloudWatch.

Only the facilitator invokes the shared pre-deployed Runtime. Participants observe.

## 6. Demo 05 Agent Control server

- [ ] The Agent Control server is installed and started from its own source. It is a separate open-source product and is not bundled with the workshop or the `agent-control-sdk` package.
- [ ] The hooks half of Demo 05 runs without the server as the baseline; the steering half needs the running server. Budget setup time.

## 7. Neo4j MCP endpoint, only if Demo 09 is selected

- [ ] A pre-deployed read-only Neo4j MCP endpoint is reachable, and discovery returns exactly `get_neo4j_schema` and `read_neo4j_cypher`.
- [ ] `NEO4J_MCP_URL` and, when required, `NEO4J_MCP_TOKEN` are set.
- [ ] The database role, server write rejection, timeout, and response cap are verified in a disposable operator preflight, not during the live module.

## 8. Repository validation and maintainer pre-event checks

- [ ] `setup/run_notebooks.py --labs 6` passes and creates no AWS resources.
- [ ] The Demo 06 offline test suite passes.
- [ ] Maintainer harnesses are run as pre-event smoke checks, not attendee exercises: the Demo 02 24-query cost and accuracy harness and the Demo 03 repeated multi-agent evaluation runs. Present only the summarized measured figures during delivery.

## 9. Cleanup readiness

- [ ] Demo 10 tag-gated AWS cleanup is available and defaults to a dry run. Deletion happens only with the explicit confirmation flag.
- [ ] The Neo4j database is terminated separately through its own environment lifecycle. No Neo4j record or index cleanup is part of the executable path.
</content>
