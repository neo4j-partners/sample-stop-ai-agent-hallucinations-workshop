# Lab 5 Teardown Reference

Delete the AWS resources that `5.1_agentcore_deploy.ipynb` created. Long-form reasoning and incident
history for `workshop_cleanup.py`; the lab README has the short version.

**At a Glance**
- **What it covers:** safe teardown of the AWS resources Lab 5 created.
- **Neo4j:** the Aura instance is deleted separately, not by this script.
- **AWS:** deletes what carries `WorkshopResource=stop-ai-agent-hallucinations`, which is the Runtime,
  ECR repository and CodeBuild project from `5.1_agentcore_deploy.ipynb`, plus tagged leftovers from
  earlier versions of this workshop.
- **What you run:** a dry-run-by-default cleanup that only deletes with an explicit flag.

## How to Run

```bash
python workshop_cleanup.py             # dry run by default: show the plan and the reasoning
python workshop_cleanup.py --dry-run   # the same read-only run, made explicit
python workshop_cleanup.py --yes       # execute it and delete the tagged resources
```

Run these from `05-agentcore-deploy/`. The default is a dry run. Deletion happens only when you pass
`--yes`, so running the script with no arguments never deletes anything.

Or open `5.2_teardown.ipynb`, which imports the same module and shows the dry run before it deletes
anything. `workshop_cleanup.py` is the one teardown implementation, so there is exactly one path to
audit.

Both exit **non-zero** if the teardown is incomplete, so they are safe to call from a script.

## This Is Only Half of Teardown

Two scripts own two halves of Lab 5's infrastructure, under two different owner tags:

| Owner | Tag | What it deletes |
|-------|-----|-----------------|
| `workshop_cleanup.py` and `5.2_teardown.ipynb` | `WorkshopResource=stop-ai-agent-hallucinations` | What `5.1_agentcore_deploy.ipynb` created: the AgentCore Runtime, its ECR repository, and its CodeBuild project |
| `setup/provision_agentcore.py teardown` | `demo06-agentcore=true` | What provisioning created: the AgentCore Gateway and its target, the reservation Lambda, the Neo4j command secret, and the three `demo06-*` IAM roles |

Run both. Either one alone leaves the other half billing. From the repository root:

```bash
uv run setup/provision_agentcore.py status
uv run setup/provision_agentcore.py teardown
```

Neither script touches the other's resources, because each gates on its own tag.

## What Gets Deleted

Lab 5 as it ships creates three AWS resources and one local file:

| Resource Type | Count | Description |
|--------------|-------|-------------|
| AgentCore Runtime | 1 | `HotelBookingAgent`, tagged by Step 5 of `5.1_agentcore_deploy.ipynb` |
| ECR Repository | 1 | `bedrock-agentcore-hotelbookingagent`, holding the Runtime image |
| CodeBuild Project | 1 | `bedrock-agentcore-hotelbookingagent-builder`, from the starter toolkit |
| Local config file | 1 | `deployment-tools/.bedrock_agentcore.yaml`, written by the starter toolkit |

`workshop_cleanup.py` also enumerates the resources earlier versions of this workshop created, so an
account that ran one of them is cleaned up by the same tag-gated path. In an account that has never run
an earlier version, every one of these prints as `not found` and nothing happens. In an account that
has, they are present and tagged, and this run deletes them along with Lab 5's own three:

| Resource Type | Count | Description |
|--------------|-------|-------------|
| AgentCore Runtime | 1 | `HotelBookingAgentWithMemory`, and its ECR repository and CodeBuild project |
| AgentCore Gateway | 1 | `HotelBookingGateway` with its Lambda targets |
| AgentCore Memory | 1 | `workshop_HotelBookingMemory` |
| Lambda Functions | 8 | 7 booking tools + 1 Neo4j query, all named `hotel-booking-*` |
| Lambda Layer | 1 | `workshop-neo4j-driver`, the Neo4j Python driver |
| DynamoDB Tables | 3 | `workshop-Hotels`, `workshop-Bookings`, `workshop-SteeringRules` |
| IAM Roles | 2 | `workshop-LambdaExecutionRole`, `workshop-AgentCoreExecutionRole` |

