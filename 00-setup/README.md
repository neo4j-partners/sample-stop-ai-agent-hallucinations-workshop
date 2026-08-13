[< Back to Main README](../README.md)

# Lab 0: Setup

> **Do this before the session, not during it.** Budget 20 to 30 minutes, and read Step 4 first. Bedrock model access is requested per model and per region, and it is the one part of Lab 0 whose timing you do not control. Everything else here takes a few minutes.

Two credentials carry the whole workshop: one Neo4j Aura instance and one AWS account with Amazon Bedrock access. Get both working here and every later lab runs without a credential detour.

Lab 0 has no notebook and nothing to install. It is a checklist that ends in one verification command.

## Where this sits

Neo4j owns the connected data, and AWS owns reasoning and hosting. That split is the through-line of all six labs, and Lab 0 provisions one of each side: the Aura instance that will hold the graph, and the Bedrock access that will do the extraction and the reasoning against it.

![The six-lab path from raw documents to a deployed agent](../images/six-lab-path.svg)

| # | Lab | What it produces |
|:-:|-----|------------------|
| 0 | Setup | An Aura instance, Bedrock model access, and one repo-root `.env` |
| 1 | [Graph build](../01-graph-build/) | The hotel knowledge graph, extracted live by Bedrock against a pinned schema, with vector and full-text indexes |
| 2 | [Retrieval](../02-retrieval/) | Four retrievers over that graph, closing on a question the graph cannot answer |
| 3 | [Agents and tools](../03-agents-and-tools/) | Strands agents, tools, hooks, and swarms, ending with `hotel_agent` calling the Lab 2 retriever |
| 4 | [The grounded write](../04-grounded-write/) | An idempotent reservation write, with a rule read from the graph rejecting a request the prompt alone would allow |
| 5 | [Deploy to AgentCore](../05-agentcore-deploy/) | The same agent on AgentCore Runtime with the retriever unchanged, then torn down |
| 6 | [Neo4j agent memory](../06-memory/) | Optional. Graph-native memory with provenance and actor isolation |

Each lab consumes what the previous one produced, so the credentials you set here are read unchanged by all six.

