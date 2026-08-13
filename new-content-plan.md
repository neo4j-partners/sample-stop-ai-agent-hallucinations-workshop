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

**Status.** Superseded, and not in the way it was meant to be. The probe never ran ahead of the content work. The numbers it wanted now exist, measured directly from the finished notebooks rather than from a proxy, so the data is better than planned and arrived too late to be the cheap scope-cut gate this phase was designed to be. Any cut from here costs authored work. Phase 11 owns the participant budget.

**Outcome.** The Lab 2 and Lab 5 time budgets are known before any content is authored, so a scope cut is cheap if one is needed.

- [x] Time a full run of `01-graphrag-demo/retrieval_patterns.ipynb` against a prepared graph, recording per-pattern time so the 2.1, 2.2, 2.3 split can be costed separately. Measured on the split notebooks themselves, which is the number that matters: `2.1` 18.3s, `2.2` 39.9s, `2.3` 17.0s.
- [x] Time one full `provision_agentcore.py provision`, deploy, smoke test, and teardown cycle end to end. Recorded in Phase 8. The teardown half alone exceeds ten minutes in an account carrying legacy resources, and its plan step takes 146s and runs twice.
- [x] Record both numbers, plus the confirmed 15-minute lite graph build, as the starting per-lab budget. Machine execution for all seven notebooks totals 311.2s: `1.1` 7.7s, `2.1` 18.3s, `2.2` 39.9s, `2.3` 17.0s, `3.1` 89.4s, `4.1` 33.5s, `6.1` 105.4s. `1.1`'s 7.7s is the "graph already complete" path, not a build, so the 15-minute lite build still stands as Lab 1's real cost.
- [x] Estimate Labs 3, 4, and 6 from cell counts rather than measuring them. Overtaken by measurement. All three ran live.
- [x] If the two measured numbers plus the estimates already exceed four hours, apply the first fallback before Phase 5 authors `2.3`. Not applicable. `2.3` was authored before any number existed.

**Validation.** A written per-lab budget with two measured entries and four estimated ones, and a stated verdict on whether `2.3` and the four retriever pairs survive.

**Validation record.** Six measured entries, no estimated ones. No verdict was reached on `2.3` or the retriever pairs from timing data, because the authoring finished first. Machine time is a floor and not a budget: 311.2s of execution says nothing about reading, discussion, or a participant fixing their own credentials. Treat the per-notebook numbers as the machine floor and take the participant budget from the Phase 11 rehearsal.

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

**Status.** Done. Authored, offline-validated, and deployed against real AWS. All four smoke questions pass from inside the Runtime, and teardown leaves nothing running.

**Outcome.** The Lab 4 agent runs on AgentCore Runtime with the retriever unchanged, and the lab ends with nothing running.

- [x] Author `5.1_agentcore_deploy.ipynb` fresh, in this shape: confirm `provision_agentcore.py` has run, configure and launch the Runtime, tag, then four smoke tests. Roughly 15 new cells.
- [x] Copy cells 24 through 27 of the restored `deploy_agentcore.ipynb` across unchanged. That is the pre-flight toolkit cleanup at 24, the `Runtime.configure` and `Runtime.launch` pair at 25, and the tagging header and code at 26-27. It is the only part of the restored notebook whose behavior is proven. Stop at 27: cell 28 is the "Step 9: Test the Agent" markdown heading the section this notebook replaces. Keep the restored notebook open as reference while authoring, and do not carry over its cell 5 recovery scaffolding, which loads DynamoDB resources, its cell 40 "Module 6 Deployment Complete" banner, or its cells 41-42 "Save Variables for Module 7."
- [x] Point `entrypoint` and `requirements_file` at `deployment-tools/booking_agent.py` and `deployment-tools/agent_requirements.txt`, and set `env_vars` to the gateway URL and `NEO4J_*` values `booking_agent.py` reads. Drop `BOOKINGS_TABLE`.
- [x] Write four smoke tests, matching what Lab 4 established: the hero question, the abstention, the guest-limit rejection, and the idempotent retry.
- [x] Author `5.2_teardown.ipynb` from `10-cleanup/`, carrying its tag-scoped deletion and its refusal to delete untagged resources.
- [x] Author `5.3_agentcore_walkthrough.ipynb` as optional, from `advanced-deployment/02_agentcore_walkthrough.ipynb`. It reads `AGENT_RUNTIME_ARN`, which `5.1` produces.
- [x] Fill in the three registry paths Phase 2 reserved for Lab 5, confirming `5.1` carries the deploy gate and `5.2` the cleanup gate.
- [x] Confirm the Lambda built by the Phase 3 packaging change imports cleanly once deployed. This is the first point at which that change is exercised for real.

**Validation.** `--labs 5 --include-deploy` deploys and passes four smoke questions without touching teardown. `--labs 5 --include-cleanup` then leaves no repository, no build project, and no Runtime. Verify by listing tagged resources after teardown.