...but only the ones carrying the workshop tag. See below.

## Deletion is Scoped by Tag, Never by Name

Every resource is deleted on one condition: it carries

```
WorkshopResource=stop-ai-agent-hallucinations
```

Nothing is selected by name prefix. Step 5 of `5.1_agentcore_deploy.ipynb` applies this tag right
after deploy, because the starter toolkit does not forward tags to the Runtime, ECR repository, or
CodeBuild project it creates. Cleanup deletes only what is tagged, so skipping that step leaves
billable infrastructure that teardown refuses to remove.

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
prints it under `BLOCKED`, and exits 1. That is deliberate. The resource is either someone else's or
came from a deployment that did not tag, and neither is a call a script should make for you. Tag it,
or delete it by hand once you have confirmed it is yours.

### An untagged workshop role blocks cleanup

If an IAM role carries a workshop name, `workshop-LambdaExecutionRole` or
`workshop-AgentCoreExecutionRole`, but no workshop tag, cleanup reports it under `BLOCKED` and exits 1
without deleting it. This is the same safety rule above, applied to roles. It affects anyone who
deployed an earlier version of this workshop before tagging landed, bug B20: those roles were created
without the `WorkshopResource` tag, so the current teardown refuses to remove them.

Lab 5 as it ships creates neither role. In an account that never ran an earlier version, both are
reported `not found`. Where an earlier run created them and tagging did land, they are deleted normally.

There are two ways to clear the block. Pick one.

1. **Tag the role, then re-run.** Adopt the role by applying the workshop tag, after which cleanup
   deletes it on the next run:

```bash
aws iam tag-role --role-name workshop-LambdaExecutionRole \
  --tags Key=WorkshopResource,Value=stop-ai-agent-hallucinations
python workshop_cleanup.py --yes
```

2. **Delete the role by hand in the console.** Open IAM in the AWS Console, confirm the role is yours
   and came from this workshop, detach its policies, and delete it.

Do either only for a role you have confirmed is yours. Tagging is a claim of ownership, and the next
cleanup run acts on it.

### Two residual deletion risks

Two paths delete without a per-name tag check. Both are deliberate and test-pinned, and both are named
here so you can recognize them:

- **The Lambda layer `workshop-neo4j-driver` is deleted by exact name.** AWS does not allow tags on
  Lambda layer versions, so this layer cannot be tag-gated and is matched by name alone. If you own an
  unrelated layer with the same name, every version of it is deleted. Rename your layer, or run this
  teardown in an account that holds no same-named layer.
- **A tagged IAM role is deleted regardless of its name.** `discover_roles` selects every role in the
  account carrying `WorkshopResource=stop-ai-agent-hallucinations`, whatever it is called. This is the
  safe default of tag over name, but it means a role you tagged with the workshop key for any other
  reason is also removed. Apply that tag only to resources you want this teardown to delete.

### The two documented exceptions

`UNTAGGABLE_KINDS` in `workshop_cleanup.py` lists the only things matched directly rather than by tag:

- **Lambda layer versions.** AWS does not support tags on them, so they are matched by exact name.
- **Local `.bedrock_agentcore.yaml` config files.** Not AWS resources. They are matched by fixed repo-relative path, never by glob. `CONFIG_FILES` holds two exact paths, `05-agentcore-deploy/deployment-tools/.bedrock_agentcore.yaml`, which is where `5.1_agentcore_deploy.ipynb` runs the toolkit from, and `05-agentcore-deploy/.bedrock_agentcore.yaml`, kept so a stale file from the earlier flat layout is still cleaned up. An earlier version globbed `~/.bedrock_agentcore*.yaml` and destroyed unrelated local config belonging to other AgentCore projects on the same machine, bug B45.

Both are matched exactly, never by prefix or glob. A unit test pins the contents of that set so the
exemption cannot quietly grow.

