[< Back to Demo 06](../README.md)

# Demo 06 Deployment Tools (Live Source)

This folder holds the deployable source for the Amazon Bedrock AgentCore deployment
of Demo 06: the Runtime entry point, its container, the single Gateway target
manifest, and the one reservation Lambda. [`setup/provision_agentcore.py`](../../setup/provision_agentcore.py)
creates the secret, the IAM roles, the Lambda, and the Gateway from this source.
[`../deploy_agentcore.ipynb`](../deploy_agentcore.ipynb) then builds the Runtime
container and launches it through the AgentCore starter toolkit.
[`../01_hybrid_retrieval.ipynb`](../01_hybrid_retrieval.ipynb) is the local participant
notebook and deploys nothing.
**Nothing here runs unless a facilitator provisions the infrastructure and opts in.**

## What is here

| File | Role |
|------|------|
| `booking_agent.py` | AgentCore Runtime entry point (Strands): runs the retrieval tool in-process and discovers one command through the Gateway |
| `Dockerfile`, `.dockerignore`, `agent_requirements.txt` | Runtime container image and its dependencies |
| `gateway_target.json` | The single Gateway target manifest that exposes only `create_reservation_request` |
| `lambda_tools/create_reservation_request/` | The one reservation Lambda; its handler wraps `reservation_command.handler` from the demo root |
| `test_runtime_integration.py` | Deployment tests for the Runtime and Gateway boundary |

## Dependencies

The Lambda and Runtime import `reservation_command.py` and `contracts.py`, which
remain in the demo root one level up. That is intentional: the local notebook and
its tests exercise the same command logic that the deployed Lambda wraps.

## Running the tests (deployment environment only)

`test_runtime_integration.py` imports `booking_agent`, and the Runtime imports
`bedrock_agentcore` and `strands`, which are absent from the local participant
environment. The local test run excludes this folder (see
[`../conftest.py`](../conftest.py)). These tests run only in the deployment
environment with the AgentCore dependencies installed.

## Production-hardening reference

The stronger boundary description (two Neo4j users and a separate Runtime-read
secret) is kept as reference in
[`../advanced-deployment/DEPLOYMENT.md`](../advanced-deployment/DEPLOYMENT.md). The
stand-alone path uses one Neo4j user and reads Neo4j from environment variables.
