# Implementation Plan: Six-Lab Workshop Rebuild

Execution plan for `new-content.md`. That document is the specification. This one is the order of operations, the checklist, and the parallelization map.

## Proposal

Today the repository is eleven independent demos, each owning one hallucination category, each with its own virtual environment and its own copy of shared code. The workshop that results runs long and repeats itself. This rebuild turns those demos into one sequence of six labs that fit a four-hour delivery: build a graph, retrieve from it, put an agent in front of it, let the agent write, deploy the agent, and finish with optional memory.

Five demo folders are deleted outright. The rest are renamed and renumbered to match lab numbers, and the code that more than one lab needs moves into a single shared package instead of being copied.

### Removed

- Semantic tool selection, all of `02-semantic-tools-demo`.
- The multi-agent swarm, `03-multiagent-demo`.
- Neurosymbolic hooks as a standalone lab, `04-neurosymbolic-demo`. The guest-limit rule survives inside Lab 4.
- Agent Control steering, `05-steering-demo`.
- Managed AgentCore memory, `07-agentcore-memory-demo`.
- MCP and controlled Text2Cypher, `09-neo4j-mcp-demo`.
- The FAISS build path in `01-graphrag-demo`, along with the index and document JSON it produces. Both are gitignored build output rather than checked-in files.
- `01-graphrag-demo/travel_agent_demo.py` and `01-graphrag-demo/tools/graph_tool.py`, a standalone graph-backed agent demo superseded by Lab 3. `graph_tool.py` has no importer besides `travel_agent_demo.py`, and the only surviving reference to either is `01-graphrag-demo/README.md`, which is being rewritten.
- `10-cleanup` as a standalone module. The teardown code survives as `5.2_teardown.ipynb` inside Lab 5.

### Fixed

- Folder names no longer match lab numbers. They will.
- Five constants are defined twice, verbatim, in `01-graphrag-demo/retrieval_contract.py:5-9` and `06-agentcore-boto3-demo/contracts.py:13-17`: `EMBEDDING_MODEL_ID`, `EMBEDDING_PURPOSE`, `EMBEDDING_DIMENSIONS`, `CHUNK_VECTOR_INDEX`, and `CHUNK_FULLTEXT_INDEX`. All five have to agree for Lab 2 to read the graph Lab 1 built, and a mismatch in the three embedding constants returns wrong results rather than an error. One definition survives.
- Lab 2's notebook resolves four of its imports only by sitting in Lab 1's folder. `retrieval_patterns.ipynb` does `from bedrock_providers import ...`, `from graph_config import ...`, `from retrieval_contract import ...`, and `from retrieval_setup import ...`, all four of which live in `01-graphrag-demo/`. The rename puts them in a sibling folder with no import path. The shared package has to cover the Lab 1 side, not just Demo 06's four modules.
- One venv per demo assumed demos ran in any order. The labs now share a graph, a contract, a retriever, an embedder, and a schema, so a shared package replaces the copies.
- A stranded `01-graphrag-demo/.env` exists and is gitignored, so `git mv` cannot see it.
- Abstention currently reads as a co-equal topic with the four retrievers. It becomes one closing section of one notebook.
- A guest-limit consistency test asserts agreement across three demos, two of which are being deleted.

### Added

- A notebook wrapper around the graph build, which is command-line only today.
- A retrieval notebook that puts `HybridRetriever` and `HybridCypherRetriever` side by side for the first time.
- A reservation-write notebook over the existing command, contracts, and fixtures.
- A closing section in the Strands primer that assembles one named `hotel_agent`, which is what Lab 4 extends.
- A shared `workshop/` package of nine modules, drawn from both `01-graphrag-demo/` and `06-agentcore-boto3-demo/`.
- A teardown notebook inside Lab 5, where the billable resources are created.
- A timing probe ahead of the content work, so the four-hour budget is sized before anything is authored.

### Deliberately not doing

- **Not collapsing the retrieval pairs.** All four retrievers stay in Lab 2. Cutting to two would save more time than the abstention trim did, and it was considered and rejected.
- **Not renumbering to five labs.** Lab 3 is now a single reused notebook, so folding the primer into Lab 4 is arguable. It stays a separate lab. Revisit only if the rehearsal in Phase 11 comes in over budget.
- **Not changing the reservation command's behavior.** Its input and output shape is a frozen contract covered by 29 tests across `test_reservation_command.py` and `test_contracts.py`. The write notebook wraps it, and nothing widens it. The often-quoted 54 is every test in Demo 06, including graph setup and retrieval.
- **Not rebuilding the AgentCore Gateway, Lambda, or IAM roles.** The provisioning script already creates them. Lab 5 launches the Runtime and nothing more.
- **Not adding abstention technique material.** No refusal prompt patterns, no confidence thresholds, no score cutoffs.
- **Not preserving the deleted demos anywhere in the tree.** Git history holds them, and that is enough.

### Decisions

