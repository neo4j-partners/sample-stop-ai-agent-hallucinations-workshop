# Workshop Refactor Implementation Review

## Review summary

- **Implementation progress:** 13 of 14 review finding tracks are complete. The facilitated four-hour rehearsal is the only track still in progress. All immediate documentation, notebook, runtime, runner-safety, dependency, inventory, packaging, environment, archival, evidence, and cleanup fixes are complete.
  - **Complete:** 13 finding tracks.
  - **In progress:** 1 finding track.
  - **Blocked:** 0 finding tracks.

- **Overall result:** The actionable content and technical fixes from the review are implemented. The workshop has stronger grounding checks, safer automation, reproducible validation evidence, and consistent documentation. Delivery-ready status remains pending until the facilitated rehearsal proves the four-hour schedule.
  - **Recommended fix:** Run the rehearsal using `workshop-delivery/rehearsal.md`, record real per-lab times, and apply the existing cut order if the total exceeds 240 minutes.
  - **Best long-term fix:** Treat delivery time and every major teaching claim as acceptance criteria backed by a rehearsal record, notebook assertion, automated test, or sanitized live result.

- **Verification result:** The inventory check passes for seven labs and ten notebooks. The four published test suites pass with 12 tests in Lab 1, 56 in Lab 4, 29 in Lab 5, and 40 in Lab 6. The new runner and `.env` helper tests add six passing tests. A live read-only Lab 2 run passed all three notebooks and showed exactly one retrieval call plus the structured missing-fact verdict. Lab 4 and Lab 6 also pass through the default runner with live writes skipped.
  - **Recommended fix:** Keep these checks as the minimum merge gate.
  - **Best long-term fix:** Add a scheduled live integration gate in a disposable AWS account with guaranteed teardown.

## Implementation checklist

### Content

- [ ] **Four-hour facilitated rehearsal:** In progress. The schedule and measurement worksheet are complete, but the measured rehearsal has not happened.
- [x] **Lab 2 abstention lesson:** Complete. Fresh-agent retrieval, exact-call assertion, evidence display, and structured answerability checks are implemented and live-validated.
- [x] **Lab 4 rejection wording:** Complete. The prompt prevents unsupported remedies while preserving the no-numeric-threshold assertion.
- [x] **Hero-question documentation:** Complete. Participant and facilitator narratives now match the notebooks.
- [x] **Graph-RAG comparison:** Complete. Universal claims are replaced with scoped evidence statements.
- [x] **Retired deployment notebook:** Complete. The hazardous notebook is archived outside the participant lab path.

### Technical

- [x] **Default runner write safety:** Complete. Live writes require explicit `--allow-writes`.
- [x] **Grounding behavior assertions:** Complete. Labs 2 and 5 assert retrieval and structured missing-fact verdicts.
- [x] **AgentCore evidence record:** Complete for the reviewed run. The sanitized record is added to the repository worktree as an implementation artifact. Richer raw evidence is deferred to the next live run.
- [x] **Dependency alignment:** Complete for the immediate fix. Runner constraints are aligned and validated deployment dependencies are pinned. A unified cross-environment lock is deferred.
- [x] **Provisioner package import:** Complete. The provisioner installs and imports the shared package normally.
- [x] **Shared `.env` editing:** Complete. Both writers use one tested atomic helper.
- [x] **Workshop inventory validation:** Complete for checked facts. Inventory consistency is enforced in CI.
- [x] **Lab 6 cleanup:** Complete. Both known run prefixes were removed and verified empty.

## Content problems

- **Four-hour delivery status:** In progress. A real facilitated run of Labs 1 through 5 is still missing. Machine execution does not measure teaching, questions, recovery, or slower participants.
  - **Implemented fix:** Added `workshop-delivery/rehearsal.md` with a provisional 240-minute schedule, warning times, separate teardown timing, a measurement sheet, required evidence, and the approved cut order.
  - **Recommended fix:** Complete the worksheet during one end-to-end rehearsal and update the delivery guide with measured times.
  - **Best long-term fix:** Rehearse every release and track target, warning, and cut times as maintained workshop data.

