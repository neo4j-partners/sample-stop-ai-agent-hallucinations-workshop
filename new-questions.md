# Open Questions: Six-Lab Workshop Rebuild

Review questions against `new-content.md` and `new-content-plan.md`, checked against the tree at commit `385ed30` on `extend-neo4j`. Each question lists the options, a recommendation, and a place to answer.

---

## 1. Teardown as a section cannot carry its own gate

**Finding.** The acceptance runner gates per notebook, not per section. `deploys_resources` and `deletes_resources` are `NotebookSpec` fields at `setup/run_notebooks.py:68-70`, checked at `:369-372` as:

```python
if notebook.deploys_resources and not include_deploy:
    reason = ...
elif notebook.deletes_resources and not include_cleanup:
    reason = ...
```

Phase 8 folds teardown into `5.1_agentcore_deploy.ipynb` as a closing section while "keeping its gate in the acceptance runner." A section cannot hold a gate. If `5.1` carries both flags, then `--labs 5 --include-deploy` alone skips the entire lab, including the deploy, which is the opposite of what that flag reads as meaning.

### Option A: Split teardown into its own notebook

`5.1_agentcore_deploy.ipynb` with `deploys_resources=True`, `5.2_teardown.ipynb` with `deletes_resources=True`, and the optional walkthrough becomes `5.3`. Both gates keep their current meaning and either can run alone.

### Option B: One notebook, both flags

`5.1` carries `deploys_resources=True` and `deletes_resources=True`. Deploy and teardown are inseparable in the runner, so no rehearsal can leave resources running. The cost is that `--include-deploy` alone becomes a silent no-op for Lab 5, and the runner's help text has to say so.

**Recommendation: Option A.** The narrative goal, teardown lives where the resources are created, is satisfied by teardown being the last notebook in the Lab 5 folder. It does not require being the last cell of the deploy notebook. Option A also keeps a failed deploy recoverable: you can run teardown without re-running the deploy above it.

**Response:** Option A

---

## 2. Lab 4 is less new than the plan credits

**Finding.** `06-agentcore-boto3-demo/01_hybrid_retrieval.ipynb` is 17 cells and already covers the write path in cells 10 through 15:

| Cell | Content |
|---|---|
| 10-11 | A 15-guest request is rejected with no write |
| 12-13 | A valid request is recorded, and safe to retry |
| 14-15 | Inspect the reservation in your graph |

Phase 7 calls `4.1_reservation_write.ipynb` new, and the renumbering table's "Built from" column for `04-grounded-write/` lists only `reservation_command.py`, `contracts.py`, and `graph_setup.py`. The notebook material is not credited. Of the four cases Phase 7 specifies, three already exist as cells. Only the unknown-hotel rejection is genuinely new.

### Option A: Split `01_hybrid_retrieval.ipynb` across Labs 2 and 4

Cells 0 through 9 become the source for `2.2_fulltext_retrievers.ipynb`, including the abstention close. Cells 10 through 16 become the spine of `4.1_reservation_write.ipynb`, with the unknown-hotel case and the Lab 3 agent wiring added. Update the "Built from" table to name the notebook.

### Option B: Author `4.1` fresh, agent-first

Write `4.1` starting from the Lab 3 agent and add `create_reservation_request` as a tool, so every case runs through an agent turn rather than through a direct command call. Cells 10 through 15 become reference material rather than the source.

### Option C: Split the notebook, wrap it in the agent

Take Option A's mechanics and Option B's framing. Cells 0 through 9 go to `2.2_fulltext_retrievers.ipynb`. Cells 10 through 16 carry forward into `4.1_reservation_write.ipynb` as the verification cells, because they are already correct and tested. `4.1` then opens by adding `create_reservation_request` to the Lab 3 agent, so each case runs as an agent turn with the existing cells confirming what landed in the graph. The unknown-hotel case is the only new authoring. Update the "Built from" table to name the notebook.

**Recommendation: Option C.** Option A alone leaves the lab reading as a script calling a function, which undercuts the point that an agent is being trusted with a real action. Option B alone discards three working, tested cells to rewrite them. Option C keeps the tested assertions and puts the agent in front of them. Whichever option you pick, correct the "Built from" table, since the plan currently understates what exists and will lead whoever picks up Phase 7 to rewrite working cells.

**Response:**Option C

---

## 3. The Strands primer already spends Lab 4's punchline

**Finding.** `00-getting-started/getting_started_strands.ipynb` already teaches both of Lab 4's rejection cases, from Python fixtures rather than from the graph:

- Cells 14-16: a lifecycle hook section printing `=== Without hook: books 15 guests (no protection) ===` then `=== With hook: BLOCKS 15 guests ===`.
- Cells 18-20: a validation section printing `=== Valid query ===` then `=== Invalid query (hotel does not exist) ===`.