- **Abstention narrows to three cells at the end of Lab 2's second notebook, using the availability question only.** The out-of-domain Antarctica case is dropped because it needs its own setup and a plain vector index handles an off-corpus query badly too, which makes it the easy version. A separate `2.4` notebook is dropped for the same budget reason. Rejected alternative: cutting abstention entirely, since the workshop is named for stopping hallucinations and this is the only place a participant watches a model decline to answer.
- **Semantic tool selection is dropped in full.** The four-hour budget is the reason. The recorded cost is that wrong tool selection loses its live demonstration, the graph never shapes the agent's control flow, and the workshop never shows a second graph in the same Aura instance.
- **The rename lands as pure moves in one commit with no content edits mixed in.** File history survives and the follow-up content commits stay reviewable.
- **A shared package replaces per-demo copies.** Rejected alternative: copying the four shared modules into three lab folders, which guarantees drift and has already started.
- **Deletion happens before the rename.** Renaming folders that are about to be deleted is wasted motion, and the reference repairs are simpler against one change at a time.
- **Teardown is its own notebook, `5.2_teardown.ipynb`, not a closing section of the deploy notebook.** The acceptance runner gates per notebook, not per section: `deploys_resources` and `deletes_resources` are `NotebookSpec` fields checked at `setup/run_notebooks.py:369-372`. A section cannot hold a gate, and putting both flags on one notebook makes `--labs 5 --include-deploy` a silent no-op. Teardown still lives in the Lab 5 folder, so the narrative goal holds. It also keeps a failed deploy recoverable, since teardown runs without re-running the deploy above it. The optional walkthrough becomes `5.3`.
- **`4.1` carries forward cells 10 through 15 of `01_hybrid_retrieval.ipynb` and wraps them in the Lab 3 `hotel_agent`.** Three of Lab 4's four cases already exist as working, tested cells: the 15-guest rejection at 10-11, the valid write and safe retry at 12-13, and the graph inspection at 14-15. The range stops at 15. Cell 16 is a "Where this goes next" markdown pointing at Demo 01b, a framing this rebuild deletes. Only the unknown-hotel rejection is new authoring. Rejected alternatives: reusing the cells unchanged, which leaves the lab reading as a script calling a function rather than an agent being trusted with an action, and authoring fresh, which discards tested cells to rewrite them.
- **The Strands primer keeps its guest-limit hook, framed as the fixture version.** `getting_started_strands.ipynb` cells 14-16 already teach Lab 4's headline rejection case from a Python constant. Lab 4 opens by pointing back at it: the hook worked, and a hardcoded `10` in Python is still the wrong home for a business rule. The repetition becomes the argument. Rejected alternative: cutting the hook and replacing it with a logging or timing example, which costs the primer its most legible hook and creates work.
- **Lab 3 closes with a new sixth section that assembles one named `hotel_agent`.** The primer is not one agent with three tools, which is how the earlier draft of this plan read it. It is five sections with separate agents: cell 7 builds a three-tool agent, cells 14-16 build a hook-guarded pair, cells 18-20 build a `Swarm` whose `lookup_hotel` validator is not a tool of any standalone agent. So "add `create_reservation_request` to the Lab 3 agent" had no referent. The five teaching sections stay unchanged and a new closing section builds `hotel_agent` with the Lab 2 retriever tool and the hook-guarded booking tool. That costs roughly three new cells in Phase 6 and gives Phase 7 something specific to extend. Rejected alternatives: leaving the primer literally as-is and having Lab 4 construct its own agent, which makes the fixture-versus-graph contrast stated rather than demonstrated, and promoting the swarm's validator into the assembled agent, which drags the swarm's framing along with it.
- **The retriever replaces `get_weather` in the primer's section 3 toolset,** not `search_hotels` or `book_hotel`. Weather is the one tool of the three that leaves the hotel domain, and the other two are what sections 4 and 6 build on.
- **The shared package is nine modules, and `graph_config.py` splits.** Phase 3's earlier four-module list covered only Demo 06 and left Lab 2 unable to import its embedder, its connection helper, its schema, or its verification functions. The package takes `retrieval_contract.py`, `bedrock_providers.py`, and `retrieval_setup.py` whole, plus `graph_connection.py` and `graph_schema.py` split out of `graph_config.py`, plus Demo 06's `contracts.py`, `graph_setup.py`, `hybrid_retrieval.py`, and `reservation_command.py`. The build-only remainder of `graph_config.py` stays in `01-graph-build/`, since only Lab 1 reads corpus selection and chunk sizes. `SCHEMA_NODE_LABELS` has to travel with the schema because `retrieval_setup.py:18-23` imports it. Rejected alternative: moving `graph_config.py` whole, which is a smaller diff but puts lite-versus-full corpus selection inside a package the Lambda installs.
- **`retrieval_contract.py` moves into the package as the constants survivor.** It is the natural survivor because `graph_config.py:27-33` already re-exports all five from it, but it cannot survive outside `workshop/` while `workshop/contracts.py` imports it. `contracts.py` itself is not deleted: it holds nine more constants, including `HYBRID_RANKER`, `MAX_GUESTS`, and `WORKSHOP_OWNER`. Only its five duplicate definitions go, replaced by an import.
- **`5.1` is authored fresh, lifting four cells from the restored notebook: 24, 25, 26, and 27.** That is the pre-flight toolkit cleanup at 24, the `Runtime.configure` and `Runtime.launch` pair at 25, and the tagging header and tagging code at 26-27. The range stops at 27; cell 28 is the "Step 9: Test the Agent" markdown belonging to the section `5.1` replaces. The deploy mechanism is intact and the deploy target changed, but the mechanism is four cells out of 43. Retargeting means deleting roughly 28 cells and inheriting DynamoDB-shaped recovery scaffolding at cell 5, a "Module 6 Deployment Complete" banner at cell 40, and "Save Variables for Module 7" at cells 41-42. Writing about 15 fresh cells around 4 copied ones is less error-prone. The restored notebook stays in the working tree as the reference while authoring.
- **The Lambda deployment package installs the `workshop` package rather than flat-copying two files.** `setup/provision_agentcore.py:63` currently declares `SHARED_MODULES = ("reservation_command.py", "contracts.py")` and copies them into the zip root, and the handler does `from reservation_command import handler`. Once those modules live in `workshop/`, a flat copy means the same file resolves its imports differently depending on where it is unzipped. The build directory gets `pip install .` of the shared package instead, which is the standard Lambda packaging path and removes the hardcoded module list. Rejected alternative: relative imports inside `workshop/` plus an updated flat-copy list, which leaves a second, path-dependent way to load the same modules and breaks at runtime the first time `reservation_command.py` grows a dependency.
- **Lab 2's three notebooks duplicate the setup cells that teach and import the constants that must match.** The graph-verification and schema-display cells appear in all three, because watching them run tells a participant whether Lab 1 succeeded. The embedder is constructed from `workshop`, because the three embedding constants must match what Lab 1 wrote to the graph and a mismatch returns wrong results silently. Two duplicated cells instead of four. Rejected alternatives: duplicating all four, which re-creates the exact drift this rebuild is fixing, and a single `connect_and_verify()` helper, which hides the verification cell.
- **Phase 2 registers all seven lab entries at once, including paths that do not exist yet.** The registry is a merge-conflict hotspot precisely because five lanes each append to the same tuple, and the deploy gate currently has no owner at all. Registering labs 0 through 6 up front, with a deploy-gated `5.1` and a cleanup-gated `5.2`, makes the registry read-mostly for every lane. This needs no runner change: `setup/run_notebooks.py:373-374` already records `"notebook file not found"` as a skip reason, and `:505` returns nonzero only on `FAIL`, so a registered-but-unwritten notebook already prints a clear message and passes.
- **`travel_agent_demo.py` and `tools/graph_tool.py` are deleted, and the rest of `01-graphrag-demo` is claimed explicitly.** The spec's "Built from" row named five items for a folder holding sixteen, which orphans files silently. `build_graph.py`, `build_graph_lite.py`, `images/`, `test_retrieval_setup.py`, and `test_graph_builder_metadata.py` all move to `01-graph-build/`. The standalone travel agent goes: Lab 3 supersedes it, and nothing but a README being rewritten references it. Rejected alternative: moving everything unclaimed and deciding later, which leaves a second agent demo competing with Lab 3 inside the graph-build folder.
- **The guest-consistency test is narrowed in Phase 1 and extended in Phase 7.** Phase 1 rewrites it to assert that `contracts.py` and `graph_setup.py` agree on the limit, so it never goes red and never disappears. Phase 7 adds a second assertion against the seeded `Rule` node, self-skipping when credentials are absent. Rejected alternatives: deleting it in Phase 1 and betting on Phase 7 to restore it, and stopping at source-file comparison, which cannot catch the failure that matters, where `contracts.py` says 10 and the `Rule` node in the participant's graph says something else.
- **No notebook is named `test_*`.** Every notebook in the new tree is `N.M_<topic>.ipynb`. The `test_` prefix means "pytest collects this" everywhere else in the repository, and `01-graphrag-demo/` currently puts `test_graphrag.ipynb` in the same directory as `test_bedrock_providers.py`, so the prefix is doing two contradictory jobs in one folder. The three `test_graphrag*.ipynb` files go in Phase 1 and nothing takes the prefix back. Phase 10 checks the surviving notebook names as part of the documentation pass. Rejected alternative: keeping the prefix and teaching the distinction in a README, which spends a paragraph on a problem a naming rule removes.
- **A timing probe runs before Phase 4, scoped to the two unknowns.** Time `retrieval_patterns.ipynb` and one full deploy-and-teardown cycle, and nothing else. Lab 1's lite build is a confirmed 15 minutes and Labs 3, 4, and 6 are small enough to estimate. This buys the Lab 2 and Lab 5 budgets for about an hour of wall clock, early enough to know whether `2.3` and the retriever pairs are affordable. Rejected alternatives: measuring only at Phase 11, when every fallback means unwinding merged work, and a four-notebook probe, which turns a cheap check into its own phase and invites skipping.

### Where to look

