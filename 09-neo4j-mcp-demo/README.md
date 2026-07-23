# Neo4j MCP and Controlled Text2Cypher

**Optional advanced module.** Demo 09 connects to a pre-deployed Neo4j MCP
read service. It shows one reviewed Cypher template and one optional
Text2Cypher question, while making the trust boundary explicit.

**At a Glance**
- **What it covers:** governed graph access through a read-only trust boundary.
- **Neo4j:** exposed through an MCP service with one reviewed Cypher template.
- **AWS:** Amazon Bedrock runs the agent that calls the MCP tools.
- **You'll build:** a read-only graph query path that fails closed unless the endpoint exposes exactly the expected tools.

## What this module teaches

- Discover tools over streamable HTTP and fail closed unless the endpoint
  exposes exactly `get_neo4j_schema` and `read_neo4j_cypher`.
- Inspect the current database schema server-side.
- Run a reviewed, parameterized, bounded Cypher template without a model.
- Optionally let a Bedrock-powered Strands agent generate read Cypher using
  only the approved tools.
- Choose templates for known production paths and controlled Text2Cypher for
  governed exploration.

The notebook never attempts a write. Event operators test write rejection in
a disposable environment before the workshop.

## The actual controls

| Control | What it provides |
|---------|------------------|
| Read-only Neo4j account | Database-level least privilege, including protection from server bugs |
| Server query classification | Rejects queries classified as writes |
| Exact notebook allowlist | Prevents unexpected discovered tools from reaching the agent |
| Query timeout | Stops a runaway read |
| Response-token cap | Truncates oversized returned text; it is not a database row limit |
| Reviewed template `LIMIT` | Deterministically bounds the template path |

`read_neo4j_cypher` intentionally accepts arbitrary read Cypher. A generated
`LIMIT` is prompt guidance rather than an independently enforced server row
limit. If the model should see only part of the graph, deploy a governed schema
tool; the official server path shown here performs live schema discovery.

## Configuration

The event operator provides:

```bash
NEO4J_MCP_URL=<streamable HTTP endpoint>
NEO4J_MCP_TOKEN=<bearer token when required>
```

The aliases `MCP_GATEWAY_URL` and `MCP_ACCESS_TOKEN` are accepted. Export the
values or put them in a `.env` file. This module does not load the earlier
workshop's `CONFIG.txt`.

The template path needs only MCP access. The optional Text2Cypher cell also
uses:

- AWS credentials with Bedrock access
- `AWS_REGION`, defaulting to `us-east-1`
- `MODEL_ID`, defaulting to `us.anthropic.claude-sonnet-4-6`

When no endpoint is configured, every live cell skips cleanly.

## Run it

```bash
# Canonical participant and repository-validation path
uv run setup/run_notebooks.py --labs 9

# Offline boundary/configuration tests
uv run --with pytest -m pytest 09-neo4j-mcp-demo/test_mcp_config.py
```

## Self-paced local server

The official server is
[`mcp-neo4j-cypher`](https://github.com/neo4j-contrib/mcp-neo4j/tree/main/servers/mcp-neo4j-cypher).
Run a version validated for your event against a dedicated read-only Neo4j
account. `NEO4J_READ_ONLY=true` enables the server's query check but does not
replace database least privilege.

```bash
NEO4J_URI=neo4j+s://<your-instance>.databases.neo4j.io \
NEO4J_USERNAME=<read-only-user> \
NEO4J_PASSWORD=<password> \
NEO4J_DATABASE=neo4j \
NEO4J_READ_ONLY=true \
NEO4J_READ_TIMEOUT=30 \
NEO4J_RESPONSE_TOKEN_LIMIT=4000 \
uvx mcp-neo4j-cypher --transport http \
  --server-host 127.0.0.1 --server-port 8000

export NEO4J_MCP_URL=http://127.0.0.1:8000/mcp/
```

For a scheduled event, pin and preflight the deployed server version rather
than resolving the latest package during the session.

## Files

| File | Purpose |
|------|---------|
| `mcp_text2cypher.ipynb` | Tool allowlist, schema discovery, template, and optional Text2Cypher path |
| `mcp_config.py` | Environment parsing, fail-closed tool selection, and tool-result validation |
| `test_mcp_config.py` | Offline tests for those boundary helpers |

## Where this fits

Demo 01b teaches in-process Text2Cypher. Demo 09 moves read execution behind an
MCP service. The production default remains Demo 06A's fixed reviewed
Hybrid-Cypher traversal; MCP Text2Cypher is the advanced exploration path.