**Validation record, offline.** All three notebooks pass `uv run setup/run_notebooks.py --labs 5` with no credentials, because every live cell self-skips behind the `DEPLOY_READY` and `RUNTIME_READY` guards.

**Validation record, live.** Provisioning created all six `demo06-agentcore=true` resources on the first run, exit 0, after one IAM propagation retry. `5.1` then launched Runtime `HotelBookingAgent-i6Jg838kmO` from ECR image `bedrock-agentcore-hotelbookingagent:20260813-124658-763`, tagged all three toolkit resources, and passed all four smoke questions. The two that matter both report `tools_used: ['search_hotel_knowledge', 'demo06-reservation-request___create_reservation_request']`, which is the evidence the phase exists to produce: retrieval ran in-process inside the container while the write crossed the Gateway to the Lambda over MCP. The graph rule still refused 15 guests with `max_guests_exceeded`, so deployment changed no behavior. `5.3` then passed all six cells against the live `AGENT_RUNTIME_ARN`. The Phase 3 Lambda packaging change is confirmed working, since the reservation Lambda imported the shared package and ran.

**Validation record, teardown.** `--labs 5 --include-cleanup` passes, `Passed: 1 Failed: 0 Skipped: 2`. All 17 selected resources were deleted and then observed gone, tier by tier: 14 in `compute-and-data`, 2 in `iam`, 1 local config file. `CLEANUP COMPLETE`, no failures. The notebook's own fifth cell rebuilds the plan afterward and reports `selected for deletion: 0  blocked: 0  absent: 24`, `Verified: no workshop resources remain`. `provision_agentcore.py teardown --yes` then deleted the gateway target, the gateway, the reservation Lambda, the three `demo06-*` roles and the command secret, exit 0, and cleared `AGENTCORE_GATEWAY_URL`, `AGENTCORE_RUNTIME_ROLE_ARN` and `NEO4J_COMMAND_SECRET_ID` from the root `.env`. `provision_agentcore.py status` reports all six `absent`. Verified independently of both scripts by the Resource Groups Tagging API, which returns an empty list for `WorkshopResource=stop-ai-agent-hallucinations` and for `demo06-agentcore=true`. Nothing from Lab 5 is still billing.

**Two findings from the live run, both since fixed.**

- **`temperature=0` is a hard failure on Sonnet 5, and it blocked the acceptance run.** `ValidationException: 'temperature' is deprecated for this model` from `ConverseStream`, at `2.2_fulltext_retrievers.ipynb` cell 8 and `4.1_reservation_write.ipynb` cell 6. `booking_agent.py` carried the same argument and would have failed every live smoke test. `workshop.bedrock_providers` already handled this correctly and documented why at lines 149-154, so the three call sites had simply never been migrated. The argument is dropped at all three. Nothing in the shared builder changed.
- **`workshop_cleanup.py` selects far more than Lab 5 creates, and that is correct.** The dry run in this development account selected 18 resources: Lab 5's own Runtime, ECR repository, CodeBuild project and local config, plus 14 legacy resources from a 2026-07-21 run that legitimately carry the workshop tag. Three unrelated `bedrock-agentcore-*-builder` CodeBuild projects in the same account were correctly excluded, which is the tag gate doing exactly what `CLEANUP.md` claims. Two `CLEANUP.md` claims that all legacy candidates print `not found` "on a fresh run" were imprecise and now state the real condition, an account that never ran an earlier version.

**One operational note for anyone re-running this.** `5.2`'s plan step takes 146s, and it runs twice, once for the dry run and once inside the delete pass. In an account carrying legacy resources the notebook exceeds ten minutes end to end. Run it detached rather than under a ten-minute command timeout.

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

Three findings, one still open:

- **`CLAUDE.md` is gitignored** at `.gitignore:59`, so the rewrite is local-only and no one who clones the repository gets it. Whether that file should ship is a question for the repository owner, not something this phase should decide. Still open.
- **The shared package printed deleted demo names.** `retrieval_setup.py:283` printed "Demo 01 readiness report:", which every Lab 1 run showed a participant, and `graph_setup.py:425` and `:465` printed "Demo 06 is not ready:" and "Demo 06 graph is ready." Resolved: every `Demo NN` string in `workshop/` now names the lab that owns the thing, and the last one outside the package, the Gateway target description in `deployment-tools/gateway_target.json`, reads "Lab 5" too. The `demo06-*` AWS resource identifiers are deliberately unchanged, because the teardown tag gate and `booking_agent.py:34` both key on them.
- **A stale import silently disabled nine tests, and three documents had written the symptom down as expected behavior.** `deployment-tools/test_runtime_integration.py` still did a bare `import contracts` after Phase 3 moved that module into the shared package, so the file died on collection. `05-agentcore-deploy/README.md`, `deployment-tools/README.md`, and `CLAUDE.md` all explained the failure as missing Runtime dependencies and instructed the reader to name `test_workshop_cleanup.py` explicitly to avoid it. That explanation was wrong: `05-agentcore-deploy/requirements.txt:11-12` declares `bedrock-agentcore` and `mcp` for exactly this reason, with a comment saying so. Fixed to `from workshop import contracts`, and a bare `pytest` in that directory now reports **29 passed**, not a collection error. The nine recovered tests are load-bearing, covering Gateway fail-closed discovery, the `request_id` hook, read-secret-only configuration, canonical UUID handling, the grounding prompt, and image exclusion. Lesson: a documented workaround is a place to look for a bug, not evidence there is not one.

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