- The graph build path and the pinned schema live in `01-graphrag-demo`, in `graph_config.py`, `graph_builder.py`, and `prepare_graph.py`.
- The Lab 1 modules Lab 2 silently depends on are `bedrock_providers.py`, `retrieval_contract.py`, and `retrieval_setup.py`, all at the root of `01-graphrag-demo`. `retrieval_patterns.ipynb` cell 2 is where all four import lines are visible at once.
- Retrieval patterns live in `01-graphrag-demo/retrieval_patterns.ipynb` and `06-agentcore-boto3-demo/01_hybrid_retrieval.ipynb`.
- The write path, its contracts, and its fixtures live at the root of `06-agentcore-boto3-demo`.
- Deployment lives in `06-agentcore-boto3-demo/deploy_agentcore.ipynb`, `deployment-tools/`, and `setup/provision_agentcore.py`.
- The notebook acceptance runner is `setup/run_notebooks.py`, and its registry is the file every lane will touch.
- Teardown scope lives in `10-cleanup/workshop_cleanup.py`, including a list of config-file paths that name two demo folders.

### Done when

- [ ] The tree contains `00-setup/` through `06-memory/` and nothing else numbered.
- [ ] No notebook anywhere in the tree is named `test_*`. Every one is `N.M_<topic>.ipynb`.
- [ ] `uv run setup/run_notebooks.py` passes end to end with labs 0 through 6 registered.
- [ ] All nine shared modules have exactly one definition, imported rather than path-hacked, including inside the Lambda deployment package. No notebook resolves an import by virtue of the directory it sits in.
- [ ] A participant can run Labs 1 through 4 with only an Aura instance and Bedrock access.
- [ ] `5.1` deploys and answers four smoke questions, and `5.2` tears down with nothing left running. Each runs behind its own gate.
- [ ] A rehearsed run of Labs 1 through 5 fits four hours with the graph build on the lite corpus, against a budget the Phase 0 probe already predicted.

## Plan

### Goal

Turn eleven demos into six labs that deliver in four hours, without losing the grounded-retrieval-to-production through-line or breaking the frozen write contract.

### Assumptions

- An Aura instance and Bedrock model access are available to whoever runs each phase.
- The lite corpus of 30 documents is what rehearsals and validation use. The full corpus of 300 takes two hours and is a delivery-day choice, not a development one.
- `nbstripout` is registered locally, so notebook diffs stay reviewable.
- Six labs, per the decision above.

### Risks

- **The four-hour fit is estimated in Phase 0 and proven in Phase 11.** Phase 0 measures the two labs whose duration is large and unmeasured, so the risk is sized before any content is authored. If Phase 11 still misses, the fallbacks in order are dropping Lab 2's optional Text2Cypher notebook, folding Lab 3 into Lab 4, then collapsing the retrieval pairs.
- **Lab 5 creates billable AWS resources.** Every rehearsal has to end in a teardown, and untagged toolkit resources are refused by the cleanup script rather than deleted. Teardown being its own gated notebook is what makes running it independently possible.
- **The notebook registry is a merge-conflict hotspot.** Phase 2 registers all seven entries up front to defuse this, which leaves each lane editing one path string rather than appending to the tuple.
- **One Aura instance shared across parallel lanes will collide.** Two lanes rebuilding the same graph will interfere.
- **`5.1` authored fresh loses the safety of a known-working notebook.** The four copied Runtime cells are the part that matters, and they come across unchanged. The risk is in what the restored notebook did implicitly around them, so keep it open side by side while authoring.
- **Phase 3 is larger than the spine's other two phases and every lane blocks on it.** Nine modules move, one splits, and four notebook import blocks change. It is also the phase whose failure surfaces latest, at Lambda runtime in Phase 8. Budget it accordingly and do not let a lane start against a half-migrated package.

---

### Phase 0: Timing probe

**Status.** Pending

**Outcome.** The Lab 2 and Lab 5 time budgets are known before any content is authored, so a scope cut is cheap if one is needed.

- [ ] Time a full run of `01-graphrag-demo/retrieval_patterns.ipynb` against a prepared graph, recording per-pattern time so the 2.1, 2.2, 2.3 split can be costed separately.
- [ ] Time one full `provision_agentcore.py provision`, deploy, smoke test, and teardown cycle end to end.
- [ ] Record both numbers, plus the confirmed 15-minute lite graph build, as the starting per-lab budget.
- [ ] Estimate Labs 3, 4, and 6 from cell counts rather than measuring them.
- [ ] If the two measured numbers plus the estimates already exceed four hours, apply the first fallback before Phase 5 authors `2.3`.

**Validation.** A written per-lab budget with two measured entries and four estimated ones, and a stated verdict on whether `2.3` and the four retriever pairs survive.

**Note.** This phase touches no files, so it runs concurrently with the serial spine below rather than blocking it.

---

### Phase 1: Prune

**Status.** Done. Six demo folders, the FAISS path, the three `test_graphrag*.ipynb` files, and the travel agent are deleted. The guest-consistency test is narrowed and passing. Two findings are recorded below the checklist.

**Outcome.** The tree holds only what the six labs need, and the acceptance runner passes on what remains.

- [x] Delete `02-semantic-tools-demo`, `03-multiagent-demo`, `04-neurosymbolic-demo`, `05-steering-demo`, `07-agentcore-memory-demo`, and `09-neo4j-mcp-demo`.
- [x] Delete the FAISS build path from `01-graphrag-demo`: `load_vector_data.py`, `load_vector_data_lite.py`, `faqs_docs.json` (2.2 MB), and `faqs_vector.index` (1.2 MB). Also dropped `faiss-cpu` from `01-graphrag-demo/requirements.txt` and from the runner's PEP 723 dependency block, along with `agent-control-sdk` and `mcp`, which only Demos 05 and 09 used.
- [x] Delete `01-graphrag-demo/test_graphrag.ipynb`, `test_graphrag-executed.ipynb`, and `test_graphrag-executed-lite.ipynb`. Lab 2's vector notebook replaces their role as the motivating demo, and it does not inherit the `test_` prefix.
- [x] Delete `01-graphrag-demo/travel_agent_demo.py` and `01-graphrag-demo/tools/`. Confirm first that `graph_tool.py` still has no importer outside `travel_agent_demo.py`, and that the only surviving references are in READMEs being rewritten. Confirmed: its only importers were `02-semantic-tools-demo/enhanced_tools.py`, `02-semantic-tools-demo/tool_graph.py`, and a code block in `03-multiagent-demo/README.md`, all three deleted in this phase.
- [x] Narrow `06-agentcore-boto3-demo/test_demo_guest_consistency.py` in place. Its single test currently makes seven assertions; drop `_load_demo04_rules()`, the `demo04_scenarios` read, and the two `demo05_path` assertions, and keep it asserting that `contracts.MAX_GUESTS` and `contracts.OVER_LIMIT_GUESTS` agree with `graph_setup.py`. Do not delete it. Phase 7 extends it against the seeded `Rule` node.
- [x] Prune the deleted notebooks from the registry in `setup/run_notebooks.py`. Labs 2, 3, 4, 5, 7, and 9 lose their only entry, and lab 1 loses `test_graphrag.ipynb`.
- [x] Drop `07-agentcore-memory-demo/.bedrock_agentcore.yaml` from `CONFIG_FILES` at `10-cleanup/workshop_cleanup.py:99-100`.
- [x] Grep the tree for the deleted folder names and fix every surviving reference in docstrings, path logic, and tests. `setup/notebook-output/` holds executed copies naming deleted demos; those are run artifacts, not living docs. Fixed: `graph_config.py`'s module docstring, which named three deleted files, and two cells of `retrieval_patterns.ipynb`, one linking to the deleted `test_graphrag.ipynb` and one pointing at Demo 09. The two FAISS mentions left in `deploy_agentcore.ipynb` sit in the Gateway section Phase 8 discards.

**Validation.** Done. `--list` shows five surviving notebooks. Every test suite passes: 55 tests plus 12 subtests in `06-agentcore-boto3-demo`, 12 plus 2 subtests in `01-graphrag-demo`, 20 in `10-cleanup`, and 22 in `08-neo4j-memory-demo`. A full offline run passes lab 0 and skips lab 10; labs 1, 6, and 8 fail on an empty graph, which is a precondition rather than a regression. See the findings below.

