[< Back to Lab 5](../README.md)

# Lab 5 reference material

This folder holds reference material for the Amazon Bedrock AgentCore
deployment. **Nothing here is run by the workshop, and the notebook runner does
not read it.** It is retained for AWS review, and as the source the shipped Lab 5
notebooks were authored from.

## What is here

| File | Role |
|------|------|
| `02_agentcore_walkthrough.ipynb` | The source `5.3_agentcore_walkthrough.ipynb` was authored from. It assumed a facilitator pointing at a pre-deployed Runtime. Run [`../5.3_agentcore_walkthrough.ipynb`](../5.3_agentcore_walkthrough.ipynb) instead |
| `DEPLOYMENT.md` | The deployable boundary described for production hardening. It deliberately describes two Neo4j users and a separate Runtime-read secret, which is stronger than the one user and environment-variable read this lab deploys |

The deployable source, the Runtime entry point, container, Gateway target
manifest, and reservation Lambda, lives one level over in
[`../deployment-tools/`](../deployment-tools/). That is the folder
`provision_agentcore.py` consumes and the one the container is built from.

## What changed in `5.3`

`5.3_agentcore_walkthrough.ipynb` keeps the five sections and the log-correlation
query from this notebook, and differs in three ways:

- **It follows a deploy the participant ran.** `5.1_agentcore_deploy.ipynb`
  deploys the Runtime and prints its ARN, so the walkthrough no longer assumes a
  facilitator provisioned one out of band.
- **Its dates are computed from today.** The original hardcoded a check-in of
  `2026-09-04`. A fixed future date rots into the past, which turns a passing
  stay into a rejected one and breaks the scenario the notebook claims to run.
- **Each invocation carries its own session ID.** The `request_id`, not the
  session, is what ties two deliveries of one reservation request together.

`5.3` reads `AGENT_RUNTIME_ARN`, which `5.1` prints and which
`provision_agentcore.py` does not write to the root `.env`. Set it by hand, or
every live cell skips.
