# Production-hardening reference: the deployable boundary

This file describes a hardened form of the Lab 5 boundary. **Nothing here is run
by the workshop.** It deliberately describes two Neo4j users and a separate
Runtime-read secret, which is stronger than the one Neo4j user and the
environment-variable read that [`../5.1_agentcore_deploy.ipynb`](../5.1_agentcore_deploy.ipynb)
deploys. Read it as the next step past Lab 5, not as a description of Lab 5.

The deployable source it describes lives one level over in
[`../deployment-tools/`](../deployment-tools/): the Runtime entry point
`booking_agent.py`, the container, the Gateway target manifest
`gateway_target.json`, and the reservation Lambda under `lambda_tools/`.

## Runtime

`../deployment-tools/booking_agent.py` is the Runtime entry point. It exposes
exactly two logical tools:

- `search_hotel_knowledge` runs in-process with the fixed Hybrid-Cypher
  retriever. In this hardened form it reads `NEO4J_READ_SECRET_ID` in the
  deployed environment. Lab 5 instead forwards `NEO4J_URI`, `NEO4J_USERNAME`,
  `NEO4J_PASSWORD`, and `NEO4J_DATABASE` as container environment variables, and
  `workshop.hybrid_retrieval` falls back to those when no read secret is named.
- `create_reservation_request` is discovered from AgentCore Gateway. The
  Gateway must contain only the target in
  `../deployment-tools/gateway_target.json`.

The Runtime also requires `GATEWAY_URL`. `MODEL_ID`, `AWS_REGION`, and
`AWS_DEFAULT_REGION` are optional configuration. The Runtime role should be
able to invoke the configured Bedrock model, read only the named Runtime-read
secret, and invoke the named Gateway. It does not need access to the command
secret or permission to invoke the reservation Lambda directly.

The system prompt requires grounded retrieval before the command, requires a
stable hotel ID from that retrieval, and forbids automatic changes to dates or
guest count. A policy rejection is returned to the caller instead of being
silently corrected.

## Gateway and Lambda

The Gateway target manifest defines only `create_reservation_request`. The
target uses the Gateway IAM role to invoke the one reservation Lambda. It does
not register the local retrieval function, any old booking-lifecycle Lambda,
a raw-Cypher Lambda, or a Neo4j MCP service. `setup/provision_agentcore.py`
creates the Gateway with `authorizerType` `NONE`, so neither Lab 5 nor this
reference adds custom JWT or other Gateway authentication infrastructure.

AgentCore accepts only a subset of JSON Schema keywords in a Lambda target.
The manifest therefore uses `type`, `description`, `properties`, and
`required`; `workshop.contracts.gateway_reservation_input_schema()` defines that
exact projection. The Lambda independently enforces the complete closed application
schema.

The reservation Lambda reads `NEO4J_COMMAND_SECRET_ID`. Both Neo4j secrets
have the same JSON shape:

```text
uri, username, password, database
```

Never place secret values in the Runtime package, Gateway schema, prompts, or
logs.

## Neo4j users

Use separate Neo4j users when the deployed Aura tier supports fine-grained
privileges:

- Runtime-read user: read the prepared Chunk, Document, Hotel, Amenity, and
  their retrieval relationships. It has no graph write privileges.
- Lambda-command user: read the `demo-06-maximum-guests` Rule and fixture Hotel
  identity, and create or read workshop-owned ReservationRequest nodes and
  `FOR_HOTEL` relationships. It must not update or delete Hotel, Chunk,
  Document, Amenity, or Rule data.

Even on a tier that cannot express all of those graph privileges separately,
keep two credentials and two secret identifiers. The Lambda's fixed,
parameterized Cypher remains the application-level command boundary.

## Request correlation

The caller creates a canonical UUID and passes it to the Runtime as
`request_id`. The Runtime passes that same value to the command. Runtime and
Lambda logs record the request ID but do not log prompts, credentials, secret
payloads, or connection strings. Gateway and AgentCore traces can therefore be
inspected using the same request ID, which is what
[`../5.3_agentcore_walkthrough.ipynb`](../5.3_agentcore_walkthrough.ipynb) does.

## Out of scope

This boundary does not model live availability, pricing, payment, confirmation,
cancellation, inventory changes, or a complete booking. DynamoDB may exist
behind a real external reservation system, but it is not part of the workshop's
executable path.