**Findings.**

- **The FAISS artifacts were never checked in.** `faqs_docs.json` and `faqs_vector.index` are gitignored at `.gitignore:88-89` and existed only as local build output. Both `new-content.md` and this plan called them "checked-in," which overstated the size win: the repository never carried the 3.4 MB, only the working tree did. The deletion is still correct, and the spec has been corrected.
- **The narrowed guest-consistency test is two tests, not one, so Demo 06 now totals 55.** Splitting the constants check from the source check was worth one extra test because the two fail for different reasons and the old single test reported them as one. Every quoted count of 54 in the documentation is now 55, which Phase 10 has to carry. The write-path count of 29 is unaffected.
- **The graph-backed notebooks cannot be validated until Lab 1 runs.** The Aura instance reachable from the root `.env` is empty, so labs 1, 6, and 8 fail at their readiness checks. Phase 4 has to build the lite graph before any lane can validate against it, which makes the graph build a prerequisite for Lane A, Lane B, and Lane D rather than only for Phase 4.

---

### Phase 2: Rename

**Status.** Done. Two commits: `054a697` holds 62 pure renames with zero content change, and the follow-up commit repoints every reference.

**Outcome.** Folder names match lab numbers, and everything that pointed at the old names points at the new ones.

- [x] Move the surviving folders to `00-setup/`, `01-graph-build/`, `02-retrieval/`, `03-agents-and-tools/`, `04-grounded-write/`, `05-agentcore-deploy/`, and `06-memory/`, as pure moves in one commit with no content edits. Done: `054a697`, `62 files changed, 0 insertions(+), 0 deletions(-)`.
- [x] Account for every file in `01-graphrag-demo/`, not just the five the spec's "Built from" row names. `build_graph.py`, `build_graph_lite.py`, `images/`, `test_retrieval_setup.py`, and `test_graph_builder_metadata.py` move to `01-graph-build/` alongside `prepare_graph.py`, `graph_builder.py`, `data/`, and `hotel-faqs.zip`. Nothing is left unassigned after Phase 1's deletions.
- [x] Move or delete `01-graphrag-demo/.env` by hand. It exists today, 174 bytes. It is gitignored at `.gitignore:46`, so `git mv` leaves it behind at the old path, and a demo-local `.env` takes precedence over the root one. A stale copy stranded in a deleted directory is a silent credential bug. Deleted: it went with the directory, and no lab folder carries a local `.env` now. Every demo reads the root `.env`, which the validation run exercised.
- [x] In a second commit, rewrite the notebook registry to hold all seven lab entries at once, labels 0 through 6, including `05-agentcore-deploy/5.1_agentcore_deploy.ipynb` with `deploys_resources=True` and `05-agentcore-deploy/5.2_teardown.ipynb` with `deletes_resources=True`. Paths that do not exist yet are expected; each content lane fills in its own. No runner change is needed for this, since `:373-374` already skips a missing path with a clear message and `:505` counts only `FAIL` toward the exit code. Confirm that behavior once rather than reimplementing it. Done: ten entries across labels 1 through 6, and the skip-and-do-not-fail behavior was confirmed by running it rather than by reading it.
- [x] Fix `--include-deploy`'s help text at `setup/run_notebooks.py:431`, which reads "Run lab 7," and `--include-cleanup`'s at `:434`, which reads "Run lab 10." Both labs are gone. Both now name lab 5.
- [x] Update the module docstring's usage examples at `:28-37`. `--labs 2-5` and `--labs 6` change meaning under the new numbering, and the line "The default run covers demos 00 through 05" is no longer true.
- [x] Repoint the cleanup script's config-file path at the new deploy folder. `CONFIG_FILES` is now a single entry, and the comment in `discover_local_config` that explained the old 06-versus-07 case was rewritten to stop naming deleted labs.
- [x] Repoint the remaining docstrings and path logic that name old folders. Beyond the docstrings: four cells of `3.1_strands_primer.ipynb` and two of `retrieval_patterns.ipynb`, plus the two Lab 4 tests that reach across the split (see Findings).

**Validation.** `git log --follow` on a moved file shows history across the rename. `--list` shows seven labs. A full offline run passes, skipping the five not-yet-authored notebooks with a clear message rather than failing.

`git log --follow 03-agents-and-tools/3.1_strands_primer.ipynb` reaches back through five commits to the file's creation under `00-getting-started/`. `--list` prints ten notebooks across labels 1 through 6. The offline run reports `Passed: 1  Failed: 1  Skipped: 8  Total: 10`: the five unwritten notebooks skip as `notebook file not found`, the three Lab 5 notebooks skip behind their deploy and cleanup gates, `3.1_strands_primer.ipynb` passes, and `6.1_neo4j_agent_memory.ipynb` fails at its readiness check against the empty Aura instance, which is the Phase 1 finding rather than a Phase 2 regression. All four test suites pass: 12 in Lab 1, 55 in Lab 4, 20 in Lab 5, 22 in Lab 6.

**Findings.**

- **The two folder splits broke two Lab 4 tests, and neither failure was predictable from a file listing.** `test_contracts.py` reads `tool_schemas/tools.json` and `test_reservation_command.py` loads `deployment-tools/.../lambda_function.py`, both as `Path(__file__).parent / ...`. Those two directories went to Lab 5 while the tests stayed in Lab 4, so both assertions now cross a folder boundary and had to be repointed at `../05-agentcore-deploy/`. Phase 3 changes the second one again when the Lambda entrypoint moves to the package path.
- **Lab 0 has no notebook, so the registry holds six labels, not seven.** The checklist item above asked for "all seven lab entries, labels 0 through 6," but Lab 0 is a credential checklist in a README. The registry holds ten notebooks across labels 1 through 6, and the module docstring now says so explicitly rather than leaving a reader to wonder where lab 0 went.
- **`02-retrieval/` and `05-agentcore-deploy/` have no `requirements.txt`.** Both were carved out of folders whose requirements file went to the other half of the split. Phase 3 writes them when it points each lab at the shared package, so this is a gap to close rather than an oversight to fix now.

---

### Phase 3: Shared package

**Status.** Done.

**Outcome.** One definition of every shared module, imported rather than resolved through path manipulation.