## Failures Are Loud

No exception is swallowed. The previous version hid a `KeyError` behind a bare `except`, printed a
clean bill of health, and left a billable AgentCore Memory resource running. The `KeyError` came from
reading `m["memoryName"]` in `list_memories()` output; that field does not exist. `MemorySummary`
is `arn, id, status, createdAt, updatedAt, managedByResourceArn`, and the memory is matched on `id`,
which has the form `<name>-<suffix>`.

Any delete that fails, and any untagged workshop resource found, produces a non-zero exit.

## Tests

```bash
cd 05-agentcore-deploy
uv run --with pytest --with-requirements requirements.txt -m pytest test_workshop_cleanup.py
```

20 tests, no AWS credentials needed. The clients are injected fakes. The headline test is
`test_untagged_unrelated_roles_are_never_selected`, which reproduces the exact account shape that bug
B6 damaged and asserts none of those roles is selected.

A bare `pytest` from this directory collects 29: these 20 plus 9 in
`deployment-tools/test_runtime_integration.py`, which pin the Runtime and Gateway boundary and also run
offline. Name the file only when you want the teardown tests alone.

## What Does NOT Get Deleted

- **Whatever `setup/provision_agentcore.py` created.** The Gateway and its target, the reservation
  Lambda, the Neo4j command secret, and the three `demo06-*` IAM roles carry a different owner tag,
  `demo06-agentcore=true`. Run `uv run setup/provision_agentcore.py teardown` from the repository root.
- **Your Aura instance and the graph Lab 1 built.** Neo4j Aura is not an AWS resource in your account,
  so nothing here can reach it. Delete the instance from the Aura console.
- **Neo4j infrastructure in the hosted environment.** The Code Editor EC2 instance and the Central
  Neo4j ECS stack come from CloudFormation. Delete via AWS Console, CloudFormation, Delete Stack.
- **CloudWatch log groups.** Retained so you can review the run.
- **The starter toolkit's shared CodeBuild role, `AmazonBedrockAgentCoreSDKCodeBuild-*`.** It is
  created by the toolkit, shared across projects, and costs nothing. Deleting it is what caused the
  original incident. If you want it gone, remove it by hand.
- **The CodeBuild source bucket, `bedrock-agentcore-codebuild-sources-<account-id>-<region>`.** See
  the section below.
- **Anything untagged.**

### The CodeBuild source bucket

`5.1_agentcore_deploy.ipynb` never creates this bucket directly. The starter toolkit does, on the
first `launch()`: it zips the `deployment-tools/` build context, uploads it to S3, and points
CodeBuild at the object. The name is fixed by the toolkit as
`bedrock-agentcore-codebuild-sources-<account-id>-<region>`.

It stays behind for three reasons, all of them deliberate:

1. **It is not tagged.** The toolkit creates it without tags, and `workshop_cleanup.py` deletes only
   what carries `WorkshopResource=stop-ai-agent-hallucinations`. There is no S3 discoverer in the
   script at all, so the bucket is not even reported as `UNTAGGED_BLOCKED`.
2. **It is not exclusively ours.** One bucket per account per region serves every AgentCore
   deployment there, not just this workshop's. Deleting it could break an unrelated deploy in the
   same account.
3. **Adding an S3 deleter would mean matching on the name.** That is the pattern bug B6 came from:
   an earlier teardown matched IAM roles by name prefix and destroyed five roles this workshop never
   created. Untagged resources get reported, never guessed at, and a resource that is not even ours
   to begin with does not get a special case.

**What it costs.** Close to nothing, and it largely empties itself. At creation the toolkit attaches
a lifecycle rule named `DeleteOldBuilds` that expires objects after 7 days, and each uploaded source
archive is a few megabytes. At S3 Standard rates that is a fraction of a cent per month while the
objects live, and an empty bucket has no storage charge at all.

**Removing it by hand.** Only once you are sure no other AgentCore deployment in that region is
using it:

```bash
aws s3 rm s3://bedrock-agentcore-codebuild-sources-<account-id>-<region> --recursive
aws s3 rb s3://bedrock-agentcore-codebuild-sources-<account-id>-<region>
```

Get `<account-id>` from `aws sts get-caller-identity --query Account --output text`, and use the
same region Lab 5 deployed into.

## Neo4j Teardown Is Separate

The workshop Neo4j database is terminated through its own environment lifecycle, not by this script.
The executable cleanup path here is AWS-only, deliberately: it contains no Neo4j record or index
cleanup, because deleting graph data from a database that is about to be terminated wholesale adds
failure modes without reclaiming anything. Workshop ownership markers on graph records are left in
place for provenance.

Lab 6's agent memory is also graph-native, stored in Neo4j rather than in AgentCore Memory, so it goes
away with the database and nothing here touches it. AgentCore Memory teardown stays in this cleanup for
one reason: an earlier version of this workshop created `workshop_HotelBookingMemory`, and it is
deleted through the same tag-gated path listed in the legacy table above.

## Reclaiming Resources From a Run Before Tagging Existed

Earlier versions of this workshop created resources without tagging them. Cleanup will refuse to
delete those, correctly: it cannot prove it created them. If you ran this workshop before, you may be
paying for orphans that this script reports and then leaves alone.

They are safe to remove, but you have to confirm they are yours first. Deletion here is by hand and by
eye, not by script, for the same reason the tag gate exists.

**Step 1. List what cleanup is refusing to touch.** The dry run names them under `BLOCKED`:

```bash
python workshop_cleanup.py --dry-run
```

**Step 2. Confirm each one predates your tagged deployment.** Creation time is the evidence that a
resource came from an older run rather than from something else you are running now:

```bash
aws dynamodb describe-table --table-name <name> --query 'Table.CreationDateTime'
aws lambda get-function-configuration --function-name <name> --query 'LastModified'
aws iam get-role --role-name <name> --query 'Role.CreateDate'
aws ecr describe-repositories --repository-names <name> --query 'repositories[0].createdAt'
```

**Step 3. Check the whole account, not just this region.** IAM is global. Lambda, DynamoDB, ECR,
CodeBuild and AgentCore are regional, so an old run in another region is invisible from this one.
Repeat with `--region` for every region you have used.

**Step 4. Delete by hand, one at a time, reading each name before you confirm it.**

Do not write a loop that deletes everything matching `hotel-booking-*` or `workshop-*`. That is
precisely the prefix-matching mistake documented above, and running it against your own account is how
five unrelated roles were destroyed. If a name looks close but you cannot account for the resource,
leave it and investigate.

**A shortcut worth knowing.** Instead of deleting an old resource, you can adopt it by applying the
workshop tag, after which cleanup will remove it normally:

```bash
aws dynamodb tag-resource --resource-arn <arn> \
  --tags Key=WorkshopResource,Value=stop-ai-agent-hallucinations
```

Only do this for resources you have confirmed came from this workshop. Tagging something is a claim of
ownership, and the next cleanup run will act on it.

**What you will probably find.** The starter toolkit's shared `AmazonBedrockAgentCoreSDKCodeBuild-*`
role survives teardown by design. It costs nothing, it is shared across projects, and deleting it is
what caused the original incident. Leaving it is the right outcome. A `bedrock-agentcore-*-builder`
CodeBuild project is different: `5.1_agentcore_deploy.ipynb` tags the one it creates, so teardown
deletes it. Only an untagged builder project from an older run survives, and that one is reported
`BLOCKED` rather than removed.

## Estimated Time

2-3 minutes for `workshop_cleanup.py --yes`. Enumerating IAM role tags across a large account dominates
the plan step, measured at roughly 145 seconds on a development account holding 426 roles.

`5.2_teardown.ipynb` takes about three times that, because it builds the plan three times: once for the
dry run you read, once inside the deletion pass, and once again to verify nothing is left. That is the
point of the notebook, and it is why a ten-minute command timeout is too short for it. Run it detached.