- **Abstention lesson status:** Complete. Lab 2 previously allowed the availability turn to reuse agent history and silently performed a direct retriever fallback when the agent skipped its tool.
  - **Implemented fix:** The availability turn now uses a fresh agent, requires exactly one retrieval call, displays the exact tool payload, removes the fallback, and asserts `answerable: false`, `missing_fact: live_room_availability`, and nonempty evidence IDs.
  - **Recommended fix:** Keep the structural assertions and inspect the live response for clear participant wording.
  - **Best long-term fix:** Maintain an evaluation set covering answerable, missing-fact, wrong-entity, and stale-data questions.

- **Unsupported rejection advice status:** Complete for the immediate fix. The Lab 4 safety boundary was correct, but the model could add remedies that were absent from the command result.
  - **Implemented fix:** The agent is now instructed to report only facts present in a rejected command response and to add no remedies or alternatives. The prompt still contains no numeric policy threshold.
  - **Recommended fix:** Keep the prompt rule and review rejection wording during live acceptance runs.
  - **Best long-term fix:** Render accepted and rejected command outcomes deterministically from the structured result.

- **Hero-question story status:** Complete. Participant and facilitator documents disagreed about where both hero questions appeared, what the matched chunks contained, whether retrieval returned an empty list, and whether the workshop still taught swarms.
  - **Implemented fix:** Corrected all stale statements. Lab 3 now clearly reuses only the amenities-and-rating question. The availability lesson now says evidence finds the hotel but lacks the requested live fact. Stale swarm promises are removed.
  - **Recommended fix:** Run the inventory check whenever lab topics, notebook names, or hero questions change.
  - **Best long-term fix:** Generate repeated workshop tables and question summaries from `workshop-inventory.json`.

- **Graph-RAG scope status:** Complete. The root narrative used universal wording that implied graph retrieval always proves answerability.
  - **Implemented fix:** The comparison now says traversal improves structure and connectivity without proving completeness, freshness, or answerability. The external 73% result is linked and limited to its evaluated setting.
  - **Recommended fix:** Preserve the scoped wording in participant materials.
  - **Best long-term fix:** Replace broad comparisons with workshop-owned retrieval and grounded-answer measurements.

- **Retired deployment path status:** Complete. A hazardous superseded notebook remained beside supported Lab 5 notebooks.
  - **Implemented fix:** Moved it to `workshop-delivery/archive/`, fixed its links, preserved its warning, and corrected the warning to explain that current teardown discovers tagged legacy targets but partial failures still need verification.
  - **Recommended fix:** Keep archived artifacts outside participant lab folders.
  - **Best long-term fix:** Exclude maintainer archives from participant distributions and preserve obsolete implementations through Git history.

## Technical problems

- **Default runner writes status:** Complete. The notebook runner could create reservation and memory records whenever local credentials were present.
  - **Implemented fix:** The runner exports `WORKSHOP_RUNNER=1` by default. Lab 4 and Lab 6 skip write scenarios under that marker. `--allow-writes` is an explicit opt-in, while direct participant notebook runs still write normally.
  - **Recommended fix:** Keep default CI and local acceptance runs write-safe.
  - **Best long-term fix:** Separate offline, live-read, and live-write runners, give write runs unique IDs, and clean them in guaranteed finalization.

- **Behavioral proof status:** Complete for the reported gaps. A green Lab 2 or Lab 5 run did not prove that availability answers used retrieval or respected missing evidence.
  - **Implemented fix:** Lab 2 asserts one actual retrieval and a structured answerability verdict. The Runtime exposes `grounding_result`, and Lab 5 smoke test 2 requires retrieval, `answerable: false`, `live_room_availability`, evidence IDs, and no reservation command call. Runtime tests cover the new contract.
  - **Recommended fix:** Keep deterministic invariants separate from model prose checks.
  - **Best long-term fix:** Score saved traces for tool choice, evidence linkage, answerability, forbidden claims, and write verdicts.