- [x] Create `workshop/` as an installable package with a `pyproject.toml`.
- [x] Move nine modules in. From `01-graphrag-demo/`: `retrieval_contract.py`, `bedrock_providers.py`, and `retrieval_setup.py`. From `06-agentcore-boto3-demo/`: `contracts.py`, `graph_setup.py`, `hybrid_retrieval.py`, and `reservation_command.py`. Plus `graph_connection.py` and `graph_schema.py`, split out of `graph_config.py` below. The Lab 1 side is the half an earlier draft of this plan missed, and without it `02-retrieval/` cannot import its embedder, its connection helper, its schema, or its verification functions.
- [x] Split `01-graphrag-demo/graph_config.py`. `NEO4J_URI` and `neo4j_auth()` from `:35-54` become `workshop/graph_connection.py`. `GRAPH_SCHEMA`, `SCHEMA_NODE_LABELS`, and `OFF_SCHEMA_LABELS` from `:63-186` become `workshop/graph_schema.py`; `SCHEMA_NODE_LABELS` has to travel because `retrieval_setup.py:18-23` imports it. `CHUNK_SIZE`, `CHUNK_OVERLAP`, `EXTRACTION_MAX_TOKENS`, `REQUIRED_CITIES`, and `select_lite_files()` stay in `01-graph-build/graph_config.py`, which then imports the rest from `workshop`.
- [x] Collapse the five constants duplicated between `retrieval_contract.py:5-9` and `contracts.py:13-17` into one definition. `retrieval_contract.py` is the survivor, because `graph_config.py:27-33` already re-exports all five from it. Delete the five definitions from `contracts.py` and replace them with an import. Do not delete `contracts.py` itself: it holds nine further constants including `HYBRID_RANKER`, `HYBRID_TOP_K`, `MAX_AMENITIES`, `WORKSHOP_OWNER`, `MAX_GUESTS_RULE_ID`, and `MAX_GUESTS`.
- [x] Preserve `contracts.py`'s no-client property. Its docstring promises it imports no AWS or Neo4j clients so the Lambda and the tests can load it freely. `retrieval_contract.py` is pure constants, so the new import is safe, but check that nothing else pulled into `workshop/__init__.py` breaks it.
- [x] Point each per-lab requirements file at the shared package in editable mode.
- [x] Update the existing tests to the new import path, keeping them where they are. `test_bedrock_providers.py`, `test_retrieval_setup.py`, and `test_graph_builder_metadata.py` move with Lab 1; Demo 06's five test files move with Labs 4 and 5.
- [x] Rework `build_lambda_zip()` at `setup/provision_agentcore.py:578-634` to `pip install .` the shared package into the build directory instead of flat-copying named files, and delete `SHARED_MODULES` at `:63`.
- [x] Change `deployment-tools/lambda_tools/create_reservation_request/lambda_function.py:5` from `from reservation_command import handler` to the package path.
- [x] Check the two Demo 06 modules that do bare `import contracts`, `hybrid_retrieval.py:25` and `graph_setup.py:23`, and `bedrock_providers.py:25`, which does a bare `from retrieval_contract import`. All three become intra-package imports.
- [x] Verify the built zip imports cleanly, since this is the one Phase 3 change whose failure surfaces only at Lambda runtime during Phase 8.

**Validation.** Every existing test passes unchanged in behavior. No file in the tree adds a sibling lab folder to the import path, and no notebook in `02-retrieval/` imports a bare module name that resolves only from Lab 1's directory. The Lambda zip resolves its imports the same way the local tests do.

All four suites pass against the package: 12 tests and 2 subtests in Lab 1, 55 and 12 in Lab 4, 20 in Lab 5, 22 in Lab 6. The no-client property was checked by running rather than by reading: with every `NEO4J_*` and `AWS_REGION` variable popped from the environment, `import workshop.contracts` succeeds and pulls in none of `boto3`, `botocore`, `neo4j`, `neo4j_graphrag`, or `dotenv`, and `contracts.CHUNK_VECTOR_INDEX is retrieval_contract.CHUNK_VECTOR_INDEX` is true, so the collapse produced one object rather than two equal strings. `build_lambda_zip()` was run against a temp directory: it emits 865 KB holding all ten package modules plus `workshop/fixtures/hotel_ids.json`, with neither `boto3` nor `neo4j_graphrag` vendored, and a subprocess launched inside the unpacked zip confirms `lambda_function.handler is workshop.reservation_command.handler`.

**Findings.**

- **The fixture manifest had to become package data.** `graph_setup.MANIFEST_PATH` resolves as `Path(__file__).parent / "fixtures" / "hotel_ids.json"`, so moving the module without the manifest broke three Lab 4 tests with `FileNotFoundError`. The file now lives inside the package and ships through a hatch `force-include` entry. Any future module that reads a file relative to itself needs the same treatment.
- **`--no-deps` keeps the Lambda zip small, and only works because of what the Lambda does not import.** The shared package declares `neo4j-graphrag`, tens of megabytes the reservation handler never touches. Installing with `--no-deps` after the platform-targeted requirements step leaves `neo4j` resolved from the Lambda's own `requirements.txt` and drops the rest. If a future change makes `reservation_command` import something outside that set, the zip will build and only fail at Lambda runtime.
- **The Runtime image cannot yet reach the shared package, and Phase 8 has to solve it.** `deployment-tools/Dockerfile` does `COPY . .` with `deployment-tools/` as its build context, which sits below `workshop/` in the tree. The stale `.dockerignore` entries for the flat-copied modules are gone and a comment marks the gap, but the build mechanism itself is deliberately unwritten rather than guessed at.
- **Lab 1 was carrying `strands-agents` and never imported it.** The dependency came along when `01-graphrag-demo/requirements.txt` was written for a folder that has since split. Lab 1 now installs the shared package and `numpy` only.

---

### Phase 4: Lab 1, the graph build notebook

**Status.** Done. Authored, offline-validated, and the live build and idempotence re-run both pass.

**Outcome.** A participant builds the graph from a notebook and lands on a graph Lab 4 can open against.

- [x] Author `1.1_build_graph.ipynb` around the existing preparation and builder scripts: configure the pinned schema, run the pipeline live, verify both indexes and the constraints. Nineteen cells, eight sections.
- [x] End the notebook by applying the Demo 06 graph fixtures, which seed the fixture hotel, the guest-limit rule, and three constraints.
- [x] Keep the idempotent and rebuild behavior of the underlying script reachable from the notebook. Section 4 reports readiness and sets `NEEDS_BUILD`; the `REBUILD` flag in section 1 is the notebook form of the script's `--rebuild`.
- [x] Fill in the registry path Phase 2 reserved for Lab 1. It was already filled; what was missing was the runner's access to the shared package, below.
- [x] Run the live build end to end against a Neo4j instance and confirm a second run rebuilds nothing.

**Validation.** Format, cell syntax, and the credential-free path are all confirmed: executed with every `NEO4J_*` and `AWS_*` variable popped and `AWS_CONFIG_FILE=/dev/null`, every live cell prints "Skipping: no Neo4j or AWS configuration." and the run ends clean.

The live build now passes. The full run reports 30 documents and 30 chunks against an expected 30 and 30, with `Hotel` 30, `Room` 91, `Amenity` 31, `Policy` 25, and `Service` 20, and no off-schema label. The idempotence re-run is the proof that mattered: cell 5 reports "The graph is already complete. The next cell will skip the build," cell 6 reports "Skipping: the graph already reports ready," `hotel_chunk_embeddings` is ONLINE at 1024 dimensions cosine, `hotel_chunk_fulltext` is ONLINE over `:Chunk(text)`, the three constraints and the `max_guests` rule are present, and the runner ends `Passed: 1  Failed: 0`.

**Findings.**

- **The acceptance runner could not import the shared package.** `setup/run_notebooks.py` is a PEP 723 script with its own dependency list, and Phase 3 moved nine modules into `workshop/` without adding it there. No notebook importing `workshop.*` could have run under the runner. Fixed by adding `"workshop"` to the inline dependency block plus a `[tool.uv.sources]` entry pointing at `../workshop` as an editable install. This is a Phase 3 gap that only Phase 4 could surface.
- **Import order is what makes the credential-free path work.** `workshop.graph_connection` raises at import when `NEO4J_PASSWORD` is unset, so the environment check uses plain `os.environ` and every module that opens a driver, `prepare_graph` included, is imported inside the guarded branch rather than at the top of the notebook. Checked by running, not by reading.
- **Top-level `await` inside an `if` block compiles under `PyCF_ALLOW_TOP_LEVEL_AWAIT`**, which is what IPython uses, so `exit_code = await run_build(paths, title)` works both interactively and under the runner.

---

### Phase 5: Lab 2, retrieval

**Status.** Done. Authored, offline-validated, and all three notebooks pass live.

**Outcome.** Four retrievers run side by side on the same questions, and the lab closes on a question the graph cannot answer.