## Post-rebuild quality review

Run on 2026-08-13, after Phases 1 through 7, 9, and 10 were marked Done. Eight
read-only reviews, one per lab plus one cross-cutting pass, each reading the
notebooks, the READMEs, and the code the lab actually executes, and verifying
claims against the tree rather than against this plan.

Two reviewers read Phases 0 and 8 as still Pending and drew conclusions from
that. Both were wrong: Phase 8 is Done, with a live deploy of Runtime
`HotelBookingAgent-i6Jg838kmO`, four passing smoke questions, and a verified
two-half teardown, and Phase 0's numbers were measured directly from the
finished notebooks. Phase 11, the rehearsal, is the only one genuinely
outstanding. Findings that rested on the Pending reading are struck below.

Status values: `open`, `fixed`, `deferred` (real but out of scope for this pass),
`wontfix` (reviewed and judged correct as written).

### Cross-cutting themes

Four patterns recur across labs and are cheaper to fix as one sweep than lab by
lab.

1. **Deleted-demo naming leaks into participant-visible output.** Labs 1, 4, 5,
   and 6 plus three shared modules print `Demo 01`, `Demo 06`, `Demo 08`, or
   `Module 1` to the participant. Real identifiers in seeded data and
   provisioned infrastructure keep their names: the `Rule` node id
   `demo-06-maximum-guests`, the `demo06_*` constraint names, the `demo06-`
   Gateway tool prefix, and the `demo08-` memory namespace. Free-text English
   prose does not.
2. **The setup path has four compounding gaps** in a participant's first thirty
   minutes: no `git clone`, no corpus unzip, an APOC step that is impossible on
   Aura, and a `.env.example` still naming deleted demos.
3. **`NEO4J_DATABASE` is required by three modules and defaulted by two**, so a
   `.env` without it gives a green Lab 1 and a red Lab 2.
4. **Em-dashes survive in ten live files**, against a repo-wide style rule, with
   the highest-visibility instances in the shared package and in participant
   output from `workshop_cleanup.py`.

### Lab 0, `00-setup/`

| ID | Finding | Where | Status |
|---|---|---|---|
| L0-B1 | Tells the participant to install APOC on Aura, which is impossible; APOC Core is preinstalled. Verified live: 162 `apoc.*` procedures with no such step performed | `00-setup/README.md:34,10,156` | fixed |
| L0-B2 | No `git clone` step anywhere in the setup path | `00-setup/README.md` | fixed |
| L0-B3 | `.env.example` still names `Demo 01 Graph-RAG`, `01-graphrag-demo/`, `Demo 06 AgentCore deploy`, `Demo 09 Neo4j MCP`, and two READMEs send participants into it | `.env.example`, `00-setup/README.md:43`, `README.md:232` | fixed |
| L0-Q1 | Python floor documented but not enforced by the check script | `00-setup/README.md:82` | fixed |
| L0-Q2 | `load_dotenv(".env")` is relative, so the check fails when run from anywhere but the repo root | `00-setup/README.md:87` | fixed |
| L0-Q3 | Failure-table row contradicts the script's own fallback | `00-setup/README.md:155` vs `:88,:146` | fixed |
| L0-N1 | "reads the graph" is false for the check script | `00-setup/README.md:79` | fixed |
| L0-N2 | Heading diverges from the `## Troubleshooting` the other six labs use | `00-setup/README.md:150` | fixed |

### Lab 1, `01-graph-build/`

| ID | Finding | Where | Status |
|---|---|---|---|
| L1-B1 | No corpus unzip step in the notebook. `data/` is gitignored and `git ls-files` returns nothing, so the only instruction sits in the README | `1.1_build_graph.ipynb` cell 1, `.gitignore:20-21` | fixed |
| L1-B2 | Cell 8's assertion misdiagnoses a missing `data/` | `1.1_build_graph.ipynb` cell 8 | fixed |
| L1-B3 | Cell 10 catches `ReadinessError` and proceeds into a doomed fifteen-minute build. `prepare_graph.py:76-80` has the correct handling the notebook lacks | `1.1_build_graph.ipynb` cell 10 | fixed |
| L1-Q1 | Cell 16 prints hardcoded claims it never verifies | `1.1_build_graph.ipynb` cell 16 | fixed |
| L1-Q2 | Cell 6's schema table drops the descriptions | `1.1_build_graph.ipynb` cell 6 | fixed |
| L1-Q3 | Cell 18 has no skip message | `1.1_build_graph.ipynb` cell 18 | fixed |
| L1-Q4 | `report()` only runs when `NEEDS_BUILD` | `graph_builder.py:250-317` | fixed |
| L1-N1 | Deleted-demo strings and em-dashes in participant output | `graph_builder.py:397,315,349,328,336,403,235,50-51`; `prepare_graph.py:3,40,86` | fixed |