Lab 4's argument is that the same guest limit comes from a `Rule` node in the graph instead of a Python constant, which the spec calls "the stronger version of the same point." That comparison lands only if the participant has not already watched the weaker version twenty minutes earlier and moved on.

### Option A: Keep both primer sections as the deliberate setup for Lab 4

Frame cells 14-16 explicitly as the fixture version, then have Lab 4 open by pointing at it: the hook worked, and here is why a hardcoded `10` in Python is the wrong home for a business rule. The repetition becomes the argument.

### Option B: Cut the guest-limit hook from the primer

Replace it with a hook that demonstrates the lifecycle mechanism on something outside Lab 4's territory, for example logging or timing a tool call, and keep the 15-guest case exclusively for Lab 4. The primer still teaches hooks; Lab 4 keeps the reveal.

**Recommendation: Option A.** Cutting it costs the primer its most legible hook example and creates work, while keeping it costs one paragraph of framing in Lab 4. The before-and-after contrast is genuinely stronger when the participant has run the fixture version themselves. This does require Lab 4's opening to name the primer explicitly, so it should be an item in Phase 7 rather than left implicit.

**Related open item.** This also answers most of "Which three tools open Lab 3" from `new-content.md`. If the primer keeps the hook and validation sections, its three tools are the Lab 2 retriever, a guest-limit-hooked booking tool, and a hotel-lookup validator, all inside the hotel domain and all pointing at Lab 4.

**Response:** Option A

---

## 4. Is retargeting `deploy_agentcore.ipynb` cheaper than authoring fresh?

**Finding.** The restored notebook is 43 cells. The retarget table in `new-content.md` deletes steps 1 through 3 (DynamoDB), step 4 (IAM), step 5 (six Lambdas plus the VPC Lambda), and steps 6 and 7 (Gateway and targets). That is roughly cells 6 through 23. Step 9's eight tests, cells 29 through 38, get replaced with four. About 26 of 43 cells go.

What survives is cells 0 through 5 (boto3 setup and recovery), cells 24 through 28 (`Runtime.configure` and `Runtime.launch`, plus the tagging cell), and cells 39 through 42 (variable display and verification, where cell 42 still reads "Verify all required variables are set for Module 7"). The recovery scaffolding at cell 5 loads existing DynamoDB resources, so it does not survive intact either.

### Option A: Retarget as the plan specifies

Delete the cells the table names, repoint step 8's `entrypoint`, `requirements_file`, and `env_vars`, swap the tests. Preserves the exact starter-toolkit invocation that is known to work, and the tagging cell verbatim.

### Option B: Author `5.1` fresh, lifting step 8 and the tagging cell

Write a new notebook whose shape is: confirm `provision_agentcore.py` has run, configure and launch the Runtime, tag, run four smoke tests. Copy cells 24 through 28 across unchanged. Roughly the same amount of surviving code, without inheriting DynamoDB-shaped recovery logic or a stale "Module 7" reference.

**Recommendation: Option B.** The plan's own framing is that "the deploy mechanism is intact, the deploy target changed." The mechanism is five cells. Everything else in the restored notebook was built for a target that no longer exists, and editing 26 cells out of a notebook is more error-prone than writing 15 fresh ones around 5 copied cells. Keep the restored notebook in the working tree as the reference while authoring.

**Response:** Option B.

---

## 5. The shared package collides with the Lambda zip

**Finding.** `setup/provision_agentcore.py:63` declares:

```python
SHARED_MODULES = ("reservation_command.py", "contracts.py")
```

These are copied flat into the deployment zip at `build_lambda_zip()`, `:578-634`. The handler at `deployment-tools/lambda_tools/create_reservation_request/lambda_function.py:5` then does:

```python
from reservation_command import handler
```

Phase 3 moves both modules into `workshop/` and requires that nothing "adds a sibling lab folder to the import path." If the imports become `from workshop.contracts import ...`, the flat copy breaks. If they stay flat, `workshop/` is a package whose members import each other by bare module name, which only works because of where they sit.

### Option A: Vendor the package into the zip

`build_lambda_zip()` copies the `workshop/` directory into the zip root instead of two files, and the handler becomes `from workshop.reservation_command import handler`. Imports are consistent everywhere, and the zip grows by whatever else is in `workshop/`.

### Option B: Keep the Lambda's imports flat

`workshop/` uses relative imports internally (`from .contracts import ...`), and `build_lambda_zip()` keeps copying named files, updated to their new paths. The handler is unchanged. Lower risk to a working deploy path, at the cost of the zip builder needing a hardcoded list that drifts when `reservation_command.py` grows a new dependency.

