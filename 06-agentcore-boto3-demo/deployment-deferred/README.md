[< Back to Demo 06](../README.md)

# Demo 06 Deployment (Deferred)

This folder holds the intact Amazon Bedrock AgentCore deployment for Demo 06: the second facilitator notebook and the full AWS machinery that hosts the same retrieval and reservation boundary as a managed service. **Nothing here is run by the workshop in the current pass.** It is retained for AWS review and pending guidance on how to package the deployment lab.

The self-contained local notebook one level up, [`../01_hybrid_retrieval.ipynb`](../01_hybrid_retrieval.ipynb), already proves the full anti-hallucination story (grounded retrieval, abstention, rule rejection, and the idempotent reservation write) against your own Neo4j Aura and Amazon Bedrock, with no AWS deployment. This folder is the path that would host that same boundary on AWS.

## What is staged here

| File | Role |
|------|------|
| `02_agentcore_walkthrough.ipynb` | Facilitator notebook that invokes and inspects a pre-deployed AgentCore Runtime, Gateway, and reservation Lambda |
| `booking_agent.py` | AgentCore Runtime entry point (Strands): runs the retrieval tool in-process and discovers one command through the Gateway |
| `deployment/gateway_target.json` | The single Gateway target manifest that exposes only `create_reservation_request` |
| `lambda_tools/create_reservation_request/` | The one reservation Lambda; its handler wraps `reservation_command.handler` from the local set |
| `Dockerfile`, `.dockerignore`, `agent_requirements.txt` | Runtime container image and its dependencies |
| `DEPLOYMENT.md` | The deployable boundary: Runtime, Gateway, Lambda, and the Secrets Manager and IAM separation of the read and command identities |
| `test_runtime_integration.py` | Deployment tests |

## Dependencies

The staged Lambda and Runtime import `reservation_command.py` and `contracts.py`, which remain in the local set one level up. That is intentional: the local notebook and its tests exercise the same command logic that the deferred Lambda wraps.

## Running these (deployment environment only)

`test_runtime_integration.py` and the Runtime import `bedrock_agentcore` and `strands`, which are absent from the local participant environment. The local test run excludes this folder (see `../conftest.py`). These tests run only in the deployment environment with the AgentCore dependencies installed.