### Lab 2, `02-retrieval/`

| ID | Finding | Where | Status |
|---|---|---|---|
| L2-B1 | The two retrievers run on different questions about different hotels in different cities at different `top_k`, so the lab's central comparison is not a comparison. Cell 12's "Both retrievers found the same chunks" is false as written. Root cause: the code was lifted verbatim from `retrieval_patterns.ipynb` cells 10 and 14 and the Phase 5 reframing rewrote only the markdown | `2.1_vector_retrievers.ipynb` cells 9, 11, 12 | fixed |
| L2-B2 | The delta is truncated out of the output. `show_results` previews 700 characters, the formatter puts the ~7300-character chunk first, so `hotel` and `related` never render | `2.1_vector_retrievers.ipynb` cells 7, 11 | fixed |
| L2-B3 | Cell 12 and the README claim a `hotel_id` the traversal does not project | `2.1` cell 11, `02-retrieval/README.md:38` | fixed |
| L2-B4 | Cell 0 and the README name the wrong pair for pattern 1. The code runs `VectorRetriever` against `HybridRetriever`, which is what the spec asked for; the framing says otherwise | `2.2_fulltext_retrievers.ipynb` cell 0, `README.md:27` | fixed |
| L2-B5 | `NEO4J_DATABASE` is required by cell 11 but absent from the readiness guard, and the resulting `ValueError` lands outside the friendly `try` | `2.2` cells 3, 11; `workshop/contracts.py:37-43` | fixed at source, SH-4 |
| L2-Q1 | The abstention close never shows the empty evidence, and `GROUNDING_INSTRUCTIONS`, the lever actually producing the refusal, is imported but never displayed. The README meanwhile claims no refusal prompt pattern is in this lab | `2.2` cells 15-18, `README.md` | fixed |
| L2-Q2 | "the traversal from 2.1" is materially different from the shared retriever's traversal | `2.2` cell 10, `README.md:44` | fixed |
| L2-Q3 | Cell 12 promises policies the 12-item cap will often slice off | `2.1` cells 11, 12 | fixed |
| L2-Q4 | The `60611` delta needs a printed rank verdict, not ten 700-character blobs | `2.2` cell 9 | fixed |
| L2-Q5 | Cell 11 re-runs a readiness check twice already done and is close to filler | `2.2` cell 11 | fixed |
| L2-Q6 | The shared preamble prints an embedding message that is false for `2.3` | `2.3_text2cypher.ipynb` cell 3 | fixed |
| L2-Q7 | `2.2`'s handoff describes what cell 16 already did; `2.3` has no Next pointer | `2.2` cell 18, `2.3` close | fixed |
| L2-Q8 | Cell 11's traversal uses a hard `MATCH`, so rows drop silently | `2.1` cell 11 | fixed |

### Lab 3, `03-agents-and-tools/`

| ID | Finding | Where | Status |
|---|---|---|---|
| L3-B1 | Five of seven agents are constructed with no `model=`, so they run Strands' default `global.anthropic.claude-sonnet-4-6`, not the standardized `us.anthropic.claude-sonnet-5`. Verified against the lab's own venv | `3.1_strands_primer.ipynb` cells 3, 5, 12, 14, 18 | fixed |
| L3-B2 | Cell 0 tells the participant to skim | `3.1` cell 0, `README.md:18` | fixed |
| L3-B3 | Cells 3 and 7 both bind `agent`, so re-running out of order silently swaps which agent answers | `3.1` cells 3, 7 | fixed |
| L3-Q1 | Cell 21's Summary precedes cell 22's section 6 | `3.1` cells 21, 22 | fixed |
| L3-Q2 | "exactly two pieces" then takes three | `3.1` cells 22, 23; `README.md:77,119` | fixed |
| L3-Q3 | README claims construction happens outside the guard; it does not | `README.md:99` | fixed |
| L3-Q4 | README's troubleshooting advice is wrong | `README.md:146` | fixed |
| L3-Q5 | Four places claim Lab 5 carries `hotel_agent`; Lab 5 constructs an unnamed `Agent` | `README.md:5,16,34,89` | verified, no change needed |
| L3-N1 | Notebook metadata says 3.11.0 | `3.1` metadata | fixed |

### Lab 4, `04-grounded-write/`

