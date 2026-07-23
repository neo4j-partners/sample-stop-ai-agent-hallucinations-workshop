# Simplified Neo4j and AWS Partnership Proposal

## Goal

Make a small, focused expansion to the existing workshop that clearly explains the Neo4j and AWS partnership without redesigning every demo.

The simplified story is:

- Neo4j stores and retrieves connected hotel knowledge.
- Amazon Bedrock supplies embeddings and grounded reasoning.
- Amazon Bedrock AgentCore can host the same Neo4j retrieval tool in a production environment.

The workshop should demonstrate this story with one read-only path. It does not need a new reservation system, memory architecture, MCP lesson, or deployment lab.

## Assumptions

- Demo 01 remains the main introduction to Neo4j Graph-RAG.
- Demos 02 through 05 keep their existing teaching goals.
- Demo 06 becomes the single Neo4j and AWS integration demo.
- The partnership expansion should add as few new services and prerequisites as possible.
- Existing workshop behavior should remain unchanged unless a small edit is needed for the partnership story.

## Proposed Areas

### 1. Root Workshop Story

Add a short section to the root README explaining the division of responsibility between Neo4j and AWS.

- **Neo4j:** Stores the hotel graph, search indexes, and connected facts.
- **AWS:** Supplies Bedrock models, embeddings, and optional AgentCore hosting.
- **Workshop flow:** Demo 01 introduces Graph-RAG, and Demo 06 shows the production integration shape.
- **Limit:**  **REJECTED**  Avoid presenting Neo4j as a required addition to every demo.

**Question:** Is this the partnership story we want to tell?

**Answer**: Review slides and site in /Users/ryanknight/projects/aws/neo4j-bedrock-graphrag-workshop
 and understand better the story.  Yes we want to add Neo4j, this is Neo4j presenting the story. 

### 2. Demo 00: Getting Started

Keep Demo 00 as the existing Strands primer. Add only the Neo4j prerequisites needed by Demo 01 and Demo 06.

- **Keep:** Agents, tools, hooks, and swarms.
- **Add:** A brief note about Aura credentials and Bedrock access.
- **Remove:** The proposed workshop-wide readiness system.
- **Reason:** A full readiness engine creates more code and maintenance than the small expansion needs.

**Question:** Should Demo 00 stay a simple primer?
**Answer**: Yes,  Demo 00 will stay small and simple. 

### 3. Demo 01: Graph-RAG

Keep Demo 01 as the main Neo4j lesson and avoid changing its original comparison more than necessary.

- **Keep:** Standard RAG compared with Neo4j Graph-RAG.
- **Keep:** The existing hotel graph and vector index.
- **Add:** A short transition explaining that Demo 06 will reuse the graph with AWS services.
- **Remove:**   **REJECTED**  Stable reservation IDs and other metadata that only support graph writes.

**Question:** Can Demo 01 remain the main Neo4j introduction?
**Answer**:  Keep reservation ID's and other metadata. No change needed here.



### 4. Demo 01b: Retrieval Patterns

Treat Demo 01b as optional. Keep it only if comparing Neo4j retrieval methods is important to the audience.

- **Keep if needed:** Vector, hybrid, and Vector-Cypher comparison.
- **Simplify:** Present Text2Cypher as a short explanation instead of adding another production path.
- **Remove:** The dependency on a future MCP demo.
- **Alternative:** Move one short retrieval comparison into Demo 01 and remove Demo 01b.

**Question:** Do we need a separate retrieval-pattern notebook?
**Answer**:   YES


### 5. Demos 02 Through 05

Leave these demos focused on their original lessons. Do not require Neo4j in each module solely to expand the partnership story.

- **Demo 02:** Keep semantic tool selection without requiring a new Neo4j tool graph unless it was already part of the accepted demo.
- **Demo 03:** Keep multi-agent validation without adding new Neo4j fixtures solely for this effort.
- **Demo 04:** Keep deterministic Python rule enforcement unchanged.
- **Demo 05:** Keep Agent Control steering unchanged.
- **Documentation:** Add only small transitions where they help the workshop narrative.

**Question:** Should Demos 02 through 05 remain independent of the new integration?

### 6. Demo 06: Simplified Neo4j and AWS Integration

Make Demo 06 one read-only integration demo. It should reuse the existing hotel graph and show how Bedrock and Neo4j work together.

- **Notebook:** Use one participant notebook instead of separate participant and facilitator notebooks.
- **Question one:** Ask for the amenities and guest rating of the Cairo hero hotel.
- **Evidence:** Show the matched chunk, hybrid score, hotel facts, and connected amenities.
- **Question two:** Ask whether the hotel guarantees availability and show grounded abstention.
- **Retriever:** Use one fixed `HybridCypherRetriever` with vector search, full-text search, and one reviewed traversal.
- **Bedrock:** Use Amazon Bedrock for the query embedding and grounded response.
- **AgentCore:** Include a small optional section or architecture note showing that the same retrieval tool can run in AgentCore Runtime.
- **Writes:** Do not write reservation requests or modify hotel data.
- **Gateway:** Do not require AgentCore Gateway.
- **Lambda:** Do not require a reservation Lambda.
- **Secrets:** Use one read-only Neo4j credential for any deployed Runtime.

