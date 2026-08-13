[< Back to Main README](../README.md)

# Lab 1: From text to a knowledge graph

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://python.org)
[![Neo4j](https://img.shields.io/badge/Neo4j-AuraDB-4581C3.svg?style=flat&logo=neo4j)](https://neo4j.com/cloud/aura-free/)
[![neo4j-graphrag](https://img.shields.io/badge/neo4j--graphrag-SimpleKGPipeline-4581C3.svg?style=flat)](https://neo4j.com/docs/neo4j-graphrag-python/current/)
[![Amazon Bedrock](https://img.shields.io/badge/Amazon-Bedrock-FF9900.svg?style=flat&logo=amazon-aws)](https://aws.amazon.com/bedrock/)

Thirty hotel FAQ documents go in as plain text. A typed graph comes out: `Hotel`, `Room`, `Amenity`, `Policy`, and `Service` nodes joined by the four relationships every later lab queries, a `Document` and a `Chunk` per source file, a 1024-dimensional embedding on every chunk, and the two Neo4j indexes retrieval runs against.

There is no ETL step, no staging table, and no separate loader to maintain. The documents are handed to `SimpleKGPipeline`, and Bedrock decides what the entities are while Neo4j stores them in the same call.

**At a Glance**
- **Failure it stops:** an ungrounded graph. A model left to invent labels per document produces `Address` in one file and `Location` in the next, and no query written against that graph can be relied on. The pinned schema is what makes the retrieval contract in Labs 2 through 5 true.
- **Neo4j:** Aura, `SimpleKGPipeline` from `neo4j-graphrag`, the pinned extraction schema, the vector index `hotel_chunk_embeddings`, the full-text index `hotel_chunk_fulltext`, three uniqueness constraints, and APOC.
- **AWS:** Bedrock `us.anthropic.claude-sonnet-5` for entity and relationship extraction, and Amazon Nova 2 Multimodal Embeddings, `amazon.nova-2-multimodal-embeddings-v1:0`, at 1024 dimensions for chunk vectors.
- **You'll build:** the graph the rest of the workshop reads, plus the fixture hotel IDs and the `max_guests` rule Labs 4 and 5 write against.

---

## The notebook

| Notebook | What it does |
|---|---|
| [`1.1_build_graph.ipynb`](1.1_build_graph.ipynb) | Pins the schema, selects the corpus, canaries the extraction, builds the graph, verifies both indexes against the embedding contract, and seeds the Labs 4 and 5 fixtures |

Nine code cells, run top to bottom, in eight numbered steps:

| Step | Cell does | Why it is there |
|:-:|---|---|
| 1 | Reads `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, and the AWS credential chain, and sets `BUILD_READY`, `MODE`, and `REBUILD` | Every module that opens a driver imports `workshop.graph_connection`, which raises at import when `NEO4J_PASSWORD` is unset. So the check reads the environment directly and the connecting cells import their modules later, inside the guard |
| 2 | Renders `GRAPH_SCHEMA` and prints the three `additional_*` flags | The flags are what turn the schema from a suggestion into a rule |
| 3 | `selected_paths(MODE)`, then asserts `missing_source_fixtures(paths)` is empty | Five source documents are load-bearing for later labs. Losing one produces a graph whose questions quietly return nothing |
| 4 | `ensure_retrieval_indexes`, then `report_readiness`, setting `NEEDS_BUILD` | The check that makes the notebook re-runnable. An empty problem list means Lab 2 can already run and there is nothing to rebuild |
| 5 | `await run_build(paths, title)` and asserts the exit code is `0` | The extraction itself: clear, canary, verify, clear, ingest, count, report |
| 6 | `verify_retrieval_indexes`, then asserts `fixture_problems(driver)` is empty | A vector index at the wrong dimension does not raise, it returns the wrong neighbours. The check is against the contract, not against existence |
| 7 | `apply_demo6_graph`, then asserts `readiness_problems` is empty | Seeds the graph-owned data Labs 4 and 5 depend on |
| 8 | Summarises what was built, then closes the driver | The counts in the readiness report above it are the evidence, not the table |

The build is also a command-line script. The notebook is a wrapper around the same `prepare_graph.py` and `graph_builder.py` code, so either path produces the same graph.

---

## The first peak of the partnership

Bedrock extraction and Neo4j storage sit in the same call path. `build_pipeline` in [`graph_builder.py`](graph_builder.py) constructs one object and hands it both:

```python
return SimpleKGPipeline(
    llm=llm,                        # Bedrock: us.anthropic.claude-sonnet-5
    driver=driver,                  # Neo4j: the Aura connection
    embedder=embedder,              # Bedrock: amazon.nova-2-multimodal-embeddings-v1:0
    schema=GRAPH_SCHEMA,
    text_splitter=FixedSizeSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP),
    from_pdf=False,
    perform_entity_resolution=True,
)
```

One `run_async` call per document splits the text, sends each chunk to Claude with the schema attached, writes the extracted nodes and relationships, asks Nova for the chunk embedding, and resolves duplicate entities into single nodes. Nothing sits between the model and the database.

`CHUNK_SIZE` is 12000 with zero overlap, set in [`graph_config.py`](graph_config.py). Source documents top out at roughly 7.4 KB, so a whole hotel lands in one chunk and its name, address, and rating are extracted in the same prompt as its rooms and amenities. That is also why `EXTRACTION_MAX_TOKENS` is 16000: the 4096 default truncates the extraction JSON mid-object and the chunk is dropped.

## The schema is pinned, so extraction cannot invent labels

`SimpleKGPipeline` runs without a schema. It then asks the model to invent labels per chunk. The contract lives in [`workshop/src/workshop/graph_schema.py`](../workshop/src/workshop/graph_schema.py) and ends with the three lines that matter:

```python
"additional_node_types": False,
"additional_relationship_types": False,
"additional_patterns": False,
```

All three are `False`. Anything outside the contract is refused rather than added.

| Node | Properties |
|---|---|
| `Hotel` | `name`, `address`, `guest_rating`, `total_rooms`, `email`, `phone` |
| `Room` | `type`, `bed_configuration`, `max_occupancy`, `min_rate`, `max_rate` |
| `Amenity` | `name`, `description`, `fee` |
| `Policy` | `name`, `description` |
| `Service` | `name`, `description`, `cost`, `hours`, `is_available`, `is_complimentary` |

The four patterns are `Hotel -HAS_ROOM-> Room`, `Hotel -OFFERS_AMENITY-> Amenity`, `Hotel -HAS_POLICY-> Policy`, and `Hotel -PROVIDES_SERVICE-> Service`. `Document` and `Chunk` come from the pipeline itself, not from extraction.

Property names are snake_case throughout, and location lives on `Hotel.address` rather than in its own node, because that is what the Lab 2 traversal and the Lab 4 write are told to expect. `OFF_SCHEMA_LABELS` in the same module lists the eleven labels earlier unpinned runs produced, including `Address`, `Location`, and `RoomType`. Their presence after a build means the schema did not hold, and the canary checks for exactly them.

## The canary: three documents before fifteen minutes

`run_build` in [`graph_builder.py`](graph_builder.py) does not start the full ingest. The order is deliberate:

```
clear -> canary (CANARY_DOCS = 3) -> check the result -> clear -> ingest all -> count -> report
```

`CANARY_DOCS` is 3, not 1. LLM extraction is stochastic, so a single-document gate intermittently fails a healthy pipeline, and a participant who hits that concludes the lab is broken.

`snapshot_chunk_ids` records the `:Chunk` element IDs before the canary and again after, and the difference is what the canary produced. Chunks are the handle rather than a node-level diff because `perform_entity_resolution=True` merges a newly extracted entity into an existing node when one matches, so re-ingesting a document already in the graph creates a `Chunk` and no new `Hotel`. A node diff reads that as "extraction produced no Hotel" when it produced one and deduplicated it. Chunks are never merged.

`check_schema_held` then walks `(:Chunk)<-[:FROM_CHUNK]-(entity)` from those chunks and reports problems:

- any label in `OFF_SCHEMA_LABELS` is a failure, strictly. Inventing an `Address` node is a schema failure, not a bad roll.
- no `:Hotel` at all is a failure.
- at least one canary hotel must have `name`, `address`, `guest_rating`, and one contracted relationship. The gate is "at least one", not "every one", because a model can miss a field on any single document without the pipeline being broken.

Either failure path calls `clear_demo_graph` and returns a non-zero exit code, so the graph is left empty rather than half-populated. A graph that is wrong in that way looks plausible right up until Lab 2 asks it a question.

The canary's own documents are then cleared before the full ingest, so entity resolution has nothing left over to merge into and the counts at the end are exactly what the full run produced.

## Run it once, alone, and let it finish

`clear_demo_graph` deletes every node carrying the `__KGBuilder__` label, which is what `neo4j-graphrag` writes, so the wipe is scoped to this lab's own output instead of `MATCH (n) DETACH DELETE n`. Because the build clears before it starts, re-running is safe.

**Two overlapping builds corrupt each other.** Each one's clear step deletes the other's work in flight, and what survives is a graph with a plausible shape and the wrong contents. This is a real failure from development, not a theoretical one. Start one build, on one machine, and let it finish before starting another.

**On macOS, a laptop that sleeps mid-build kills it.** Also a real failure from development. Keep the machine awake for the whole run:

```bash
caffeinate -i uv run prepare_graph.py --mode lite
```

`caffeinate -i` prevents idle sleep for as long as the command it wraps is running. Closing the lid still sleeps the machine, so leave it open. When running the notebook rather than the script, start `caffeinate -i -t 3600` in a separate terminal before the build cell and let it expire on its own.

The build asserts its own completeness rather than trusting the run. `count_documents` and `count_chunks` compare against the number of selected source files, and a mismatch prints the reason and exits non-zero:

```
❌ Document or chunk count does not match the selected source files. That means a
build was incomplete, another build overlapped this one, or a partial run was
left behind.
```

`report_readiness` reports the same mismatch as `document count is N, expected M`. That assertion firing is the safety net doing its job. The fix is one clean re-run, alone.

Individual ingest errors are handled separately and are less serious. `ingest` catches a timeout or an exception per document so one bad document cannot stop the build, and `DOC_TIMEOUT_SECONDS` is 180, set above the worst case of the Bedrock retry chain. If acknowledgements were lost but every source still has a committed `Document` and `Chunk`, the build prints a warning and continues to fixture validation.

## The corpus selection is stratified, not alphabetical

The lite build is 30 documents out of 300, and it is not the first 30 filenames. Lab 2 asks about Paris and Cairo by name, and an alphabetical cut stops at Boston. `select_lite_files` in [`graph_config.py`](graph_config.py) takes every Paris and Cairo document first, then fills the remainder round-robin across the other cities so the sample still spans the corpus.

Five documents are load-bearing for later labs, listed as `DEMO_CRITICAL_SOURCE_FILES` in [`workshop/src/workshop/retrieval_setup.py`](../workshop/src/workshop/retrieval_setup.py): `hotel-paris-001.txt`, `hotel-paris-002.txt`, `hotel-cairo-001.txt`, `hotel-cairo-002.txt`, and `hotel-chicago-001.txt`. `missing_source_fixtures` checks for them before any Bedrock call is made, and the build refuses to start if one is absent.

`fixture_problems` checks the graph facts the later labs actually ask for: at least two Paris hotels with a rating, a hotel connected to a pool amenity, a Cairo hotel with both spa and pool, the Windward Mile Tower hotel at postal code `60611`, and an embedded chunk containing both that name and that postal code at the contracted dimension. That last one is what Lab 2's full-text comparison depends on.

## The indexes are created here and verified against a contract

`ensure_retrieval_indexes` creates both indexes idempotently with `fail_if_exists=False`, calls `db.awaitIndexes` with a 300-second timeout, then calls `verify_retrieval_indexes`, which raises unless both match:

| | `hotel_chunk_embeddings` | `hotel_chunk_fulltext` |
|---|---|---|
| Type | `VECTOR` | `FULLTEXT` |
| Target | `:Chunk(embedding)` | `:Chunk(text)` |
| State | `ONLINE` | `ONLINE` |
| Dimensions | 1024 | not applicable |
| Similarity | cosine | not applicable |

The names and the embedding settings come from `workshop.retrieval_contract`, which is the single definition Lab 2 also imports. A dimension or similarity mismatch does not raise at query time, it returns confident wrong neighbours, which is why it is checked here at build time instead.

## Seeding the fixtures Labs 4 and 5 depend on

Extraction gives each hotel a name and an address, which is enough to retrieve against. It does not give them a stable identifier, and the reservation write in Lab 4 needs one. An agent that books against a hotel found by name books against whatever the model spelled that day.

Step 7 calls `apply_demo6_graph` from [`workshop/src/workshop/graph_setup.py`](../workshop/src/workshop/graph_setup.py). This is graph-owned data rather than extracted data, and it is `MERGE` and `SET` throughout, so running it twice changes nothing:

- **Three uniqueness constraints:** `demo06_fixture_hotel_id` on `Hotel.hotel_id`, `demo06_reservation_request_id` on `ReservationRequest.request_id`, and `demo06_rule_id` on `Rule.rule_id`.
- **The fixture hotel IDs.** `load_manifest` reads the committed filename-to-UUID mapping at `workshop/src/workshop/fixtures/hotel_ids.json`, validates that each ID is an opaque UUID and that the manifest holds exactly the two Cairo fixtures, then resolves each source filename through `Document -> Chunk -> Hotel` and stamps the ID onto the matching hotel. One of the two is the hero hotel, `AnyCompany Cairo Nile View`.
- **The `max_guests` rule.** A single `:Rule` node with `rule_type` `MAXIMUM_GUESTS`, `max_guests` from `contracts.MAX_GUESTS`, `enabled` true, and both a rejection message and a steering message. Lab 4 reads this node inside the write transaction and rejects a request the prompt alone would have allowed.

`apply_demo6_graph` returns blocking problems rather than raising, and `readiness_problems` re-checks everything without writing: the two indexes, the three constraints, the fixture resolution with IDs required, the hero hotel's name, address, rating of 4.5 and expected amenity terms, and the rule's field values. Both are asserted empty in the notebook. Skip this step and Lab 4 opens onto an unprepared graph.

## Nothing ships pre-embedded

Only the raw corpus, `hotel-faqs.zip`, is checked into git. `data/` is gitignored and the graph is a build artifact every participant generates. The extraction runs against their own Aura instance with their own Bedrock credentials, so what they take into Lab 2 is what their models actually produced. The same 30 documents run twice produce slightly different extractions, which is the honest starting point for the rest of the workshop.

| Build | Documents | Time |
|---|:-:|---|
| Lite, the workshop default | 30 | about 15 minutes |
| Full | 300 | about 2 hours |

At an AWS event the Code Editor instance pre-extracts the zip so participants skip a download. The extraction and embedding still run live.

---

## Quick Start

### Prerequisites

- [Python](https://python.org/downloads) 3.12+. The shared package this lab installs declares `requires-python = ">=3.12"` in [`workshop/pyproject.toml`](../workshop/pyproject.toml), so `-e ../workshop` refuses to install on anything older.
- [uv](https://docs.astral.sh/uv/) package manager.
- The repo-root `.env` filled in with `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, and `AWS_REGION`, per [`00-setup/README.md`](../00-setup/README.md).
- **APOC enabled** on the Aura instance. `neo4j-graphrag` uses it during the build.
- **Bedrock model access for both models** in `AWS_REGION`: `us.anthropic.claude-sonnet-5` for extraction and `amazon.nova-2-multimodal-embeddings-v1:0` for embeddings. Enabling one and not the other fails part way through the build.

This lab creates no AWS resources. It makes Bedrock inference calls and nothing else.

### Install

```bash
cd 01-graph-build
uv venv && uv pip install -r requirements.txt
```

`requirements.txt` is two lines: `-e ../workshop` brings the shared package along with `boto3`, `neo4j`, `neo4j-graphrag`, and `python-dotenv`, plus `numpy`.

### Extract the corpus

```bash
cd 01-graph-build
unzip -q -o hotel-faqs.zip -d data/
```

That writes 300 `hotel-<city>-<nnn>.txt` files into `data/`, which is where both the notebook and the scripts look. Skip this at an AWS event; the files are already there.

### Run

Open `1.1_build_graph.ipynb` in VS Code, Kiro, or any editor with notebook support, and run the cells in order. Keep the machine awake for the build cell.

`MODE` in step 1 is `"lite"`. Change it to `"full"` for all 300 documents. `REBUILD` is `False`, which means a graph that already reports ready is verified rather than rebuilt.

The command-line equivalent, which is what the notebook wraps:

```bash
cd 01-graph-build
uv run prepare_graph.py --check-only              # read-only readiness report
uv run prepare_graph.py --mode lite               # build 30 documents if needed
uv run prepare_graph.py --mode full               # build all 300 if needed
uv run prepare_graph.py --mode lite --rebuild     # discard and rebuild
```

`prepare_graph.py` is idempotent. Without `--rebuild` it creates any missing indexes, reports readiness, and skips extraction when the graph is already complete. `build_graph_lite.py` and `build_graph.py` are the plain unconditional builds behind it, always rebuilding their respective corpus.

### Tests

```bash
cd 01-graph-build
uv run --with pytest --with-requirements requirements.txt -m pytest
```

**12 tests and 2 subtests**, all offline. No Neo4j instance, no AWS credentials, and no network:

| File | Tests | What it pins |
|---|:-:|---|
| `test_bedrock_providers.py` | 5 | Conversation history is passed to Bedrock with roles and content intact, `ainvoke` times out instead of hanging, both clients apply `BEDROCK_CONFIG`, and the worst-case retry chain fits inside `DOC_TIMEOUT_SECONDS` |
| `test_retrieval_setup.py` | 6 | The lite sample contains every demo-critical source, a missing source is reported by filename, and the index contract accepts the expected indexes while failing clearly on a missing full-text index or wrong vector dimensions |
| `test_graph_builder_metadata.py` | 1 | `ingest` passes `source_filename` through as document metadata, which is what `graph_setup.py` resolves fixture hotels by |

The notebook is also registered with the shared runner, and `uv run setup/run_notebooks.py --list` from the repository root shows it. Executing Lab 1 through the runner performs a real build against a real graph and takes as long as the build does, so treat it the same as running the notebook: once, alone, on a machine that stays awake.

---

## Troubleshooting

**The canary failed.** The output names the problem before it clears the graph. `off-schema labels present: ['Address']` means the schema was not honoured; confirm the notebook printed `False` for all three `additional_*` flags and that nothing local overrides `GRAPH_SCHEMA`. `none of the N canary hotels had name, address, guest_rating and a contracted relationship` is usually a truncated extraction: check `EXTRACTION_MAX_TOKENS` is still 16000 and that the extraction model has not been swapped for a smaller one. Either way the graph is left empty, so a re-run starts clean.

**`Canary produced no :Chunk — extraction did not run.`** No chunk was written at all, so the failure is upstream of the schema. Check the per-document lines above it: `⏰ timeout` on all three points at Bedrock throttling or a region mismatch, and `❌ <message>` carries the underlying error. Confirm `AWS_REGION` matches the region where both models are enabled, and that the Aura instance is running rather than paused.

**Document or chunk counts do not match.** The assertion is correct and the graph is wrong. Two builds overlapped, or a previous build was interrupted and left nodes behind. Run one build, alone, and let it finish. `uv run prepare_graph.py --mode lite --rebuild` clears and rebuilds from scratch. Confirm no second notebook kernel or terminal is still running a build against the same instance before starting.

**The machine slept and the build stopped part way.** Re-run it, wrapped this time:

```bash
cd 01-graph-build
caffeinate -i uv run prepare_graph.py --mode lite --rebuild
```

`--rebuild` is what discards the partial graph. Without it, the readiness check may report the graph as merely incomplete and the counts will not line up. Leave the lid open; `caffeinate -i` blocks idle sleep, not lid-close sleep.

**Bedrock access denied.** Two models have to be enabled, and the error names only the one that was called. Enable both `us.anthropic.claude-sonnet-5` and `amazon.nova-2-multimodal-embeddings-v1:0` in the [Bedrock Model Access console](https://console.aws.amazon.com/bedrock/home#/modelaccess), in the region `AWS_REGION` names. An extraction failure on every document points at the Claude model; extraction succeeding while chunks end up with no embedding points at Nova.

**APOC is missing.** `neo4j-graphrag` calls APOC procedures during the build, and a missing procedure surfaces as `Unknown procedure` or `There is no procedure with the name apoc...` on every document. Enable the APOC plugin from the Aura instance settings and wait for the instance to restart, then re-run.

**`Retrieval index check failed:`** followed by one line per problem. `missing index 'hotel_chunk_embeddings'` after a build that reported success means index creation was interrupted; re-run the notebook, which is idempotent and recreates them. `has 384 dimensions, expected 1024` means the graph was built with a different embedding model. Do not edit the constants to match the index: the vectors themselves are wrong for the retrieval contract, so rebuild with `workshop.retrieval_contract` unmodified.

**`the graph is not ready for Lab 4`.** Step 7's assertion. The message names each problem. `missing constraint demo06_rule_id` or `maximum-guests rule is missing` means step 7 did not complete; re-run that cell, which is a `MERGE` and safe to repeat. `<file> resolves to 0 documents, expected 1` means the build did not record `Document.source_filename` for a fixture file, which requires a rebuild rather than a re-run of step 7. `hero hotel rating is None` means extraction missed a field on `hotel-cairo-001.txt`; rebuild, since extraction is stochastic and a second pass usually catches it.

**Cells print "Skipping" and nothing runs.** `NEO4J_URI`, `NEO4J_USERNAME`, or `NEO4J_PASSWORD` is unset, or no AWS credentials were found. Step 1 names which. The hosted Workshop Studio environment writes `NEO4J_USER` while every lab reads `NEO4J_USERNAME`; check that first if authentication fails only there.

**`No source documents found in .../data`.** The corpus is not extracted. Run `unzip -q -o hotel-faqs.zip -d data/` from this directory. Run the notebook and the scripts from `01-graph-build/`, since `DATA_DIR` is the relative path `data`.

---

## What's next

**[Lab 2: Retrieval, with and without the graph](../02-retrieval/)** runs four retrievers in pairs against the graph you just built, on the same questions with the same embedding, then closes on a question the graph cannot answer. The RAG-versus-GraphRAG comparison lives there, in `2.1_vector_retrievers.ipynb`, where both sides run against this one graph.

- **Previous:** [Lab 0: Setup](../00-setup/)

---

## Contributing

Contributions are welcome. See [CONTRIBUTING](../CONTRIBUTING.md) for more information.

## Security

If you discover a potential security issue in this project, notify AWS/Amazon Security via the [vulnerability reporting page](https://aws.amazon.com/security/vulnerability-reporting/). Please do **not** create a public GitHub issue.

## License

This library is licensed under the MIT-0 License. See the [LICENSE](../LICENSE) file for details.

> Last updated: August 2026 | Python 3.12+ | Amazon Bedrock | Neo4j AuraDB