| ID | Finding | Where | Status |
|---|---|---|---|
| L4-B1 | Agent output prints twice. Strands installs `PrintingCallbackHandler` by default, so the surrounding `print` renders `AgentResult.__str__` again | `4.1_reservation_write.ipynb` cells 10, 16 | fixed |
| L4-B2 | Cells 12 and 14 share `REQUEST_ID`, muddying the idempotency demonstration | `4.1` cells 12, 14 | fixed |
| L4-B3 | Cells 3 and 7 build drivers without `notifications_min_severity="OFF"`, so `01N51`/`01N52` warnings surface. The shared package sets it; the notebook does not | `4.1` cells 3, 7 | fixed |
| L4-Q1 | "two changes" is three | `4.1` cell 6 | fixed |
| L4-Q2 | The idempotency proof omits the string-identity check | `4.1` cell 11 | fixed |
| L4-Q3 | The duplicate=false argument is omitted | `4.1` cell 13 | fixed |
| L4-Q4 | Delivery arithmetic is wrong, in the notebook and again in the README | `4.1` cell 18, `README.md:237` | fixed |
| L4-Q5 | README credits `conftest.py` with a job it does not do; `collect_ignore_glob` names two directories that live in Lab 5, making it a no-op | `README.md:211`, `conftest.py:12` | fixed |
| L4-Q6 | Folder tree omits `01_hybrid_retrieval.ipynb` | `README.md:249-260` | fixed |
| L4-N1 | `"Hotel is not a prepared Demo 06 fixture."` is participant-visible | `workshop/reservation_command.py:432` | fixed |

### Lab 5, `05-agentcore-deploy/`

| ID | Finding | Where | Status |
|---|---|---|---|
| L5-B1 | The four smoke tests assert nothing, so a hallucinating agent or a Lambda whose `workshop` import fails still produces a green notebook. Phase 8 confirmed all four by reading the output, which is why this did not bite, but the automated path cannot fail | `5.1_agentcore_deploy.ipynb` cells 13-17 | fixed |
| L5-B2 | Cells 5 and 7 are unguarded, so `--labs 5 --include-deploy` fails rather than skips, contradicting `new-content.md:125`. Cell 7 deletes `.bedrock_agentcore.yaml` even when nothing is deployed | `5.1` cells 5, 7 | fixed |
| L5-B3 | `5.1` never persists `AGENT_RUNTIME_ARN`, so `5.3`, registered `deploys_resources=True` and running in its own kernel, reports Passed having done nothing. `5.3` also calls bare `load_dotenv()` with no repo-root walk | `5.1` cell 9, `5.3` cell 1, `setup/run_notebooks.py:131-132` | fixed |
| L5-B4 | The CodeBuild source bucket `bedrock-agentcore-codebuild-sources-<account>-<region>` is created by the toolkit, never tagged, never deleted, and never mentioned. `workshop_cleanup.py` has no S3 discoverer, so `5.2` cell 10's "leaves nothing behind" is untrue | `workshop_cleanup.py`, `5.2` cell 10, `CLEANUP.md` | fixed |
| L5-B5 | The README documents folder-prefixed `entrypoint` and `requirements_file` that contradict the notebook's bare-name call after the chdir. Following the README makes the toolkit generate its own Dockerfile | `README.md:182-204` | fixed |
| L5-Q1 | No cost figure anywhere. Four places say "billable" and none says what it costs | `README.md:26-30`, root `README.md:180,210` | fixed |
| L5-Q2 | `5.2` cell 3's dry run prints roughly twenty irrelevant SKIP lines | `5.2` cell 3 | fixed |
| L5-Q3 | `5.2` has no closing "you are done", no breadcrumb, no environment cell, and a Title Case title | `5.2` | fixed |
| L5-Q4 | ~~Stale build-status claims~~ | `README.md:47,332`, root `README.md:49` | wontfix, the claims match Phase 8's record |
| L5-Q5 | README says Python 3.11+; the floor is 3.12+ | `README.md:114` | fixed |
| L5-Q6 | Folder tree omits `5.1` and `5.3` | `README.md:300-323` | fixed |
| L5-N1 | Deleted-demo strings and em-dashes in participant output | `workshop_cleanup.py:3,57-85,106-112,183,461,670,870,895`; `booking_agent.py:3` | fixed |
| L5-N2 | `.bedrock_agentcore.yaml` is in the working tree holding a real account ID, a live runtime ARN, and an absolute home path. Gitignored and deleted by `5.1` cell 7, so nothing has leaked, but it should not be on screen during a shared session | `deployment-tools/.bedrock_agentcore.yaml` | fixed |

### Lab 6, `06-memory/`