**Recommendation: Option A.** The whole point of Phase 3 is one definition and one import path, and Option B leaves a second, path-dependent way to load the same modules. Vendoring the directory also removes the maintenance hazard: a new import inside `reservation_command.py` breaks the Lambda at runtime under Option B, and works under Option A. Either way, this belongs on the Phase 3 checklist explicitly, since Phase 3 currently does not mention the zip builder and Lane C would discover it during Phase 8.

**Response:** what is best practice?

---

## 6. Lab 2's split duplicates the shared setup three times

**Finding.** `01-graphrag-demo/retrieval_patterns.ipynb` is 22 cells, ordered:

| Cell | Content |
|---|---|
| 2 | Environment |
| 4 | Verify the prepared graph |
| 6 | The pinned hotel graph schema |
| 8 | Shared query embedding contract |
| 10 | Pattern 1: Vector retrieval |
| 12 | Pattern 2: Hybrid retrieval |
| 14 | Pattern 3: Vector-Cypher |
| 16 | Pattern 4: Text2Cypher |

The plan's split assigns patterns 1 and 3 to `2.1`, pattern 2 plus a new `HybridCypherRetriever` to `2.2`, and pattern 4 to `2.3`. Cells 2 through 8, four code cells of setup, then have to exist in all three notebooks.

Confirmed: cell 18, "Going further: HybridCypherRetriever," is markdown only, so `2.2`'s hybrid-cypher code does have to come from `01_hybrid_retrieval.ipynb` as the spec says.

### Option A: Duplicate the setup cells in each notebook

Each of the three notebooks opens with the same four cells. Every notebook stays self-contained and runnable in isolation, which is what participants and the acceptance runner both want. Four cells drift across three files.

### Option B: A `workshop` helper the notebooks import

One `connect_and_verify()` returning a driver and embedder, called in a single opening cell per notebook. One definition, and the pinned schema and embedding contract become printable from the package. The participant sees less of the wiring, which is part of the Lab 2 lesson.

### Option C: Duplicate what teaches, import what must match

Split the setup by whether the participant learns from watching it run. The graph-verification and schema-display cells are duplicated in all three notebooks, because watching them is part of the lab. The embedder is constructed from `workshop`, since `EMBEDDING_MODEL_ID`, `EMBEDDING_PURPOSE`, and `EMBEDDING_DIMENSIONS` must match what Lab 1 wrote to the graph. Two duplicated cells instead of four, and the values that break retrieval when they drift have one definition.

**Recommendation: Option C.** Option A duplicates the embedding constants, which is the one part of the setup where a silent mismatch returns wrong results rather than an error, and it is the same class of drift that already produced the duplicate index names this rebuild is fixing. Option B hides the graph verification, which is the cell that tells a participant whether Lab 1 actually succeeded. Option C keeps the visible parts visible and centralizes only the contract.

**Response:**

---

## 7. No deploy-gated notebook survives Phase 1

**Finding.** The only registry entry with `deploys_resources=True` is `07-agentcore-memory-demo/deploy_memory_agent.ipynb` at `setup/run_notebooks.py:127-128`, which Phase 1 deletes. `--include-deploy`'s help text at `:431` reads "Run lab 7, which creates or updates AWS resources." `deploy_agentcore.ipynb` is not in the registry at all.

Phase 2 says "keeping the deploy gate on Lab 5," which reads as repointing an existing entry. There is nothing to repoint. Registering a deploy-gated Lab 5 is a new entry plus a help-text change plus a docstring change.

### Option A: Phase 2 registers all seven lab entries at once

Phase 2 adds entries for labs 0 through 6, including a deploy-gated Lab 5 and a cleanup-gated teardown, pointing at paths that do not exist yet, and updates the help text and docstring. Each content lane then fills in its notebook. This is the alternative the plan's own contention section already suggests for the registry merge-conflict problem.

### Option B: Phase 8 owns the Lab 5 registration

Phase 2 prunes and repoints only what exists. Phase 8 adds the Lab 5 entries and fixes the flag help text as part of the deploy work.

**Recommendation: Option A.** It solves two listed problems at once: the registry becomes a merge-conflict hotspot precisely because five lanes each append to the same tuple, and the deploy gate has no owner. Registering all seven up front makes the registry read-mostly for every lane. It requires the runner to skip missing paths with a clear message rather than erroring, which is a small change to add to Phase 2.

**Response:**

---

## 8. The guest-consistency test decision lands in the wrong phase

**Finding.** `06-agentcore-boto3-demo/test_demo_guest_consistency.py` holds one test asserting the guest limit agrees across Demos 04, 05, and 06 by reading source files out of `04-neurosymbolic-demo/` and `05-steering-demo/`. Phase 1 deletes both of those. Phase 1's checklist says "Rewrite it against Lab 4's rule alone, or delete it and record why," but Lab 4 does not exist until Phase 7, so there is nothing to rewrite it against during Phase 1.

