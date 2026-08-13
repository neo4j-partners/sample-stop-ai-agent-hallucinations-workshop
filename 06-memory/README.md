[< Back to Main README](../README.md)

# Lab 6: Neo4j agent memory

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://python.org)
[![Amazon Bedrock](https://img.shields.io/badge/Amazon-Bedrock-FF9900.svg?style=flat&logo=amazon-aws)](https://aws.amazon.com/bedrock/)
[![Neo4j](https://img.shields.io/badge/Neo4j-Agent_Memory-4581C3.svg?style=flat&logo=neo4j)](https://neo4j.com)

**This lab is optional.** The core path ends at Lab 5, with the agent deployed on AgentCore Runtime and torn down again. Lab 6 is extra material for anyone whose agent needs to remember something between sessions and who wants that memory to be inspectable rather than opaque.

**At a Glance**
- **What it covers:** explicit, graph-native memory with provenance and actor isolation, and when to prefer it over a managed store.
- **Neo4j:** holds each memory record, the message it came from, and its link to a real `Hotel`, in the same Aura instance Lab 1 built.
- **AWS:** Amazon Bedrock supplies the memory embeddings through Titan Text Embeddings V2. AgentCore Memory is the managed alternative this lab weighs itself against.
- **You build:** two actors with conflicting preferences about the same hotel, each recalling only their own in a fresh session, and each tracing back to the exact message that produced it.

**This lab depends on Lab 1.** Optional and last does not mean standalone. The notebook requires exactly one `Hotel` named `AnyCompany Cairo Nile View`, which `1.1_build_graph.ipynb` creates. Without it, section 2 stops with a `RuntimeError` naming the missing hotel rather than writing partial memory.

---

## The notebook

`6.1_neo4j_agent_memory.ipynb` runs one bounded story: persist a preference statement, recall it for the same actor in a fresh session, prove a second actor with the opposite preference about the same hotel gets their own row and never the first actor's, and inspect where each preference came from and which real `Hotel` it describes.

| Section | What it does |
|---------|--------------|
| 1. Configure one isolated run | Builds actor and session IDs from a fresh run ID under the `demo08-` namespace, so rerunning cannot append to an earlier transcript |
| 2. Persist the preference statement | Verifies the Lab 1 hero `Hotel`, then writes two fixture messages for actor A |
| 3. Write one explicit preference and its provenance | Creates the actor-owned `Preference` in this run's `category` namespace, then adds `DERIVED_FROM` to its source message and `ABOUT_HOTEL` to the existing `Hotel` |
| 4. Recall in a fresh session and isolate a second actor | Opens a new session for actor A, then gives actor B the opposite preference about the same `Hotel`. The same actor-anchored traversal, one parameter apart, returns each actor exactly their own row |
| 5. Inspect the complete provenance path | Walks backward along `DERIVED_FROM` to the source message and its conversation, forward along `ABOUT_HOTEL` to the canonical `Hotel`, then back down `ABOUT_HOTEL` to every memory about that hotel. Closes with a Neo4j Browser query that renders the subgraph |
| Mark this run for cleanup | Stamps the run's records with `workshop_owner` so cleanup has a second handle beyond the ID prefix |
| Choosing a memory architecture | The closing comparison against AgentCore Memory |
| Where this leaves you | The workshop's through-line applied one last time, and where to go next |

Each live cell opens and closes its own memory client, so a failure in a later cell cannot leak a connection. Every live cell skips cleanly when Neo4j or AWS credentials are absent.

**The story uses fixture messages, not another model call.** Extraction is switched off through `ExtractorType.NONE` and every message is written with `extraction_mode="skip"`, so the assertions are deterministic and the lesson stays on the memory graph. Wiring the same pattern around the Lab 3 `hotel_agent` is a straightforward extension and is not required here.

## Why memory in the graph rather than a managed store

A managed memory service is the shorter path to a working agent, and for many applications it is the right one. AWS operates the store, extraction happens for you, and there is no embedding contract to own. What it does not give you is the last thing this notebook does.

When a preference is a node in the same graph as the hotels, it is traversable in both directions. Backward, `DERIVED_FROM` reaches the exact `Message` that produced it, and through `HAS_MESSAGE` the `Conversation` that message belongs to. Forward, `ABOUT_HOTEL` reaches the canonical `Hotel` the preference is about, from which every other memory pointing at that hotel is one hop away. Section 5 asks for all of that in one query and gets a traversal, not a similarity score. That is the difference between memory you can query and memory you can only retrieve from. It is the same argument the rest of the workshop makes about hotel knowledge, applied to what the agent remembers, and it costs the operational convenience of a store somebody else runs.

| Dimension | AgentCore Memory | Neo4j graph memory, this lab |
|-----------|------------------|------------------------------|
| How memory is written | Raw events, plus optional managed extraction into long-term records. This lab turns extraction off and writes explicitly | Explicit application writes |
| When it is recallable | Raw event records immediately; extracted long-term records after asynchronous extraction | Immediately after the write |
| Inspectability | Retrieved through a service API | Queryable graph with source provenance |
| Domain linking | Separate from domain data | Workshop-owned edge to the real `Hotel` |
| Isolation | Actor namespaces managed by the service | Scoped writes and actor-anchored reads, with the application authorizing sessions |
| Operations | AWS operates the store | You operate Neo4j and the embedding contract |

Choose AgentCore Memory for managed extraction and managed operations. Choose graph memory when explicit writes, immediate visibility, provenance, and domain relationships matter.

## The isolation boundary is explicit and limited

`build_memory_settings` turns on `MemoryConfig(multi_tenant=True)`, so the supported memory writes raise `ValueError` when `user_identifier` is missing. That makes the actor-isolation lesson structural rather than conventional. It is not an authorization system, and this lab is careful about the difference:

- **The application must still authenticate actors and authorize session IDs.** Multi-tenant mode checks that an identifier was supplied. It never checks that the caller is entitled to it. Binding actor and session IDs to an authenticated caller is application work.
- **The library's semantic searches are store-wide in the pinned 0.5.0 release.** `SEARCH_PREFERENCES_BY_EMBEDDING` calls `db.index.vector.queryNodes('preference_embedding_idx', ...)` with no owner filter, so a similarity hit can belong to any actor. This lab therefore does not use semantic search as an isolation boundary.
- **Recall starts at the selected `User` instead.** `get_actor_preferences_for_hotel` matches `(:User {identifier: $user_identifier})-[:HAS_PREFERENCE]->(:Preference)-[:ABOUT_HOTEL]->(:Hotel {name: $hotel_name})`, so a preference the actor does not own is not reachable by the query at all. There is nothing to filter out, and so nothing to forget to filter. That is why section 4's two actors, who differ in nothing else the store can see, each get exactly their own row.

## Configuration

This lab uses the same Aura instance and the same credentials as Lab 1. If the repo-root `.env` described in [Neo4j setup](../README.md#neo4j-setup) is in place, nothing else is needed. The values that matter:

- `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD`
- `NEO4J_DATABASE` when the target database is not named `neo4j`
- `AWS_REGION`, defaulting to `us-east-1`
- AWS credentials permitted to invoke `amazon.titan-embed-text-v2:0`

`load_config` reads `06-memory/.env` first, then the repo-root `.env`, and values already exported into the shell win over both. It does not read another lab's folder, so credentials that live only in `01-graph-build/.env` have to be copied to the repo root or into this folder.

**The memory embedding contract is deliberately separate from the chunk one.** The library's Bedrock embedder supports the Titan and Cohere request formats, so memory uses Titan Text Embeddings V2 at 1024 dimensions and writes to its own `message_embedding_idx` and `preference_embedding_idx` indexes. Lab 1's chunk vectors keep using Nova 2 and `hotel_chunk_embeddings`. Two contracts, two sets of indexes, no conflict.

**`memory_helpers.py` builds the embedder explicitly, and that is not cosmetic.** In 0.5.0 `MemoryClient._create_embedder` returns `None` for the Bedrock provider, which leaves the client without an embedder while `generate_embedding=True` still succeeds and writes zero-length vectors. Semantic recall then finds nothing, silently. The Titan embedder is constructed in `build_memory_embedder` and passed through `embedder=` for that reason, and `EmbeddingConfig.dimensions` is pinned to 1024 because the field defaults to OpenAI's 1536.

## Run it

Install this lab's dependencies, from the repository root:

```bash
cd 06-memory
uv venv && uv pip install -r requirements.txt
```

Then open `6.1_neo4j_agent_memory.ipynb` in VS Code, Kiro, or any editor with notebook support and run it top to bottom. The notebook is part of the default `setup/run_notebooks.py` run described in the root README, so it is also exercised by the repository's offline acceptance gate.

Run the offline tests, from inside `06-memory/`:

```bash
uv run --with pytest --with-requirements requirements.txt -m pytest
```

27 tests in `test_memory_helpers.py` cover configuration loading, the memory settings contract, the actor-scoped read, the tagging query, the scoping of every cleanup query, and the hotel-count guard that makes cleanup abort if the hotel graph moved. They need no credentials and touch no graph.

Check the live memory foundations before teaching from this lab, from inside `06-memory/`:

```bash
uv run --with-requirements requirements.txt python smoke_test.py
```

The smoke test proves four things against the real instance: an unscoped write is rejected by multi-tenant enforcement, a scoped message reads back through `get_context`, both memory vector indexes exist at 1024 dimensions, and the stored embedding is full width rather than empty. It deletes everything it wrote, including its throwaway `User`. Without credentials it prints a skip message and exits 0.

## Cleanup

One notebook run writes eleven nodes: two `User` nodes, three `Conversation` nodes, four `Message` nodes, and two `Preference` nodes, one per actor. Reset the lab whenever those accumulate, from inside `06-memory/`:

```bash
uv run --with-requirements requirements.txt python cleanup_memory.py
```

**It removes every Lab 6 run on the instance, not just yours.** The session and user sweeps match the bare `demo08-` prefix with no run ID in it, which is what makes an interrupted earlier run recoverable. The consequence is that on a Neo4j instance shared by several participants, whoever runs the script deletes everybody's Lab 6 records, including runs still in progress. On a shared instance, wait until everyone is finished. Run scoping exists in section 1 of the notebook precisely because instances get shared; cleanup deliberately does not use it.

**What it removes:** workshop-owned `ABOUT_HOTEL` relationships, then `Conversation` and `Message` nodes whose `session_id` starts with `demo08-`, then `User` nodes whose `identifier` starts with `demo08-`, then orphaned preferences, which are those tagged `neo4j-ftw-demo-8` or whose `category` starts with `hotels-demo08-` and that no user still owns.

**What it never touches:** `Hotel` nodes, the hotel chunk indexes, and any other lab's data. The script counts hotels before and after and raises an `AssertionError` if the number moves. The library-managed memory vector indexes are left in place: they are shared infrastructure, they cost nothing while empty, and the smoke test checks them.

**Recovering from an interrupted run.** Every record this lab writes is namespaced from the moment it is created, while `workshop_owner` is only stamped by the notebook's second-to-last cell. A run that died before that cell is therefore still fully removable. Conversations, messages, and users carry the `demo08-` prefix in their identifiers. A `Preference` has no identifier of its own to carry it, so the namespace goes in its `category`, as `hotels-demo08-<run id>`. That matters more than it looks: by the time the preference sweep runs, the preceding sweeps have already removed the `ABOUT_HOTEL` edge, detach-deleted the `Message` behind `DERIVED_FROM`, and detach-deleted the owning `User`. Without the category handle an untagged preference would be left at zero degree with nothing able to find it, one per interrupted run. The ownership marker is a second handle, not the only one.

**Do not rename the prefix.** `DEMO_ID_PREFIX = "demo08-"` in `memory_helpers.py` is the single definition; `cleanup_memory.py` imports it and `test_memory_helpers.py` asserts its value, so a rename propagates and fails loudly rather than silently orphaning records. The reason not to rename it is different: records already written to a shared instance under the old prefix stop matching the new one, and nothing in the lab can then find them. The digits are `08` because this lab was Demo 08 before the renumber to six labs. The value is arbitrary, only its stability matters, and it is participant-visible in section 5's output and in the Neo4j Browser query. The paired constants are `WORKSHOP_OWNER = "neo4j-ftw-demo-8"` and `PREFERENCE_CATEGORY_PREFIX`, which is derived from `DEMO_ID_PREFIX` rather than restated.

**What it needs:** live Neo4j credentials and no AWS access at all. It prints a skip message and exits 0 when Neo4j is not configured.

## Files

| File | Purpose |
|------|---------|
| `6.1_neo4j_agent_memory.ipynb` | The five-step participant story |
| `memory_helpers.py` | Configuration loading, the pinned memory client and its explicit Titan embedder, the namespace constants, the actor-scoped read, the two relationship writes, and the run-tagging query |
| `smoke_test.py` | Live connection, multi-tenant, vector-index, and embedding-width checks |
| `cleanup_memory.py` | Prefix- and owner-scoped cleanup that never mutates `Hotel` nodes |
| `test_memory_helpers.py` | 27 offline tests over configuration, helpers, cleanup scope, and the hotel-count guard |
| `requirements.txt` | The shared `workshop` package plus `neo4j-agent-memory[bedrock]==0.5.0` |

## Troubleshooting

**Section 2 fails with "Lab 1 must create exactly one Hotel named 'AnyCompany Cairo Nile View'".** The hero `Hotel` is missing, or the graph holds duplicates of it. This lab looks the hotel up by exact name because the name is also what appears in the notebook output and the Browser query, so a near-miss name does not match. Confirm what the graph holds:

```cypher
MATCH (h:Hotel {name: "AnyCompany Cairo Nile View"}) RETURN count(h) AS hotels
```

If the count is zero, Lab 1 has to run. There is no lightweight seeding step to reach for: the hero `Hotel` is a node Bedrock extracts from `hotel-cairo-001.txt` during the build, and Lab 1's closing step only stamps the fixture `hotel_id` from `workshop/src/workshop/fixtures/hotel_ids.json` onto the node extraction already produced. The faster of the two paths is the script form rather than the notebook:

```bash
cd ../01-graph-build && uv run prepare_graph.py --mode lite
```

It is idempotent, builds the 30-document corpus only if the graph is not already complete, and applies the fixture IDs either way.

If the count is above one, an interrupted or overlapping Lab 1 build is the usual cause. Run one build, alone, and let it finish: `uv run prepare_graph.py --mode lite --rebuild`.

**An `AccessDeniedException` on the first memory write.** Memory embeddings need `amazon.titan-embed-text-v2:0` enabled in `AWS_REGION`, and that is a different model from the Nova 2 embeddings Lab 1 uses. Lab 1 succeeding proves nothing about Titan access. Enable the model in the [Bedrock Model Access console](https://console.aws.amazon.com/bedrock/home#/modelaccess) for the region in your `.env`, then re-run.

**Connecting raises an embedding dimension mismatch.** Memory vector indexes already exist on this instance at a different width, usually 1536 from an earlier run configured for OpenAI defaults. Run `smoke_test.py`, which reports the dimensions it found on `message_embedding_idx` and `preference_embedding_idx`. Drop the two mismatched indexes and let the next connect recreate them at 1024.

**Recall returns nothing even though the write succeeded.** Check that the memory client was built through `build_memory_client`. A client constructed without the explicit Titan embedder writes zero-length vectors and raises no error.

**Leftover memory nodes from an interrupted run.** Run `cleanup_memory.py`. It removes namespaced records whether or not the tagging cell ever ran, so an interrupted notebook needs no manual repair. If cleanup itself fails with a changed hotel count, stop and investigate before re-running: something outside this lab is writing `Hotel` nodes, and cleanup deliberately refuses to continue.

**Every cell prints a skip message.** Neo4j or AWS credentials are missing. This is the intended offline behavior, and it is what keeps the notebook green in the repository's credential-free acceptance run.

## Where this leaves you

This is the end of the workshop, and memory is the last place its through-line shows up. Neo4j owns the connected data. AWS owns reasoning and hosting. In this lab AWS's share of that is narrow on purpose: Bedrock supplies the memory embeddings through Titan Text Embeddings V2 and nothing else. Extraction is off, no LLM is constructed, and every memory record is written explicitly rather than inferred by a model. What the agent remembers went into the same graph as what it knows, joined to it by a real relationship to the `Hotel` node Lab 1 built rather than to a copy of it or a string that matches its name.

[`../workshop-delivery/architecture.md`](../workshop-delivery/architecture.md) has the production view for anyone taking this further: how the pieces fit, which boundaries survive contact with a real deployment, and what changes when the graph is not a workshop instance.

- **Previous:** [Lab 5: Deploy to AgentCore](../05-agentcore-deploy/)
- **Start from the beginning:** [Lab 1: Graph build](../01-graph-build/)

---

## Contributing

Contributions are welcome. See [CONTRIBUTING](../CONTRIBUTING.md) for more information.

## Security

If you discover a potential security issue in this project, notify AWS/Amazon Security via the [vulnerability reporting page](https://aws.amazon.com/security/vulnerability-reporting/). Please do **not** create a public GitHub issue.

## License

This library is licensed under the MIT-0 License. See the [LICENSE](../LICENSE) file for details.

> Last updated: August 2026 | Python 3.12+ | Amazon Bedrock | Neo4j Agent Memory 0.5.0