**At a Glance**
- **Neo4j:** one Aura instance, serving all six labs. APOC Core ships with it, so there is no plugin to enable.
- **AWS:** Bedrock model access for `us.anthropic.claude-sonnet-5` and `amazon.nova-2-multimodal-embeddings-v1:0`, plus `amazon.titan-embed-text-v2:0` if you are running the optional Lab 6.
- **You'll end with:** one `.env` file at the repository root and one command that proves both credentials work.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- The [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html), used in Step 4 to confirm which identity the SDK will use
- An AWS account with [Amazon Bedrock](https://aws.amazon.com/bedrock/) access
- A Neo4j Aura account, or the instance details handed out at a hosted workshop

---

## Step 1: Clone the repository

Every lab runs from a checkout of this repository, and Step 3 writes a file into its root.

```bash
git clone https://github.com/aws-samples/sample-stop-ai-agent-hallucinations-workshop.git
cd sample-stop-ai-agent-hallucinations-workshop
```

**At a hosted workshop:** the repository is already cloned on the provided Code Editor instance. Open a terminal there and skip to Step 2.

## Step 2: Get a Neo4j Aura instance

One Aura instance serves every lab. It holds the hotel knowledge graph, the vector and full-text indexes, the `max_guests` production rule, the reservation requests, and the optional memory graph.

**At a hosted workshop:** an instance is provided. Collect the URI, the username, and the password from the event materials and skip to Step 3.

**Self-paced:**

1. Go to [console.neo4j.io](https://console.neo4j.io) and create a free **AuraDB** instance.
2. Download the credentials file when prompted. It holds the connection URI, the username, and the generated password. The password is shown once, so save the file.
3. Wait for the instance to report **Running**.

APOC Core is preinstalled on every Aura instance, so Lab 1's graph build has nothing to enable. There is no plugin step here.

The graph itself is empty at this point. Lab 1 builds it: roughly 15 minutes for the 30-document lite corpus, or 2 hours for the full 300.

## Step 3: Write the repo-root `.env`

Which command you run depends on whether an environment was generated for you.

**At a hosted workshop.** The CloudFormation environment writes `/workshop/.env` with the provided instance already filled in. Copy that file rather than the template, because the template would replace real credentials with `NEO4J_PASSWORD=changeme`:

```bash
ls -l /workshop/.env          # confirm the generated file exists
cp /workshop/.env .env
```

Then add one line to the copy. The generated file names the username `NEO4J_USER`, and every lab in this repository reads `NEO4J_USERNAME`:

```bash
echo "NEO4J_USERNAME=$(grep '^NEO4J_USER=' .env | cut -d= -f2-)" >> .env
```

If authentication fails only inside the hosted workshop, this mismatch is the first thing to check. The verification script in Step 5 accepts `NEO4J_USER` and warns when it had to, so a passing check with that warning still means Lab 1 will fail.

**Self-paced.** Copy the template, from the repository root, and leave an existing `.env` alone:

```bash
[ -f .env ] || cp .env.example .env
```

Two values always need typing:

| Variable | Value |
|---|---|
| `NEO4J_URI` | `neo4j+s://<your-instance>.databases.neo4j.io` from the credentials file. The template ships the same string with `<your-instance>` still in it, so this one always needs replacing |
| `NEO4J_PASSWORD` | the generated password from the credentials file. The template ships `changeme` |

The rest of the file ships with a working value:

| Variable | Shipped value | Change it when |
|---|---|---|
| `NEO4J_USERNAME` | `neo4j` | Your instance uses a different username. `neo4j` is what Aura provisions |
| `NEO4J_DATABASE` | `neo4j` | You are targeting a non-default database. The variable is optional, and the labs default it to `neo4j` through `workshop.contracts.DEFAULT_NEO4J_DATABASE` |
| `AWS_REGION` | `us-east-1` | Your Bedrock models are enabled somewhere else. Use one region where all of them are |

Every lab loads the nearest `.env` first, so a `.env` inside a lab folder overrides this one. Keeping a single file at the repository root is the simplest arrangement, and Step 5 reports which file it read. `.env` is gitignored; keep it that way.

**After changing any credential, restart the notebook kernel.** A notebook reads `.env` once, when the kernel starts, so an already-running kernel keeps the old values and fails with the error you just fixed.

## Step 4: Request and confirm Bedrock model access

Start here, because access is granted per model and per region and the request is not always instant.

Open the [Bedrock Model Access console](https://console.aws.amazon.com/bedrock/home#/modelaccess) in the region named by `AWS_REGION` and request access to these models:

| Model ID | Used for | Needed by |
|---|---|---|
| `us.anthropic.claude-sonnet-5` | Lab 1 entity and relationship extraction, then agent reasoning in Labs 2 through 5 | Required |
| `amazon.nova-2-multimodal-embeddings-v1:0` | Lab 1 chunk embeddings and every Lab 2 query embedding, at 1024 dimensions | Required |
| `amazon.titan-embed-text-v2:0` | Lab 6 memory embeddings, also at 1024 dimensions. A separate embedding contract from the one above, on purpose | Lab 6 only |

Enabling one model proves nothing about the others, so request all three unless you are certain you will skip Lab 6. The `us.` prefix marks a cross-region inference profile, so pair it with a US region such as `us-east-1`.

AWS credentials come next. At a hosted workshop they are already configured; self-paced participants run `aws configure` or export `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`. Confirm the identity the SDK will use, from the repository root:

```bash
aws sts get-caller-identity --query Arn --output text
```

## Step 5: Verify both credentials

Run this from the repository root:

```bash
uv run 00-setup/verify_setup.py
```

From inside a lab folder the path is `../00-setup/verify_setup.py`, and the check works the same either way.

`00-setup/verify_setup.py` is a [PEP 723](https://peps.python.org/pep-0723/) script, so `uv` reads its dependencies from the header and manages the environment for it. There is no virtual environment to create and nothing to install first.

It checks the Python version before importing anything, reports which `.env` supplied the values, connects to Aura, counts APOC procedures, sends one short Bedrock prompt, and embeds one string through the same `BedrockEmbeddings` class Lab 1 writes chunk vectors with. It writes nothing to the graph and creates no AWS resources. The model IDs, the embedding purpose, and the 1024-dimension width are imported from the shared `workshop` package rather than restated, so this check and the labs cannot disagree about them.

A finished Lab 0 looks like this:

```
Workshop setup check

  [ OK ] Environment file: /path/to/repo/.env supplied the values
  [ OK ] AWS region: us-east-1, from .env
  [ OK ] Neo4j settings: database neo4j, from .env
  [ OK ] Neo4j connection: neo4j+s://<your-instance>.databases.neo4j.io, database neo4j, 162 APOC procedures
  [ OK ] Bedrock chat: us.anthropic.claude-sonnet-5 answered in us-east-1
  [ OK ] Bedrock embeddings: amazon.nova-2-multimodal-embeddings-v1:0 returned 1024 dimensions, purpose GENERIC_INDEX
  [ OK ] Lab 6 embeddings: amazon.titan-embed-text-v2:0 returned 1024 dimensions

Every check passed. Open 01-graph-build/1.1_build_graph.ipynb next.
```

The APOC count varies by Aura version, and any nonzero count is fine. The embedding width must read 1024, because that is what Lab 1 writes into the vector index and Lab 2 queries against.

Lab 6 is optional, so a Titan failure is reported as a warning and the run still exits zero. Add `--lab6` to make that check required:

```bash
uv run 00-setup/verify_setup.py --lab6
```

The exit code is what to trust: zero means every required check passed. A `[FAIL]` or `[SKIP]` line names the credential that is still missing, and the table below covers each message.

---

## Troubleshooting

| Message | Fix |
|---|---|
| `Python 3.12+ is required` | The interpreter `uv` picked is older than the floor the shared `workshop` package declares. Install Python 3.12 or newer, or run `uv run --python 3.12 00-setup/verify_setup.py` |
| `[FAIL] Environment file: no .env found` | Nothing named `.env` sits in the working directory, its parents, or the repository root. Revisit Step 3 |
| `[FAIL] Neo4j settings: missing from .env: ...` | The named variables are absent or blank. `NEO4J_DATABASE` never appears in this list, because it is optional and defaults to `neo4j` |
| `[WARN] Environment file: ... shadows the repository-root ...` | A lab-local `.env` is winning over the root one, which is the documented precedence. Values absent from the closer file still fall through to the root file, so the two can disagree without an error. Delete the lab-local file unless you meant to have it |
| `[WARN] Neo4j username: NEO4J_USERNAME is unset and NEO4J_USER is set` | The hosted Workshop Studio spelling. This check accepts it and the labs do not, so add `NEO4J_USERNAME` with the same value before starting Lab 1 |
| `[FAIL] Neo4j APOC: connected, but no APOC procedures are visible` | The URI points at something other than an Aura instance. Aura ships APOC Core; a self-hosted Neo4j needs the APOC plugin installed |
| `Neo4jError: ... AuthenticationRateLimit` or `Unauthorized` | The username or password is wrong. Re-read them from the downloaded credentials file |
| `Unable to retrieve routing information` or a connection timeout | The URI is wrong, or the instance is paused. Confirm it reads **Running** in the Aura console and that the URI starts with `neo4j+s://` |
| `AccessDeniedException` from Bedrock | Read the model ID in the message before acting: access is per model, so having one enabled proves nothing about another. Request access for that exact ID in the [Bedrock Model Access console](https://console.aws.amazon.com/bedrock/home#/modelaccess), in the region `AWS_REGION` names. Lab 6 is the usual surprise here, because it is the only lab that uses `amazon.titan-embed-text-v2:0` |
| `ThrottlingException` from Bedrock | The account hit a per-region rate limit, which is common when a room of participants runs the same check at once. Wait a minute and run it again. If it persists through Lab 1's build, request a quota increase for the model in [Service Quotas](https://console.aws.amazon.com/servicequotas/), or move `AWS_REGION` to a region with headroom |
| `ValidationException` naming the model | The model ID is unavailable in that region. Switch `AWS_REGION` to a US region such as `us-east-1` |
| `NoCredentialsError` or `ExpiredToken`, or `[SKIP] Amazon Bedrock` | AWS credentials are missing or stale. Run `aws configure`, or refresh the SSO session, then run Step 5 again |
| `cp: command not found` on Windows | PowerShell has no `cp`. Use `Copy-Item .env.example .env` for Step 3. Step 5 is a single `uv run` command and needs no translation |

---

## Navigation

- **Previous:** [The main README](../README.md), which has the Platform Responsibilities and Data Ownership tables behind the through-line above.
- **Next:** [Lab 1: Graph build](../01-graph-build/) builds the hotel knowledge graph in `1.1_build_graph.ipynb`, with Bedrock extracting entities and relationships against a pinned schema and Neo4j storing them alongside the vector and full-text indexes every later lab reads.

Contributors have one more step before opening a notebook: register the `nbstripout` git filter once per clone, under [Notebook setup](../README.md#notebook-setup-nbstripout) in the main README. Running the labs does not need it.

---

## Contributing

Contributions are welcome. See [CONTRIBUTING](../CONTRIBUTING.md) for more information.

## Security

If you discover a potential security issue in this project, notify AWS/Amazon Security via the [vulnerability reporting page](https://aws.amazon.com/security/vulnerability-reporting/). Please do **not** create a public GitHub issue.

## License

This library is licensed under the MIT-0 License. See the [LICENSE](../LICENSE) file for details.

> Last updated: August 2026 | Python 3.12+ | Amazon Bedrock | Neo4j AuraDB
