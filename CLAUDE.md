# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A joint Neo4j/AWS workshop. The through-line: **Neo4j owns the connected data** and **AWS owns reasoning and hosting**. Neo4j holds the hotel knowledge graph, the retrieval indexes, the production rules, the reservation requests, and the optional memory. AWS supplies Bedrock models and embeddings, AgentCore Runtime and Gateway, Secrets Manager, IAM, Lambda, and CloudWatch. Agents are built with [Strands Agents](https://strandsagents.com); the patterns are framework-agnostic.

The repository is one sequential path of six labs, not a set of independent demos. Each lab consumes what the previous one produced.

| Lab | Folder | What it produces |
|---|---|---|
| 0 | `00-setup/` | A credential checklist plus `verify_setup.py`. No notebook |
| 1 | `01-graph-build/` | The hotel knowledge graph, built live from raw documents by Bedrock extraction against a pinned schema, plus the vector and full-text indexes and the graph fixtures |
| 2 | `02-retrieval/` | Four retrievers over that graph, closing on a question the graph cannot answer |
| 3 | `03-agents-and-tools/` | Strands agents, tools, and lifecycle hooks, ending with one named `hotel_agent` that calls the Lab 2 retriever |
| 4 | `04-grounded-write/` | An idempotent reservation write, with a rule read from the graph rejecting a request the prompt alone would allow |
| 5 | `05-agentcore-deploy/` | The same agent on AgentCore Runtime with the retriever unchanged, then torn down |
| 6 | `06-memory/` | Optional. Graph-native agent memory with provenance and actor isolation |

Only Lab 6 is optional. `2.3_text2cypher.ipynb` and `5.3_agentcore_walkthrough.ipynb` are optional notebooks inside required labs.

Read the root `README.md` for the Platform Responsibilities and Data Ownership tables and the FAQ before making cross-cutting changes. It is the canonical source of truth for what each lab is scoped to include or exclude.

## Repository layout

- Each notebook lab keeps its own `requirements.txt`, its own `.venv`, and its own `test_*.py` files where it has tests. `00-setup/` has no notebook, lab environment, requirements file, or test suite. Its executable is the PEP 723 script `00-setup/verify_setup.py`, run from the repository root with `uv run 00-setup/verify_setup.py`. All seven folder READMEs exist and are current.
- **Labs are no longer self-contained.** Shared code lives in `workshop/`, a src-layout installable package holding ten modules under `workshop/src/workshop/`. Every lab installs it in editable mode: each `requirements.txt` starts with `-e ../workshop`. Do not copy a shared module into a lab folder and do not add a sibling lab folder to `sys.path`; add to or import from the package instead.
- The ten shared modules: `retrieval_contract.py`, `bedrock_providers.py`, `retrieval_setup.py`, `graph_connection.py`, `graph_schema.py`, `contracts.py`, `graph_setup.py`, `hybrid_retrieval.py`, `reservation_command.py`, and `env_file.py`. The five embedding and index constants, `EMBEDDING_MODEL_ID`, `EMBEDDING_PURPOSE`, `EMBEDDING_DIMENSIONS`, `CHUNK_VECTOR_INDEX`, and `CHUNK_FULLTEXT_INDEX`, have exactly one definition in `retrieval_contract.py`. A mismatch between the lab that writes the graph and the labs that read it returns wrong results with no error. `MEMORY_EMBEDDING_MODEL` sits beside them in the same file: Lab 6's memory embeddings are a separate contract on a different model, and the two are never mixed.
- A single repo-root `.env`, copied from `.env.example`, holds the `NEO4J_*` and `AWS_REGION` values every lab reads. A lab-local `.env` takes precedence over the root one if present.
- `setup/` holds repo-wide utilities: `run_notebooks.py` and `provision_agentcore.py`.
- `workshop-delivery/` holds the architecture document and delivery notes.
- Four notebooks in the tree are source material the rebuild drew from, kept for reference and deliberately absent from the runner's registry: `02-retrieval/retrieval_patterns.ipynb`, `04-grounded-write/01_hybrid_retrieval.ipynb`, `workshop-delivery/archive/deploy_agentcore.ipynb`, and `05-agentcore-deploy/advanced-deployment/02_agentcore_walkthrough.ipynb`. Do not edit them to fix a lab; edit the `N.M_*.ipynb` notebook the lab actually ships.
- `backups/` and `logs/` hold historical run logs and design notes. Read for context on prior decisions; treat as append-only history, not living docs.
- `workshop-delivery/internal/` holds the rebuild record: `new-content-plan.md`, the twelve-phase plan whose per-phase Findings record the gotchas that were hit for real, and `new-content.md`, the content brief it was written against. The directory is gitignored, so a fresh clone will not have it. It is facilitator material, never participant material, and no shipped file should link to it.
- `.github/workflows/offline-gate.yml` is the CI gate. It runs the notebook runner with no credentials present and the four per-lab pytest suites, and it asserts each suite's count so the numbers quoted below cannot drift unnoticed.