| ID | Finding | Where | Status |
|---|---|---|---|
| L6-B1 | An interrupted run leaks an orphan `Preference` that cleanup can never find, because `workshop_owner` is stamped only by the second-to-last cell while the node is created in cell 7. `README.md:118` promises the opposite. The fix is available: the node already carries a `hotels-demo08-` category prefix | `cleanup_memory.py:65-71`, `README.md:118`, notebook cell 7 | fixed |
| L6-B2 | "the current Module 1 graph does not assign stable hotel ids" is both a renumber leftover and factually stale; Lab 1 stamps them now | `memory_helpers.py:93` | fixed |
| L6-B3 | "keeps this module focused on Neo4j" in participant prose | notebook cell 4 | fixed |
| L6-Q1 | The provenance payoff does not land: the thesis promises three questions and section 5 answers two, the markdown never says this is the payoff, the output is a flat five-line dump with no direction, and no Neo4j Browser query is offered so the participant never sees the subgraph | notebook cells 0, 10, 11; `README.md:43` | fixed |
| L6-Q2 | Actor isolation is demonstrated against an actor with no data rather than different data, so the negative result is over-determined. The result line is hardcoded prose, not a count. The isolation query is buried in a helper while the less important provenance query is shown inline | notebook cells 8, 9; `memory_helpers.py:312-326` | fixed |
| L6-Q3 | Two rows of the managed-store table overstate: raw AgentCore events are immediately recallable, and "managed extraction" is a choice this lab made via `ExtractorType.NONE`, not a property of the service | notebook cell 14 | fixed |
| L6-Q4 | Renumber and dead-plan debris: five `Demo 08 plan` citations, `Demo 06's convention`, a `Lab_5_Agent_Memory` reference that now collides with this repo's Lab 5, two `Phase 1` labels, and 3.11.0 notebook metadata. Also the prefix rationale in `README.md:120` is wrong, and nothing anywhere explains why a lab numbered 6 stamps `08` | `memory_helpers.py`, `test_memory_helpers.py`, `smoke_test.py`, `README.md:120` | fixed |
| L6-Q5 | Cleanup is workshop-wide, not run-scoped, and the module docstring says otherwise. On a shared instance it deletes other participants' in-flight records | `cleanup_memory.py:5` | fixed |
| L6-Q6 | The test guarding the strongest claim asserts a variable name, while the mechanism that actually protects the hotel graph has no test | `test_memory_helpers.py:334-344`, `cleanup_memory.py:91,112-118` | fixed |
| L6-Q7 | The lab closes the workshop by stopping. The notebook's last line is a bash command; the README is the only lab README with no License and no footer | notebook close, `README.md:153` | fixed |
| L6-Q8 | "whose closing step seeds the fixture Hotel" misdescribes Lab 1, which extracts the hotel and then stamps an id onto it | `README.md:137` | fixed |
| L6-X1 | `HERO_HOTEL_NAME` is defined twice, in `memory_helpers.py:95` and `workshop/graph_setup.py:27` | both | fixed |

### Shared package and repo root

| ID | Finding | Where | Status |
|---|---|---|---|
| SH-1 | `RULE_REJECTION_MESSAGE` and `RULE_STEERING_MESSAGE` hardcode the number 10 while `contracts.MAX_GUESTS` is imported two lines above and `_rule_problems` compares against it | `workshop/graph_setup.py:31-32,23,311-312` | fixed |
| SH-2 | Deleted-demo strings in module docstrings and participant output | `retrieval_setup.py:283,3-7`; `graph_setup.py:3-7,228`; `hybrid_retrieval.py:3,184`; `reservation_command.py:432` | fixed |
| SH-3 | Em-dash on Lab 4's read path | `graph_connection.py:6` | fixed |
| SH-4 | `Neo4jConfig.from_environment` hard-requires `NEO4J_DATABASE` while two other modules default it to `neo4j`. Resolve once here rather than patching three notebooks' guard tuples | `workshop/contracts.py:37-43` | fixed |
| SH-5 | `# Demo 08` comment in the notebook registry, the file Phase 10 swept | `setup/run_notebooks.py:19` | fixed |
| SH-6 | Root README: stale build-status forward reference, "Run a lab" omits the unzip, nbstripout instructions use `pip` not `uv`, points at the stale `.env.example`, repeats the impossible APOC step | `README.md:49,158-164,212-221,232,254-257` | fixed, one clause disproved |
| SH-7 | `workshop-delivery/architecture.md:79` lists only `2.1` in the Lab 2 box; `2.2` and `2.3` are missing | `architecture.md:79` | disproved |
| SH-8 | `new-content.md:280` lists `02-retrieval/README.md` as still saying Python 3.9+; it says 3.12+. `new-content.md:174` claims Lab 6 uses Bedrock for reasoning; it uses embeddings only | `new-content.md` | fixed |

