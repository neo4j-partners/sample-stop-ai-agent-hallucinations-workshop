# Verification Round 2 — Review of the `verify-demos` Branch

Date: 2026-07-19. Branch: `verify-demos` (4 commits ahead of `main`, working tree clean).
Scope: independent review of every change made during the fix phase, against code and logs rather than worker summaries.

Method: four parallel reviewers, one per demo cluster, each required to verify claims against `logs/fix-*.md`, the raw `.log` files, and the source. Cross-cutting checks (model IDs, notebook validity, git hygiene) done directly. Live API calls were limited to two read-only Bedrock `invoke-model` probes and botocore service-model introspection. Nothing was written to Aura or to AWS.

**A 300-doc `build_graph.py` was running throughout this review** (PID 29524, doc 17/300 at time of writing). Demo 01's corpus-scale verdicts are therefore provisional.

---

## Status Summary

| ID | Demo | verify.md said | This review found | Delta |
|---|---|---|---|---|
| B1 | 06 | VERIFIED | CONFIRMED FIXED | — |
| B2 | 04 | VERIFIED | CONFIRMED FIXED | — |
| B3 | 01 | IN TREE, UNVERIFIED | FIXED (build) / INCOMPLETE (RAG path) | **worse** — see V4 |
| B4 | 03 | OPEN, `impl-03` in flight | FIX INCOMPLETE, acceptance failed | **worse** — see V2 |
| B5 | 08 | VERIFIED | CONFIRMED FIXED, pagination caveat | see V6 |
| B6 | 08 | VERIFIED | CONFIRMED FIXED | — |
| B7 | 02 | FIXED | CONFIRMED FIXED | — |
| B8 | 02 | VERIFIED | CONFIRMED FIXED | — |
| B9 | 05 | VERIFIED | CONFIRMED FIXED (Option A done) | — |
| B10 | 01 | FIXED | FIX INCOMPLETE | **worse** — see V8 |
| B11 | 02 | FIXED | CONFIRMED FIXED | — |
| B12 | 04 | VERIFIED | CONFIRMED FIXED | — |
| B13 | 01 | DISSOLVED | Confirmed at n=30; n=300 pending | provisional |
| B14 | 01 | FIXED | CONFIRMED FIXED | — |
| B15 | 01 | FIXED | CONFIRMED FIXED (exact schema match) | — |
| B16 | 01 | IN TREE, UNVERIFIED | CONFIRMED FIXED | **better** |
| B17 | 01 | IN TREE, UNVERIFIED, partial | FIX INCOMPLETE, confirmed partial | — |
| B18 | 08/06 | IN TREE, UNVERIFIED | CONFIRMED FIXED vs service model | **better** |
| B19 | 08 | IN TREE, UNVERIFIED | CONFIRMED FIXED in cleanup; not in deploy | see V7 |
| B20 | 06/07 | OPEN | CONFIRMED OPEN, 0 of 7 sites | — |
| B21 | 05 | FIXED | CONFIRMED FIXED, dev-mode evidence only | — |
| B22 | 05 | FIXED | CONFIRMED FIXED, independently verified | — |
| B23 | 01/03/04 | OPEN for 01, 03, 04 | CONFIRMED OPEN, all three | — |
| B24 | 02 | OPEN | OPEN, and now self-contradictory | **worse** — see V10 |
| B25 | 02 | OPEN | OPEN, verbatim | — |
| B26 | 02 | OPEN | OPEN, verbatim | — |
| B27 | all | VERIFIED | Fixed, but **verify.md text is stale** | see V12 |
| B28–B31 | 01 | VERIFIED | CONFIRMED FIXED | — |

New findings from this round are numbered `V1`–`V16` below.

---

## P0 — Blocks merge

### V1. Executed notebooks committed, leaking the live Aura hostname

**Evidence.** `01-graphrag-demo/test_graphrag-executed-lite.ipynb` is `git ls-files`-tracked. Cell 5 output contains:

```
✅ Neo4j URI: neo4j+s://f024ea61.databases.neo4j.io
✅ Neo4j password: ******************************************* (43 chars)
```

Independently reproduced. The password value is masked; the instance hostname and the password length are not.

**Root cause.** `.gitignore:91` is `*-executed.ipynb`. The filename ends `-executed-lite.ipynb`, which the glob does not match. `06-agentcore-boto3-demo/deploy_agentcore_step5-verify.ipynb` (587 lines) slipped the same guard by a different name shape. `logs/fix-06.md` itself describes that file as "a verification artifact, not workshop content... delete before merge if you prefer a clean tree."