**Question:** Does Demo 06 need a live AgentCore invocation, or is an architecture explanation enough?

### 7. Demo 06 Reservation Work

Remove the reservation subsystem because it is not required for the partnership story.

- **Remove:** ReservationRequest nodes and `FOR_HOTEL` relationships.
- **Remove:** Maximum-guests Rule nodes in Neo4j.
- **Remove:** Stable fixture UUIDs used only for reservation identity.
- **Remove:** Date validation and idempotency behavior.
- **Remove:** The reservation Lambda and Gateway target.
- **Remove:** Separate read and command secrets.
- **Remove:** Request-ID correlation across Runtime, Gateway, Lambda, and Neo4j.
- **Keep elsewhere:** Demos 04 and 05 continue to teach the maximum-guests policy.

**Question:** Can all reservation creation be removed from Demo 06?

### 8. Demo 06B: Deployment Lab

Remove Demo 06B from the published workshop plan.

- **Remove:** From-scratch IAM, Secrets Manager, Runtime, Gateway, and Lambda deployment work.
- **Replace with:** A short operator note for deploying the read-only retrieval agent if needed later.
- **Reason:** An unimplemented future lab makes the workshop appear larger and less complete.

**Question:** Can Demo 06B be removed from the module list?

### 9. Demo 07: AgentCore Memory

Leave Demo 07 outside the Neo4j partnership expansion.

- **Keep:** Its existing managed-memory lesson if the workshop still needs it.
- **Do not add:** A dependency on the simplified Demo 06 design.
- **Do not rebuild:** The existing booking backend solely for this proposal.
- **Document:** Mark the module optional and list its existing prerequisites honestly.

**Question:** Should Demo 07 remain an optional standalone lesson?

### 10. Demo 08: Neo4j Memory

Remove the new inspectable Neo4j memory module from this expansion.

- **Remove:** The memory notebook and helper code.
- **Remove:** Titan embedding configuration and memory vector indexes.
- **Remove:** Preference provenance and actor-isolation work.
- **Remove:** Neo4j memory cleanup logic.
- **Reason:** Memory is a separate product and architecture story.

**Question:** Can Neo4j memory be deferred to a future workshop?

### 11. Demo 09: Neo4j MCP and Text2Cypher

Remove the new MCP module from this expansion.

- **Remove:** MCP endpoint configuration and client code.
- **Remove:** Tool discovery and allowlist logic.
- **Remove:** The controlled Text2Cypher notebook.
- **Remove:** MCP-specific operator security checks.
- **Reason:** MCP adds a second production architecture that competes with the fixed retrieval story.

**Question:** Is MCP required for the partnership announcement?

### 12. Cleanup

Return cleanup to the smallest scope supported by the remaining workshop.

- **Keep:** Existing tag-scoped AWS cleanup for resources the workshop actually creates.
- **Remove:** Cleanup entries for removed reservation infrastructure.
- **Remove:** Cleanup changes needed only by the new memory and MCP modules.
- **Neo4j:** Continue terminating the workshop Aura database through its normal environment lifecycle.
- **Numbering:** Restore the original cleanup number if Demos 08 and 09 are removed.

**Question:** Should cleanup return to its original module number?

### 13. Workshop Documentation

Replace the expanded delivery package with a small set of clear documentation changes.

- **Root README:** Add the partnership summary and point to Demo 01 and Demo 06.
- **Architecture:** Use one small diagram showing Bedrock, AgentCore Runtime, and Neo4j Aura.
- **Demo 06 README:** Document setup, the two questions, expected evidence, and optional AgentCore hosting.
- **Remove:** Multiple audience tracks, detailed timing matrices, and broad operator runbooks.
- **Keep:** A short prerequisites and troubleshooting section.

**Question:** Is one README and one architecture diagram enough?

### 14. Testing

Reduce the new test surface to the read-only retrieval contract.

- **Keep:** Tests for the fixed retriever configuration.
- **Keep:** Tests for bounded, null-safe results.
- **Keep:** Tests for the expected evidence shape.
- **Keep:** Tests that prevent model-generated or caller-supplied Cypher.
- **Keep if AgentCore remains:** One test proving the Runtime exposes only the retrieval tool.
- **Remove:** Reservation, rule, date, idempotency, Lambda, Gateway, memory, MCP, and expanded cleanup tests.

**Question:** Is a small retrieval-focused test suite sufficient?

### 15. Delivery and Validation

Validate only the simplified path needed for the partnership story.

- **Offline:** Run the retrieval tests and the notebook's credential-free path.
- **Live Aura:** Confirm the indexes and hero-hotel result.
- **Live Bedrock:** Confirm the grounded answer and availability abstention.
- **AgentCore:** Validate one read-only Runtime invocation only if it remains in scope.
- **Timing:** Confirm that the simplified Demo 06 fits comfortably within the existing workshop.

