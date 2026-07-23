# Grounded AI Agents with Neo4j and AWS: Stop Agent Hallucinations from Retrieval to Production

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://python.org)
[![Strands Agents](https://img.shields.io/badge/Strands_Agents-1.27+-00B4D8.svg?style=flat)](https://strandsagents.com)
[![Amazon Bedrock](https://img.shields.io/badge/Amazon-Bedrock-FF9900.svg?style=flat&logo=amazon-aws)](https://aws.amazon.com/bedrock/)
[![Neo4j](https://img.shields.io/badge/Neo4j-Graph--RAG-4581C3.svg?style=flat&logo=neo4j)](https://neo4j.com)
[![License: MIT-0](https://img.shields.io/badge/License-MIT--0-green.svg)](LICENSE)
[![Last Updated](https://img.shields.io/badge/Updated-July_2026-brightgreen.svg?style=flat)]()

When a booking agent invents a cancellation policy, confirms a room it never checked, or books past the maximum-guest limit, the cost lands on a real guest and a real reservation. An answer a business cannot trace is an answer it cannot act on. This workshop makes every agent answer traceable to connected data.

This is a joint Neo4j and AWS workshop. It shows how a grounded agent moves from retrieval and deterministic controls into a production-shaped deployment, using connected data to stop the failures that make agents hallucinate: fabricated statistics, wrong tool picks, ignored business rules, and false claims of success.

**Why Neo4j and AWS?** Two platforms solve different problems well. AWS supplies the reasoning and generation layer; Neo4j makes relationships traversable so retrieval returns connected, verifiable facts. Together they form one grounded agent stack.

The central story is a division of responsibility:

- **Neo4j** owns the connected hotel knowledge graph, the retrieval indexes, the tool metadata, the production rules, and the optional inspectable memory.
- **AWS** supplies Bedrock models and embeddings, AgentCore hosting and tool exposure, Secrets Manager, IAM, Lambda integration where needed, and observability through CloudWatch and AgentCore.

The main production demonstration, Demo 06, fits a rehearsed 30 to 45 minute session and runs entirely on a participant's own Aura and Amazon Bedrock. It is not a from-scratch AWS deployment lab and it does not implement a hotel reservation system. The AgentCore deployment that hosts the same boundary as a managed service is staged in [`06-agentcore-boto3-demo/advanced-deployment/`](06-agentcore-boto3-demo/advanced-deployment/).

> Based on the Dev.to series [Stop AI Agent Hallucinations: 4 Essential Techniques](https://dev.to/aws/stop-ai-agent-hallucinations-4-essential-techniques-2i94) and [5 Techniques to Stop AI Agent Hallucinations in Production](https://dev.to/aws/5-techniques-to-stop-ai-agent-hallucinations-in-production-oik).

Built with [Strands Agents](https://strandsagents.com) and Amazon Bedrock. The same patterns apply in LangGraph, AutoGen, CrewAI, or any other agent framework.

> **Architecture diagram:** A detailed architecture view of Demo 06, showing AgentCore Runtime with Hybrid-Cypher retrieval, AgentCore Gateway, the reservation Lambda, Bedrock, Secrets Manager, IAM, CloudWatch, and Neo4j Aura, is maintained in [`workshop-delivery/architecture.md`](workshop-delivery/architecture.md). The Neo4j MCP service appears only in the separate Demo 09 view. That guide is under active drafting; treat this reference as the placeholder for the canonical diagram.

---

## Graph-RAG vs. Standard RAG: Why It Matters for Hallucinations

| Approach | Hallucination Risk | Retrieval Method | Best For |
|---|---|---|---|
| Standard RAG (vector) | High. Returns similar content even when irrelevant | Cosine similarity | General Q&A |
| Graph-RAG (Neo4j) | 73% lower per RAG-KG-IL, arXiv 2503.13514; grounded in entity relationships | Graph traversal plus Cypher | Structured domains such as hotels, products, and finance |

> **Key insight:** Vector search always returns *something similar*, even when the answer does not exist in the database, which causes fabrication. Graph-RAG returns only what is explicitly connected in the knowledge graph.

**What comes back for "amenities at AnyCompany Cairo Nile View?"**

| Approach | What the agent gets back |
|---|---|
| Vector search alone | "Here are text chunks mentioning pool, gym, and free breakfast." |
| Graph-RAG (Neo4j) | "Here are amenity chunks for AnyCompany Cairo Nile View (with its stable hotel_id), guest rating 4.4, connected to its 12 amenities and cancellation policy, or nothing if the graph has no such hotel." |

---

## Platform Responsibilities

Neo4j and AWS each own a clear part of the grounded agent. One side holds the connected data and deterministic rules; the other side supplies the models, hosting, and operational surface.

| Responsibility | Neo4j | AWS |
|---|---|---|
| Connected domain data | Hotel knowledge graph and relationship traversal | Bedrock reasons over retrieved evidence |
| Retrieval | Vector, full-text, and graph traversal indexes | Bedrock creates document and query embeddings |
| Production graph reads | Vector and full-text indexes plus a reviewed graph traversal | AgentCore Runtime hosts the `HybridCypherRetriever` and Bedrock supplies query embeddings |
| Reservation request | Stores the workshop-owned request, relationship, and production rule | One Lambda validates and performs the command |
| Tool selection | Tool descriptions, embeddings, and workflow relationships | Strands and AgentCore expose and invoke tools |
| Rules and steering | Demo 06 production rule data | Demo 04 hooks, Demo 05 Agent Control, and the Demo 06 Lambda apply the policy |
| Memory | Optional inspectable memory graph with provenance | AgentCore Memory provides the managed alternative |
| Security and operations | Read and write roles appropriate to each service | IAM, Secrets Manager, Runtime, Gateway, CloudWatch, and AgentCore observability |

---

## Data Ownership

| Data | Owner |
|---|---|
| Hotels, amenities, policies, services, and graph relationships | Neo4j |
| Chunk vector and full-text indexes | Neo4j |
| Tool graph | Neo4j |
| Demo 06 production rule and steering message | Neo4j |
| Demo 04 rule fixture | Existing Python implementation, unchanged |
| Demo 05 steering fixture | Existing Agent Control configuration, unchanged |
| Workshop reservation requests | Neo4j |
| Credentials | AWS Secrets Manager |
| Traces and logs | AgentCore and CloudWatch |
| Real inventory, booking, payment, and confirmation state | External reservation system |

**One Neo4j Aura instance is enough.** A single Aura graph supports retrieval, tool selection, validation, the Demo 06 production rules, and the optional inspectable graph memory. There is no separate hotel catalog to maintain and no duplicated store to keep in sync.

**DynamoDB is not part of the executable core path.** The expanded production architecture may identify DynamoDB as one optional persistence choice behind an external reservation system. The workshop does not create or teach DynamoDB hotel, rule, booking, or payment tables, and real inventory, booking, payment, and confirmation state stay behind that external-system boundary.

---

## Module List and Tracks

![Why AI agents fail: the six-demo progressive flow](images/why-ai-agents-fail-six-demos-progressive-flow.png)

Every module is marked as one of three tracks:

- **Core:** the reliable end-to-end path an event should always run.
- **Audience-dependent:** add these based on the audience and available time.
- **Optional-advanced:** deeper technical tracks that any event can omit without affecting the core path.

| # | Demo | Track | What It Solves | Stack |
|:-:|------|-------|----------------|-------|
| 00 | [Getting Started](./00-getting-started/) | Core | Strands Agents primer: agents, tools, lifecycle hooks, and multi-agent swarms | ![Strands](https://img.shields.io/badge/Strands_Agents-00B4D8?style=flat) ![AWS](https://img.shields.io/badge/AWS-FF9900?style=flat&logo=amazon-aws) |
| 01 | [Graph-RAG vs RAG](./01-graphrag-demo/) | Core | Fabricated statistics, incomplete retrieval, out-of-domain hallucination | ![Neo4j](https://img.shields.io/badge/Neo4j-4581C3?style=flat&logo=neo4j&logoColor=white) ![FAISS](https://img.shields.io/badge/FAISS-blue?style=flat) |
| 01b | [Neo4j Retrieval Patterns](./01-graphrag-demo/) | Audience-dependent | Compares vector, hybrid, Vector-Cypher, and library Text2Cypher retrieval | ![Neo4j](https://img.shields.io/badge/Neo4j-4581C3?style=flat&logo=neo4j) |
| 02 | [Semantic Tool Selection](./02-semantic-tools-demo/) | Audience-dependent | Wrong tool picks and token waste at scale, using vector similarity plus workflow relationships | ![Neo4j](https://img.shields.io/badge/Neo4j-4581C3?style=flat&logo=neo4j) ![Embeddings](https://img.shields.io/badge/Embeddings-teal?style=flat) |
| 03 | [Graph-Backed Domain Validation](./03-multiagent-demo/) | Audience-dependent | Undetected hallucinations checked against the appropriate source of truth | ![Swarm](https://img.shields.io/badge/Swarm-green?style=flat) ![Neo4j](https://img.shields.io/badge/Neo4j-4581C3?style=flat&logo=neo4j) |
| 04 | [Deterministic Rule Enforcement](./04-neurosymbolic-demo/) | Core | Agents ignoring business rules in prompts, blocked by a Python lifecycle hook | ![Hooks](https://img.shields.io/badge/Hooks-purple?style=flat) |
| 05 | [Agent Control Steering](./05-steering-demo/) | Core | Hard-blocking stops the task instead of steering the agent toward safe behavior | ![Agent Control](https://img.shields.io/badge/Agent_Control-orange?style=flat) |
| 06 | [Grounded Hotel Retrieval and Safe Reservations](./06-agentcore-boto3-demo/) | Core | Taking the grounded path to a real action, run locally: one Hybrid-Cypher retrieval tool and one idempotent reservation-request write | ![AgentCore](https://img.shields.io/badge/Bedrock-AgentCore-FF9900?style=flat&logo=amazon-aws) ![Neo4j](https://img.shields.io/badge/Neo4j-4581C3?style=flat&logo=neo4j) ![Lambda](https://img.shields.io/badge/Lambda-FF9900?style=flat&logo=aws-lambda) |
| 06 deploy | [AgentCore Deployment (deferred)](./06-agentcore-boto3-demo/advanced-deployment/) | Optional-advanced | Staged, not run in this pass: host the same boundary as a managed AWS service (Runtime, Gateway, Lambda) | ![AgentCore](https://img.shields.io/badge/Bedrock-AgentCore-FF9900?style=flat&logo=amazon-aws) |
| 07 | [AgentCore Memory](./07-agentcore-memory-demo/) | Optional-advanced | Managed cross-session memory with no memory infrastructure to operate | ![Memory](https://img.shields.io/badge/AgentCore-Memory-FF9900?style=flat) |
| 08 | [Inspectable Neo4j Memory](./08-neo4j-memory-demo/) | Optional-advanced | Explicit, inspectable memory with provenance and actor isolation | ![Neo4j](https://img.shields.io/badge/Neo4j-Memory-4581C3?style=flat&logo=neo4j) |
| 09 | [Neo4j MCP and Controlled Text2Cypher](./09-neo4j-mcp-demo/) | Optional-advanced | Governed graph exploration through a read-only MCP trust boundary | ![MCP](https://img.shields.io/badge/Neo4j-MCP-4581C3?style=flat&logo=neo4j) |
| 10 | [Cleanup](./10-cleanup/) | Core | Safe, tag-scoped AWS teardown. The Neo4j database is terminated separately | ![Cleanup](https://img.shields.io/badge/Workshop-Cleanup-555555?style=flat) |

The facilitator may include optional modules, but Demo 06 remains a bounded 30 to 45 minute module. Every audience-dependent and optional-advanced module can be omitted without affecting the core path.

---

## How Do the Modules Build on Each Other?

The learning path is progressive, and each demo can also run on its own.

**Core track.** Demo 00 is the Strands Agents primer covering the core concepts every later demo uses. Demo 01 shows why connected data reduces hallucination. Demos 04 and 05 show deterministic rule enforcement and Agent Control steering for the same maximum-guests policy. Demo 06 takes the grounded path to a protected action, run locally, with the AgentCore deployment staged for later. Demo 10 cleans up tagged AWS resources.

**Audience-dependent additions.** Demo 01b compares Neo4j retrieval patterns. Demo 02 adds semantic tool selection backed by workflow relationships. Demo 03 adds graph-backed domain validation against the appropriate source of truth.

**Optional-advanced tracks.** The Demo 06 AgentCore deployment is staged in `06-agentcore-boto3-demo/advanced-deployment/` as deferred future work. Demo 07 shows managed AgentCore Memory, and Demo 08 shows inspectable Neo4j graph memory with provenance; the two close with a shared decision guide. Demo 09 teaches MCP and controlled Text2Cypher as a trust-boundary alternative to Demo 06's fixed Hybrid-Cypher path.

---

## Demo 06: The Production Core

Demo 06 is the central production demonstration. In 30 to 45 minutes, learners run one predictable graph-enriched retrieval path against their own Aura instance, watch the grounded agent abstain on a question the graph cannot answer, then exercise one protected reservation command locally: a 15-guest request is rejected with no write, a corrected request is recorded idempotently, and the stored request is read back from the graph.

**The two hero questions.** The workshop is anchored by two questions asked against the same graph:

- *"What amenities and guest rating does AnyCompany Cairo Nile View have?"* returns connected, grounded evidence.
- *"Does AnyCompany Cairo Nile View guarantee room availability next weekend?"* makes the agent abstain, because the graph holds no live availability. The abstention is the point: the agent answers only from evidence.

**One notebook:**

`01_hybrid_retrieval.ipynb` is the participant hands-on path, run entirely against each participant's own Aura instance and Amazon Bedrock. It covers grounded retrieval, abstention, the maximum-guests rejection, the idempotent reservation write, and graph inspection. The facilitator notebook that invokes a pre-deployed AgentCore Runtime is staged in `06-agentcore-boto3-demo/advanced-deployment/` and is not run in this pass.

**Two logical tools:**

| Tool | Responsibility |
|---|---|
| Hybrid retrieval tool | One `HybridCypherRetriever` that combines vector and full-text chunk matching with a reviewed Cypher traversal |
| Reservation command | Loads the applicable Neo4j rule, enforces it, and creates workshop-owned reservation requests |

In the deferred AWS deployment, the retrieval tool runs in the AgentCore Runtime and the reservation command runs as a Lambda behind the Gateway. There is exactly one write command in this design. The retriever uses one fixed pattern with explicit `NAIVE` fusion and `top_k=5`, accepts only `query`, and returns bounded chunk evidence, a combined score, exact matched terms, and the connected hotel with its stable `hotel_id`, name, address, guest rating, and up to 12 amenities.

**What Demo 06 deliberately excludes from the core path:** no DynamoDB tables, no retriever-mode or ranker selector, no Neo4j MCP server or Text2Cypher, no model-generated or caller-supplied Cypher, no separate validation Lambda, and no payment, confirmation, or inventory simulation. The AWS deployment that hosts this boundary as a managed service is staged in `advanced-deployment/` and is not run in the core path.

> **Offline status:** The self-contained notebook is built and registered on the `extend-neo4j` branch. The deterministic offline gates pass, with `uv run setup/run_notebooks.py --labs 6` reporting Passed 1 / Failed 0 while every live cell self-skips and no AWS resources are created. Live participant retrieval, the local reservation write, and event timing remain operator rehearsal tasks that need Neo4j and AWS credentials. The deferred deployment and its facilitator notebook are staged in `advanced-deployment/`.

---

## How Do I Run These Demos?

### Prerequisites

- Python 3.9+
- [uv](https://docs.astral.sh/uv/) package manager
- AWS account with [Amazon Bedrock](https://aws.amazon.com/bedrock/) access, with Claude Sonnet 5 enabled in your region
- One Neo4j Aura instance for the retrieval, tool selection, validation, rule, and optional memory modules

### Run Any Demo

```bash
cd 01-graphrag-demo   # or any demo folder
uv venv && uv pip install -r requirements.txt

# Run the demo
uv run <main_script>.py
# Or open the .ipynb notebook in your IDE (VS Code, Kiro, or any editor with notebook support)
```

Each demo README has specific setup instructions and prerequisites.

### Run Notebooks as Tests

The shared notebook runner uses `nbconvert` to execute source notebooks without
modifying them. It creates its own cached environment through `uv`, writes
executed notebooks to a temporary directory, and exits nonzero if a cell raises
an error:

```bash
uv run setup/run_notebooks.py              # Labs 00-05
uv run setup/run_notebooks.py --labs 4     # One lab
uv run setup/run_notebooks.py --labs 2-5   # A range
```

`setup/run_notebooks.py --labs 6` is the repository acceptance path for Demo 06. It executes the self-contained participant notebook, whose live cells self-skip when Neo4j or Bedrock is absent, and it never creates or modifies AWS resources. Labs 08 and 09 are optional notebook-only modules. Lab 10 deletes tagged workshop resources and requires `--include-cleanup`. See
[`setup/README.md`](setup/README.md) for the complete command reference.

### Notebook Setup (nbstripout)

This repository strips notebook output on commit through a git filter declared in `.gitattributes` (`*.ipynb filter=nbstripout diff=ipynb`). Register the filter once after cloning, or every `.ipynb` checkout runs against an undefined filter:

```bash
pip install nbstripout
nbstripout --install
```

Run both commands from the repository root. `nbstripout --install` writes the `filter.nbstripout` entries into your local git config so the `.gitattributes` rule resolves.

### Neo4j Setup

The workshop uses one Neo4j Aura instance across its graph-backed modules: Graph-RAG retrieval, retrieval-pattern comparison, tool selection, domain validation, the Demo 06 production rules, and optional inspectable memory.

**Create the credentials once at the repo root.** Copy `.env.example` to a single `.env` file in the repository root and fill in your Aura values. Every graph-backed module reads these same credentials, so you configure them once rather than per demo:

```bash
cp .env.example .env
```

```
NEO4J_URI=neo4j+s://<your-instance>.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<your-password>
NEO4J_DATABASE=neo4j
AWS_REGION=us-east-1
```

The demos load the nearest `.env` first, so a `.env` inside a specific demo folder still works and takes precedence over the repo-root file. Keeping one file at the root is the simplest setup because it covers Demo 01 through the optional memory module without copying credentials between folders.

**Running as part of a workshop:** A Neo4j Aura instance will be provided. You will receive the connection credentials (`NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`) at the start of the session. Add them to the repo-root `.env` file.

> **Workshop Studio username variable:** the hosted CloudFormation environment writes `NEO4J_USER`, while every demo in this repository reads `NEO4J_USERNAME`. If a demo cannot authenticate inside the hosted workshop, confirm which name is set.

**Running independently:** Create your own free Neo4j Aura instance:

1. Go to [console.neo4j.io](https://console.neo4j.io) and create a free **AuraDB** instance
2. Download the credentials file when prompted; it contains your URI, username, and password
3. Fill in the repo-root `.env` created above with those values
4. Enable the **APOC** plugin in your Aura instance settings
5. For Demo 01, run `build_graph_lite.py` (30 docs, about 15 min) or `build_graph.py` (300 docs, about 2 hours) to populate the graph

Participants use their own Aura instance for the hands-on retrieval and reservation path through Demo 06. The AgentCore deployment that would host this boundary on shared infrastructure is staged in `06-agentcore-boto3-demo/advanced-deployment/` and is not run in this pass.

---

## Frequently Asked Questions

### What types of AI agent hallucinations does this repository address?

This repository addresses four main categories: **(1)** fabricated statistics, when RAG agents guess numbers instead of computing them; **(2)** wrong tool selection, when agents pick inappropriate tools from large toolsets; **(3)** business rule violations, when agents ignore constraints expressed only in prompts; and **(4)** undetected failures, when single agents claim success without validation.

### What do Neo4j and AWS each provide?

Neo4j holds the connected hotel knowledge, the retrieval indexes, the tool metadata, the production rules, and the optional inspectable memory. AWS supplies Bedrock models and embeddings, AgentCore hosting and tool exposure, Secrets Manager, IAM, Lambda integration where needed, and observability. See the Platform Responsibilities and Data Ownership tables above.

### Do I need DynamoDB?

No. DynamoDB is not part of the executable core path. It appears only as one optional persistence choice behind an external reservation system in the going-further architecture notes. The workshop does not create or teach DynamoDB tables.

### Can I use these patterns with frameworks other than Strands Agents?

Yes. The patterns (Graph-RAG, semantic tool filtering, multi-agent validation, neurosymbolic guardrails, steering controls) are framework-agnostic concepts. These demos use Strands Agents, but the same approaches apply in LangGraph, AutoGen, CrewAI, Haystack, or custom implementations. The key insight is architectural, not framework-specific.

### Do I need an AWS account to run the demos?

Yes. All demos use Amazon Bedrock (Claude Sonnet 5) as the default LLM provider. You need an AWS account with Bedrock access enabled in your region.

### How long does it take to run each demo?

Demos 02 through 05 run in under 5 minutes. Demo 01 has a lite mode (30 docs, about 15 minutes) and a full mode (300 docs, about 2 hours) for building the knowledge graph. Demo 06 is designed as a rehearsed 30 to 45 minute session.

### What LLM providers are supported?

All demos default to Amazon Bedrock (Claude Sonnet 5) but work with any provider supported by Strands Agents: Anthropic API, OpenAI, Ollama for local models, or any OpenAI-compatible endpoint. See [Strands Model Providers](https://strandsagents.com/docs/user-guide/concepts/model-providers/amazon-bedrock/) for configuration.

---

## Common Issues and How to Fix Them

**Bedrock access denied:** Ensure the model (`us.anthropic.claude-sonnet-5` or similar) is enabled in your region via the [Bedrock Model Access console](https://console.aws.amazon.com/bedrock/home#/modelaccess).

**Neo4j connection fails:** Verify `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD` are set in your `.env` file and that APOC is enabled on your Aura instance.

**OpenTelemetry warnings:** "Failed to detach context" warnings in demos 03 through 05 are harmless and do not affect functionality.

**Model alternatives:** Change the model in any demo by modifying the `BedrockModel(model_id=...)` call. See [Strands Model Providers](https://strandsagents.com/docs/user-guide/concepts/model-providers/amazon-bedrock/) for all supported options.

For demo-specific issues, check the troubleshooting section in each demo's README.

---

## From Workshop to Production

Demo 06 is deliberately small. It runs on your own Aura and Amazon Bedrock, so you can watch a grounded agent work without building everything from scratch. A real deployment grows from here in four ways:

- **Add more data and rules to the graph.** The workshop uses a small set of hotels. Production adds more hotels, more relationships between them, and the business rules that keep answers correct.
- **Keep returning the right evidence.** Tune how the agent searches the graph so it still finds the connected facts an answer needs as the amount of data grows.
- **Run and watch the agent.** Host the agent on AWS AgentCore and follow each request from start to finish, so you can see exactly what the agent did and why.
- **Keep the graph up to date.** Build the process that loads new documents and data into the graph over time.

Neo4j Aura is Neo4j's fully managed cloud graph database service. Neo4j and AWS are collaborating to deepen the integration of Neo4j with Amazon Bedrock and AgentCore.

---

## References

1. Fuentes, E. (2025). *Stop AI Agent Hallucinations: 4 Essential Techniques.* Dev.to / AWS. [dev.to/aws/stop-ai-agent-hallucinations-4-essential-techniques-2i94](https://dev.to/aws/stop-ai-agent-hallucinations-4-essential-techniques-2i94)
2. Fuentes, E. (2025). *5 Techniques to Stop AI Agent Hallucinations in Production.* Dev.to / AWS. [dev.to/aws/5-techniques-to-stop-ai-agent-hallucinations-in-production-oik](https://dev.to/aws/5-techniques-to-stop-ai-agent-hallucinations-in-production-oik)
3. Edge et al. (2024). *From Local to Global: A Graph RAG Approach to Query-Focused Summarization.* Microsoft Research. [arXiv:2404.16130](https://arxiv.org/abs/2404.16130)
4. AWS. *Reducing hallucinations in large language models with custom intervention using Amazon Bedrock Agents.* [AWS Blog](https://aws.amazon.com/blogs/machine-learning/reducing-hallucinations-in-large-language-models/)

---

## Contributing

Contributions are welcome! See [CONTRIBUTING](CONTRIBUTING.md) for more information.

---

## Security

If you discover a potential security issue in this project, notify AWS/Amazon Security via the [vulnerability reporting page](https://aws.amazon.com/security/vulnerability-reporting/). Please do **not** create a public GitHub issue.

---

## License

This library is licensed under the MIT-0 License. See the [LICENSE](LICENSE) file for details.

> Last updated: July 2026 | Strands Agents 1.27+ | Python 3.9+