## Commands

### Per-lab setup and run

```bash
cd 01-graph-build          # or any lab folder
uv venv && uv pip install -r requirements.txt
```

Then open the lab's `N.M_*.ipynb` notebooks in order in any editor with notebook support. Each lab README lists its notebooks and prerequisites.

Lab 1's graph build also has a script form, which is what to use for a long build or a readiness check:

```bash
cd 01-graph-build
uv run prepare_graph.py --check-only              # read-only readiness report
uv run prepare_graph.py --mode lite               # build 30 documents if needed
uv run prepare_graph.py --mode full               # build all 300 if needed
uv run prepare_graph.py --mode lite --rebuild     # discard and rebuild
```

### Notebook validation (the repository's acceptance path)

```bash
uv run setup/run_notebooks.py              # Labs 1 through 4 and 6
uv run setup/run_notebooks.py --labs 2     # one lab
uv run setup/run_notebooks.py --labs 2-4   # a range
uv run setup/run_notebooks.py --list       # show the notebook registry
```

This is a PEP 723 script; `uv` manages its own cached environment, and it installs `workshop` from `../workshop` as an editable source. It executes notebooks into a temp copy, so originals are never modified, and exits nonzero on any cell error. Every live cell self-skips when Neo4j or Bedrock credentials are absent, so the default run is green offline and creates no AWS resources.

Lab 5's three notebooks touch real, billable AWS resources and are gated behind flags:

```bash
uv run setup/run_notebooks.py --labs 5 --include-deploy    # 5.1 and 5.3
uv run setup/run_notebooks.py --labs 5 --include-cleanup   # 5.2
```

A clean run only proves cells did not raise. It does not validate narrative or model-quality claims unless the notebook itself asserts them.

### Tests

Tests are per-lab and run from inside that lab's directory. There is no single top-level test command.

```bash
cd 01-graph-build     && uv run --with pytest --with-requirements requirements.txt -m pytest   # 12 tests
cd 04-grounded-write  && uv run --with pytest --with-requirements requirements.txt -m pytest   # 56 tests
cd 06-memory          && uv run --with pytest --with-requirements requirements.txt -m pytest   # 40 tests
cd 05-agentcore-deploy && uv run --with pytest --with-requirements requirements.txt -m pytest  # 29 tests
```

Lab 5's 29 are 20 in `test_workshop_cleanup.py` plus 9 in `deployment-tools/test_runtime_integration.py`, and a bare `pytest` collects both. That second file used to die on collection with a stale `import contracts` left behind when the module moved into the shared package, which silently disabled all 9. Its imports of `bedrock_agentcore` and `mcp` are not the problem and never were: `05-agentcore-deploy/requirements.txt` declares both so they resolve in the lab venv. If those 9 stop collecting, suspect an import, not a missing dependency.

Labs 2 and 3 have no test files; the notebook runner covers them. `06-memory/smoke_test.py` is a live connection check, run with `uv run --with-requirements requirements.txt python smoke_test.py`. Live tests self-skip when credentials are absent.

### AgentCore provisioning (a real prerequisite for Lab 5)

Labs 1 through 4 never need this and create no AWS resources beyond Bedrock inference calls. Lab 5 requires it: it stands up the Neo4j command secret, three least-privilege IAM roles, the reservation Lambda, and the AgentCore Gateway with its single target, then writes the resulting identifiers into the repo-root `.env` for `5.1_agentcore_deploy.ipynb` to read.

```bash
uv run setup/provision_agentcore.py provision
uv run setup/provision_agentcore.py status
uv run setup/provision_agentcore.py teardown [--yes]
```