| SH-9 | `.gitignore:93` negates the blanket `*.zip` rule through `01-graphrag-demo/hotel-faqs.zip`, a path that no longer exists. The corpus zip is still tracked only because Git does not re-apply ignore rules to tracked files, so any `git rm --cached` and re-add silently drops the whole source corpus. Lines 74-75 also name a pruned demo | `.gitignore:74-75,92-93` | fixed |
| SH-10 | Both PEP 723 headers declare `requires-python = ">=3.10"` while the package they install editable declares `>=3.12`. Latent resolution failure in the repository's own acceptance command | `setup/run_notebooks.py:3`, `setup/provision_agentcore.py:3` | fixed |
| SH-11 | Two independent Nova embedder classes with byte-identical request payloads, and two verbatim copies of `BEDROCK_CONFIG`. They agree today only because both read the same constants. This is the exact write-path/read-path divergence the package exists to prevent | `bedrock_providers.py:40,85`, `hybrid_retrieval.py:29,118` | fixed |
| SH-12 | The `neo4j` pin disagrees across four files. The deployed Runtime and the reservation Lambda require 6.x while local labs may resolve 5.28, so the shared write path is exercised locally against a driver major version it never meets in production | `workshop/pyproject.toml:17`, `run_notebooks.py:13`, `agent_requirements.txt:5`, `lambda_tools/.../requirements.txt:1` | fixed |
| SH-13 | `booking_agent.py` imports `bedrock_agentcore` and `mcp`; neither is in the lab's `requirements.txt`, and `mcp` is not in `agent_requirements.txt` either, arriving only transitively | `05-agentcore-deploy/requirements.txt`, `agent_requirements.txt` | fixed |
| SH-14 | `architecture.md:584-586` claims the 3.11+ badges are gone from all seven lab READMEs, inside a section headed "since resolved". One is not gone. The document also still carries a DRAFT header | `architecture.md:1,584-586` | fixed |
| SH-15 | `CLAUDE.md` says every lab folder keeps its own `requirements.txt` and `.venv`. `00-setup/` correctly has neither | `CLAUDE.md` | fixed |
| SH-16 | `new-questions.md` is a pre-rebuild design Q&A with six empty `**Response:**` fields and one unanswered question to the reader, sitting untracked in the repo root next to the two live spec docs and indistinguishable from them by name | `new-questions.md` | fixed |
| SH-17 | `images/why-ai-agents-fail-six-demos-progressive-flow.png` is referenced by nothing and its filename uses retired vocabulary | `images/` | fixed |
| SH-18 | `apply_demo6_graph()` is participant-visible in Lab 1 Step 7 and Lab 4, across eleven call sites. Recommend renaming to `apply_lab4_fixtures()`. The graph data identifiers stay: `demo-06-maximum-guests`, `demo6_fixture`, the three `demo06_*` constraints, and the `demo06` AWS prefix are all load-bearing for already-built graphs or for teardown | `graph_setup.py:326` and eleven call sites | fixed |

### Findings the review disproved

Several items both spec documents list as outstanding are already done, and leaving
them marked open degrades the plan as a record. Two more were disproved during the fix
pass itself and are recorded here rather than left as false findings.

| Claimed outstanding | Actual state |
|---|---|
| SH-6's clause "Run a lab omits the unzip" | False. `1.1_build_graph.ipynb` cell 2 already auto-extracted with `zipfile` and skipped when already extracted. Chasing it did surface a real adjacent bug: `prepare_graph.py` never extracted, so the documented script path dead-ended on a fresh clone. Fixed with `ensure_corpus_extracted()` called first in `main()` |
| SH-7, `architecture.md:79` lists only `2.1` in the Lab 2 box | False. Lines 80 through 82 list `2.1`, `2.2`, and `2.3`, with `2.3` marked optional |
| `workshop-delivery/README.md` is still an eleven-demo document with audience tracks | Already a clean 139-line six-lab facilitator guide |
| The root README's build-status note claims `5.1` and `5.3` are still being authored | `README.md:49` is accurate as written |
| `04-grounded-write/README.md:241` names an old model | Already says Sonnet 5 |
| Phase 8 has never been validated against real AWS, so Lab 5 is unproven end to end | Phase 8 is Done. A live run deployed Runtime `HotelBookingAgent-i6Jg838kmO`, passed all four smoke questions with `tools_used` showing in-process retrieval alongside a Gateway write, and tore down 17 resources verified gone by the Resource Groups Tagging API |
| Phase 0 never produced timing numbers | Superseded but measured. Seven notebooks total 311.2s of machine execution, per-notebook figures recorded. Machine time is a floor, not a participant budget, which is what Phase 11 still owes |
| Both READMEs' build-status notes are stale | Both are accurate as written and match Phase 8's validation record |

Verified correct and needing no change: the five embedding and index constants have
exactly one definition each, confirmed by identity at runtime; `contracts.py` imports
with no Neo4j or boto3 client and no environment variables; the fixture manifest ships
in the built wheel; all five quoted test counts and all ten quoted notebook cell counts
match the tree; the runner registry matches disk with correct gates on all three Lab 5
entries; `six-lab-path.svg` matches the six labs; and the model ID has a single
definition with no other Claude version named in any non-vendored file.

### Fix progress

