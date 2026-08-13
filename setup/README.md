# Workshop Utilities

This directory contains repository-wide utilities and sorts after the numbered
workshop labs in a normal directory listing.

## Run the notebooks

`run_notebooks.py` executes the workshop notebooks with `nbconvert` and reports
pass, fail, or skip for each notebook. While a notebook runs, it reports each
code cell's source preview and elapsed time, followed by the cell's captured
text output. Run it from the repository root:

```bash
uv run setup/run_notebooks.py                 # Labs 1-4 and 6; Lab 5 is gated
uv run setup/run_notebooks.py --labs 4        # One lab
uv run setup/run_notebooks.py --labs 2,3,4    # A list
uv run setup/run_notebooks.py --labs 1-4      # A range
uv run setup/run_notebooks.py --list          # Show the notebook registry
```

The runner is a PEP 723 script. `uv` creates and caches its shared environment,
including `nbconvert` and all notebook dependencies, on the first run. No
top-level virtual environment or separate installation step is required.

The original notebook files are never modified. Executed notebooks are written
to a temporary directory and removed after the run. To retain them for
inspection, use:

```bash
uv run setup/run_notebooks.py --labs 4 --keep-output
```

Retained notebooks are stored under `setup/notebook-output/`, which is ignored
by Git.

### AWS side effects

The default command runs every lab except Lab 5. Lab 5's three notebooks change
AWS resources, so the two that deploy and the one that deletes each require
their own flag. Lab 0 is a credential checklist in a README and has no notebook,
so it never appears in a run.

```bash
# Deploy or update the AgentCore resources: 5.1 and 5.3
uv run setup/run_notebooks.py --labs 5 --include-deploy

# Delete the tagged workshop resources: 5.2
uv run setup/run_notebooks.py --labs 5 --include-cleanup
```

The runner treats an uncaught cell error as a failure and exits nonzero when
any selected notebook fails. A clean execution does not validate narrative or
model-quality claims unless the notebook contains assertions for those claims.

### Interactive notebook output

The runner protects source notebooks because it executes in-memory copies.
When notebooks are run interactively in an IDE, Git output stripping is still
handled by the repository's `nbstripout` filter. Register it once after cloning
as described in the root README.

## Provision the Lab 5 AgentCore infrastructure

`provision_agentcore.py` stands up the slow, privileged AWS infrastructure that
the Lab 5 deployment depends on: the Neo4j command secret, the IAM roles, the
reservation Lambda, and the Gateway. It mirrors what Workshop Studio
pre-provisions for hosted participants.

**Labs 1 through 4 and Lab 6 never need this script.** They run against your own
Aura and Amazon Bedrock and create no AWS resources. Lab 5 does need it. Run it
before
[`../05-agentcore-deploy/5.1_agentcore_deploy.ipynb`](../05-agentcore-deploy/5.1_agentcore_deploy.ipynb),
which reads `AGENTCORE_GATEWAY_URL` and `AGENTCORE_RUNTIME_ROLE_ARN` from the
root `.env` and skips every live cell until both are present.

**This creates real, billable AWS resources.** It is idempotent, so re-running it
is safe. Teardown is two halves under two owner tags. `teardown` here deletes
what this script created, tagged `demo06-agentcore=true`;
[`../05-agentcore-deploy/5.2_teardown.ipynb`](../05-agentcore-deploy/5.2_teardown.ipynb)
and [`../05-agentcore-deploy/workshop_cleanup.py`](../05-agentcore-deploy/workshop_cleanup.py)
delete what `5.1_agentcore_deploy.ipynb` created, tagged
`WorkshopResource=stop-ai-agent-hallucinations`. Either half alone leaves the
other billing.

Like the notebook runner, this is a PEP 723 stand-alone script: `uv` resolves
its single dependency, `boto3`, on the first run, with no separate install step.
The dependency arrow points one way. This script reads Lab 5 files to package
the Lambda and installs the shared `workshop` package into it; Lab 5 never reads
anything under `setup/`. Everything that crosses back to the deployment is
written to the repo-root `.env` as a handful of identifiers.

### Prerequisites

