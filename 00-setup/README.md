[< Back to Main README](../README.md)

# Lab 0: Setup

Two credentials carry the whole workshop: one Neo4j Aura instance and one AWS account with Amazon Bedrock access. Get both working here and every later lab runs without a credential detour.

Lab 0 has no notebook and nothing to install. It is a checklist that ends in one verification command.

**At a Glance**
- **Neo4j:** one Aura instance, serving all six labs. APOC Core ships with it, so there is no plugin to enable.
- **AWS:** Bedrock model access for `us.anthropic.claude-sonnet-5` and `amazon.nova-2-multimodal-embeddings-v1:0`, plus `amazon.titan-embed-text-v2:0` if you are running the optional Lab 6.
- **You'll end with:** one `.env` file at the repository root and one command that proves both credentials work.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
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

Copy the template once, from the repository root:

```bash
cp .env.example .env
```

Then fill in these five values:

| Variable | Value |
|---|---|
| `NEO4J_URI` | `neo4j+s://<your-instance>.databases.neo4j.io` from the credentials file. The template ships a `bolt://localhost:7687` placeholder, so this one always needs replacing |
| `NEO4J_USERNAME` | `neo4j` on a default Aura instance |
| `NEO4J_PASSWORD` | the generated password from the credentials file |
| `NEO4J_DATABASE` | `neo4j` |
| `AWS_REGION` | one region where every Bedrock model you need is enabled. The template ships `us-east-1` |

Every lab loads the nearest `.env` first, so a `.env` inside a lab folder overrides this one. Keeping a single file at the repository root is the simplest arrangement. `.env` is gitignored; keep it that way.

> **Workshop Studio username variable.** The hosted CloudFormation environment writes `NEO4J_USER`, and every lab in this repository reads `NEO4J_USERNAME`. If authentication fails only inside the hosted workshop, this mismatch is the first thing to check. Set `NEO4J_USERNAME` to the same value.

## Step 4: Confirm Bedrock access

AWS credentials come first. At a hosted workshop they are already configured; self-paced participants run `aws configure` or export `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`. Confirm the identity the SDK will use, from the repository root:

```bash
aws sts get-caller-identity --query Arn --output text
```

