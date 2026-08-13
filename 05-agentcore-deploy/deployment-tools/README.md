[< Back to Lab 5](../README.md)

# Lab 5 deployment source

This folder holds the deployable source for the Amazon Bedrock AgentCore
deployment: the Runtime entry point, its container, the single Gateway target
manifest, and the one reservation Lambda.

Two things consume it. [`setup/provision_agentcore.py`](../../setup/provision_agentcore.py)
creates the secret, the IAM roles, the Lambda, and the Gateway from this source.
[`../5.1_agentcore_deploy.ipynb`](../5.1_agentcore_deploy.ipynb) then builds the
Runtime container and launches it through the AgentCore starter toolkit.

**This folder is the container build context.** `5.1` changes directory into it
before calling `configure` and `launch`, because the starter toolkit treats the
current directory as the build root: it honors the `Dockerfile` here, and copies
only this directory into the image. Run the toolkit from the lab folder instead
and it would generate its own `Dockerfile`, ignore this one, and ship the whole
lab.

## What is here

| File | Role |
|------|------|
| `booking_agent.py` | AgentCore Runtime entry point (Strands): runs the retrieval tool in-process and discovers one command through the Gateway |
| `Dockerfile`, `.dockerignore`, `agent_requirements.txt` | Runtime container image and its dependencies |
| `vendor/` | Where `5.1` builds the `workshop` wheel just before launch. The wheel itself is not committed. See [`vendor/README.md`](vendor/README.md) |
| `gateway_target.json` | The single Gateway target manifest that exposes only `create_reservation_request` |
| `lambda_tools/create_reservation_request/` | The one reservation Lambda; its handler wraps `workshop.reservation_command.handler` |
| `test_runtime_integration.py` | Deployment tests for the Runtime and Gateway boundary |

## Dependencies

`booking_agent.py` and the Lambda both import from the shared `workshop`
package, which lives at the repository root in [`../../workshop/`](../../workshop/).
The Runtime gets it from a wheel: `5.1` builds one into `vendor/` and the last
line of `agent_requirements.txt` installs it by exact filename. The `Dockerfile`
copies `vendor/` into the image before running the install, because the package
source sits outside this build context and is unreachable from inside the image
any other way.

That shared package is the point. The retrieval tool the Runtime serves and the
reservation command the Lambda wraps are the same code Lab 2 and Lab 4 ran
locally, imported rather than copied.

## Running the tests

`test_runtime_integration.py` runs against the lab venv and needs no AWS
credentials. It imports `booking_agent`, which imports `bedrock_agentcore`,
`strands`, and `mcp`, and [`../requirements.txt`](../requirements.txt) declares
all three so a facilitator reading this directory has them resolved. Nine tests,
all offline: every AWS and Neo4j call is mocked.

```bash
cd ..
uv run --with pytest --with-requirements requirements.txt -m pytest
```

That collects these nine plus the twenty in
[`../test_workshop_cleanup.py`](../test_workshop_cleanup.py), 29 in total.

These tests pin the deployed boundary rather than the deployment: the Gateway
fails closed if it discovers anything but the one reservation command, the hook
refuses a call whose `request_id` is not the caller's, the read path touches only
the read secret, and the image excludes the Lambda and the legacy notebooks.

## Production-hardening reference

The stronger boundary description, two Neo4j users and a separate Runtime-read
secret, is kept as reference in
[`../advanced-deployment/DEPLOYMENT.md`](../advanced-deployment/DEPLOYMENT.md).
The path this lab actually deploys uses one Neo4j user and reads Neo4j from
environment variables passed to the Runtime at launch.