- **[uv](https://docs.astral.sh/uv/)**, which runs the script and builds the
  Lambda package.
- **AWS credentials** allowed to create the resources below: Secrets Manager,
  IAM, Lambda, and `bedrock-agentcore-control`. The region resolves from
  `AWS_REGION`, then `AWS_DEFAULT_REGION`, then defaults to `us-east-1`.
- **Neo4j values in the repo-root `.env`** (`NEO4J_URI`, `NEO4J_USERNAME`,
  `NEO4J_PASSWORD`, `NEO4J_DATABASE`). The script refuses to run if any are
  missing, because they become the command secret.
- **Amazon Bedrock model access.** The Runtime role authorizes
  `us.anthropic.claude-sonnet-5` by default; override with `MODEL_ID`.

### Commands

Run all three from the repository root:

```bash
uv run setup/provision_agentcore.py provision      # Create every resource in dependency order
uv run setup/provision_agentcore.py status         # Report presence of each resource, no changes
uv run setup/provision_agentcore.py teardown       # Delete every resource (prompts to confirm)
uv run setup/provision_agentcore.py teardown --yes # Delete without the confirmation prompt
```

`provision` is idempotent: re-running it reuses existing roles, updates the
secret and Lambda in place, and rewrites the managed `.env` keys rather than
appending duplicates. `teardown` deletes in reverse dependency order (target,
gateway, Lambda, roles, secret) and comments the managed keys back out of `.env`.

### What `provision` creates

Each resource is tagged `demo06-agentcore=true` so `teardown` can find it. That
tag is what separates this half from the half
[`../05-agentcore-deploy/workshop_cleanup.py`](../05-agentcore-deploy/workshop_cleanup.py)
owns, and neither script touches the other's resources. The names all share the
`demo06` prefix, which you can override with the `DEMO06_PREFIX` environment
variable.

| Resource | Name | Role |
|----------|------|------|
| Secrets Manager secret | `demo06/neo4j-command` | Holds the Neo4j command credential (`uri`, `username`, `password`, `database`) that the reservation Lambda reads |
| IAM role (Lambda) | `demo06-reservation-lambda-role` | Reservation Lambda execution role: writes its own log group, reads only its own secret |
| IAM role (Gateway) | `demo06-gateway-role` | Gateway role scoped to invoke only the one reservation Lambda |
| IAM role (Runtime) | `demo06-runtime-role` | AgentCore Runtime execution role: ECR pulls, Runtime log groups, X-Ray, workload-identity tokens, and Bedrock model invocation. Grants no secret access |
| Lambda function | `demo06-reservation-request` | The single reservation command behind the Gateway; its handler wraps `workshop.reservation_command.handler` from the shared package |
| AgentCore Gateway | `demo06-gateway` | NONE-auth MCP Gateway exposing exactly one target |
| Gateway target | `demo06-reservation-request` | The sole target, defined by [`../05-agentcore-deploy/deployment-tools/gateway_target.json`](../05-agentcore-deploy/deployment-tools/gateway_target.json), exposing only `create_reservation_request` |

### The `.env` handoff

`provision` writes three identifiers into a managed block in the repo-root
`.env`, and `teardown` clears them. You never set these by hand:

| Key | Meaning |
|-----|---------|
| `AGENTCORE_GATEWAY_URL` | The MCP URL the Runtime uses to discover the reservation command |
| `AGENTCORE_RUNTIME_ROLE_ARN` | The Runtime execution role ARN the deploy step launches the Runtime with |
| `NEO4J_COMMAND_SECRET_ID` | The command secret ARN the reservation Lambda reads Neo4j from |

There is no `NEO4J_READ_SECRET_ID`. The stand-alone path uses one Neo4j user:
the deployed Runtime reads Neo4j from the `NEO4J_*` environment values, and only
the reservation Lambda reads from a secret. The stronger two-user, two-secret
boundary is kept as reference in
[`../05-agentcore-deploy/advanced-deployment/DEPLOYMENT.md`](../05-agentcore-deploy/advanced-deployment/DEPLOYMENT.md).

### How the Lambda package is built

`provision` builds the reservation Lambda deployment package in a temporary
directory before creating or updating the function:

- Dependencies install with a Linux platform target, `aarch64-manylinux2014` for
  the ARM64/Graviton Lambda, so the wheels import at cold start even when the
  provisioning host is macOS. `neo4j` is the only third-party dependency;
  `boto3` and `botocore` already ship in the Lambda runtime and are not vendored.
- The shared `workshop` package installs in a second step with `--no-deps` and no
  platform target. It is pure Python, and its declared dependencies are the union
  of what all nine of its modules need, including `neo4j-graphrag`, which the
  reservation Lambda never imports.
- The wrapper `lambda_function.py` is copied to the package root, because
  `lambda_function.handler` is the configured entry point. It imports
  `workshop.reservation_command.handler`, which resolves from the installed
  package.

The function runs on `python3.12`, `arm64`, with a 30-second timeout and 256 MB
of memory, and reads its Neo4j credential from the command secret through the
`NEO4J_COMMAND_SECRET_ID` environment variable.

### After provisioning

With the three `.env` keys in place,
[`../05-agentcore-deploy/5.1_agentcore_deploy.ipynb`](../05-agentcore-deploy/5.1_agentcore_deploy.ipynb)
builds and launches the Runtime container against the provisioned Gateway and
role. That notebook creates real resources too: an AgentCore Runtime, an ECR
repository, and a CodeBuild project, all tagged
`WorkshopResource=stop-ai-agent-hallucinations` so
[`../05-agentcore-deploy/5.2_teardown.ipynb`](../05-agentcore-deploy/5.2_teardown.ipynb)
can delete them. See
[`../05-agentcore-deploy/deployment-tools/README.md`](../05-agentcore-deploy/deployment-tools/README.md)
for the deployable source and
[`../05-agentcore-deploy/advanced-deployment/DEPLOYMENT.md`](../05-agentcore-deploy/advanced-deployment/DEPLOYMENT.md)
for the production-hardening boundary reference.