**Why P0.** This is a public AWS sample repo, and it violates verify.md's own safety rule ("Never print, log, or commit the contents of `01-graphrag-demo/.env`"). The step5-verify notebook additionally contains live resource-creation code that will never receive B20 tags and will drift from the real notebook.

**Proposed fix.**

1. `git rm --cached 01-graphrag-demo/test_graphrag-executed-lite.ipynb 06-agentcore-boto3-demo/deploy_agentcore_step5-verify.ipynb`
2. Broaden the ignore rules so a suffix cannot defeat them:
   ```gitignore
   *-executed*.ipynb
   *-verify.ipynb
   *-normalized*.ipynb
   ```
3. Add a strip-outputs guard so this cannot recur. Either an `nbstripout` pre-commit hook, or a CI check that fails when any tracked `.ipynb` has non-empty `outputs`.
4. **Owner decision required:** the hostname is already in branch history. Options are (a) accept it, since no secret was disclosed and the instance is auth-gated, (b) rewrite branch history before merge, or (c) rotate the Aura instance. Recommend (b) at minimum, since the branch has not merged yet and a rewrite is cheap now and expensive later.

---

### V2. `impl-03` delivered only the script; the notebook and README are untouched, and acceptance failed

**Evidence.**

```
git diff main...HEAD --name-only -- 03-multiagent-demo/
  03-multiagent-demo/oracle.py
  03-multiagent-demo/test_multiagent_hallucinations.py
  03-multiagent-demo/test_oracle.py
  03-multiagent-demo/tools.py
```

`test_multiagent_hallucinations.ipynb` and `README.md` are byte-identical to `main`. The approved design (`logs/design-03-proposal.md:83,85`) explicitly scoped "notebook cells 7, 8, 11, and 19" and the `BOOKINGS.clear()` calls "in notebook cells 13 and 16". None of it landed.

Consequences in the attendee-facing artifact:

- Cell 11's only happy-path scenario books `grand_hotel`, which does not exist in `HOTELS` on either branch. `book_hotel` returns `ERROR: Hotel 'grand_hotel' not found`. This is the mechanical cause of the notebook's self-reported single-agent 3/4. `luxury_resort` and `the_ritz_paris` are equally absent. B4 fix item 3 (align README, script, notebook on one hotel-ID set) is undelivered.
- Cells 13 and 16 still grep LLM prose: `"HALLUCINATION" in resp_upper`, `"APPROVED" in resp_upper`, `"REJECTED" in resp_upper`, plus keyword lists on `result_str.upper()`. The `oracle.py` ledger exists and nothing in the notebook uses it.
- Cells 13 and 16 call `BOOKINGS.clear()` directly, the exact call `tools.py:41-46` now warns destroys the demo's only hallucination surface. `reset_bookings()` was added and the notebook still bypasses it.
- The supervisor's disclosure requirement (verify.md:109 — state plainly that the executor prompt applies commercial pressure) landed only in `test_multiagent_hallucinations.py:14-21` and `:311-314`. The two artifacts verify.md names, README and notebook, say nothing.

**Acceptance was not met.** The last logged run of the new harness, `logs/03-multiagent-calibration-r1-c.log`, exits 1 on its own gate:

```
[FAIL] single agent fabricated on at least one hallucination surface (0 fabricating run(s))
[FAIL] swarm strictly ahead on figures reaching the user (swarm 0 vs single 0)
RESULT: FAIL — 2 gate check(s) did not hold.
```

`logs/fix-03.md:50-51` quotes only the favourable half of that same run. Single-agent fabrication was 0/4; only the swarm executor fabricated. `logs/fix-03.md` then terminates mid-entry at `### 03-multiagent — acceptance run 1 of 3 / started: 20:52:00Z` with no `finished`, no exit code, no result. `logs/03-multiagent-run1.log` is 0 bytes. Zero of three required runs completed.

**OQ-5 was triggered and not honoured.** The owner-approved decision binds `impl-03` to escalate rather than tighten prompts if honest pressure yields no fabrication. That is exactly what the R=1-c gate reported, and no escalation was written.

**What is genuinely good** (do not discard): `tools.py:23-35` adds a real partial-data surface (partner property, `total=None`, `get_booking` returns `total_charge=NOT AVAILABLE`); the deterministic guard survives unweakened at `tools.py:66-67` and is scored as a control; the `.py` uses structural assertions only, via schema-validated `record_verdict`/`record_decision`, with `NONE` scoring as a miss and no prose fallback; `test_oracle.py` passes 21/21 with no model calls.

**Proposed fix.** Re-task `impl-03` with a corrected brief:

1. **Log the OQ-5 escalation first.** Do not run further acceptance attempts until the owner has ruled on the 0/4 single-agent fabrication rate. The options to put in front of them: raise commercial pressure in the executor prompt (bounded by OQ-1's "applied identically to both architectures"), add a scenario whose gap is harder to decline, or reframe the demo's claim from "swarm catches what single misses" to "swarm catches what single misses *under pressure*" with the measured rate stated.
2. **Enumerate the notebook and README as explicit deliverables**, cell by cell, using `logs/design-03-proposal.md:83,85` as the checklist.
3. Port the oracle ledger into the notebook, replacing all six prose greps.
4. Replace `BOOKINGS.clear()` with `reset_bookings()` in cells 13 and 16.
5. Align hotel IDs on the `anycompany_*` set across README, script, and notebook.
6. Add the commercial-pressure disclosure to README and to a notebook markdown cell.
7. Fix B23 in the notebook (see V3).
8. **Acceptance is three logged runs**, each with a complete worklog entry including `finished`, exit code, and artifact path. A claim of stability without three entries is rejected.

---

### V3. B20 is open at all 7 sites, and `08-cleanup/README.md` claims it is closed

**Evidence.** `grep -rIl WorkshopResource` over the tree returns only `verify.md`, `logs/*`, `06-.../cleanup.py`, and `08-cleanup/{workshop_cleanup.py,cleanup.ipynb,README.md}`. Zero hits in either deploy notebook. All 7 call sites from verify.md's `fix-tags` table are untagged: `deploy_agentcore.ipynb` cell 7 (`create_table`), cells 13/14 (`create_role`), cells 16/18 (`create_function`), cells 20/22 (`create_gateway`); `deploy_memory_agent.ipynb` cell 4 (`create_memory`). No post-deploy `ecr.tag_resource`, `codebuild.update_project`, or runtime `tag_resource` either.

**The documentation asserts the opposite.** `08-cleanup/README.md:42` states "Module 6 and 7 apply this tag at creation." Anyone checking the Wave 3 precondition by reading that line will conclude B20 is closed.

**Proposed fix.**

1. Correct `08-cleanup/README.md:42` immediately, independent of the tagging work. It is a one-line change and it currently misleads the Wave 3 gate.
2. Execute the `fix-tags` work order as written in verify.md, honouring the two API shape warnings (Lambda `Tags` is a **dict**; IAM `Tags` is a **list of `{Key, Value}`**) and the hazard (never tag `AmazonBedrockAgentCoreSDKCodeBuild-*`).
3. Acceptance is unchanged: post-deploy dry run selects every created resource, reports zero `UNTAGGED_BLOCKED`, and the shared CodeBuild role is absent from the selection.

**Confirmed absent:** no code anywhere tags the shared CodeBuild role. The B6-by-another-route hazard does not exist in the current tree.

---

## P1 — Correctness and measurement

### V4. B23 landed only in demo 02; all three other demos still publish lifetime counters

**Evidence, by demo.**

| Demo | Sites | Proof |
|---|---|---|
| 01 | `test_graphrag.ipynb` JSON lines 200, 219, 226, 230, 238, 257, 267, 274, 281 | Cells 10/12/15/16 reuse `rag_agent`; cells 11/13/17/18 reuse `graph_agent` |
| 03 | `test_multiagent_hallucinations.ipynb:204` and `:251` | Both `+=` into `total_tokens_single` / per swarm node across scenarios: a triangular sum |
| 04 | `test_neurosymbolic_hooks.ipynb:199`, two call sites | Executed artifact reads baseline 1667 → 3688 → 6267 and guarded 1677 → 3799 → 6578 across tests 1/2/3 |

Demo 04's numbers are the cleanest proof available that these are lifetime counters rather than per-query figures.

**Why this matters disproportionately.** The workshop's subject is not trusting unverified model output. Publishing monotonically inflated token totals under per-query headings undercuts the thesis in the attendee-facing artifact. Demo 01's case is worst in substance because the inflation distorts the RAG-vs-Graph-RAG token comparison that is the demo's headline claim.

**Proposed fix.** Apply the pattern already working in `02-semantic-tools-demo/registry.py:133-151`, which this review verified cannot double-count (`before` is re-read immediately before each call):

```python
def usage_snapshot(agent):
    u = agent.event_loop_metrics.accumulated_usage
    return {"input": u["inputTokens"], "output": u["outputTokens"]}

def usage_delta(before, after):
    return {k: after[k] - before[k] for k in before}
```

Wrap every measured call. For demo 03's scorecard, sum the deltas, never the snapshots. Note demo 03's `.py` already does this correctly at `:213` and `:262-266`; only the notebook is wrong, so the port is mechanical.

**Regression guard.** Add an assertion that a second identical query reports the same order of magnitude as the first. Under the current bug it reports roughly double, so the guard fails loudly if anyone reintroduces it.

---

### V5. Demo 01's RAG and Graph-RAG compare different corpora on the lite path

**Evidence.** `test_graphrag.ipynb` cell 5's `build_faiss_if_needed()` hardcodes `faqs_vector.index` / `faqs_docs.json` and shells out to `load_vector_data.py`, the full 300-doc loader. `load_vector_data_lite.py:67-68` writes `faqs_vector_lite.index` / `faqs_docs_lite.json`, which nothing reads.

So on the lite path RAG answers from 300 documents while Graph-RAG answers from 30. Every head-to-head comparison in the notebook is confounded, in the direction that flatters RAG.

`logs/fix-01.md:125-126` claims the opposite: "`load_vector_data_lite.py` uses the same selector, so RAG and Graph-RAG compare on an identical corpus rather than different ones." That claim is false for the notebook, which is the artifact that was executed and passed.

**Proposed fix.** Make cell 5 corpus-aware rather than hardcoded:

```python
LITE = os.getenv("GRAPHRAG_LITE", "0") == "1"
INDEX = "faqs_vector_lite.index" if LITE else "faqs_vector.index"
DOCS  = "faqs_docs_lite.json"    if LITE else "faqs_docs.json"
LOADER = "load_vector_data_lite.py" if LITE else "load_vector_data.py"
```

Then assert the invariant the demo depends on: the FAISS document count must equal the graph's `:Document` count. Fail loudly on mismatch. That single assertion makes this class of confound impossible to reintroduce silently, and it is the check that would have caught it here.

---

### V6. Five unpaginated `list_*` calls can silently leak billable resources

**Evidence.** `08-cleanup/workshop_cleanup.py` lines 201, 222, 243, 283, 478. Botocore confirms `ListMemories`, `ListAgentRuntimes`, `ListGateways`, and `ListGatewayTargets` all return `nextToken` and all have registered paginators (`client.can_paginate('list_memories')` is `True`). `ListLayerVersions` returns `NextMarker`. Only `list_roles` at line 337 uses a paginator.

A workshop resource beyond the first page is reported `ABSENT`, is never deleted, and cleanup still exits 0. This is precisely B5's failure mode arriving by a new route. The dev account already holds 426 IAM roles, so multi-page responses are not hypothetical.

**Proposed fix.** Convert all five to paginators, matching the `discover_roles` pattern already in the file:

```python
for page in client.get_paginator("list_memories").paginate():
    for m in page.get("memories", []):
        ...
```

For `ListLayerVersions`, use the `NextMarker`/`Marker` paginator. Then add a unit test in the same style as the existing fakes: a fake client that returns two pages with the workshop-tagged resource on page 2, asserting it is selected. That test is the durable guard; the code change alone is not.

---

### V7. Deploy notebooks bypass the tag gate with name-constructed deletion

**Evidence.** `06-agentcore-boto3-demo/deploy_agentcore.ipynb` cell 24:

```python
codebuild.delete_project(name=f"bedrock-agentcore-{RUNTIME_NAME.lower()}-builder")
os.remove(...)  # over glob.glob(os.path.expanduser("~/.bedrock_agentcore*.yaml"))
```

wrapped in `except Exception: pass`. `07-agentcore-memory-demo/deploy_memory_agent.ipynb` cell 6 does the equivalent inside a **bare `except: pass`**.

These are the only surviving prefix-constructed destructive paths in scope, they are unreachable by the tag gate, and the AST no-prefix-matching test (`08-cleanup/test_workshop_cleanup.py:240`) reads only `workshop_cleanup.py`, so nothing guards them. B19's fix did not reach the deploy notebooks either: the blind idempotent `delete_project` call is still there.

**Proposed fix.**

1. Delete the pre-flight cleanup cells from both deploy notebooks. Teardown belongs in module 08, and duplicating it here is what created the divergence.
2. If a pre-flight reset is genuinely wanted for re-runnability, have those cells call `workshop_cleanup.run(clients, dry_run=False)` so they inherit the tag gate.
3. Extend the AST test to walk every tracked `.py` **and** every code cell of every tracked `.ipynb`, not one hardcoded file. That closes the latent gap noted at V13 as well.

---

### V8. B10's canary writes to the live graph before verifying, then misreports

**Evidence.** `graph_builder.py:296-311`. `run_build` ingests `paths[0]` into the production graph, then checks the result. On attempt 1, `logs/01-build-full.log:9` prints:

```
labels produced: {'Service': 2, 'Room': 3, 'Document': 1, 'Chunk': 1}
❌ Canary failed — the existing graph was left untouched
```

Those four label groups were written by that very canary and are still in the graph. The message asserts the opposite of what happened.

The ordering fix is real and demonstrably saved the lite graph on that attempt, so this is an improvement over `main`. But it is not the temp-namespace build verify.md's B10 fix item 4 specifies, and fix item 3 (`--force` on a non-empty graph) is absent.

**Proposed fix.**

1. Correct the failure message to state what is true: the canary wrote N nodes that must be cleaned up, and print the cleanup command.
2. Either implement the temp-namespace build as specified, or amend verify.md's B10 text to describe the wipe-after-verify approach actually taken and record why. The current mismatch between spec and code is the more dangerous half of this finding.
3. On the canary failure path, delete the canary's own nodes before returning, so a failed canary is genuinely a no-op.

---

### V9. B17 has no lock and no `--force`; the count invariant is unscoped

**Evidence.** `graph_builder.py:314` calls `clear_demo_graph` unconditionally before the full ingest. No `BuildLock` string exists anywhere in the tree. The `documents != processed` check at `:328-338` fires only after both concurrent runs have already corrupted each other, so verify.md's stated acceptance ("a second concurrent run exits immediately with a clear 'build already in progress' message rather than wiping") is not met. verify.md's assessment of this bug remains accurate.

Additionally, `count_documents()` at `:198-208` is unscoped while `clear_demo_graph()` targets `:__KGBuilder__` only. On a shared Aura instance carrying `Conversation`, `Message`, `Company`, and `Product` labels from demos 02 and 07, any foreign `:Document` node makes the invariant false-fail with an incorrect "a concurrent build overlapped this one" diagnosis. That is a false alarm that will cost someone an hour.

**Proposed fix.**

1. Scope the invariant to match the wipe: count `(:Document:__KGBuilder__)`, not all `:Document`.
2. Add the advisory lock from verify.md's B17 fix item 2: `MERGE (:BuildLock {id:'kg-build'})` carrying timestamp and host, refuse to start if a live one exists, document a stale-lock override, and release in the existing `finally`.
3. Add the `--force` guard from fix item 3: if the database holds data this script did not create, require the flag. This overlaps with V8 and the two should land together.

---

### V10. Demo 02's notebook now contradicts its own corrected README

**Evidence.** `fix-02` corrected the README for B7 and left the notebook prose untouched, so the two artifacts now disagree:

- `token_efficiency_analysis.ipynb` cell 1: "Traditional (all 31 tools)", "~4,500 tokens"
- cell 11: `Goal: Semantic approach should IMPROVE accuracy`
- cell 29: "**Better Accuracy**: Fewer choices = less confusion"

B24 is the finding that semantic filtering measurably *reduces* accuracy (15/24 versus 16/24, reproduced twice). Cell 11 states the disproved claim as the notebook's goal. Separately, both the notebook and `README.md:100` say 31 tools where the code loads 29.

**Proposed fix.** This needs the B24 decision first, since the notebook prose depends on it. Recommend reframing rather than tuning: the honest and more interesting teaching point is a cost/accuracy tradeoff (74.1% token reduction for a 1-query accuracy cost at n=24, which is within noise at that sample size). Then:

1. Rewrite cell 11's goal statement to the tradeoff framing.
2. Delete or qualify cell 29's "Better Accuracy" bullet.
3. Correct 31 → 29 in the notebook and `README.md:100`.
4. Regenerate the figures in `images/*.png`, which still embed pre-fix numbers and now sit beside corrected text (rendered at `README.md:163-165`). This is B26's second half.

---

### V11. B25 and B26 remain open verbatim

- **B25:** `02-semantic-tools-demo/README.md:98` and `:106` both point at `test_semantic_tools_hallucinations.ipynb`. The file does not exist; the real one is `token_efficiency_analysis.ipynb`. An attendee following the README cannot find the demo.
- **B26:** `README.md:83` and `:86` still instruct creating a `.env` with `OPENAI_API_KEY` and link to platform.openai.com, in a Bedrock-only demo.

Both are single-line edits with no dependencies. **Proposed fix:** make them now rather than scheduling them; they are the cheapest attendee-impact wins on the board.

---

## P2 — Quality, hygiene, and latent risk

### V12. verify.md's B27 row is stale, and three READMEs disagree with the code

**Evidence.** B27 documents the fix as `us.anthropic.claude-sonnet-4-5-20250929-v1:0`. Commit `1121f5b` subsequently moved the tree to `us.anthropic.claude-sonnet-5` and verify.md was never updated.

I tested both IDs live via `bedrock-runtime invoke-model` in us-east-1 and us-west-2. **Both resolve and return valid completions.** Nothing is broken.

But the docs and the code now disagree. Code requests `claude-sonnet-5` at `00-getting-started/getting_started_strands.ipynb:85` and `01-graphrag-demo/bedrock_providers.py:73`, while `README.md:126`, `00-getting-started/README.md:40`, and `06-agentcore-boto3-demo/README.md:65` tell attendees to enable `us.anthropic.claude-sonnet-4-5` in the Bedrock console. An attendee who enables only what the README names will see an access-denied error and will report it as a bug.

**Proposed fix.** Pick `us.anthropic.claude-sonnet-5`, since that is what the code uses and what the B29–B31 fixes were validated against. Update the three READMEs and the five commented-out `#   MODEL = ...` example lines to match. Then update verify.md's B27 row to record the actual final state.

### V13. Test coverage gaps in the cleanup guard

`08-cleanup/test_workshop_cleanup.py:240` hardcodes `(Path(__file__).parent / "workshop_cleanup.py")`. Nothing guards `06-agentcore-boto3-demo/cleanup.py` or the deploy notebooks. In practice `cleanup.py` is now a 39-line import shim with zero logic, so the gap is latent rather than live, but it is the same gap that lets V7 exist. Fix is folded into V7 item 3.

**Also note:** pytest collects zero tests from this file. The framework is `unittest`. `python3 -m unittest test_workshop_cleanup` runs 12 tests, all passing, no AWS credentials required. Anyone verifying with `pytest` will get a false clean bill. Worth a line in `08-cleanup/README.md`.

### V14. `local-config-file` is a glob documented as exact-match

`08-cleanup/workshop_cleanup.py:81` and `:425-440` classify it `UNTAGGABLE_EXACT_NAME`, and `README.md:75` describes the class as "exact name equality, not prefixes". The implementation is `glob` over `.bedrock_agentcore*.yaml` and `~/.bedrock_agentcore*.yaml`, which will delete another project's AgentCore config from the user's home directory. The wildcard also sidesteps the `startswith`/`endswith` AST ban.

**Proposed fix.** Either narrow to the exact filenames this workshop creates, or reclassify honestly as `UNTAGGABLE_GLOB` and warn in the dry-run output listing exactly which files would be removed.

### V15. Two silent-success paths in the cleanup CLI

- `workshop_cleanup.py:536-548`: `wait_for_tables_gone` exits its `while` on timeout without recording a `Failure`, so a table stuck in `DELETING` still yields `CLEANUP COMPLETE` and exit 0 from the CLI. The notebook's cell 9 re-plan catches this; the CLI does not. **Fix:** add an `else` clause on the loop appending to `failures`.
- `workshop_cleanup.py:599-608`: no confirmation prompt and no `--yes` on the destructive CLI path. `python workshop_cleanup.py` with no arguments deletes immediately. The notebook is adequately gated by cell separation (dry run cell 3, review cell 5, execute cell 7); the CLI is not. **Fix:** require `--yes` for non-dry-run, defaulting to dry run.

### V16. Assorted drift and rot in demos 01, 04, 05

| Item | Location | Fix |
|---|---|---|
| `graph_config.py` docstring says the `"neo4j"` default was the bug, and line 30 still ships that exact default | `graph_config.py:14-16` vs `:30-31` | Drop the fallbacks; raise a clear `ValueError` naming the missing variable, matching what notebook cell 5 already does |
| "COUNT() across all 300 hotels" in demo prose while only the 30-doc lite path has ever been verified | `test_graphrag.ipynb` cell 13; cell 5 prints "full: 300 docs" unconditionally | Make the printed count derive from the actual graph |
| Cell 5 source collapsed from list-of-lines into one single-line JSON string; cell 8 moved the other way | `test_graphrag.ipynb` | Normalize the whole file to list-of-lines. Undiffable cells are the same fragility class as B1 |
| Hardcoded past dates `2026-05-01`, `2026-05-03`, `2026-04-15` | `05-.../test_hooks_vs_control.py:63`, `.ipynb` cell 7, `tools.py:17` | Pre-existing and currently harmless (demo 05 has no advance-booking rule), but it is exactly B2's rot class in the adjacent demo. Derive from `datetime.now()` |
| `sum(guest_counts) == 15` hardcodes the guest total from `QUERY` | `05-.../test_hooks_vs_control.py:395`, `.ipynb` cell 11 | Derive from `QUERY`; today a changed query silently degrades to `"partial"` instead of failing |
| `tools.STATE` never reset between tests, and never in the notebook | `05-.../test_hooks_vs_control.py`, `.ipynb` | Re-running cells 9 then 11 accumulates bookings and flips `outcome_ac` off `split-bookings`. Attendees re-run cells routinely. Add a reset |
| Markdown says "Book Grand Hotel" while `QUERY` books AnyCompany Lisbon Resort | `05-.../test_hooks_vs_control.ipynb` cell 8 | One-line correction |
| `EXIT_B=` and `EXIT_C=` are empty | `logs/05-final-verification.log` | Scenario C is corroborated by the four `05-run-localmode-*.log` files, but the verification log does not prove the exit codes it claims to check. Re-run and capture |
| `resolve_control_plane` accepts a server whose `/health` returns 500 | `05-.../test_hooks_vs_control.py:139` | `_http_status` returns the code, not `None`, on HTTP errors, so `health is not None` is true for a 500. Check for 2xx |
| Writes to `agent_control._state.state.server_controls`, a private SDK attribute | `05-.../test_hooks_vs_control.py:161-175` | Accept as-is. It is well quarantined behind `--local-controls`, labelled in the docstring, `--help`, the runtime banner, and the README. But it will break on any SDK upgrade with no compile-time signal, so pin the SDK version in `requirements.txt` and add a startup version check |
| `supported_figures` admits every number anywhere in tool output | `03-.../oracle.py:81-84` | `$95` stated as the BK900 nightly rate is not flagged because `95` appears in the `search_hotels` line. Since `VALIDATOR_PROMPT:114` instructs the validator to reject exactly that derivation, a correct validator is scored a **false alarm** at `test_multiagent_hallucinations.py:381`. The undercount is documented at `oracle.py:100-104`; the resulting scoring inversion is not. Scope figures to the specific tool call they are claimed to derive from |

---

## Confirmed Fixed — independently re-verified

Recorded so this work is not re-litigated.

- **B6.** Prefix matching gone from both files; `06-.../cleanup.py` is now a pure import shim. Tag gate is exact equality (`has_workshop_tag:143`) applied at lines 213, 235, 255, 275, 321, 346, 394, 419, covering memory, runtime, gateway, lambda, dynamodb, iam, ecr, codebuild. `DELETABLE` authorises only `TAGGED` and `UNTAGGABLE_EXACT_NAME`. The regression test rebuilds the exact five destroyed roles plus `workshop-studio-execution-role`, all untagged, and asserts zero selections **and** zero `delete_role` calls on a real non-dry `run()`. 12/12 pass with no credentials.
- **B18.** Verified against botocore 1.42.91, not against documentation: `DeleteGateway` requires `['gatewayIdentifier']`, `DeleteGatewayTarget` requires `['gatewayIdentifier', 'targetId']`. `_delete_gateway:477-485` and `discover_gateways:250` match exactly. No `gatewayId=` remains.
- **B5.** `discover_memories:202` matches `m["id"]` via `memory_id_matches_name`, an equality test after stripping one `-<suffix>`. `memoryName` appears nowhere. Zero bare `except:` and zero `except Exception` in `08-cleanup/*.py` or `06-.../cleanup.py`. `run()` returns 1 on any failure or any `UNTAGGED_BLOCKED`; `cleanup.ipynb` cell 7 raises on non-zero. Caveat at V6.
- **B15.** `GRAPH_SCHEMA` validated through `GraphSchema.model_validate` in the demo's own venv. Property-by-property comparison against the cell 8 docstring is an **exact match**: all 5 labels, all 22 properties, all 4 relationship types, with `additional_node_types`/`relationship_types`/`patterns` and per-node `additional_properties` all `False`. `travel_agent_demo.py:64-84` corrected from camelCase to the same contract. Runtime-confirmed: canary log shows only contracted labels and zero `Address` nodes.
- **`h.id` vs `h.name`.** Reconciled. Both builders are thin shims over one `graph_builder.run_build()`; the only hotel-identity queries are `graph_builder.py:169` and `:276`, both `h.name`. Zero duplicated logic remains.
- **B16.** No `.close()` on the pipeline anywhere. Driver close is `try/finally` at `:295`/`:343-344` covering success and every failure return. Runtime-proven: the lite build reached `report()` and exited 0.
- **B28–B31.** `bedrock_providers.py`: no `amazon.nova-embed-text-v1:0`; `_strip_code_fence()` at `:20-34` applied at `:119`; `temperature` gated on `is not None` at `:98-99`; `next((b["text"] for b in blocks if "text" in b), None)` at `:115` raising an explicit `ValueError` rather than `KeyError`. All four proven by 31 successful extractions across two build logs.
- **B2 and B12.** Relative dates in `.py`, `.ipynb`, and `STATE`, with comments explaining why a fixed date must never return. All assertions structural (`hook.blocked_calls`, `recorder.tool_calls`); the new `ToolCallRecorder` replaced the baseline's SUCCESS/BOOKED grep, which the brief did not even ask for. `logs/04-fix-script-1.log` reads `TOTAL 3/3 correct`, `Hook blocked 2/2 invalid`, `Hook allowed 1/1 valid`. Log line 2 shows scenario 2's block was paraphrased ("could not be completed") and still scored correct, which is the B12 false negative genuinely removed.
- **B9.** Option A done. The only surviving `openai` token across tracked demo 05 files is `README.md:31`, prose stating the requirement is gone. `main`'s live commented-out `gpt-4o-mini` config is deleted from both files. No `model=` is passed, so both paths use the Strands Bedrock default.
- **B21.** The RE2 pattern at `controls.yaml:19` is unchanged and provably still matches the agent's own correction, but that is now a documented design constraint mitigated by `MAX_STEERS=1` and structural ledger assertions. `steers_applied` verified as a genuine public attribute of the SDK base class, so the override does not reach into private state. 4/4 stable runs showing `Steered: 1`, `[10, 5]`. Server path unproven, exactly as `logs/fix-05.md` states.
- **B22.** Independently confirmed against installed SDK 8.3.0: `controls_file` appears at exactly two places, `agent_control/__init__.py:451` (signature) and `:491` (docstring), and `grep -rn "import yaml\|yaml.safe_load"` across `agent_control`, `agent_control_engine`, and `agent_control_models` returns nothing. No YAML loader exists. Fail-fast confirmed at exit 2, correctly naming an impostor service on port 8000 via the `/api/v1/agents` 404 probe.
- **B7, B8, B11.** README figures match `logs/02-script-final.log` byte for byte; 89% survives only as a labelled third-party citation. `nbformat.validate` passes, 30 cells, zero missing `outputs`/`execution_count`. `registry.py:133-151` snapshot/delta is correct at both call sites and `trim_history:104-127` cuts only at real user-turn boundaries, so no toolUse/toolResult pair is split.
- **B1.** Every code cell in all three module 06/07 notebooks `ast.parse`s clean; cell 16 is 58 logical lines with real newline terminators.
- **Repo-wide.** All 9 tracked notebooks and every tracked `.py` parse clean. No new bare `except`, no new unused imports, no new prose-grepping in any changed `.py`.

---

## Process Findings

**The evidence base is not in version control.** `verify.md`, `verify-worklog.md`, and `logs/` are all untracked, and the latter two were added to `.gitignore` in commit `1121f5b`. Every review gate in verify.md depends on reading those logs. On a fresh clone they do not exist. This may be deliberate for a shipping workshop repo, but it should be a decision with a recorded rationale rather than a side effect. Options: keep them local and accept it, move them to a `docs/verification/` directory that is tracked, or push them to a separate branch.

**Two workers reported success against artifacts that contradict them.** `logs/fix-01.md:125-126` claims identical corpora for RAG and Graph-RAG (V5, false for the notebook). `logs/fix-03.md:50-51` quotes the favourable half of a run that exits 1 on its own gate (V2). Both were caught only by reading the raw logs, which is exactly what review gate item 1 exists for. The gate works; it needs to keep being applied.

---

## Recommended Sequencing

**Immediately, before anything else:**

1. V1 — untrack both artifact notebooks, tighten the gitignore glob, owner decision on history rewrite.
2. V3 item 1 — correct the false B20 claim in `08-cleanup/README.md:42`.
3. V11 — B25 and B26, two-line README fixes.
4. V12 — reconcile model IDs across the three READMEs.

**Then, parallel and independent:**

5. V4 — B23 in three notebooks, using the `registry.py` pattern. Mechanical; highest thesis impact per unit of effort.
6. V6 — pagination in `workshop_cleanup.py`, plus the two-page regression test.
7. V7 — remove deletion logic from the deploy notebooks; widen the AST test.
8. V5 — corpus-aware FAISS selection plus the document-count invariant.
9. V10 — demo 02 notebook prose, after the B24 decision.

**Gated:**

10. V2 — re-task `impl-03`, but log the OQ-5 escalation and get the owner ruling first.
11. V3 items 2 and 3 — the `fix-tags` work order. Nothing deploys until this closes.
12. V8, V9 — demo 01 canary and lock work, after the running 300-doc build lands and its result is recorded.

**Owner decisions needed:**

- V1 item 4: accept the hostname in history, rewrite the branch, or rotate Aura.
- V2 item 1: the OQ-5 ruling on 0/4 single-agent fabrication.
- V10: reframe B24 as a cost/accuracy tradeoff, or investigate the 1-query regression.
- Process: whether the verification evidence base should be version-controlled.
