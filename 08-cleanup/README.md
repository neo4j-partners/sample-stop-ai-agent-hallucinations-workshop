# Module 8: Cleanup

Delete the resources created in Modules 6 and 7.

## How to Run

```bash
python workshop_cleanup.py --dry-run   # read-only: show the plan and the reasoning
python workshop_cleanup.py             # execute it
```

Or open `cleanup.ipynb`, which runs the same code and shows the dry run before it deletes anything.
`../06-agentcore-boto3-demo/cleanup.py` is a thin wrapper around the same module, so there is exactly
one teardown path to audit.

Both exit **non-zero** if the teardown is incomplete, so they are safe to call from a script.

## What Gets Deleted

| Resource Type | Count | Description |
|--------------|-------|-------------|
| AgentCore Runtimes | 2 | HotelBookingAgent + HotelBookingAgentWithMemory |
| AgentCore Gateway | 1 | HotelBookingGateway with its Lambda targets |
| AgentCore Memory | 1 | workshop_HotelBookingMemory |
| Lambda Functions | 8 | 7 booking tools + 1 Neo4j query |
| Lambda Layer | 1 | Neo4j Python driver |
| DynamoDB Tables | 3 | Hotels, Bookings, SteeringRules |
| IAM Roles | 2 | Lambda + AgentCore execution roles |
| ECR Repositories | 2 | Container images for both agents |
| CodeBuild Projects | 2 | Build projects from the starter toolkit |

...but only the ones carrying the workshop tag. See below.

## Deletion is Scoped by Tag, Never by Name

Every resource is deleted on one condition: it carries

```
WorkshopResource=stop-ai-agent-hallucinations
```

Nothing is selected by name prefix. Module 6 and 7 apply this tag at creation; cleanup deletes only
what is tagged.

**Why this matters.** An earlier version of this teardown selected IAM roles like so:

```python
cb_roles = iam.list_roles(PathPrefix="/")["Roles"]
for role in cb_roles:
    if role["RoleName"].startswith("AmazonBedrockAgentCoreSDKCodeBuild"):
        ... iam.delete_role(RoleName=rn)
```

IAM is global, so that swept the entire account across every region and destroyed five roles this
workshop never created, two of them in a different region. A name prefix describes what a resource is
*called*. A tag records who *owns* it. Only the second is safe to delete on.

Measured on the development account: 426 IAM roles exist, 126 of them have names a prefix scheme
would plausibly match, and the tag gate selects **zero** of them.

### Untagged resources are reported, not deleted

If a resource exists under a workshop name but carries no workshop tag, cleanup refuses to delete it,
prints it under `BLOCKED`, and exits 1. That is deliberate — the resource is either someone else's or
came from a deployment that did not tag, and neither is a call a script should make for you. Tag it,
or delete it by hand once you have confirmed it is yours.

### The two documented exceptions

`UNTAGGABLE_KINDS` in `workshop_cleanup.py` lists the only things matched by name rather than tag:

- **Lambda layer versions** — AWS does not support tags on them.
- **Local `.bedrock_agentcore*.yaml` config files** — not AWS resources.

Both use *exact* name equality, not prefixes. A unit test pins the contents of that set so the
exemption cannot quietly grow.

## Failures Are Loud

No exception is swallowed. The previous version hid a `KeyError` behind a bare `except`, printed a
clean bill of health, and left a billable AgentCore Memory resource running. The `KeyError` came from
reading `m["memoryName"]` in `list_memories()` output — that field does not exist. `MemorySummary`
is `arn, id, status, createdAt, updatedAt, managedByResourceArn`, and the memory is matched on `id`,
which has the form `<name>-<suffix>`.

Any delete that fails, and any untagged workshop resource found, produces a non-zero exit.

## Tests

```bash
python -m unittest discover -s . -v
```

12 tests, no AWS credentials needed — the clients are injected fakes. The headline test is
`test_untagged_unrelated_roles_are_never_selected`, which reproduces the exact account shape that
bug B6 damaged and asserts none of those roles is selected.

## What Does NOT Get Deleted

- **Neo4j infrastructure** — Code Editor EC2 or the Central Neo4j ECS stack from Module 1.
  Delete via AWS Console → CloudFormation → Delete Stack.
- **CloudWatch log groups** — retained so you can review the run.
- **The starter toolkit's shared CodeBuild role** (`AmazonBedrockAgentCoreSDKCodeBuild-*`). It is
  created by the toolkit, shared across projects, and costs nothing. Deleting it is what caused the
  original incident. If you want it gone, remove it by hand.
- **Anything untagged.**

## Estimated Time

2-3 minutes. Enumerating IAM role tags across a large account adds roughly a minute to the plan step.