Idempotent. This creates real, billable AWS resources; confirm with the user before running `provision` or an unflagged `teardown`.

### Cleanup

Teardown is two halves, tagged differently, and each one leaves the other billing if run alone.

- `05-agentcore-deploy/5.2_teardown.ipynb` and `05-agentcore-deploy/workshop_cleanup.py` delete what `5.1_agentcore_deploy.ipynb` created. Scoped strictly by the tag `WorkshopResource=stop-ai-agent-hallucinations`. An untagged resource under a workshop-looking name is reported as `UNTAGGED_BLOCKED` and the run fails rather than guessing. Never match on a name prefix here: an earlier version matched IAM role names across the account and deleted five roles the workshop never created.
- `setup/provision_agentcore.py teardown` deletes the provisioning half, tagged `demo06-agentcore=true`.

Treat both as destructive and confirm scope with the user before running, especially outside a disposable sandbox account. `05-agentcore-deploy/CLEANUP.md` is the detailed reference.

### Notebook diffs

Notebooks are stripped of output on commit via `nbstripout`, declared as `*.ipynb filter=nbstripout` in `.gitattributes`. If a fresh clone shows huge notebook diffs, the filter likely isn't registered locally. Fix it from the repo root with `uv tool install nbstripout && nbstripout --install`.

## Working conventions specific to this repo

- **Notebooks are named `N.M_name.ipynb`.** Never name a notebook `test_*`: that prefix collides with the Python test files and pytest will try to collect it.
- **Run only one Lab 1 graph build at a time.** Each build clears the graph before it starts, so two overlapping builds wipe each other mid-flight and the document-count assertion fails with a count that keeps changing. On macOS, wrap a long build in `caffeinate -i -s`, because system sleep kills it. Closing the lid still sleeps the machine.
- **Dates in demo code must be computed relative to "now," never hardcoded.** A fixed future date silently rots into the past and flips a rule from passing to failing.
- **The model ID is standardized on `us.anthropic.claude-sonnet-5`,** defined once as `workshop.bedrock_providers.DEFAULT_MODEL_ID`, with `bedrock_providers.default_model_id()` applying a `MODEL_ID` environment override. No non-vendored file should name a different Claude version. A Strands `Agent(...)` built without an explicit `model=` silently falls back to Strands' own default, which is a different Claude version, so every agent in the tree passes one.
- **There is one embedder, `workshop.bedrock_providers.BedrockEmbeddings`.** Lab 1 writes chunk vectors with it and Labs 2 onward embed queries with it. Do not define a second embedder class anywhere; it would agree with this one only by coincidence, and a disagreement returns wrong results with no error.
- **The shared `workshop` package requires Python 3.12+.** `workshop/pyproject.toml` declares `requires-python = ">=3.12"`.
- **`NEO4J_USERNAME` vs `NEO4J_USER`:** every lab reads `NEO4J_USERNAME`. The hosted Workshop Studio CloudFormation environment instead writes `NEO4J_USER`. If auth fails only inside the hosted environment, check for this mismatch first.
- **Live/AWS-touching and Neo4j-touching cells and tests self-skip when credentials are absent.** This is how the default `run_notebooks.py` run passes offline. Preserve that behavior rather than making new cells or tests hard-fail.
- **The retrieval tool and the reservation command have a frozen input/output contract,** now in `workshop/src/workshop/hybrid_retrieval.py` and `workshop/src/workshop/reservation_command.py` and documented in `04-grounded-write/CONTRACTS.md`. Changes that widen it go against the workshop's deliberate scope: extra params, retriever or ranker selection, actor and identity fields, a second write path. Flag before adding any of them.
- **Lab 5's container build context is `05-agentcore-deploy/deployment-tools/`.** `5.1_agentcore_deploy.ipynb` chdirs into it before calling the starter toolkit so the toolkit honors the hand-written `Dockerfile` there. The `workshop` package ships into the image as a wheel built into `deployment-tools/vendor/` at deploy time, pinned by exact filename in `agent_requirements.txt`.
- **Import order is what makes the credential-free notebook path work.** `workshop.graph_connection` raises at import when `NEO4J_URI` or `NEO4J_PASSWORD` is unset, so environment checks use plain `os.environ` and any module that opens a driver is imported inside the guarded branch, not at the top of the notebook.
