[< Back to Main README](../README.md)

# Lab 5: Deploy to AgentCore

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://python.org)
[![AgentCore](https://img.shields.io/badge/Bedrock-AgentCore-FF9900.svg?style=flat&logo=amazon-aws)](https://aws.amazon.com/bedrock/agentcore/)
[![Lambda](https://img.shields.io/badge/AWS-Lambda-FF9900.svg?style=flat&logo=aws-lambda)](https://aws.amazon.com/lambda/)
[![Neo4j](https://img.shields.io/badge/Neo4j-AuraDB-4581C3.svg?style=flat&logo=neo4j)](https://neo4j.com/cloud/aura-free/)

Take the agent Labs 3 and 4 built, containerize it, launch it on AgentCore Runtime, expose the reservation write through AgentCore Gateway to a Lambda, correlate one request end to end, then tag and tear it all down.

The Neo4j retrieval logic does not change. `deployment-tools/booking_agent.py` imports `search_hotel_knowledge` from `workshop.hybrid_retrieval`, which is the same module Labs 2, 3, and 4 call. Same `HybridCypherRetriever`, same indexes, same reviewed Cypher traversal, same grounding instructions. Only the operational surface around it is new.

**At a Glance**
- **Failure it stops:** a grounded agent losing its grounding on the way to hosted infrastructure, where the retrieval boundary is the easiest thing to quietly widen.
- **Neo4j:** Aura reached from inside AWS, the same `HybridCypherRetriever` from Lab 2 running unchanged, and the command credential held in Secrets Manager as a JSON document of `uri`, `username`, `password`, and `database`.
- **AWS:** `bedrock-agentcore-starter-toolkit` `Runtime.configure` and `Runtime.launch`, AgentCore Runtime on ARM64, AgentCore Gateway with one Lambda target, ECR, CodeBuild, AWS Lambda, three least-privilege IAM roles, Secrets Manager, CloudWatch and AgentCore observability correlated by `request_id`, and tag-scoped teardown.
- **You'll build:** the Lab 4 agent hosted on AgentCore, invoked once end to end, then deleted by tag.

---

## Cost and cleanup: read this first

**Lab 5 is the only lab that creates billable AWS resources.** Labs 1 through 4 and Lab 6 create nothing beyond Bedrock inference calls. This lab creates an AgentCore Runtime, an AgentCore Gateway with one target, an ECR repository holding a container image, a CodeBuild project, a Lambda function, a Secrets Manager secret, and three IAM roles. They keep costing money until they are deleted.

**Teardown is part of this lab, not an afterthought.** `5.2_teardown.ipynb` is a numbered notebook in this folder for exactly that reason. Run it at the end of every rehearsal and at the end of the workshop.

**The tagging step is what makes teardown possible.** The starter toolkit creates the ECR repository, the CodeBuild project, and the Runtime itself, and it does not forward tags. `5.1_agentcore_deploy.ipynb` tags those three immediately after launch. Skipping that step means `workshop_cleanup.py` reports them as `UNTAGGED_BLOCKED`, refuses to delete them, and exits non-zero, and the infrastructure keeps running and keeps costing money.

### Roughly what it costs

> **Estimate, not a quote.** Figures are US East (N. Virginia) list prices read on 13 August 2026 and rounded hard. They vary by region, and AWS changes them. Check the [AgentCore](https://aws.amazon.com/bedrock/agentcore/pricing/), [Lambda](https://aws.amazon.com/lambda/pricing/), [ECR](https://aws.amazon.com/ecr/pricing/), [Secrets Manager](https://aws.amazon.com/secrets-manager/pricing/), and [CodeBuild](https://aws.amazon.com/codebuild/pricing/) pricing pages before quoting a number to anyone. Bedrock model tokens are billed separately and are the same for this lab as for Labs 2 through 4.

The shape of the bill is the thing to understand, and it is not the shape people expect. **AgentCore Runtime has no idle hourly charge.** It bills per session: CPU only while the agent is actually computing, memory per second for the life of the session, and nothing at all between sessions. A deployed Runtime that nobody invokes costs nothing for compute.

| Component | What drives the charge | Rough figure |
|---|---|---|
| AgentCore Runtime | Per session, per second. CPU is charged only during active processing, memory for the whole session including I/O wait | Well under a cent per invocation at this agent's size. All four smoke tests together are a fraction of a cent |
| AgentCore Gateway | $0.005 per 1,000 API invocations, plus $0.02 per 100 tools indexed per month. This lab indexes one tool | Effectively free at workshop volume. Under a cent a month standing |
| Lambda | Per request and per GB-second. A handful of short invocations | Effectively free, and inside the perpetual free tier |
| ECR storage | $0.10 per GB-month for the stored image | The image is on the order of 1 to 2 GB, so roughly 10 to 20 cents a month if you leave it |
| Secrets Manager | $0.40 per secret per month, prorated hourly, plus API calls | One secret, so about $0.40 a month. This is the largest standing charge in the lab |
| CodeBuild | Per build minute on `arm1.small`, and the first 100 build minutes a month are free tier | A few minutes per deploy, so typically nothing |

**Per full run of Lab 5**, deploy through smoke tests through teardown in one sitting, the AWS infrastructure charges land in the low single-digit cents, dominated by the prorated hour or two of Secrets Manager.

**Per hour left running**, the standing cost is roughly a tenth of a cent: the ECR image sitting in storage and the secret sitting in Secrets Manager, since neither the Runtime nor the Gateway charges for being idle. That is small, and it is also exactly why an untorn-down lab is easy to forget about. Over a month it is about 60 cents a participant, which stops being a rounding error once a room of fifty people leaves theirs behind.

**Cleanup is tag-scoped and refuses to delete untagged resources.** Two tags are in play, one per creation path:

| Tag | Applied by | Deleted by |
|---|---|---|
| `WorkshopResource=stop-ai-agent-hallucinations` | The tagging step in `5.1_agentcore_deploy.ipynb` | `workshop_cleanup.py` and `5.2_teardown.ipynb` |
| `demo06-agentcore=true` | `setup/provision_agentcore.py provision` | `setup/provision_agentcore.py teardown` |

`demo06` is a real identifier in code, not a leftover label. It is the resource-name prefix and tag key that `setup/provision_agentcore.py` writes, overridable with the `DEMO06_PREFIX` environment variable.

**Two teardown paths, because there were two creation paths.** `5.2_teardown.ipynb` removes what the deploy notebook created. `setup/provision_agentcore.py teardown` removes what provisioning created. Run both.

**The Gateway has no authorizer.** `setup/provision_agentcore.py` creates it with `authorizerType="NONE"` to keep the lab to one prerequisite instead of three. That makes the Gateway URL a credential: anyone holding it can call the reservation command and write `ReservationRequest` nodes into your graph, with no sign-in. Keep it out of screen shares and chat, do not commit it, and run both teardowns when you are done, which is what makes the URL stop existing. [`advanced-deployment/DEPLOYMENT.md`](advanced-deployment/DEPLOYMENT.md) describes the authorizer a production deployment adds.

### Many participants, one account

**Every name this lab creates comes from one prefix, which defaults to `demo06`.** That is fine when each participant has their own AWS account, which is the shape a Workshop Studio event usually hands out. It is not fine when a room shares an account: everyone provisions the same Gateway, Lambda, secret and roles, everyone launches a Runtime under the same name, and `launch(auto_update_on_conflict=True)` overwrites rather than complaining. The first teardown then deletes the whole room's work.

Give each participant a unique prefix and the collision goes away:

```bash
export DEMO06_PREFIX=demo06-yourname
```

Export it before `setup/provision_agentcore.py provision`, before opening `5.1_agentcore_deploy.ipynb`, and again before either teardown. Everything downstream follows from it:

| Derived from the prefix | Default | With `DEMO06_PREFIX=demo06-alice` |
|---|---|---|
| Resource-name prefix and owner tag key | `demo06`, `demo06-agentcore=true` | `demo06-alice`, `demo06-alice-agentcore=true` |
| Gateway target, and half the MCP tool name | `demo06-reservation-request` | `demo06-alice-reservation-request` |
| AgentCore Runtime | `HotelBookingAgent` | `HotelBookingAgentDemo06Alice` |
| ECR repository and CodeBuild project | `bedrock-agentcore-hotelbookingagent` and its `-builder` | the same, from the longer Runtime name |

`5.1` passes the target name into the container as `GATEWAY_TARGET_NAME` beside `GATEWAY_URL`, because `booking_agent.py` builds the MCP tool name from it and refuses to run against a Gateway publishing anything else. Runtime names allow letters, digits and underscores only, so the prefix is folded into CamelCase and capped at 48 characters; `5.1` fails immediately with the length rather than in a CodeBuild log five minutes later.

**A wrong prefix at teardown is the failure mode to know about.** Both teardowns derive their names the same way, so on a prefix that does not match what you provisioned they find nothing, report everything absent, and exit clean while your resources keep billing. Export the same value you deployed with.

**The Neo4j database is terminated separately.** Neo4j Aura is not an AWS resource in your account, so nothing in this folder can reach it. Delete the instance from the Aura console when you are finished. The cleanup path here is AWS-only on purpose: deleting graph records from a database that is about to be dropped wholesale adds failure modes without reclaiming anything.

---

## Notebooks

> **Build status:** all three notebooks are in place and pass with credentials absent, where every live cell skips. The live deploy, the four smoke tests, and the teardown against real AWS resources were run for real, and the record is kept with the facilitator notes rather than in this repository.

| Notebook | Status | What it does |
|---|---|---|
| `5.1_agentcore_deploy.ipynb` | **In place** | Builds the `workshop` wheel, configures and launches the Runtime, tags the toolkit-created ECR repository, CodeBuild project, and Runtime, then runs four smoke tests |
| `5.2_teardown.ipynb` | **In place** | Dry run, review, delete, then verify by listing rather than by trusting the success message |
| `5.3_agentcore_walkthrough.ipynb` | Optional. **In place** | Invokes the deployed Runtime and correlates AgentCore and CloudWatch logs by `request_id` |

`5.3` is optional and depends on `5.1`. It reads `AGENT_RUNTIME_ARN`, the value `5.1` produces at launch. Provisioning does not write that key, because provisioning does not know the ARN: only a launch produces one. `5.1` writes it into the repository-root `.env` itself, with the same in-place upsert `setup/provision_agentcore.py` uses for its three keys, so `5.3` finds it in a fresh kernel with nothing to copy by hand. It also prints the `export` line if you would rather set it in a shell. If neither has happened, every live cell in `5.3` skips.

The order to run them is `5.1`, then `5.3` if you want it, then `5.2` last. The table above is numbered, not sequenced: `5.2` deletes the Runtime that `5.3` invokes, so teardown goes at the end whether or not you take the optional walkthrough. Start here, from this directory:

```bash
code 5.1_agentcore_deploy.ipynb
```

`5.1` requires `setup/provision_agentcore.py provision` to have run first. It reads `AGENTCORE_GATEWAY_URL` and `AGENTCORE_RUNTIME_ROLE_ARN` from the repository-root `.env` and skips every live cell until both are set.

`5.2_teardown.ipynb` also runs correctly from the repository root. Its first cell searches the current directory, `05-agentcore-deploy/`, and `../05-agentcore-deploy/` for `workshop_cleanup.py` and raises with the paths it tried rather than importing something unexpected.

### The two reference sources being retargeted

`deploy_agentcore.ipynb` is present in this folder as the **source material for authoring `5.1`**, not as a participant path, and it opens with a banner saying so. It targets the earlier module layout: DynamoDB hotel, booking, and steering-rule tables, its own IAM roles, seven booking-lifecycle Lambdas, and its own Gateway creation. Two parts of it carry over unchanged: step 8, which calls `Runtime.configure` and `Runtime.launch` from `bedrock_agentcore_starter_toolkit`, and the tagging cell that follows it.

**Do not run it.** It references a `query_knowledge_graph` Lambda that no longer exists, so it fails partway through with billable resources already created, and it points at an `08-cleanup/` folder that is gone. Nothing it creates carries the `WorkshopResource` tag, so `5.2_teardown.ipynb` will not clean up after it.

`advanced-deployment/02_agentcore_walkthrough.ipynb` is the source material for `5.3`. See [`advanced-deployment/README.md`](advanced-deployment/README.md).

---

## The second peak of the partnership

Lab 1 is the first peak, where Bedrock extraction and Neo4j storage sit in the same call path. Lab 5 is the second and higher one, and it makes the cleanest partnership argument in the workshop by changing as little as possible.

What is identical to Lab 2:

- the same `HybridCypherRetriever` configuration, the same vector and full-text indexes, and the same reviewed Cypher traversal
- the same `search_hotel_knowledge` function, imported by `booking_agent.py` from `workshop.hybrid_retrieval`
- the same `GROUNDING_INSTRUCTIONS` text in the system prompt
- the same two hero questions, one grounded and one that forces abstention

What changes:

- the retrieval tool runs in a container on AgentCore Runtime instead of in a notebook kernel
- the reservation write from Lab 4 is reached over MCP through AgentCore Gateway to a Lambda instead of being called in process
- credentials come from Secrets Manager instead of a local `.env`
- the request is observable in CloudWatch and AgentCore traces instead of in cell output

Neo4j owns the connected data and the retrieval contract. AWS owns hosting, tool exposure, identity, and observability. Nothing in the first list has to move for the second list to arrive.

### Architecture

```
caller (prompt + request_id)
   -> AgentCore Runtime  [booking_agent.py, ARM64 container from ECR]
        |
        +-- search_hotel_knowledge   in-process -> Neo4j Aura   (read)
        |
        +-- AgentCore Gateway (MCP, one target)
                 -> create_reservation_request Lambda -> Neo4j Aura   (rule check + idempotent write)
```

The Gateway exposes exactly one tool, named `demo06-reservation-request___create_reservation_request` on the default prefix: the Gateway target name and the schema tool name joined by three underscores. `booking_agent.py` builds that name from the `GATEWAY_TARGET_NAME` the launch passes in, calls `list_tools_sync()` at startup, and raises if the discovered tool list is anything other than that single name, so a Gateway that has grown an extra target fails loudly instead of handing the model a wider surface.

---

## Prerequisites

- **Labs 1 through 4 completed.** Lab 5 deploys what Lab 4 produced, against the graph Lab 1 built.
- **[Python](https://python.org/downloads) 3.12+.** That is the floor `requirements.txt` installs: its first line is `-e ../workshop`, and `workshop/pyproject.toml` declares `requires-python = ">=3.12"`. `workshop_cleanup.py` also uses `enum.StrEnum`, which is 3.11 and later, so the script alone cannot run below 3.11 even if you install it without the package.
- **[uv](https://docs.astral.sh/uv/)** package manager.
- **AWS credentials** allowed to create Secrets Manager secrets, IAM roles, Lambda functions, and `bedrock-agentcore-control` resources. The region resolves from `AWS_REGION`, then `AWS_DEFAULT_REGION`, then defaults to `us-east-1`.
- **Amazon Bedrock model access.** The deployed agent runs on `us.anthropic.claude-sonnet-5`, the one model id the whole workshop uses, defined in `workshop.bedrock_providers` and overridable with the `MODEL_ID` environment variable, which `5.1` forwards into the container. Enable that model in your region's Bedrock console before deploying. The Runtime role itself grants `bedrock:InvokeModel` on foundation models generally rather than on one model id, so a `MODEL_ID` override needs no IAM change.
- **Neo4j values in the repo-root `.env`:** `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD`. `NEO4J_DATABASE` is optional and defaults to `neo4j`. Provisioning refuses to run without the first three, because they become the command secret.

Install this lab's dependencies:

```bash
cd 05-agentcore-deploy
uv venv && uv pip install -r requirements.txt
```

That installs `bedrock-agentcore-starter-toolkit`, `strands-agents`, and the shared `workshop` package in editable mode with `-e ../workshop`.

No local ARM64 Docker build is required. The starter toolkit creates a CodeBuild project and builds the ARM64 image there, which is why the tagging step has a CodeBuild project to tag.

---

## Step 1: Provision the infrastructure

`setup/provision_agentcore.py` runs first and stands up the slow, privileged infrastructure that the deploy notebook depends on. It mirrors what Workshop Studio pre-provisions for hosted participants. Run all three subcommands from the repository root:

```bash
uv run setup/provision_agentcore.py provision      # Create every resource in dependency order
uv run setup/provision_agentcore.py status         # Report the presence of each resource, no changes
uv run setup/provision_agentcore.py teardown       # Delete every resource, prompts to confirm
uv run setup/provision_agentcore.py teardown --yes # Delete without the confirmation prompt
```

**`provision` creates real, billable AWS resources.** `status` is read-only and safe to run at any point. `teardown` deletes in reverse dependency order: target, gateway, Lambda, roles, secret.

`provision` is idempotent. Re-running it reuses existing roles, updates the secret and the Lambda in place, and rewrites the managed `.env` block rather than appending duplicates.

### What `provision` creates

Every resource is tagged `demo06-agentcore=true` and named with the `demo06` prefix.

| Resource | Name | Role |
|---|---|---|
| Secrets Manager secret | `demo06/neo4j-command` | Holds the Neo4j command credential that the reservation Lambda reads |
| IAM role, Lambda | `demo06-reservation-lambda-role` | Reservation Lambda execution: writes its own log group, reads only its own secret |
| IAM role, Gateway | `demo06-gateway-role` | Scoped to invoke only the one reservation Lambda |
| IAM role, Runtime | `demo06-runtime-role` | ECR pulls, Runtime log groups, X-Ray, workload-identity tokens, and Bedrock model invocation. Grants no secret access |
| Lambda function | `demo06-reservation-request` | The single reservation command behind the Gateway, wrapping `workshop.reservation_command` |
| AgentCore Gateway | `demo06-gateway` | NONE-auth MCP Gateway exposing exactly one target |
| Gateway target | `demo06-reservation-request` | The sole target, defined by `deployment-tools/gateway_target.json`, exposing only `create_reservation_request` |

Three least-privilege roles rather than one shared role. The Runtime can invoke the model and pull its image but cannot read the command secret. The Gateway can invoke one Lambda and nothing else. The Lambda can read one secret and write one log group.

The Lambda runs on `python3.12`, `arm64`, with a 30-second timeout and 256 MB of memory. Its dependencies install with an `aarch64-manylinux2014` platform target so the wheels import at cold start even when the provisioning host is macOS.

### The `.env` handoff

`provision` writes three identifiers into a managed block in the repo-root `.env`, and `teardown` removes them along with the block's header line, so nothing stale is left pointing at AWS. Never set these by hand:

| Key | Meaning |
|---|---|
| `AGENTCORE_GATEWAY_URL` | The MCP URL the Runtime uses to discover the reservation command |
| `AGENTCORE_RUNTIME_ROLE_ARN` | The Runtime execution role ARN the deploy step launches with |
| `NEO4J_COMMAND_SECRET_ID` | The command secret ARN the reservation Lambda reads Neo4j from |

The dependency arrow points one way. `setup/provision_agentcore.py` reads files in this folder to package the Lambda and to learn the contracts. Nothing in this folder reads anything under `setup/`. The full reference is in [`../setup/README.md`](../setup/README.md).

---

## Step 2: Deploy the Runtime

`5.1_agentcore_deploy.ipynb` configures and launches the Runtime. The mechanism, carried over from `deploy_agentcore.ipynb` step 8:

```python
import os
from bedrock_agentcore_starter_toolkit import Runtime

# The container build context. The toolkit builds from the current directory:
# it honors the Dockerfile it finds there and copies only that directory into
# the image. Run it from 05-agentcore-deploy/ instead and the toolkit generates
# its own Dockerfile, ignores the hand-written one, and ships the whole folder.
os.chdir("deployment-tools")

agent_runtime = Runtime()
agent_runtime.configure(
    entrypoint="booking_agent.py",
    execution_role=AGENTCORE_RUNTIME_ROLE_ARN,
    auto_create_ecr=True,
    requirements_file="agent_requirements.txt",
    region=REGION,
    agent_name=RUNTIME_NAME,
    deployment_type="container",
    non_interactive=True,
)
result = agent_runtime.launch(
    auto_update_on_conflict=True,
    env_vars={
        "AWS_REGION": REGION,
        "GATEWAY_URL": GATEWAY_URL,
        "GATEWAY_TARGET_NAME": GATEWAY_TARGET_NAME,
        ...,
    },
)
```

Both filenames are bare, not folder-prefixed, and that follows from the `chdir`. They are resolved against the build context, so `deployment-tools/booking_agent.py` would be looked for at `deployment-tools/deployment-tools/booking_agent.py` and would not be found.

`configure` writes a `.bedrock_agentcore.yaml` file into `deployment-tools/`, beside the entrypoint, holding the runtime ID from that deploy. `5.1` deletes any existing one as pre-flight, because a stale ID makes the next run try to update a Runtime teardown already deleted. `launch` builds the ARM64 image in CodeBuild, creates the ECR repository, pushes the image, and creates the Runtime. Budget three to five minutes for the launch. `result.agent_arn` is the value `5.3` needs as `AGENT_RUNTIME_ARN`, and `5.1` writes it into the repository-root `.env` rather than only printing it.

`GATEWAY_URL` is required. `booking_agent.py` raises `GATEWAY_URL is required for the deployed Runtime` when it is absent, rather than starting up with no command tool. `GATEWAY_TARGET_NAME` is what makes a per-participant prefix work; leave it out and the container falls back to `demo06-reservation-request` and fails Gateway discovery on every invocation.

## Step 3: Tag what the toolkit created

Immediately after launch, `5.1` tags three resources the toolkit created on your behalf:

| Resource | Name shape |
|---|---|
| ECR repository | `bedrock-agentcore-<runtime-name-lowercased>` |
| CodeBuild project | `bedrock-agentcore-<runtime-name-lowercased>-builder` |
| AgentCore Runtime | tagged by the ARN the launch returned |

Each is addressed by exact name or by ARN. Nothing is enumerated and nothing is prefix-matched. The Runtime tag is read back and verified rather than assumed. The toolkit's shared `AmazonBedrockAgentCoreSDKCodeBuild-*` IAM role is deliberately left untagged: it is shared across projects, costs nothing, and tagging it would make it eligible for deletion.

## Step 4: Correlate one request end to end, optional

`5.3_agentcore_walkthrough.ipynb` invokes the deployed Runtime and follows a single request through every layer.

The caller creates a canonical UUID and passes it as `request_id` alongside the prompt. The Runtime passes that exact value to the Gateway command. `ReservationRequestGuard`, a Strands `BeforeToolCallEvent` hook in `booking_agent.py`, cancels the tool call with a `BLOCKED:` message if the model omits the request ID or substitutes one of its own. The same ID appears in Runtime logs, Lambda logs, AgentCore traces, and on the stored `ReservationRequest` node in Neo4j, so one CloudWatch Logs Insights search on `request_id=` recovers the whole path.

Every invocation returns four keys, and the fourth is the one worth reading. `response` is the model's prose, `tools_used` lists the tools it attempted, `request_id` echoes what the caller sent, and `command_result` is the reservation command's own response: the `status`, `reason_code`, and `duplicate` that `workshop.reservation_command` computed inside the Lambda after reading the rule out of the graph. A second Strands hook, `CommandResultRecorder`, carries it out of the container on `AfterToolCallEvent`. It matters because `tools_used` records an attempt: a call the guard cancelled, a Lambda that failed on auth, and a Gateway 5xx all put the command's name in that list and all leave the graph empty, which is exactly what a genuine rule rejection also looks like. `command_result` is what tells them apart, and it is `null` when the command was never reached, which is why `5.1`'s third smoke test asserts on its `reason_code`.

Logs record the request ID and never prompts, credentials, secret payloads, or connection strings.

## Step 5: Tear down

```bash
python workshop_cleanup.py             # dry run by default: print the plan, touch nothing
python workshop_cleanup.py --dry-run   # the same read-only run, made explicit
python workshop_cleanup.py --yes       # execute it and delete the tagged resources
```

Run these from `05-agentcore-deploy/`. The default is a dry run, so running the script with no arguments never deletes anything. All three exit non-zero when the teardown is incomplete, so they are safe to call from a script. `5.2_teardown.ipynb` runs the same module and shows the dry run before it deletes.

Deletion happens in tiers, and each tier is polled to actual absence before the next one is touched, with a 600-second timeout per tier:

1. **AgentCore plane:** runtime, gateway, memory. These hold references to everything else.
2. **Compute and data:** Lambda functions, Lambda layer versions, DynamoDB tables, ECR repositories, CodeBuild projects.
3. **IAM:** roles, last, so nothing is still assuming them.
4. **Local:** the `.bedrock_agentcore.yaml` config file, which is not an AWS resource and cannot race.

Accepting a delete request is not the same as the resource being gone, which is why absence is observed rather than assumed. Anything still standing when the timeout expires is named in the output and forces a non-zero exit.

### Two documented exceptions to the tag gate

`UNTAGGABLE_KINDS` in `workshop_cleanup.py` lists the only two kinds matched directly rather than by tag, and a unit test pins the contents of that set so the exemption cannot quietly grow:

- **Lambda layer versions.** AWS does not support tags on them, so they are matched by exact name.
- **The local `.bedrock_agentcore.yaml` config file.** Matched by fixed repo-relative path, one per lab directory, never by glob. An earlier version globbed `~/.bedrock_agentcore*.yaml` and destroyed unrelated local config belonging to other AgentCore projects on the same machine.

### Why tags and not names

An earlier version of this teardown selected IAM roles whose names started with `AmazonBedrockAgentCoreSDKCodeBuild`. IAM is global, so that swept the entire account across every region and destroyed five roles this workshop never created, two of them in a different region. A name prefix describes what a resource is *called*. A tag records who *owns* it. Only the second is safe to delete on. Measured on the development account: 426 IAM roles exist, 126 of them have names a prefix scheme would plausibly match, and the tag gate selects zero of them.

The inverse also holds. `discover_roles` selects every role in the account carrying the workshop tag, whatever it is named. Apply that tag only to resources you want this teardown to delete.

### What teardown does not delete

- **Your Aura instance and the graph Lab 1 built.** Delete the instance from the Aura console.
- **CloudWatch log groups.** Retained so the run can be reviewed. Delete them by hand.
- **The toolkit's shared `AmazonBedrockAgentCoreSDKCodeBuild-*` IAM role.** Deleting it is what caused the original incident.
- **The toolkit's CodeBuild source bucket, `bedrock-agentcore-codebuild-sources-<account-id>-<region>`.** The toolkit creates it untagged and shares it across every AgentCore deployment in that account and region, so it is outside the tag gate and there is no S3 discoverer here at all. It carries a 7-day object expiry rule and a few megabytes of build source, so it is close to free. `CLEANUP.md` has the reasoning and the two commands to remove it by hand.
- **Anything untagged.** By design.

---

## Credentials and secrets

The reference boundary in [`advanced-deployment/DEPLOYMENT.md`](advanced-deployment/DEPLOYMENT.md) describes two Neo4j identities that never share a credential:

- **Runtime-read.** Reads the prepared `Chunk`, `Document`, `Hotel`, and `Amenity` data and their retrieval relationships. No graph write privileges.
- **Lambda-command.** Reads the `max_guests` rule and fixture hotel identity, and creates workshop-owned `ReservationRequest` nodes and `FOR_HOTEL` relationships. Cannot update or delete canonical hotel, chunk, document, amenity, or rule data.

Both secrets have the same JSON shape:

```text
uri, username, password, database
```

**The executable path here is the one-user form of that boundary.** `setup/provision_agentcore.py` creates a single secret, `demo06/neo4j-command`, for the Lambda. There is no `NEO4J_READ_SECRET_ID`: the deployed Runtime reads Neo4j from `NEO4J_*` environment variables through `workshop.hybrid_retrieval`. The two-user, two-secret split is documented as the production hardening step, and `DEPLOYMENT.md` is explicit that both credentials should be kept even on an Aura tier that cannot express every graph privilege separately, because the Lambda's fixed parameterized Cypher remains the application-level command boundary.

Secret values must never appear in a deployment package, a Gateway schema, a prompt, or a log.

---

## Tests

```bash
cd 05-agentcore-deploy
uv run --with pytest --with-requirements requirements.txt -m pytest
```

**29 tests**, no AWS credentials needed. A bare `pytest` collects both files in this lab and both run against the lab venv.

**20 in `test_workshop_cleanup.py`.** Every AWS client is an injected fake. The headline test is `test_untagged_unrelated_roles_are_never_selected`, which reproduces the exact account shape the original incident damaged and asserts none of those roles is selected. `test_dry_run_issues_no_mutating_calls` pins the dry run to read-only calls, and `test_resource_in_use_is_retried_and_never_reported_deleted` pins the poll-to-absence behavior.

**9 in `deployment-tools/test_runtime_integration.py`.** These pin the Runtime and Gateway boundary offline: that the Gateway fails closed when it discovers anything other than the one reservation command, that the hooks refuse a reservation call whose `request_id` is not the caller's and record the command's verdict without reshaping a broken call into something that reads like a rule rejection, that the deployed read path touches only the read secret, and that the image excludes the Lambda and the legacy notebooks. They run locally because `requirements.txt` declares `bedrock-agentcore` and `mcp` for exactly this reason.

---

## What is in this folder

```
05-agentcore-deploy/
├── README.md                       # This file
├── 5.1_agentcore_deploy.ipynb      # Build the wheel, launch the Runtime, tag it, four smoke tests
├── 5.2_teardown.ipynb              # Tag-scoped teardown, dry run first
├── 5.3_agentcore_walkthrough.ipynb # Optional: one request correlated end to end
├── deploy_agentcore.ipynb          # Superseded, banner says so. Reference source for authoring 5.1, never run
├── workshop_cleanup.py             # The one teardown implementation
├── test_workshop_cleanup.py        # 20 tests, fakes injected, no AWS needed
├── CLEANUP.md                      # Long-form teardown reasoning and incident history
├── requirements.txt                # Starter toolkit, Strands, and -e ../workshop
├── tool_schemas/
│   └── tools.json                  # Read only by Lab 4's test_contracts.py. The Gateway
│                                   #   reads deployment-tools/gateway_target.json instead
├── deployment-tools/               # The deployable source, and the container build context
│   ├── booking_agent.py            # Runtime entry point: in-process retrieval + one Gateway command
│   ├── Dockerfile, .dockerignore   # Runtime container image
│   ├── agent_requirements.txt      # Runtime dependencies deployed to AgentCore
│   ├── vendor/                     # The workshop wheel, rebuilt by 5.1 on every deploy, gitignored
│   ├── gateway_target.json         # The single Gateway target manifest
│   ├── lambda_tools/
│   │   └── create_reservation_request/
│   └── test_runtime_integration.py # Deployment-environment tests only
└── advanced-deployment/            # Reference only
    ├── 02_agentcore_walkthrough.ipynb  # Reference source for authoring 5.3
    └── DEPLOYMENT.md               # The production-hardening boundary
```

Read `CLEANUP.md` for the reasoning behind the tag gate and for the incident history. Take `workshop_cleanup.py` itself as the authority on what is deleted.

## The acceptance runner

The notebook registry in `setup/run_notebooks.py` already lists all three Lab 5 notebooks with their gates: `5.1_agentcore_deploy.ipynb` and `5.3_agentcore_walkthrough.ipynb` carry `deploys_resources=True`, and `5.2_teardown.ipynb` carries `deletes_resources=True`. That is why teardown is its own notebook rather than a closing section: the gate is a `NotebookSpec` field, and a section cannot hold one.

The registry lists them in run order, `5.1`, `5.3`, `5.2`, rather than by number, so passing both flags at once deploys, walks through, and then tears down. Registered by number, the pair would tear the Runtime down and then run the walkthrough against a deleted ARN.

Both gated commands create or delete real, billable AWS resources, and both need a provisioned account to pass:

```bash
uv run setup/run_notebooks.py --labs 5 --include-deploy
uv run setup/run_notebooks.py --labs 5 --include-cleanup
```

Without those flags, Lab 5 is skipped, which is how the default `uv run setup/run_notebooks.py` stays green and free.

---

## Troubleshooting

**The Runtime launch fails.** Read the CodeBuild logs first; the image build is where most launch failures actually happen. Then check three things in order: that `AGENTCORE_RUNTIME_ROLE_ARN` in the repo-root `.env` is populated and that the role still exists, that the Bedrock model the Runtime role authorizes is enabled in your region, and that `.bedrock_agentcore.yaml` in this folder is not left over from an earlier attempt against a different agent name. Delete that file and re-run `configure` if it is stale. `launch(auto_update_on_conflict=True)` updates an existing Runtime instead of failing on a name conflict. A launch that fails part way can still have created a tagged ECR repository and CodeBuild project, so run the teardown even after a failed launch.

**`GATEWAY_URL is required for the deployed Runtime`.** The `env_vars` argument to `launch` did not include `GATEWAY_URL`. Take the value from `AGENTCORE_GATEWAY_URL` in the repo-root `.env`.

**`Gateway must expose only demo06-reservation-request___create_reservation_request`.** Three causes, in the order worth checking. The Gateway has more than one target. Its single target was created from something other than `deployment-tools/gateway_target.json`. Or you provisioned under a `DEMO06_PREFIX` and the launch did not pass the matching `GATEWAY_TARGET_NAME`, so the container is looking for the default name and the Gateway is publishing yours; the error message names what it wanted and lists what it found, so the two spellings are visible side by side. `booking_agent.py` raises rather than handing the model a wider tool surface. Run `uv run setup/provision_agentcore.py status` to see which targets exist.

**The `.env` identifiers from provisioning are missing.** `AGENTCORE_GATEWAY_URL`, `AGENTCORE_RUNTIME_ROLE_ARN`, and `NEO4J_COMMAND_SECRET_ID` are written by `provision` and cleared by `teardown`, never set by hand. Run `uv run setup/provision_agentcore.py status` from the repository root to see what exists, then re-run `provision`, which is idempotent and rewrites the managed block. If `provision` refuses to start, one of `NEO4J_URI`, `NEO4J_USERNAME`, or `NEO4J_PASSWORD` is missing from the repo-root `.env`; those three plus `NEO4J_DATABASE`, which defaults to `neo4j`, become the command secret. `AGENT_RUNTIME_ARN` is a separate case: provisioning never writes it, `5.1` produces it at launch, and `5.3` needs it set.

**Resources are left behind after teardown.** Read the exit output rather than assuming. Anything listed under `UNTAGGED_BLOCKED` exists but carries no workshop tag, which usually means the tagging step in `5.1` was skipped or a partial launch created a resource before tagging ran. Two ways to clear the block, and both start with confirming the resource is yours:

```bash
# 1. Adopt it by tagging, then re-run cleanup. Tagging is a claim of ownership.
aws ecr tag-resource --resource-arn <arn> \
  --tags Key=WorkshopResource,Value=stop-ai-agent-hallucinations
python workshop_cleanup.py --yes
```

Or delete it by hand in the console, one resource at a time, reading each name before confirming. Do not write a loop over a name prefix; that is the mistake that destroyed five unrelated roles.

Anything listed under `FAILURES` hit a real error or was still present when its tier timed out. Re-run the dry run to see the current state. IAM is global but Lambda, ECR, CodeBuild, and AgentCore are regional, so an older run in another region is invisible from this one; repeat the dry run with `--region` for every region you have used. Creation time is the evidence that a resource came from an older run:

```bash
aws ecr describe-repositories --repository-names <name> --query 'repositories[0].createdAt'
aws lambda get-function-configuration --function-name <name> --query 'LastModified'
aws iam get-role --role-name <name> --query 'Role.CreateDate'
```

**Teardown says it succeeded but the bill does not drop.** Two things survive on purpose: CloudWatch log groups, and the Aura instance. Delete the log groups by hand if you want them gone, and terminate the Aura instance from the Aura console. Also confirm you ran both teardown paths, since `workshop_cleanup.py` does not touch what `setup/provision_agentcore.py` created.

**Skip cleanup entirely if you are in an AWS-provided workshop account.** Those are cleaned up for you.

---

## What's next

**[Lab 6: Neo4j agent memory](../06-memory/)**, which is optional. Graph-native memory with full provenance and actor isolation, weighed against the managed alternative. The core path ends here, on the AWS crescendo.

- **Previous:** [Lab 4: The grounded write](../04-grounded-write/)
- **Start from the beginning:** [Lab 1: Graph build](../01-graph-build/)

---

## Contributing

Contributions are welcome. See [CONTRIBUTING](../CONTRIBUTING.md) for more information.

## Security

If you discover a potential security issue in this project, notify AWS/Amazon Security via the [vulnerability reporting page](https://aws.amazon.com/security/vulnerability-reporting/). Please do **not** create a public GitHub issue.

## License

This library is licensed under the MIT-0 License. See the [LICENSE](../LICENSE) file for details.

> Last updated: August 2026 | Strands Agents 1.27+ | Python 3.12+ | Amazon Bedrock AgentCore