Then open the [Bedrock Model Access console](https://console.aws.amazon.com/bedrock/home#/modelaccess) in the region named by `AWS_REGION` and request access to these models:

| Model ID | Used for | Needed by |
|---|---|---|
| `us.anthropic.claude-sonnet-5` | Lab 1 entity and relationship extraction, then agent reasoning in Labs 2 through 5 | Required |
| `amazon.nova-2-multimodal-embeddings-v1:0` | Lab 1 chunk embeddings and every Lab 2 query embedding, at 1024 dimensions | Required |
| `amazon.titan-embed-text-v2:0` | Lab 6 memory embeddings, also at 1024 dimensions. A separate embedding contract from the one above, on purpose | Lab 6 only |

Access is granted per model and per region, so enabling one proves nothing about the others. The verification script in step 5 covers the first two, because those are what Labs 1 through 5 need; if you are running Lab 6, enable the third as well. The `us.` prefix marks a cross-region inference profile, so pair it with a US region such as `us-east-1`.

## Step 5: Verify both credentials

Run this from anywhere inside the repository: it walks up from the working directory to find the repo-root `.env`. It checks the Python version, connects to Aura, counts APOC procedures, sends one short Bedrock prompt, and requests one embedding. It touches no graph data of its own, and it needs no virtual environment because `uv` fetches the three packages into a cached one:

```bash
uv run --with neo4j --with boto3 --with python-dotenv python - <<'PY'
import json, os, sys, boto3
from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase

if sys.version_info < (3, 12):
    sys.exit(f"Python 3.12+ is required; this interpreter is {sys.version.split()[0]}")

start = Path.cwd().resolve()
root = next(
    (folder for folder in (start, *start.parents) if (folder / ".env.example").exists()),
    start,
)
load_dotenv(root / ".env")
os.environ.setdefault("NEO4J_USERNAME", os.environ.get("NEO4J_USER", ""))
missing = [
    name
    for name in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "NEO4J_DATABASE", "AWS_REGION")
    if not os.environ.get(name)
]
if missing:
    sys.exit("Missing from .env: " + ", ".join(missing))

uri, user = os.environ["NEO4J_URI"], os.environ["NEO4J_USERNAME"]
database, region = os.environ["NEO4J_DATABASE"], os.environ["AWS_REGION"]

with GraphDatabase.driver(uri, auth=(user, os.environ["NEO4J_PASSWORD"])) as driver:
    driver.verify_connectivity()
    with driver.session(database=database) as session:
        apoc = session.run(
            "SHOW PROCEDURES YIELD name WHERE name STARTS WITH 'apoc.' RETURN count(*) AS n"
        ).single()["n"]
if apoc == 0:
    sys.exit("Connected, but no APOC procedures are visible. Aura ships APOC Core, so this is not an Aura instance.")
print(f"Neo4j OK: {uri}, database {database}, {apoc} APOC procedures")

bedrock = boto3.client("bedrock-runtime", region_name=region)
bedrock.converse(
    modelId="us.anthropic.claude-sonnet-5",
    messages=[{"role": "user", "content": [{"text": "Reply with the word OK."}]}],
    inferenceConfig={"maxTokens": 5},
)
print(f"Bedrock OK: us.anthropic.claude-sonnet-5 answered in {region}")

response = bedrock.invoke_model(
    modelId="amazon.nova-2-multimodal-embeddings-v1:0",
    body=json.dumps({
        "taskType": "SINGLE_EMBEDDING",
        "singleEmbeddingParams": {
            "embeddingPurpose": "GENERIC_INDEX",
            "embeddingDimension": 1024,
            "text": {"truncationMode": "END", "value": "hotel amenities"},
        },
    }),
    contentType="application/json",
    accept="application/json",
)
vector = json.loads(response["body"].read())["embeddings"][0]["embedding"]
print(f"Bedrock OK: nova-2-multimodal-embeddings returned {len(vector)} dimensions")
PY
```

Three lines mean Lab 0 is done:

```
Neo4j OK: neo4j+s://<your-instance>.databases.neo4j.io, database neo4j, 162 APOC procedures
Bedrock OK: us.anthropic.claude-sonnet-5 answered in us-east-1
Bedrock OK: nova-2-multimodal-embeddings returned 1024 dimensions
```

The APOC count varies by Aura version. Any nonzero count is fine. The embedding dimension must read 1024, because that is the width Lab 1 writes into the vector index and Lab 2 queries against.

The `NEO4J_USER` line in the script exists so the check still passes inside Workshop Studio. Labs 1 through 6 read `NEO4J_USERNAME` only, so set it properly rather than relying on that fallback.

---

## Troubleshooting

| Message | Fix |
|---|---|
| `Python 3.12+ is required` | The interpreter `uv` picked is older than the floor the shared `workshop` package declares. Install Python 3.12 or newer, or pass `--python 3.12` to `uv run` |
| `Missing from .env: ...` | The named variables are absent or blank in the repo-root `.env`. Revisit Step 3 |
| The check passes, but a lab fails to authenticate inside Workshop Studio | The hosted environment sets `NEO4J_USER`, which this script falls back to and the labs do not. Add `NEO4J_USERNAME` with the same value |
| `Connected, but no APOC procedures are visible` | The URI points at something other than an Aura instance. Aura ships APOC Core; a self-hosted Neo4j needs the APOC plugin installed |
| `Neo4jError: ... AuthenticationRateLimit` or `Unauthorized` | The username or password is wrong. Re-read them from the downloaded credentials file |
| `Unable to retrieve routing information` or a connection timeout | The URI is wrong, or the instance is paused. Confirm it reads **Running** in the Aura console and that the URI starts with `neo4j+s://` |
| `AccessDeniedException` from Bedrock | Read the model ID in the exception before acting: access is per model, so having one enabled proves nothing about another. Request access for that exact ID in the [Bedrock Model Access console](https://console.aws.amazon.com/bedrock/home#/modelaccess), in the region `AWS_REGION` names. Lab 6 is the usual surprise here, because it is the only lab that uses `amazon.titan-embed-text-v2:0` |
| `ValidationException` naming the model | The model ID is unavailable in that region. Switch `AWS_REGION` to a US region such as `us-east-1` |
| `NoCredentialsError` or `ExpiredToken` | AWS credentials are missing or stale. Run `aws configure`, or refresh the SSO session, then rerun Step 4 |

One more thing before opening a notebook: register the `nbstripout` git filter once per clone, described under [Notebook setup](../README.md#notebook-setup-nbstripout) in the main README. Without it every `.ipynb` checkout runs against an undefined filter.

---

## Next

[Lab 1: Graph build](../01-graph-build/) builds the hotel knowledge graph in `1.1_build_graph.ipynb`, with Bedrock extracting entities and relationships against a pinned schema and Neo4j storing them alongside the vector and full-text indexes every later lab reads.

## License

This library is licensed under the MIT-0 License. See the [LICENSE](../LICENSE) file for details.