**Question:** Which live environment will be used for final validation?

## Files to Keep

The simplified Demo 06 should need only a small set of files:

- One hybrid retrieval notebook.
- One hybrid retrieval module.
- One small README.
- Local requirements.
- Optional Runtime entry point and container files if live AgentCore hosting is required.
- A focused retrieval test file or small test set.

## Files or Areas to Remove

- Reservation command implementation.
- Reservation Lambda directory.
- Gateway target and tool schemas.
- Stable hotel-ID fixture manifest.
- Reservation and rule contracts.
- The second facilitator reservation notebook.
- Demo 06B planning and deployment scope.
- Demo 08 Neo4j memory module.
- Demo 09 MCP module.
- Expanded workshop-delivery material.
- Tests that exist only for removed features.

## Risks

- **Removing too much:** The partnership story could lose its production connection if AgentCore disappears entirely.
- **Keeping too much:** Reservation, memory, and MCP work will continue to distract from the core integration.
- **Documentation drift:** Removed modules may remain in the root README or notebook registry.
- **Existing dependencies:** Demo 07 may still require old infrastructure and must be described honestly.
- **Untracked work:** Files selected for the simplified implementation must be reviewed and added to version control.

## Phased Implementation Plan

### Phase 1: Confirm the Small Scope

**Status:** Pending

**Outcome:** The team agrees on the minimum partnership story before files are removed or rewritten.

**Checklist:**

- [ ] Confirm that Demo 01 and Demo 06 are the only required Neo4j partnership modules.
- [ ] Decide whether Demo 01b remains optional or is removed.
- [ ] Decide whether Demo 06 includes a live AgentCore invocation.
- [ ] Confirm that reservation creation, Neo4j memory, and MCP are out of scope.
- [ ] Confirm how Demo 07 will be described.

**Validation:** Every proposed area above has a clear keep, remove, or defer decision.

### Phase 2: Reduce Demo 06

**Status:** Pending

**Outcome:** Demo 06 contains one read-only Neo4j and Bedrock retrieval path.

**Checklist:**

- [ ] Keep the fixed Hybrid-Cypher retriever and bounded evidence.
- [ ] Keep the hero question and unsupported availability question.
- [ ] Remove reservation writes, rules, IDs, Lambda, Gateway, and command secrets.
- [ ] Collapse the workshop flow into one notebook.
- [ ] Keep only the AgentCore code required by the decision from Phase 1.
- [ ] Reduce the tests to the remaining retrieval boundary.

**Validation:** Demo 06 answers the grounded question, abstains on availability, and writes no graph or AWS data.

### Phase 3: Remove Optional Expansion Work

**Status:** Pending

**Outcome:** The repository no longer advertises or carries modules outside the agreed scope.

**Checklist:**

- [ ] Remove Demo 06B from published workshop material.
- [ ] Remove or defer Demo 08 Neo4j memory work.
- [ ] Remove or defer Demo 09 MCP work.
- [ ] Stop retrofitting Neo4j into unrelated demos.
- [ ] Restore simple cleanup numbering and scope if approved.

**Validation:** The module list contains only supported, runnable workshop content.

### Phase 4: Simplify Documentation

**Status:** Pending

**Outcome:** The partnership story is clear without a large delivery framework.

**Checklist:**

- [ ] Shorten the root README changes to the partnership summary and module path.
- [ ] Publish one small architecture diagram.
- [ ] Rewrite the Demo 06 README around the single retrieval flow.
- [ ] Update the notebook registry and setup guide.
- [ ] Remove stale references to deleted modules and files.

**Validation:** A reader can understand the partnership story and run the demo without consulting planning documents.

### Phase 5: Validate and Finish

**Status:** Pending

**Outcome:** The simplified expansion is tested and ready to review.

**Checklist:**

- [ ] Run the reduced offline test suite.
- [ ] Run the simplified notebook without credentials and confirm safe skipping.
- [ ] Run the notebook against Aura and Bedrock.
- [ ] Validate AgentCore only if it remains in scope.
- [ ] Confirm that removed files and modules are no longer referenced.
- [ ] Review the final working tree and add all intended files to version control.

**Validation:** The final branch contains a small, coherent Neo4j and AWS expansion with no unsupported modules or conflicting documentation.

## Completion Criteria

- The root README tells a concise Neo4j and AWS partnership story.
- Demo 01 remains the Graph-RAG foundation.
- Demo 06 contains one read-only Hybrid-Cypher integration path.
- The demo shows one grounded answer and one evidence-based abstention.
- Reservation creation, Gateway, Lambda, memory, and MCP are outside the expansion.
- Demos 02 through 05 retain their original teaching goals.
- Demo 07 is clearly optional and is not rebuilt for this work.
- Documentation and cleanup match the reduced module list.
- The remaining tests and live checks pass.
