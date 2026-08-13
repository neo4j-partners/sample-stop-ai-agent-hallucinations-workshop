[< Back to Main README](../README.md)

# Lab 4: The grounded write

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://python.org)
[![Neo4j](https://img.shields.io/badge/Neo4j-AuraDB-4581C3.svg?style=flat&logo=neo4j)](https://neo4j.com/cloud/aura-free/)
[![Amazon Bedrock](https://img.shields.io/badge/Amazon-Bedrock-FF9900.svg?style=flat&logo=amazon-aws)](https://aws.amazon.com/bedrock/)
[![Strands Agents](https://img.shields.io/badge/Strands_Agents-1.27+-00B4D8.svg?style=flat)](https://strandsagents.com)

Lab 3 blocked a 15-guest booking with `MaxGuestsHook`, and the block held. The hook fires on `BeforeToolCallEvent`, the model receives a cancellation instead of a tool result, and rephrasing gets it nowhere. As a demonstration that a guardrail can sit outside the model's reach, that is exactly right.

The number is the problem. `10` is a Python literal inside a hook class, in one notebook, next to one agent. A second caller of the same business rule has nothing to read it from, and the two copies begin drifting the day someone edits one of them. A business rule is connected data, and it belongs where the hotels and the reservations already live, enforced inside the same boundary as the write it governs.

Lab 4 moves it there. The limit comes out of a `Rule` node in your graph, the reservation command reads that node inside the same transaction as the write, and the same 15-guest request is rejected with nothing written.

**At a Glance**
- **Failure it prevents:** an agent taking a real action that violates a business rule the prompt never mentioned, and a retried action being written twice.
- **Neo4j:** the `Rule` node `demo-06-maximum-guests` read inside the write transaction, the `ReservationRequest` node and its `FOR_HOTEL` relationship, three uniqueness constraints, and parameterized Cypher only.
- **AWS:** Bedrock Claude reasons over the structured command response, and the Strands `@tool` boundary carries the closed five-field input schema.
- **You'll build:** `hotel_agent` again, with the reservation write registered and `MaxGuestsHook` removed, then four command outcomes run against your own graph.

---

## The one notebook

`4.1_reservation_write.ipynb` has 21 cells in six sections. It creates no AWS resources.

| Section | What it does |
|---|---|
| 1. Connect, and confirm the rule is in the graph | Applies the idempotent graph preparation, reports what is still missing, then reads the `Rule` node and asserts it agrees with the shared constant |
| 2. Register the write on `hotel_agent` | Rebuilds Lab 3's `hotel_agent` with `create_reservation_request_tool` added and `MaxGuestsHook` removed |
| 3. A 15-guest request is rejected | Computes the dates and the two request ids, asks the agent to book 15 guests, then calls the command directly twice to read the fields the agent was working from and to show the rejection stored nothing |
| 4. A valid request is recorded, and safe to retry | Accepts a within-limit request on the booking `request_id`, then re-delivers it identically |
| 5. A hotel that does not exist is rejected | Sends `hotel_id hotel-does-not-exist` through the agent, then through the command directly |
| 6. Inspect the reservation in your graph | Matches on `request_id` and asserts exactly one row |

Live cells self-skip. Cell 3 sets `NEO4J_READY` from `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD`, `BEDROCK_READY` from whether boto3 finds AWS credentials, and `AGENT_READY` from both, so the notebook runs top to bottom with no configuration at all.

---

## Where the limit lives now

Section 1 reads the rule out of the graph before anything is written. That cell is the whole argument of the lab: the number is not in this notebook, not in a prompt, and not in a hook class. It is a property on a node, with its rejection message and its enable flag beside it, and any caller that can reach the graph reads the same value.

```python
from workshop.contracts import MAX_GUESTS, MAX_GUESTS_RULE_ID
from workshop.graph_setup import RULE_QUERY

rule = session.run(RULE_QUERY, rule_id=MAX_GUESTS_RULE_ID).single()
assert rule["max_guests"] == MAX_GUESTS
```

`MAX_GUESTS_RULE_ID` is `demo-06-maximum-guests` and `MAX_GUESTS` is `10`, both from `workshop.contracts`. `RULE_QUERY` is parameterized Cypher in `workshop.graph_setup`, and it returns `max_guests`, `enabled`, `rejection_message`, `steering_message`, and a count of matching rule nodes. The notebook prints all four properties, so the rule's origin is visible rather than asserted.

The assertion runs in that direction on purpose. When the constant and the graph disagree, the graph is the one that decides, because the graph is what the command reads. `demo-06-maximum-guests` is a real identifier in seeding and query code, not a leftover label; it is not renamed by the six-lab renumbering.

### The hook comes off the agent

Section 2 rebuilds `hotel_agent` with three changes from Lab 3. `create_reservation_request_tool` joins the toolset, `MaxGuestsHook` is gone, and the system prompt gains one instruction about passing the caller's identifiers through.

Removing the hook is the point rather than a simplification. The rule it enforced now lives in the graph, and `workshop.reservation_command` reads it inside the write transaction, so the limit holds for every caller of the command: this notebook calling it directly, the agent calling it as a tool, and the Lambda Lab 5 puts behind AgentCore Gateway. A hook protects one agent. A rule in the graph, checked at the write boundary, protects the data.

The system prompt still carries `GROUNDING_INSTRUCTIONS` from `workshop.hybrid_retrieval`, the same abstention text Lab 2 used, plus one instruction to pass the caller's `request_id`, `hotel_id`, and dates through exactly as written and never to claim a booking succeeded unless the response says `accepted`.

---

## The write contract is frozen

The command accepts exactly five fields and nothing else:

```python
request_id, hotel_id, check_in, check_out, guests
```

There is no actor field, no guest identity, no room selection, no payment field, and no booking-lifecycle operation. `reservation_input_schema()` in `workshop.contracts` is closed with `additionalProperties: False`, and dates are `YYYY-MM-DD`. There is exactly one write path in the workshop, and widening it is deliberately out of scope: an extra parameter, a second write, or a caller-selectable retriever all go against the frozen contract in [`CONTRACTS.md`](CONTRACTS.md). Flag it before adding one.

Every response is a structured document rather than prose, so the agent reports an outcome instead of composing an apology:

| Outcome | `status` | `reason_code` | Write behavior |
|---|---|---|---|
| Accepted | `accepted` | omitted | One `ReservationRequest` plus one `FOR_HOTEL` relationship |
| Duplicate delivery | `accepted` | omitted | Returns the existing request with `duplicate=true` |
| Policy rejection | `rejected` | `max_guests_exceeded` | No write. Also returns `max_guests` |
| Unknown hotel | `rejected` | `unknown_hotel` | No write |
| Invalid dates | `rejected` | `invalid_dates` | No write |
| Unauthorized | `error` | `unauthorized` | No write |
| Service failure | `error` | `service_error` | No intentional write |

`status`, `request_id`, `hotel_id`, `duplicate`, and `message` are present on every response. Accepted and duplicate responses add `created_at`, a Neo4j-generated timestamp.

### The four cases the notebook runs

1. **`max_guests_exceeded`.** The agent is asked to book `OVER_LIMIT_GUESTS`, which is `15`, into the hero hotel. Nothing in the prompt mentions a limit of 10, so the model could not have been argued out of one. The command reads the rule, rejects, and writes nothing. Section 3 then calls the command directly and asserts `status == "rejected"` and `reason_code == "max_guests_exceeded"`. It delivers the same payload once more and asserts `duplicate` is still false, which is what proves the rejection stored nothing: a duplicate can only be reported against a stored request.
2. **Accepted.** The booking `request_id` with `guests=MAX_GUESTS` creates one `ReservationRequest` linked to the hero hotel by `FOR_HOTEL`. The cell asserts `status == "accepted"` and `duplicate` is false.
3. **Duplicate delivery.** The identical payload delivered a second time returns the stored record with `duplicate=true` and its original `created_at`, and creates no second node. The cell asserts `replay["duplicate"] is True`, and it also serializes `status`, `request_id`, `hotel_id`, and `created_at` from both responses and asserts the two strings are equal, so the claim that one record came back twice is shown rather than stated.
4. **`unknown_hotel`.** `hotel_id hotel-does-not-exist` matches no prepared fixture `Hotel`, so the command rejects rather than creating an orphan request. This is why grounded retrieval returns an opaque `hotel_id` and not a display name: a name a model half-remembers fails this check, and a name it invents outright fails it too.

### The notebook creates the `request_id`, not the model

Section 3 generates two of them and prints both:

```python
OVER_LIMIT_REQUEST_ID = str(uuid.uuid4())
BOOKING_REQUEST_ID = str(uuid.uuid4())
```

One id per case, because the two cases make different points. The over-limit id shows that a rejected request leaves nothing behind. The booking id shows that the same id delivered twice produces one node.

Idempotence cannot be demonstrated any other way. A model that invents a fresh UUID on the retry produces two distinct requests and two nodes, and the second delivery is a new write rather than a replay. The caller owns the key, reuses it on every retry, and the agent is told to pass it through verbatim. `_validate_command` rejects anything that is not a canonical UUID before a session is opened.

Idempotence itself is enforced by the graph, not by a check the caller remembered to write. `demo06_reservation_request_id` makes `ReservationRequest.request_id` unique, the command reads any existing request inside the write transaction first, and a concurrent delivery that loses the uniqueness race reads the winning record instead of writing a second one. Reusing a `request_id` with different input returns `service_error` and never changes the stored request.

### Dates are computed, never hardcoded

```python
check_in = (date.today() + timedelta(days=30)).isoformat()
check_out = (date.today() + timedelta(days=32)).isoformat()
```

A fixed future date silently rots into the past and flips this lab from a clean accept into an `invalid_dates` rejection, on a date nobody chose. The command refuses a check-in earlier than today, so relative dates are what keep the notebook runnable next year. Any new date in this lab has to be computed the same way.

---

## What this lab writes, and what it does not

This lab writes workshop-owned reservation **requests**. Every rule and request node it touches carries `workshop_owner=neo4j-ftw-demo-6`.

It does not hold inventory, book a room, take a payment, or confirm anything. Real inventory, booking, payment, and confirmation state stay behind an external-system boundary that this workshop does not cross. The command's Cypher cannot update or delete canonical `Hotel`, `Chunk`, `Document`, `Amenity`, or `Rule` data, and `test_cypher_cannot_modify_canonical_hotel_data` pins that.

The graph shape is small on purpose:

```
(:ReservationRequest {request_id, check_in, check_out, guests, status, created_at, workshop_owner})
      -[:FOR_HOTEL]-> (:Hotel {hotel_id})
```

Three uniqueness constraints make it safe, created idempotently by `apply_lab4_fixtures`:

| Constraint | Guarantees |
|---|---|
| `demo06_fixture_hotel_id` | `Hotel.hotel_id` is unique, so one `hotel_id` names one hotel |
| `demo06_reservation_request_id` | `ReservationRequest.request_id` is unique, which is what makes a retry safe |
| `demo06_rule_id` | `Rule.rule_id` is unique, so there is one `demo-06-maximum-guests` rule and not two disagreeing ones |

No Cypher in this lab is generated by a model. Every query is a named, parameterized constant in `workshop/src/workshop/reservation_command.py` or `workshop/src/workshop/graph_setup.py`, and no part of a request is interpolated into a query string.

---

## Quick Start

### Prerequisites

- Python 3.12+ and the [uv](https://docs.astral.sh/uv/) package manager
- The repo-root `.env` filled in, per [`00-setup/README.md`](../00-setup/README.md)
- Lab 1 finished, so the fixture hotels, the three constraints, and the `Rule` node exist
- Lab 3 read, so `hotel_agent` and `MaxGuestsHook` are familiar
- Amazon Bedrock access for the agent turns and for the query embedding behind the retrieval tool

### Step 1: Install dependencies

```bash
cd 04-grounded-write
uv venv && uv pip install -r requirements.txt
```

`requirements.txt` installs the shared package with `-e ../workshop`, which brings neo4j, boto3, neo4j-graphrag, and python-dotenv, plus `strands-agents` and `bedrock-agentcore-starter-toolkit`.

### Step 2: Confirm the command and the rule constant import

```bash
cd 04-grounded-write
uv run python -c "from workshop.reservation_command import create_reservation_request; from workshop.contracts import MAX_GUESTS, MAX_GUESTS_RULE_ID; print(MAX_GUESTS_RULE_ID, MAX_GUESTS)"
```

This prints `demo-06-maximum-guests 10` and proves the editable install resolved. It opens no connection, so it works with or without credentials.

### Step 3: Run the notebook

Open `4.1_reservation_write.ipynb` in VS Code, Kiro, or any editor with notebook support, and run the cells in order. Section 1 raises with a named corrective action if the graph is not ready, so a missing rule or fixture is reported before any write is attempted.

The notebook is registered with the shared acceptance runner as lab 4:

```bash
uv run setup/run_notebooks.py --list
```

Run that from the repository root. Executing lab 4 through the runner writes to your graph exactly as running the notebook by hand does, so run it deliberately rather than alongside a graph build. The root [README](../README.md) documents how to execute a lab through the runner.

---

## Tests

```bash
cd 04-grounded-write
uv run --with pytest --with-requirements requirements.txt -m pytest
```

**56 tests**, plus 12 subtests reported by the cases that use them:

| File | Tests | What it covers |
|---|--:|---|
| `test_reservation_command.py` | 22 | Every frozen outcome, idempotency, the concurrent-retry race, fail-closed behavior on a missing or invalid rule, and that the Cypher cannot modify canonical hotel data |
| `test_graph_setup.py` | 12 | Constraint shape rather than only constraint name, fixture resolution by source filename, manifest determinism, and that the reservation graph shape carries no actor |
| `test_hybrid_retrieval.py` | 12 | The frozen retrieval contract this lab writes against: fixed indexes, static traversal, frozen ranker and `top_k`, bounded null-safe results |
| `test_contracts.py` | 7 | The closed schemas, the Gateway projection, the reason-code set, and that the reservation contract has no actor or booking lifecycle |
| `test_demo_guest_consistency.py` | 3 | That the guest limit has one source of truth |

`test_reservation_command.py` and `test_contracts.py` account for 29 of the 56, which is the reservation command and its contracts.

Every test but one runs without a live graph. `SeededRuleTests::test_seeded_rule_matches_the_contract` in `test_demo_guest_consistency.py` needs a live graph: it reads the `Rule` node with `RULE_QUERY` and asserts the node exists exactly once, carries `max_guests == MAX_GUESTS`, and is enabled. Its `setUp` calls `load_dotenv()` and skips with `Neo4j is not configured` when `NEO4J_URI`, `NEO4J_USERNAME`, or `NEO4J_PASSWORD` is absent, which is how the offline suite stays green. The other two tests in that file read `graph_setup.py` as source, using `ast` to prove the seeding call binds `max_guests` to `contracts.MAX_GUESTS` rather than to a literal `10`, because a literal and a constant reference evaluate identically at runtime and only the source drifts.

That live test is also the one that reports a graph problem rather than a code problem. Run against a graph whose build had not yet reached the rule-seeding step, it fails with `AssertionError: 0 != 1 : Expected exactly one demo-06-maximum-guests rule node`, and the other 55 tests pass. Read a failure there as "re-run Lab 1", or as "the build is still running", before reading it as a regression.

Collection needs no configuration in this folder. It holds exactly the five test files above, neither notebook is named `test_*`, and pytest skips `.venv` by default, so a bare `pytest` from here collects those five files and nothing else. `conftest.py` records that boundary and sets no options; the staged deployment directories its earlier `collect_ignore_glob` named live in Lab 5, not here.

---

## Troubleshooting

**No `Rule` node found, or `enabled maximum-guests rule is unavailable`.** The command fails closed rather than accepting an unchecked request, so this is the correct behavior for an unseeded graph. `1.1_build_graph.ipynb` seeds `demo-06-maximum-guests` in its closing step, and section 1 of this notebook applies the same idempotent preparation again through `apply_lab4_fixtures`. Re-run Lab 1 and let it finish. Confirm the node is there without writing anything:

```bash
cd 04-grounded-write
uv run python -c "
from neo4j import GraphDatabase
from dotenv import load_dotenv
from workshop.contracts import MAX_GUESTS_RULE_ID
from workshop.graph_setup import RULE_QUERY
from workshop.hybrid_retrieval import Neo4jConfig
load_dotenv()
c = Neo4jConfig.from_environment()
with GraphDatabase.driver(c.uri, auth=(c.username, c.password)) as d:
    with d.session(database=c.database) as s:
        print(dict(s.run(RULE_QUERY, rule_id=MAX_GUESTS_RULE_ID).single()))
"
```

A `rule_count` of `0` means the rule is missing. A `rule_count` of `1` with `enabled: False` means the command will not enforce the limit and will not write either. A `max_guests` that disagrees with `contracts.MAX_GUESTS` means the graph was seeded by older code; re-seed the graph rather than changing the constant, since the graph is what the command reads.

**A duplicate looks like a failure.** It is not. `duplicate=true` with `status=accepted` is the designed outcome of re-delivering the same `request_id` with the same payload, and it means no second node was written. The `created_at` in that response is the original timestamp, not a new one, which is the evidence that nothing was updated. Section 6 asserts exactly one row after two deliveries of the booking `request_id`, and the over-limit `request_id` from section 3, delivered twice on its own, leaves no row at all. A retry that returns `duplicate=false` is the outcome to be suspicious of: it means the `request_id` changed between attempts, most likely because a model invented a new one instead of passing the caller's through. If instead you get `service_error` on a retry, the `request_id` was reused with different `hotel_id`, dates, or `guests`; the stored request is immutable and was left untouched.

**An unknown-hotel rejection on a hotel you can see in the graph.** `reason_code=unknown_hotel` means the `hotel_id` matched no `Hotel` node carrying `demo6_fixture = true`. Only hotels in the committed fixture manifest have a stable `hotel_id`, and grounded retrieval returns `hotel_id: null` for every other hotel, precisely so those hotels cannot be sent to the write path. Take the ID from `manifest.hotels[HERO_SOURCE]` as section 3 does, or from a retrieval result's `hotel_id` field, and never from a hotel name. If the fixture hotels themselves are unresolved, section 1 names that as a readiness problem and the fix is to re-run Lab 1.

**Bedrock access denied, or `AccessDeniedException` on the first agent call.** Enable the model in your region through the [Bedrock Model Access console](https://console.aws.amazon.com/bedrock/home#/modelaccess), and confirm `AWS_REGION` in the repo-root `.env` matches that region. The notebook reads `MODEL_ID` from the environment and defaults to `us.anthropic.claude-sonnet-5`, so override that variable to use a different model. The three agent cells are gated on `AGENT_READY`; the direct-command cells need only Neo4j, so a Bedrock problem leaves the four command outcomes still demonstrable.

**Cells print `Skipping: needs both Neo4j and AWS credentials.`** That is `AGENT_READY` reporting absent configuration, not an empty graph. Check `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD` in the repo-root `.env`, and note that the hosted Workshop Studio environment writes `NEO4J_USER` while every lab here reads `NEO4J_USERNAME`.

---

## What is in this folder

```
04-grounded-write/
├── 4.1_reservation_write.ipynb   # The one notebook, 21 cells
├── 01_hybrid_retrieval.ipynb     # Retired authoring source, not in the runner registry
├── CONTRACTS.md                  # The frozen retrieval and command contracts
├── requirements.txt              # -e ../workshop, strands-agents, starter toolkit
├── conftest.py                   # Records the pytest collection boundary, sets no options
├── test_reservation_command.py   # 22 tests
├── test_graph_setup.py           # 12 tests
├── test_hybrid_retrieval.py      # 12 tests
├── test_contracts.py             # 7 tests
└── test_demo_guest_consistency.py  # 3 tests, one of them live
```

The implementation is not here. It lives in the shared package, because Lab 5 deploys the same code: [`workshop/src/workshop/reservation_command.py`](../workshop/src/workshop/reservation_command.py), [`contracts.py`](../workshop/src/workshop/contracts.py), and [`graph_setup.py`](../workshop/src/workshop/graph_setup.py). [`CONTRACTS.md`](CONTRACTS.md) states the frozen shapes in prose; `contracts.py` is the authority when the two disagree.

---

## What's next

**[Lab 5: Deploy to AgentCore](../05-agentcore-deploy/)** takes this same retrieval tool and this same reservation command and runs them as a managed service on Amazon Bedrock AgentCore. The retriever is unchanged, the five-field contract is unchanged, and the rule stays in the graph. The Runtime holds a read identity, the reservation Lambda holds a command identity, and the request is correlated end to end by the same `request_id` you created here. The contracts do not change. The trust boundary does.

- **Previous:** [Lab 3: Agents and tools](../03-agents-and-tools/)
- **Start from the beginning:** [Lab 1: Graph build](../01-graph-build/)

---

## Contributing

Contributions are welcome. See [CONTRIBUTING](../CONTRIBUTING.md) for more information.

## Security

If you discover a potential security issue in this project, notify AWS/Amazon Security via the [vulnerability reporting page](https://aws.amazon.com/security/vulnerability-reporting/). Please do **not** create a public GitHub issue.

## License

This library is licensed under the MIT-0 License. See the [LICENSE](../LICENSE) file for details.

> Last updated: August 2026 | Strands Agents 1.27+ | Python 3.12+
