[< Back to Demo 06](../README.md)

# Demo 06 Advanced Deployment (Reference Only)

This folder holds reference material for the Amazon Bedrock AgentCore deployment of
Demo 06. **Nothing here is run by the workshop in the current pass, and nothing
automated reads it.** It is retained for AWS review and for facilitators who want to
understand the deployed shape.

The self-contained local notebook one level up,
[`../01_hybrid_retrieval.ipynb`](../01_hybrid_retrieval.ipynb), already proves the
full anti-hallucination story (grounded retrieval, abstention, rule rejection, and
the idempotent reservation write) against your own Neo4j Aura and Amazon Bedrock,
with no AWS deployment.

## What is here

| File | Role |
|------|------|
| `02_agentcore_walkthrough.ipynb` | Facilitator notebook that invokes and inspects a pre-deployed AgentCore Runtime, Gateway, and reservation Lambda, with CloudWatch and `request_id` log correlation and Neo4j graph inspection |
| `DEPLOYMENT.md` | The deployable boundary described for production hardening. It deliberately describes two Neo4j users and a separate Runtime-read secret, which is stronger than the stand-alone path's one user and environment-variable read |

The live, deployable source (the Runtime entry point, container, Gateway target
manifest, and reservation Lambda) lives one level over in
[`../deployment-tools/`](../deployment-tools/). That is the folder the stand-alone
provisioning script consumes.

## Running the walkthrough

`02_agentcore_walkthrough.ipynb` reads a manually-set `AGENT_RUNTIME_ARN`. The
stand-alone provisioning path writes `AGENTCORE_GATEWAY_URL` and
`AGENTCORE_RUNTIME_ROLE_ARN` to the root `.env` but does not write
`AGENT_RUNTIME_ARN`, so a facilitator must fill that value in by hand after a
Runtime exists. The local test run excludes this folder, and the deferred
deployment tests run only in the deployment environment with the AgentCore
dependencies installed.