- **Live AgentCore evidence status:** Complete for the reviewed run. The repository previously contained only a prose claim about a live run. Capturing richer raw evidence remains deferred until the next live run.
  - **Implemented fix:** Added `workshop-delivery/validation/agentcore-live-run-2026-08-13.md` with the date, Runtime and image names, provisioning results, smoke verdicts, teardown inventory, and known evidence gaps. Root, Lab 5, and architecture documentation link to it.
  - **Recommended fix:** Retain raw sanitized Runtime envelopes and package inventory during the next live run.
  - **Best long-term fix:** Use a manually approved or scheduled workflow in a disposable account and publish sanitized artifacts only after teardown verification passes.

- **Dependency drift status:** Complete for the immediate fix. The runner and Lab requirements could resolve incompatible Strands versions, and AgentCore dependencies did not reproduce the validated environment. A unified cross-environment lock remains deferred.
  - **Implemented fix:** Aligned the runner to `strands-agents>=1.27.0,<2.0.0` and pinned the validated AgentCore, Strands, MCP, boto3, Neo4j, and GraphRAG versions in deployment requirements.
  - **Recommended fix:** Refresh pins only through a tested dependency update.
  - **Best long-term fix:** Generate one lock covering local labs, the runner, the Runtime image, and Lambda packaging.

- **Package import path status:** Complete. The provisioner inserted `workshop/src` into `sys.path` instead of installing the shared package.
  - **Implemented fix:** The provisioner now declares the local `workshop` package as a PEP 723 source and imports it normally.
  - **Recommended fix:** Keep all executables on the package installation path.
  - **Best long-term fix:** Build one wheel and test that exact artifact in notebooks, Runtime, and Lambda packaging.

- **Duplicate `.env` keys status:** Complete. Two writers had separate update logic that could leave a stale duplicate key as the effective value.
  - **Implemented fix:** Added one atomic shared helper that removes all live and commented duplicates, writes one managed block, preserves file permissions, and supports a dry-run diff. Both the provisioner and Lab 5 notebook use it. Shared tests cover update, removal, duplicates, and dry run.
  - **Recommended fix:** Route every managed `.env` change through this helper.
  - **Best long-term fix:** Add ownership conflict reporting when another tool manages the same key.

- **Workshop inventory drift status:** Complete for checked facts. Notebook lists, hero questions, topics, and optional status were maintained in several documents with no consistency check.
  - **Implemented fix:** Added `workshop-inventory.json`, `setup/check_workshop_inventory.py`, and an offline CI job. The check validates lab structure, notebook files, per-lab README mentions, runner order, hero-question notebook markers, and repeated notebook and hero-question mentions in the root and delivery documents.
  - **Recommended fix:** Update the inventory first whenever the workshop structure changes.
  - **Best long-term fix:** Generate the repeated Markdown tables from the inventory instead of validating hand-written copies.

- **Lab 6 leftovers status:** Complete. Two known acceptance runs remained on the shared Aura instance.
  - **Implemented fix:** Dry-ran and deleted `demo08-33d55968-` and `demo08-4089757b-` separately. Each deletion removed 11 memory nodes and 17 relationships. Follow-up dry runs returned zero for every scoped category, and all 30 Hotel nodes remained.
  - **Recommended fix:** Keep using one exact `--run-prefix` per cleanup.
  - **Best long-term fix:** Make every live acceptance run clean its own prefix in guaranteed finalization.

## Remaining release work

- [ ] **Required before delivery-ready status:** Complete and record the four-hour facilitated rehearsal. Status: In progress.
- [ ] **Recommended for the next live AgentCore run:** Preserve sanitized raw response envelopes and exact package inventory. Status: Deferred until the next live run.
- [ ] **Disposable-account integration workflow:** Status: Deferred long-term improvement.
- [ ] **Cross-environment dependency lock:** Status: Deferred long-term improvement.
- [ ] **Generated documentation tables:** Status: Deferred long-term improvement.
- [ ] **Deterministic write-result rendering:** Status: Deferred long-term improvement.
- [ ] **Trace-based grounding evaluation:** Status: Deferred long-term improvement.
