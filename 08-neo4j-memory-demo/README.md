# Module 8: Inspectable Neo4j Memory

This optional module shows one bounded memory story: persist a hotel
preference, recall it for the same actor in a fresh session, prove a different
actor sees nothing, and inspect its source and domain link in Neo4j.

**At a Glance**
- **What it covers:** explicit memory you can inspect, with provenance and per-actor isolation.
- **Neo4j:** stores each memory, its source, and its link to the hotel domain.
- **AWS:** Amazon Bedrock provides the embeddings.
- **You'll build:** a memory that persists a preference, recalls it for the same user, and hides it from others.

## What the notebook does

1. Creates run-specific actor and session IDs under the `demo08-` namespace.
2. Verifies that Module 1 created the fixed hero Hotel,
   `AnyCompany Cairo Nile View`.
3. Persists two fixture messages and one explicit actor-owned preference.
4. Adds workshop-owned `DERIVED_FROM` and `ABOUT_HOTEL` relationships so the
   preference points to its exact source message and the existing Hotel.
5. Starts a fresh session for actor A and recalls the preference with an
   actor-anchored graph read. The same read for actor B returns nothing.
6. Renders the full provenance path in one parameterized Cypher query.

The participant path intentionally uses fixture messages rather than another
agent or model call. That keeps the lesson focused on memory and makes every
assertion deterministic. Wiring the same pattern around a grounded agent is a
straightforward extension, but it is not required for this demo.

## Isolation boundary

Multi-tenant mode makes the library reject supported writes that omit a
`user_identifier`. It does not authenticate callers or authorize reads.

- The live recall path starts at `(:User {identifier: ...})` and traverses only
  that actor's `HAS_PREFERENCE` relationships.
- The application must bind actor and session IDs to an authenticated caller.
- The library's semantic searches are store-wide in 0.5.0, so this demo does
  not use them as an isolation boundary.

## Configuration and preflight

This module uses the same Neo4j Aura instance and credentials as Module 1. If
you created the repo-root `.env` described in the top-level
[README](../README.md#neo4j-setup), this module needs no extra setup. The
required values are:

- `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD`
- `NEO4J_DATABASE` when the target database is not `neo4j`
- `AWS_REGION`, defaulting to `us-east-1`
- AWS credentials permitted to invoke
  `amazon.titan-embed-text-v2:0`

`load_config` reads `08-neo4j-memory-demo/.env` first, then the repo-root
`.env`, and values already present in the environment win over both. If you
placed the Module 1 credentials inside `01-graphrag-demo/.env`, copy them to
the repo root or into this folder, or export them into your shell, because this
module does not read another demo's folder. Without any Neo4j credentials the
notebook and scripts skip every live cell cleanly.

Module 1 must have created exactly one Hotel named
`AnyCompany Cairo Nile View`. The memory indexes use Titan Text Embeddings V2
at 1024 dimensions, separately from the hotel-chunk embedding index. A live
smoke test reports a clear failure if existing memory indexes use another
dimension.

## Run it

```bash
# Notebook through the repository validation harness
uv run setup/run_notebooks.py --labs 8

# Offline tests
uv run --with-requirements 08-neo4j-memory-demo/requirements.txt \
  python 08-neo4j-memory-demo/test_memory_helpers.py

# Live memory/index smoke test
uv run --with-requirements 08-neo4j-memory-demo/requirements.txt \
  python 08-neo4j-memory-demo/smoke_test.py
```

To reset the demo afterward, see [Cleanup](#cleanup) below.

Without Neo4j and AWS credentials the notebook and scripts print clear skip
messages, which keeps repository validation credential-free.

## Cleanup

Each notebook run writes about ten memory records under a fresh run ID, so run
the cleanup script whenever you want to reset the demo:

```bash
uv run --with-requirements 08-neo4j-memory-demo/requirements.txt \
  python 08-neo4j-memory-demo/cleanup_memory.py
```

- **What it removes:** conversations, messages, and users in the `demo08-`
  namespace; the workshop-owned `ABOUT_HOTEL` links; and any orphaned
  preferences tagged `neo4j-ftw-demo-8`. The prefix sweep also catches records
  from a run that failed before its tagging step.
- **What it never touches:** Hotel nodes, the hotel-chunk indexes, and other
  modules' data. The script asserts the Hotel count is unchanged and fails
  loudly if it ever moves. The library-managed memory vector indexes are left
  in place because they are shared infrastructure, cost nothing while empty,
  and the smoke test checks them.
- **What it needs:** live Neo4j credentials only. It uses no AWS access, and it
  prints a skip message and exits 0 when Neo4j is not configured.

## Files

| File | Purpose |
|------|---------|
| `inspectable_memory.ipynb` | Five-step participant story |
| `memory_helpers.py` | Pinned memory client plus actor-scoped read and two relationship writes |
| `smoke_test.py` | Live connection, multi-tenant write, vector-index, and embedding checks |
| `cleanup_memory.py` | Prefix- and owner-scoped memory cleanup; never mutates Hotel nodes |
| `test_memory_helpers.py` | Offline configuration, helper, and cleanup-scope tests |
| `requirements.txt` | Dependencies pinned to `neo4j-agent-memory` 0.5.0 |

## Relationship to Module 7

Module 7 demonstrates managed AgentCore Memory, with asynchronous extraction
and AWS-operated storage. This module demonstrates explicit writes that are
immediately visible in a graph with source provenance and a direct link to the
domain. They are optional alternatives, and neither is required by Module 6.
