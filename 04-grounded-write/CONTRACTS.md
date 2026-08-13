# Frozen contracts

These contracts are shared by the local retrieval and write path Lab 4 runs and
the deployed Runtime, Gateway, and Lambda Lab 5 stands up. Nothing in this file
deploys AWS resources.

## Hotel retrieval

The tool accepts one field, `query`. Callers cannot select a retriever, ranker,
weight, or result count. The implementation always uses:

- `HybridCypherRetriever`
- vector index `hotel_chunk_embeddings`
- full-text index `hotel_chunk_fulltext`
- Amazon Nova 2 embeddings, 1,024 dimensions, `GENERIC_INDEX` purpose
- explicit `NAIVE` fusion and `top_k=5`
- one reviewed, parameterized Cypher traversal

Each result contains at most 1,200 characters of chunk evidence, the combined
hybrid score, up to 20 whole query terms found verbatim in that evidence, hotel
ID, hotel name, address, guest rating, and at most 12 alphabetically sorted
amenities. Missing graph facts are returned as null or an empty list. Hotel IDs
are null for non-fixture hotels, which cannot be sent to the reservation
command. No generated Cypher or per-index diagnostics are returned.

The retriever does not claim that a hotel has live inventory or guaranteed
availability. The agent must abstain when the returned evidence does not support
an answer.

## Reservation request command

The command accepts exactly `request_id`, `hotel_id`, `check_in`, `check_out`,
and `guests`. The caller creates a UUID and reuses it for retries. There is no
actor or guest identity field. Dates use `YYYY-MM-DD`.

The committed Gateway manifest,
`05-agentcore-deploy/deployment-tools/gateway_target.json`, uses the smaller JSON
Schema subset accepted by AgentCore. The Lambda still enforces the full closed
schema, canonical UUID, strict date format, and positive guest count at the
command boundary.

Responses have one of these stable outcomes:

| Outcome | `status` | `reason_code` | Write behavior |
| --- | --- | --- | --- |
| Accepted | `accepted` | omitted | Creates one request and one `FOR_HOTEL` relationship |
| Duplicate delivery | `accepted` | omitted | Returns the existing request with `duplicate=true` |
| Policy rejection | `rejected` | `max_guests_exceeded` | No write |
| Unknown hotel | `rejected` | `unknown_hotel` | No write |
| Invalid dates | `rejected` | `invalid_dates` | No write |
| Unauthorized | `error` | `unauthorized` | No write |
| Service failure | `error` | `service_error` | No intentional write |

Every response contains `status`, `request_id`, `hotel_id`, `duplicate`, and
`message`. Accepted and duplicate responses also contain `created_at` and omit
`reason_code`. Rejections and errors contain `reason_code`; only the
maximum-guests rejection also contains `max_guests`.

Only a hotel with a stable ID from the committed fixture manifest at
`workshop/src/workshop/fixtures/hotel_ids.json` can be selected. Check-in cannot
be in the past, check-out must be after check-in, and the enabled Neo4j rule
limits the request to 10 guests.

An accepted request persists `status=accepted` and a Neo4j-generated
`created_at` timestamp. The response returns that timestamp. A repeat delivery
is accepted as a duplicate only when its hotel ID, dates, and guest count match
the immutable stored request; it returns the original timestamp without an
update. Reusing the request ID with different input returns `service_error` and
does not change the existing request.

The manifest contains only the two Cairo source files guaranteed by the lite
graph. Graph extraction records each source filename on its `Document`, and the
preparation step follows `Document` to `Chunk` to `Hotel` before assigning the
opaque ID. It never treats a generated hotel name as identity.

## Neo4j reads and writes

The retrieval credential can read chunk search indexes and traverse from a
matched chunk to connected hotel and amenity data. It cannot write.

The command credential can read the `demo-06-maximum-guests` rule, match a
fixture hotel by stable ID, and create a workshop-owned `ReservationRequest`
plus its `FOR_HOTEL` relationship. It cannot update canonical hotel facts.

Workshop-owned rule and request nodes carry `workshop_owner=neo4j-ftw-demo-6`.
`request_id` is the correlation identifier in application logs. Passwords,
secret values, and complete connection strings must never be logged.

Local code and the Runtime Lab 5 deploys read `NEO4J_URI`, `NEO4J_USERNAME`,
`NEO4J_PASSWORD`, and `NEO4J_DATABASE`. The reservation Lambda reads
`NEO4J_COMMAND_SECRET_ID`. `workshop.hybrid_retrieval` also honors
`NEO4J_READ_SECRET_ID` when it is set, which is the two-credential production
form in
[`../05-agentcore-deploy/advanced-deployment/DEPLOYMENT.md`](../05-agentcore-deploy/advanced-deployment/DEPLOYMENT.md)
rather than what Lab 5 deploys. Each referenced secret contains `uri`,
`username`, `password`, and `database`.