- [x] Author `2.1_vector_retrievers.ipynb` from cells 10 and 14 of `retrieval_patterns.ipynb`, the vector and vector-cypher patterns, framed as standard RAG against GraphRAG.
- [x] Author `2.2_fulltext_retrievers.ipynb` from cell 12 of `retrieval_patterns.ipynb`, the hybrid pattern, plus cells 0 through 6 of `01_hybrid_retrieval.ipynb` for the hybrid-cypher retriever and the hero question. Cells 7 through 9 of that notebook are the abstention close and are listed separately below, so the two ranges do not overlap. Cell 18 of `retrieval_patterns.ipynb`, "Going further: HybridCypherRetriever," is markdown only, so the code has to come from the Demo 06 notebook. These have never appeared together.
- [x] Give each of the three notebooks its own copy of the graph-verification and schema-display cells, cells 4 and 6 of `retrieval_patterns.ipynb`. Watching those run is what tells a participant whether Lab 1 succeeded. Both now import from `workshop`: `verify_retrieval_indexes` and `fixture_problems` from `retrieval_setup`, and `GRAPH_SCHEMA` from `graph_schema`.
- [x] Construct the embedder from `workshop.bedrock_providers` rather than duplicating cell 8. The three embedding constants must match what Lab 1 wrote, and a mismatch returns wrong results with no error.
- [x] Close `2.2` with the availability question, carried from cells 7 through 9 of `01_hybrid_retrieval.ipynb`: markdown cell 7 for framing, then code cells 8 and 9, the grounded agent and the availability question. Three cells, one line on what did not happen.
- [x] Author `2.3_text2cypher.ipynb` as optional, reusing cell 16 as-is. Skip this notebook if the Phase 0 probe already put Lab 2 over budget.
- [x] End `2.2` with the one-sentence mechanism statement: vector search finds candidates, traversal finds what is connected.
- [x] Fill in the three registry paths Phase 2 reserved for Lab 2.

**Validation.** All three notebooks are valid nbformat, every code cell compiles, and all three run clean with credentials stripped: 2.1 skips three live cells, 2.2 six, 2.3 one, and the schema-display cell renders in every one of them without touching a driver. The abstention close is three cells as specified, markdown framing plus the grounded agent plus the availability question, and the mechanism sentence ends the notebook. No notebook defines an embedding constant locally: all five come from `workshop.retrieval_contract` by import, and the embedder is `workshop.bedrock_providers.BedrockEmbeddings`. The live run is now done and the abstention claim is re-observed rather than carried over. `--labs 2` reports `Passed: 3  Failed: 0`. The grounded question returns AnyCompany Cairo Nile View at 789 Corniche el-Nil with guest rating 4.5 and its six amenities, and the availability question answers "I cannot determine that from the available hotel knowledge," then explains that "subject to availability" in the policy text is not a guarantee of inventory. That is the abstention the lab claims, produced by the graph returning no matching context.

**Findings.**

- **Lab 2 needed `strands-agents` and did not declare it.** `02-retrieval/requirements.txt` listed only the shared package, but 2.2's abstention close builds a Strands agent. Added with the reason in a comment.
- **The registry entries were already filled.** Phase 2 reserved and populated all three paths; nothing to do beyond confirming them.
- **The carried-forward cells defaulted `MODEL_ID` to `us.anthropic.claude-sonnet-4-6`** while `workshop.bedrock_providers` uses `us.anthropic.claude-sonnet-5`. **Resolved:** standardized on Sonnet 5 everywhere. Seven files changed, `2.2_fulltext_retrievers.ipynb`, `4.1_reservation_write.ipynb`, the retired `01_hybrid_retrieval.ipynb`, `deployment-tools/booking_agent.py`, `setup/provision_agentcore.py` including its inference-profile docstring, and the prose in `05-agentcore-deploy/README.md` and `setup/README.md`. `workshop.bedrock_providers` holds the one definition; no non-vendored file names Sonnet 4-6 now.
- **2.2 verifies the Lab 1 fixtures rather than applying them.** The source notebook called `apply_demo6_graph`; seeding is Lab 1's job now, so 2.2 calls `readiness_problems` and tells the participant to re-run Lab 1 if anything is missing.

---

### Phase 6: Lab 3, agents and tools

**Status.** Done. Authored, offline-validated, and the live run passes.

**Outcome.** A participant holds one named agent, `hotel_agent`, whose tools include the Lab 2 retriever, and which Lab 4 extends by name.

- [x] Move the Strands primer in as `3.1_strands_primer.ipynb`. Its five teaching sections stay as they are.
- [x] In the section 3 toolset at cell 7, replace `get_weather` with the Lab 2 retriever behind a `@tool` boundary, importing from `workshop.hybrid_retrieval`. Weather is the one tool of the three that leaves the hotel domain; `search_hotels` and `book_hotel` are what sections 4 and 6 build on.
- [x] Keep the guest-limit hook section at cells 14-16 and the swarm section at cells 18-20 unchanged. Note that these are separate agents from section 3's, not additional tools on one agent, which is how an earlier draft of this plan read them.
- [x] Author a new closing section, roughly three cells, that assembles one named `hotel_agent` carrying the retriever tool and the hook-guarded `book_hotel`, with `BookingGuardrailsHook` attached. This is the only new authoring in Phase 6 and it is what Phase 7 registers the write onto.
- [x] Add one markdown line to the hook section naming the limit as a Python constant, so Lab 4 has something specific to point back at. Do not explain the graph alternative here; that is Lab 4's opening.
- [x] Confirm nothing in the notebook references tool selection, the tool graph, or the token-cost comparison. Check the summary table at cell 21, which maps concepts to workshop modules by their old numbers.
- [x] Fill in the registry path Phase 2 reserved for Lab 3.

**Validation.** Twenty-six cells, valid nbformat, every code cell compiles, and the whole notebook runs clean with credentials stripped: every agent turn, every swarm turn, and both closing turns skip with a reason, while all five sections still construct their agents and print what they built. The live run is now done, so both claims are observed rather than inherited. All 17 cells pass. Cell 10, with no hook, answers "I'll book the AnyCompany Lisbon Resort for 15 guests right away!" Cell 11, with the hook, reaches the same intent and is then refused, reporting that the resort "has a maximum capacity of 10 guests per room" and that 15 exceeds it. The contrast is the beat, and it lands. The swarm flags the unknown hotel in cell 14: `lookup_hotel` returns nothing for AnyCompany Antarctica Lodge and the agent reports it "was not found in the database" instead of inventing a rating, while cell 13 returns the real Lisbon Resort at 4 stars and $95/night.

**Findings.**

- **`BookingGuardrailsHook` and `book_hotel` have no referent in this notebook.** The plan names them; the primer's section 4 defines `MaxGuestsHook` and `book_room`, and `book_hotel` is one of section 3's simulated tools. Since the plan also says sections 4 through 6 stay unchanged, the closing section reuses the names that exist. The plan's names look like a holdover from the deleted steering demo.
- **Every live cell in the primer had to learn to skip.** The notebook hard-failed without AWS credentials, which would have made `--labs 3` red offline against the convention in `CLAUDE.md`. Guards went on the ten cells that actually invoke a model; agent and swarm *construction* needs no credentials, so the teaching code stayed unindented and readable.
- **Two summary references pointed at content this rebuild deleted.** Section 3.5 cited "the cost of a broad retrieval against a targeted one (Lab 2)" and the summary table mapped `AgentResult.metrics` to Lab 2. Lab 2 no longer has a token comparison. Both now describe what they actually do.
- **Section 3.5 rebound the name `agent`.** It reassigned the same variable the three-tool agent uses, so re-running the section 3 tests after it silently exercised a tool-less agent. Renamed to `agent_metrics`.

---

### Phase 7: Lab 4, the grounded write

**Status.** Done. Authored, offline-validated, and the live run passes.

**Outcome.** The agent writes to the graph, and a rule in the graph stops the write it should stop.