Fixes are partitioned so no two owners touch the same file: one owner per lab
folder, and the shared package, the repo root, `setup/`, and
`workshop-delivery/` under a single owner. The shared-package changes land
first, because L2-B5 depends on SH-4.

| Wave | Scope | Status |
|---|---|---|
| R1 | Shared package, root README, `.env.example`, `setup/`, `workshop-delivery/` | done |
| R2 | Labs 0 and 1, Lab 2, Lab 3, Lab 4, Lab 5, Lab 6, in parallel | done |
| R3 | Re-run `setup/run_notebooks.py` and the four test suites | done, green |

Every finding above is closed. Four are closed as something other than "fixed":
SH-6's unzip clause and SH-7 are disproved, L3-Q5 was already true in the tree and
needed no edit, and L5-Q4 is `wontfix` because the build-status claims it called stale
match Phase 8's live validation record.

Two items were closed by their owner as deliberate deferrals, each with a reason:
`workshop_cleanup.py` keeps every legacy `TABLE_NAMES` / `LAMBDA_FUNCTIONS` /
`ROLE_NAMES` / `CONFIG_FILES` entry, because those are matching patterns and dropping
one strands a returning participant's real resources on their bill; the resulting SKIP
noise was handled under L5-Q2 instead. And the five "Demo 06" test docstrings that live
in `04-grounded-write/` were out of Lab 5's scope; Lab 4's owner cleared them.

### Items found during the fix pass, not on any finding list

| Item | Resolution |
|---|---|
| Lab 6 needs a **third** Bedrock model, `amazon.titan-embed-text-v2:0` at 1024 dimensions, and only `06-memory/README.md` said so. A participant who reached Lab 6 with two models enabled hit an access denial with nothing telling them why | Added to the root README's prerequisites and its Bedrock troubleshooting entry, to `00-setup/README.md`, and to `workshop-delivery/README.md`. All three now say access to one model proves nothing about the others |
| `CLAUDE.md` claimed a single `DEFAULT_MODEL_ID` definition in `bedrock_providers.py` that did not exist. Lab 3's owner hit this and escalated it: with nothing importable, five notebooks each restated the literal | Added `DEFAULT_MODEL_ID` and `default_model_id()`, which applies the `MODEL_ID` environment override, then repointed `2.2`, `3.1`, `4.1`, and `5.1` at it. `booking_agent.py` keeps its own copy on purpose: it ships into the container and its import surface is deliberately narrow |
| SH-12's remaining half. Removing the four restated deps from `run_notebooks.py` closed one source of the `neo4j` disagreement, but `workshop/pyproject.toml` still declared `>=5.28.0` while the Runtime and the Lambda pin `>=6.0.0` | Raised the package floor to `>=6.0.0,<7.0.0`. Every lab already resolved 6.2.0 in practice, including Lab 6 through `neo4j-agent-memory==0.5.0`, so the declaration now matches what actually installs and what production requires |
| `deployment-tools/.bedrock_agentcore.yaml` held a real AWS account id, a live runtime ARN, and an absolute home path | No leak: it is gitignored at `.gitignore:73` and `5.1` cell 7 deletes it as pre-flight. Recorded as L5-N2 so it is not left on screen during a shared session |

### R3 evidence

- `uv run setup/run_notebooks.py` with every credential stripped: **7 passed, 0 failed, 3 skipped**. The three skips are Lab 5's, behind `--include-deploy` and `--include-cleanup` as designed.
- All ten shipping notebooks parse, and every code cell compiles.
- Test suites: Lab 1 **12 passed**, Lab 4 **56 passed**, Lab 5 **29 passed** (20 plus the 9 in `deployment-tools/test_runtime_integration.py`, which now collect), Lab 6 **27 passed**. 124 total.

One caveat on Lab 4's suite: run inside a network-blocked sandbox it reports 1 failed,
because `test_seeded_rule_matches_the_contract` skips on credential *absence* rather
than reachability, and a root `.env` still supplies credentials the sandbox cannot use.
Unsandboxed it is 56 of 56. Not a lab defect, but it is why a sandboxed CI run would
look broken.

### Still outstanding

- **Phase 11, the rehearsal.** The only genuinely unfinished phase. Machine execution is measured at 311.2s across seven notebooks, and that is a floor, not a participant budget. A rehearsed per-lab time budget is what the facilitator guide still owes.
- **A live pass over Lab 2's new Cypher.** `2.1`'s traversal was rewritten under L2-Q3 and L2-Q8 into a scoped `CALL (hotel) { … }` subquery with a per-type name cap and a map projection over a possibly-null `hotel`. The offline gate proves it parses; it has not run against a database.
- **One Lab 6 run left on the shared Aura instance.** Lab 6's live acceptance run wrote 11 nodes under prefix `demo08-33d55968-`. It was left in place deliberately: `cleanup_memory.py` sweeps instance-wide, which is the exact L6-Q5 hazard, so deleting it is a decision for the instance's owner.
