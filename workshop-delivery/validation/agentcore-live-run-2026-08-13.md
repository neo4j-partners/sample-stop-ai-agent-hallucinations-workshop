# AgentCore Live Validation Record

## Scope

- **Date:** 2026-08-13
- **Region:** Not retained in the sanitized source record
- **Runtime name:** `HotelBookingAgent-i6Jg838kmO`
- **ECR image:** `bedrock-agentcore-hotelbookingagent:20260813-124658-763`
- **Source:** Sanitized from the completed Phase 8 record in the internal workshop rebuild plan

This file records the evidence that is safe to keep in the public repository. It contains no account identifiers, ARNs, Gateway URLs, credentials, secret values, or graph connection strings.

## Deployment result

- **Provisioning:** Created six resources carrying `demo06-agentcore=true`.
- **Runtime launch:** Passed after one IAM propagation retry.
- **Runtime package:** The reservation Lambda imported the built `workshop` package and handled a command successfully.
- **Optional walkthrough:** All six cells of `5.3_agentcore_walkthrough.ipynb` passed against the deployed Runtime.

## Behavioral smoke results

- **Grounded hero question:** Passed. `tools_used` included `search_hotel_knowledge`.
- **Availability question:** Passed the recorded manual review. The response declined to guarantee unavailable inventory data.
- **Over-limit request:** Passed. Retrieval and the Gateway command both ran, and the command returned `reason_code=max_guests_exceeded`.
- **Idempotent retry:** Passed. Repeating the corrected request left one accepted graph record.

The live payloads are not retained here because the original record did not sanitize them for publication. Future runs should retain redacted request and response envelopes so these results can be audited without relying on prose.

## Teardown result

- **Notebook-owned resources:** Deleted 17 selected items. The recorded tiers were 14 compute-and-data resources, two IAM resources, and one local configuration file.
- **Post-delete plan:** Reported zero selected, zero blocked, and 24 absent candidates.
- **Provisioner-owned resources:** Deleted the Gateway target, Gateway, reservation Lambda, three IAM roles, and command secret.
- **Environment cleanup:** Removed `AGENTCORE_GATEWAY_URL`, `AGENTCORE_RUNTIME_ROLE_ARN`, and `NEO4J_COMMAND_SECRET_ID` from the managed `.env` block.
- **Independent verification:** The Resource Groups Tagging API returned no resources for either workshop owner tag.

## Reproduction gaps

- **Exact package versions:** The original run record retained the image tag but not a complete resolved package inventory.
- **Raw smoke envelopes:** The original run record retained verdicts and selected tool names but not publishable redacted payloads.
- **CloudWatch evidence:** Log group paths and trace excerpts were not retained in a public-safe form.
- **Automated schedule:** The repository has no credentialed integration workflow that repeats this validation.

## Requirements for the next live run

- Record the AWS region and resolved package inventory.
- Save redacted request, response, tool-use, command-result, and graph-witness records for all smoke cases.
- Save the teardown plan before and after deletion.
- Verify both workshop owner tags independently after teardown.
- Publish only the sanitized artifact. Keep account identifiers, ARNs, URLs, and credentials out of the repository.