- [x] Author `4.1_reservation_write.ipynb` by carrying forward cells 10 through 15 of `01_hybrid_retrieval.ipynb`, which already cover the 15-guest rejection, the valid write, the safe retry, and the graph inspection. These are working, tested cells; they become the verification cells. Stop at 15: cell 16 is a "Where this goes next" markdown pointing at Demo 01b. No new backend code.
- [x] Open by registering `create_reservation_request` on the `hotel_agent` that Phase 6's closing section built, so every case runs as an agent turn and the carried-forward cells confirm what landed in the graph.
- [x] Author the unknown-hotel rejection, which is the only genuinely new case of the four.
- [x] Open with two paragraphs naming the Lab 3 hook explicitly: it worked, and a hardcoded `10` in Python is still the wrong home for a business rule. This is the contrast the whole lab rests on, so it cannot be left implicit.
- [x] Make the rule's origin visible. It is read from the `Rule` node `demo-06-maximum-guests`, not asserted in the prompt.
- [x] Extend `test_demo_guest_consistency.py`, narrowed in Phase 1, with an assertion that the seeded `Rule` node's limit matches `contracts.MAX_GUESTS`. Self-skip when credentials are absent.
- [x] Fill in the registry path Phase 2 reserved for Lab 4.

**Validation.** Twenty-one cells, valid nbformat, every code cell compiles, and the notebook runs clean with credentials stripped: all nine live cells skip with a reason. The suite is 55 passed and 12 subtests, plus the new live test. Each of the four cases carries its own assertion in the notebook rather than relying on the reader to check the printed JSON: `rejected` with `max_guests_exceeded`, `accepted` with `duplicate` false then true, `rejected` with `unknown_hotel`, and exactly one row from the graph inspection. The live run is now done. All 11 cells pass. The agent's write of 15 guests comes back `"status": "rejected"`, `"reason_code": "max_guests_exceeded"`, `"max_guests": 10`, and the agent relays the refusal in prose without retrying it. The idempotence pair then returns `"status": "accepted"`, `"duplicate": false` on first delivery under one `request_id`. The rule text never appears in the system prompt, so the refusal comes from the graph.

One cosmetic finding, not a failure. Every verification query emits four Neo4j `01N51`/`01N52` warnings, that `FOR_HOTEL`, `check_in`, `check_out`, and `guests` do not exist, whenever it runs before any `ReservationRequest` has been persisted. The query is correct and the warnings are accurate for an empty slice of the graph, but they are noisy in participant output.

**Findings.**

- **The new live test works, and proved it by failing.** `SeededRuleTests` was run against the partially built graph and failed on a missing `Rule` node with the message telling the reader to run Lab 1. It needs `load_dotenv()` in `setUp`, because participants keep credentials in the repo-root `.env` rather than exported, and without it the test would skip on every machine that actually has a graph worth checking.
- **The write tool mirrors the frozen contract exactly, `request_id` included.** Letting the agent invent a UUID would have made idempotence untestable, so the notebook creates the `request_id`, prints it, and passes it in the user turn. No field was added to the command and no second write path exists.
- **`MaxGuestsHook` comes off the agent in Lab 4, which is the point of the lab.** The retrieval tool and the write tool stay; the hook goes, because the rule it enforced now lives in the graph and the command reads it inside the write transaction.

---

### Phase 8: Lab 5, deploy and tear down

**Status.** Pending

**Outcome.** The Lab 4 agent runs on AgentCore Runtime with the retriever unchanged, and the lab ends with nothing running.

- [ ] Author `5.1_agentcore_deploy.ipynb` fresh, in this shape: confirm `provision_agentcore.py` has run, configure and launch the Runtime, tag, then four smoke tests. Roughly 15 new cells.
- [ ] Copy cells 24 through 27 of the restored `deploy_agentcore.ipynb` across unchanged. That is the pre-flight toolkit cleanup at 24, the `Runtime.configure` and `Runtime.launch` pair at 25, and the tagging header and code at 26-27. It is the only part of the restored notebook whose behavior is proven. Stop at 27: cell 28 is the "Step 9: Test the Agent" markdown heading the section this notebook replaces. Keep the restored notebook open as reference while authoring, and do not carry over its cell 5 recovery scaffolding, which loads DynamoDB resources, its cell 40 "Module 6 Deployment Complete" banner, or its cells 41-42 "Save Variables for Module 7."
- [ ] Point `entrypoint` and `requirements_file` at `deployment-tools/booking_agent.py` and `deployment-tools/agent_requirements.txt`, and set `env_vars` to the gateway URL and `NEO4J_*` values `booking_agent.py` reads. Drop `BOOKINGS_TABLE`.
- [ ] Write four smoke tests, matching what Lab 4 established: the hero question, the abstention, the guest-limit rejection, and the idempotent retry.
- [ ] Author `5.2_teardown.ipynb` from `10-cleanup/`, carrying its tag-scoped deletion and its refusal to delete untagged resources.
- [ ] Author `5.3_agentcore_walkthrough.ipynb` as optional, from `advanced-deployment/02_agentcore_walkthrough.ipynb`. It reads `AGENT_RUNTIME_ARN`, which `5.1` produces.
- [ ] Fill in the three registry paths Phase 2 reserved for Lab 5, confirming `5.1` carries the deploy gate and `5.2` the cleanup gate.
- [ ] Confirm the Lambda built by the Phase 3 packaging change imports cleanly once deployed. This is the first point at which that change is exercised for real.

**Validation.** `--labs 5 --include-deploy` deploys and passes four smoke questions without touching teardown. `--labs 5 --include-cleanup` then leaves no repository, no build project, and no Runtime. Verify by listing tagged resources after teardown.

---

### Phase 9: Lab 6, memory

**Status.** Done, including the live notebook run.

**Outcome.** Optional memory material closes the workshop with the managed contrast recorded.

- [x] Move the inspectable memory notebook in as `6.1_neo4j_agent_memory.ipynb`, reused as-is.
- [x] Add the one-paragraph callout on why the workshop uses Neo4j memory rather than the managed store, which is the comparison the deleted Demo 07 used to carry.
- [x] Fill in the registry path Phase 2 reserved for Lab 6.

**Validation.** `test_memory_helpers.py` passes, 22 tests. The notebook is valid nbformat and every code cell compiles. The live run is now done, against the Phase 4 graph it depends on. All 7 cells pass. Two fixture messages store into a per-run session, the extracted preference links to both its source message and the real Lab 1 `Hotel`, and actor isolation holds in a fresh session: Actor A gets back "Loves AnyCompany Cairo Nile View and wants a room on a high floor away from the elevator" while Actor B returns no preference.

**Findings.**

- **"Reused as-is" could not survive the renumber.** The notebook opened as "Module 8" and told the reader to run "Module 1". Six prose references across six cells now name labs. Nothing in code changed: the `demo08-` identifier prefix stays exactly as it is, because `cleanup_memory.py` matches on it.
- **The managed-store paragraph is an argument, not a disclaimer.** It says what a managed service gives you, then names the one thing it does not: the last section of this notebook, where a preference is traversed back to the message that produced it and forward to the `Hotel` it describes.

---

### Phase 10: Documentation and the diagram

**Status.** Done.

**Outcome.** Every document describes six labs and one path, with no surviving promise of four hallucination categories.