### Option A: Delete in Phase 1, re-add in Phase 7

Phase 1 deletes the file and records why in the commit message. Phase 7 gains a checklist item: add a test asserting the `Rule` node's limit matches what the notebook and any prompt text claim. The new test reads the graph rather than parsing source files, which is the stronger assertion anyway.

### Option B: Narrow it in place during Phase 1

Rewrite it now to assert only that `contracts.py` and `graph_setup.py` agree on the limit, dropping the two deleted sources. Nothing is lost and no phase has to remember to restore it.

### Option C: Narrow in Phase 1, extend in Phase 7

Phase 1 rewrites the test to assert that `contracts.py` and `graph_setup.py` agree on the limit, so it never goes red and never disappears. Phase 7 then adds a second assertion against the seeded `Rule` node itself, self-skipping when credentials are absent. The test covers source agreement offline and graph agreement when a graph exists.

**Recommendation: Option C.** The test's value is catching a limit that disagrees between two places, and two places still exist after the prune, so Option A throws away working coverage and bets on Phase 7 remembering to restore it. Option B stops at source-file comparison, which cannot catch the failure that actually matters: `contracts.py` says 10 and the `Rule` node in the participant's graph says something else. Option C keeps the offline assertion that guards every commit and adds the graph assertion where Lab 4 makes it meaningful.

**Response:**

---

## 9. Phase 11 tests the biggest risk last

**Finding.** The plan names the four-hour fit as its first risk and states that nothing before Phase 11 measures it. All three fallbacks mean unwinding merged work: dropping `2.3` discards a Phase 5 deliverable, folding Lab 3 into Lab 4 merges two lanes' output, and collapsing the retriever pairs guts Lab 2. Lab 5 alone is scoped at 30 to 45 minutes in the current README, and Lab 1's lite build is a confirmed 15 minutes.

### Option A: Rehearse only at Phase 11, as planned

Fewer moving parts, one measurement against the real artifacts. Accept that a miss costs rework.

### Option B: A timing probe before Phase 4

Time the existing `retrieval_patterns.ipynb`, `01_hybrid_retrieval.ipynb`, `getting_started_strands.ipynb`, and one deploy against the current tree. That produces a rough per-lab floor before any content is authored, so the Lab 2 and Lab 5 budgets are known while there is still cheap room to change scope.

### Option C: Probe only the two unknowns, before Phase 4

Time `retrieval_patterns.ipynb` and one full deploy-and-teardown cycle, and nothing else. Those are the two labs whose duration is both large and unmeasured. Lab 1's lite build is a confirmed 15 minutes, and Labs 3, 4, and 6 are small enough that estimates will do. Two measurements against the current tree, runnable in parallel with the serial spine because it touches no files.

**Recommendation: Option C.** Option A discovers the problem when the fallbacks are most expensive to apply. Option B times four notebooks, two of which you already have numbers for or can estimate, which turns a cheap probe into its own small phase and invites it to be skipped. Option C buys the Lab 2 and Lab 5 budgets for roughly an hour of wall clock, which is enough to know before Phase 5 whether `2.3` and the retriever pairs are affordable. Phase 11 then confirms rather than discovers.

**Response:**

---

## Two corrections to make before they reach a README

### The test count

`new-content.md` and the plan both say the write path has 54 passing tests. 54 is all of Demo 06:

| File | `def test_` count |
|---|---|
| `test_reservation_command.py` | 22 |
| `test_graph_setup.py` | 12 |
| `test_hybrid_retrieval.py` | 12 |
| `test_contracts.py` | 7 |
| `test_demo_guest_consistency.py` | 1 |
| **Total** | **54** |

The command plus its contracts is 29. Adding the graph fixtures makes 41.

**Recommendation.** Say "the command and its contracts are covered by 29 tests" where the claim is about the write path, and keep 54 only where the claim is about Demo 06 as a whole.

**Response:**

---

### The orphaned demo-local `.env`

`01-graphrag-demo/.env` exists and is gitignored at `.gitignore:46`. `git mv` will not carry it, so it stays behind at the old path while `01-graph-build/` inherits nothing. Since a demo-local `.env` takes precedence over the root one, whoever runs Phase 2 on this working tree will silently lose their per-demo overrides, and a stale copy will sit in an otherwise deleted directory.

**Recommendation.** Add an explicit Phase 2 item: move or delete `01-graphrag-demo/.env` by hand alongside the `git mv`, and note in the Phase 2 validation that untracked files need checking separately.

**Response:**
