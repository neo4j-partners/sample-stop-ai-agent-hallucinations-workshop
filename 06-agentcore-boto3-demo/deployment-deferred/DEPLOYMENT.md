# Demo 06A deployable boundary

This directory prepares, but does not deploy, the production boundary used by
the facilitator walkthrough.

## Runtime

`booking_agent.py` is the Runtime entry point. It exposes exactly two logical
tools:

- `search_hotel_knowledge` runs in-process with the fixed Hybrid-Cypher
  retriever. It reads `NEO4J_READ_SECRET_ID` in the deployed environment.
- `create_reservation_request` is discovered from AgentCore Gateway. The
  Gateway must contain only the target in `deployment/gateway_target.json`.

The Runtime also requires `GATEWAY_URL`. `MODEL_ID`, `AWS_REGION`, and
`AWS_DEFAULT_REGION` are optional configuration. The Runtime role should be
able to invoke the configured Bedrock model, read only the named Runtime-read
secret, and invoke the named Gateway. It does not need access to the command
secret or permission to invoke the reservation Lambda directly.

The system prompt requires grounded retrieval before the command, requires a
stable hotel ID from that retrieval, and forbids automatic changes to dates or
guest count. A policy rejection is returned to the facilitator instead of
being silently corrected.

## Gateway and Lambda

The Gateway target manifest defines only `create_reservation_request`. The
target uses the Gateway IAM role to invoke the one reservation Lambda. It does
not register the local retrieval function, any old booking-lifecycle Lambda,
a raw-Cypher Lambda, or a Neo4j MCP service. This pass adds no custom JWT or
other Gateway authentication infrastructure.

AgentCore accepts only a subset of JSON Schema keywords in a Lambda target.
The manifest therefore uses `type`, `description`, `properties`, and
`required`; `contracts.gateway_reservation_input_schema()` defines that exact
projection. The Lambda independently enforces the complete closed application
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
- Lambda-command user: read the Demo 06 Rule and fixture Hotel identity, and
  create or read workshop-owned ReservationRequest nodes and `FOR_HOTEL`
  relationships. It must not update or delete Hotel, Chunk, Document, Amenity,
  or Rule data.

Even on a tier that cannot express all of those graph privileges separately,
keep two credentials and two secret identifiers. The Lambda's fixed,
parameterized Cypher remains the application-level command boundary.

## Request correlation

The caller creates a canonical UUID and passes it to the Runtime as
`request_id`. The Runtime passes that same value to the command. Runtime and
Lambda logs record the request ID but do not log prompts, credentials, secret
payloads, or connection strings. Gateway and AgentCore traces can therefore be
inspected using the same request ID during the facilitator walkthrough.

## Out of scope

This package does not model live availability, pricing, payment, confirmation,
cancellation, inventory changes, or a complete booking. DynamoDB may exist
behind a real external reservation system, but it is not part of the Demo 06
executable path.