- [x] Rewrite the root README title line, the module table, and the hallucination-categories FAQ answer. Two of four categories keep a live demonstration.
- [x] Correct every quoted test count. 54 is all of Demo 06, across five files: 22 in `test_reservation_command.py`, 12 each in `test_graph_setup.py` and `test_hybrid_retrieval.py`, 7 in `test_contracts.py`, and 1 in `test_demo_guest_consistency.py`. The reservation command and its contracts are 29. Use 29 wherever the claim is about the write path. Counted again after the move: `grep -c "def test_"` gives 22, 12, 12, 7, and 3, which is 56, and 56 is what the three docs quoting it now say.
- [x] Replace the module-build-order section with the path description from the framing.
- [x] Collapse the core, audience-dependent, and optional-advanced split. Only Lab 6 is optional.
- [x] Rewrite `CLAUDE.md` for the new layout, the shared package, and the single acceptance command.
- [x] Write a README for each of the seven folders, with Step 0 being a credential checklist rather than a notebook.
- [x] Update the architecture document in the delivery folder.
- [x] Redraw the progressive-flow diagram as the six-lab path.
- [x] Confirm no notebook in the tree carries the `test_` prefix, and that every per-folder README refers to notebooks by their `N.M_` names.
- [x] Sync `new-content.md` against what actually shipped. The spec has already been corrected for the nine-module package, the `graph_config.py` split, Lab 3's assembled `hotel_agent`, the `5.2` teardown notebook and `5.3` walkthrough renumber, the deleted travel agent, the corrected "Built from" rows, and the abstention cell count. Anything Phase 11 changes goes back into it too, so the spec stays the record rather than the first draft.

**Validation.** Done. No document names a deleted demo except in the record of what was removed: the only live files that still carry the old folder names are `workshop-delivery/architecture.md`, in its "what this document deliberately dropped" section, and `new-content.md`, in its deletion and "built from" tables. Everything else is under `logs/` and `backups/`, which are append-only history.

`git ls-files "*test_*.ipynb"` returns nothing, so the naming rule holds for everything that ships. Eight `test_*.ipynb` files do exist on disk, all of them `--keep-output` artifacts under the gitignored `setup/notebook-output/` from runs of demos that no longer exist. The only non-`N.M_` notebook names in any lab README are `deploy_agentcore.ipynb` and `02_agentcore_walkthrough.ipynb`, both documented as reference source rather than participant paths.

The Python floor is now stated one way. `workshop/pyproject.toml` sets `requires-python = ">=3.12"` and every lab installs it with `-e ../workshop`, so the 3.9+ and 3.11+ badges made the documented install commands fail as written. All of them now read 3.12+.

Two findings worth carrying forward:

- **`CLAUDE.md` is gitignored** at `.gitignore:59`, so the rewrite is local-only and no one who clones the repository gets it. Whether that file should ship is a question for the repository owner, not something this phase should decide.
- **The shared package prints deleted demo names.** `workshop/src/workshop/retrieval_setup.py:283` prints "Demo 01 readiness report:", which every Lab 1 run shows a participant, and `graph_setup.py:425` and `:465` print "Demo 06 is not ready:" and "Demo 06 graph is ready." These are code rather than documentation, and tests may assert on them, so they are left alone pending a decision.

---

### Phase 11: Rehearsal

**Status.** Pending

**Outcome.** A measured run that either fits four hours or produces the specific cut that makes it fit.

- [ ] Run Labs 1 through 5 end to end on the lite corpus, timing each lab.
- [ ] Record the graph build time separately, since it is the one unavoidable wait.
- [ ] Compare each lab against the Phase 0 budget and record where the estimate was wrong, so the next rebuild estimates better.
- [ ] Compare the total against a four-hour budget with room for questions and stragglers.
- [ ] If over, apply the fallbacks in order and record which one was used.
- [ ] Resolve the open question of whether Lab 3 still earns its own folder.

**Validation.** A written per-lab time budget measured against Phase 0's prediction, and a full acceptance run including the deploy and cleanup gates.

---

### Completion criteria

The plan is done when every item in "Done when" above is checked, the acceptance runner passes with all gates enabled, and a rehearsed run has a recorded per-lab time budget that fits four hours.

## Parallel execution

### The serial spine

Phases 1, 2, and 3 are strictly serial and block everything else. They change folder names and import paths, so any content work started before they land will be rewritten. One person runs them, back to back, and announces when Phase 3 merges.

Phase 0 sits outside the spine. It touches no files, so it runs alongside Phases 1 through 3 and must report before Phase 5 starts authoring `2.3`.

### Lanes after Phase 3

| Lane | Phases | Owner needs | Blocked by |
|---|---|---|---|
| A, graph and retrieval | 4, then 5 | Aura, Bedrock | Phase 3, and Phase 0's verdict on `2.3` |
| B, agent and write | 6, then 7 | Aura, Bedrock | Phase 3 |
| C, deploy | 8 | AWS account with billing, Aura | Phase 7 for the four smoke questions |
| D, memory and docs | 9, then 10 | Aura for Lab 6 | Phase 3 for Lab 6, everything for the final doc pass |
| E, diagram | The diagram item in Phase 10 | Nothing | Nothing, it can start immediately |
| F, timing probe | 0 | Aura, Bedrock, an AWS account with billing | Nothing, it starts immediately |

Lanes A, B, D, E, and F run concurrently. Lane C authors `5.1` concurrently but cannot finish its smoke questions until Lane B lands Phase 7.

Lane F needs the same billable AWS account as Lane C, and its deploy-and-teardown cycle is the same infrastructure Lane C will use. Run Lane F to completion before Lane C starts, or give them separate accounts.

Phase 11 is serial again. It needs everything merged.

### Cross-lane dependencies

- **Phase 5 authoring does not need Phase 4, but Phase 5 validation does.** Lane A can write both retrieval notebooks against the existing graph, and only the final validation pass needs the graph the new build notebook produces.
- **Phase 6 needs the shared retriever, not Lab 2's notebooks.** The retriever lives in the shared package after Phase 3, so Lane B never waits on Lane A.
- **Phase 7 needs nothing from Lane A.** The write path, its contracts, and its tests already exist.
- **Phase 8's smoke questions need Phase 7.** The rejection and retry cases must match what Lab 4 established. Everything else in `5.1`, including the copied Runtime cells and the tagging cell, is authorable before Phase 7 lands.
- **Phase 7 needs Phase 6, and now depends on an artifact rather than a framing.** Lab 4 registers the write onto the `hotel_agent` that Phase 6's closing section builds, and its opening argument depends on the primer's guest-limit hook being framed as the fixture version. Lane B's two phases stay strictly in order.
- **Phase 8 is the first real test of Phase 3's Lambda packaging change.** If the shared package does not import inside the deployed Lambda, the fix is in `workshop/` and belongs to Phase 3's owner, not Lane C.
- **Phase 10's final pass needs every lane.** Start the per-folder READMEs early and hold the root README and architecture document until the end.

### Contention to manage

- **The notebook registry.** Resolved by Phase 2 registering all seven entries up front. Each lane then edits one path string in an entry nobody else touches, instead of appending to a shared tuple.
- **The Aura instance.** Lanes A, B, and F all want a graph, and the build is destructive on rebuild. Give each lane its own Aura instance or its own database name, or serialize the builds and share one read-only graph afterward.
- **The shared package.** Freeze it at the end of Phase 3. Changes after that go through one owner, because every lane imports it and the Lambda zip now installs it.
- **AWS resources.** Lanes C and F both create billable infrastructure. Keep them to one owner and one account, run F first, and tear down after every rehearsal.

### Suggested wave order

1. **Wave 1, serial spine plus one probe.** Phases 1, 2, 3 under one owner, with Lane F running Phase 0 alongside them. Phase 0 reports before Wave 2 begins.
2. **Wave 2, parallel.** Lane A on 4 then 5, Lane B on 6 then 7 in that order, Lane D on 9, Lane E on the diagram. Lane C authors `5.1`, `5.2`, and `5.3` up to the smoke tests.
3. **Wave 3, mostly parallel.** Lane C finishes Phase 8's smoke tests against Lab 4's cases and exercises the Lambda packaging change. Lane D runs the documentation pass in Phase 10.
4. **Wave 4, serial.** Phase 11, the rehearsal, with everything merged, measured against Phase 0's prediction.
