# Module 7: Production Deploy with Memory

Deploy AgentCore agent with long-term memory that recalls user preferences across sessions.

> **Optional managed-memory reference.** This module is not part of the core
> workshop path. It layers AgentCore Memory onto a pre-provisioned booking
> agent deployment and teaches one lesson: cross-session recall with a managed
> memory service. It does not create the booking backend it connects to. The
> core path (Demo 06A) uses a simplified single-reservation-Lambda
> architecture, so the multi-table booking deployment this reference reuses is
> a pre-provisioned dependency rather than part of the current core build.
> Module 8 runs independently.

## Prerequisites

**A pre-provisioned booking agent deployment must already exist.** This module
does not deploy it; it connects to and reuses:
- AgentCore Gateway (`HotelBookingGateway`)
- The gateway's tool Lambdas
- The backing DynamoDB tables
- IAM role (`workshop-AgentCoreExecutionRole`)

The core workshop path does not create this deployment. Run this reference only
in an environment where it has been provisioned separately.

## What This Module Does

1. **Creates AgentCore Memory resource** with two strategies:
   - `UserPreferences` — hotel preferences (stars, cities)
   - `UserFacts` — user information (name, loyalty number)

2. **Deploys a second agent** with `memory_mode="STM_AND_LTM"`:
   - Code: `booking_agent_with_memory.py`
   - Memory integration via `AgentCoreMemorySessionManager`
   - Connects to the pre-provisioned booking deployment (Gateway + Lambdas)

3. **Tests cross-session memory recall**:
   - **Session A:** User shares name and preferences
   - **Wait for records:** Poll until AgentCore has extracted facts and preferences
   - **Session B:** New session, same actor → agent recalls from long-term memory

## Files

| File | Purpose |
|------|---------|
| `deploy_memory_agent.ipynb` | Create Memory resource, deploy agent, test cross-session recall |
| `booking_agent_with_memory.py` | Strands agent with AgentCore Memory integration |
| `memory_check.py` | Wait for extracted fact and preference records before testing LTM |
| `test_memory_check.py` | Offline tests for the readiness check |
| `agent_requirements.txt` | Python dependencies (strands-agents, bedrock-agentcore-starter-toolkit) |

## Key Differences: Baseline Agent vs Memory-Enabled Agent

| Baseline booking agent | Memory-enabled agent (this module) |
|----------|----------|
| Runtime memory only (ephemeral) | AgentCore Memory with `STM_AND_LTM` |
| No Memory resource | AgentCore Memory with strategies |
| `booking_agent.py` | `booking_agent_with_memory.py` |
| Conversation buffer (lost on session end) | Persistent memory (recalled across sessions) |

**Memory types explained:**
- **Runtime memory** (Module 6): Temporary conversation buffer maintained by Strands Agent. Lost when session ends.
- **STM (Short-Term Memory)**: Session-scoped memory managed by AgentCore. Lost when session ends.
- **LTM (Long-Term Memory)**: Persistent memory managed by AgentCore. Extracts strategies asynchronously and recalls across sessions.

**About the extraction wait:** LTM extraction is a managed background pipeline. After a session's messages are stored, AgentCore analyzes them asynchronously and writes fact and preference records into the actor's namespaces, which usually takes tens of seconds to a few minutes. A fact from Session A is not recallable in Session B until that pipeline completes, so the notebook polls for actual extracted records via `memory_check.py` instead of sleeping for a guessed duration.

## How Memory Works

**AgentCore Memory** stores extracted strategies from conversations and recalls them across sessions. The memory-enabled agent integrates with AgentCore Memory via the Strands Agent `session_manager` parameter:

```python
from strands_agents.models import Agent
from bedrock_agentcore_starter_toolkit import AgentCoreMemoryConfig, AgentCoreMemorySessionManager

# Configure memory retrieval
memory_config = AgentCoreMemoryConfig(
    memory_id=MEMORY_ID,              # AgentCore Memory resource ID
    session_id=context.session_id,     # Current session
    actor_id=actor_id,                 # User identifier
    retrieval_config={
        f"/users/{actor_id}/facts": RetrievalConfig(top_k=3, relevance_score=0.5),
        f"/users/{actor_id}/preferences": RetrievalConfig(top_k=3, relevance_score=0.5)
    }
)

# Create session manager
session_manager = AgentCoreMemorySessionManager(memory_config, region)

# Pass to Strands Agent
agent = Agent(
    model=model,
    tools=tools,
    system_prompt=SYSTEM_PROMPT,
    hooks=hooks,
    session_manager=session_manager  # ← Enables AgentCore Memory integration
)
```

The runtime reuses this agent only while both actor ID and session ID are
unchanged. A new session creates a new memory session manager, which retrieves
the actor's LTM instead of continuing the previous session's STM.

**Actor ID** scopes memory by user (format: `user-{8-char-uuid}`). Same actor ID across sessions → shared memory. Passed via custom HTTP header:
```python
'X-Amzn-Bedrock-AgentCore-Runtime-Custom-Actor-Id': user_id
```

## Run the Demo

Open `deploy_memory_agent.ipynb` and execute all cells. The notebook:
1. Connects to the pre-provisioned booking deployment (Gateway, IAM role)
2. Creates AgentCore Memory resource with strategies
3. Deploys memory-enabled agent with `memory_mode="STM_AND_LTM"`
4. Tests STM (same session)
5. Polls for extracted fact and preference records (up to 5 minutes)
6. Tests LTM (different session, same actor)

## Expected Results

**Session A (STM):**
```
User: My name is Alex and I prefer 4-star hotels in Paris.
Agent: I've noted your preferences, Alex.

User: What's my loyalty number?
Agent: Your loyalty number is HOTEL-12345.
```

**Session B (LTM, after records are ready):**
```
User: Do you remember me? What's my name?
Agent: Yes, I remember you! Your name is Alex.

User: Find me a hotel based on my preferences
Agent: Based on your preference for 4-star hotels in Paris, I recommend...
```

## Next Module: Inspectable Neo4j Memory (Module 8)

AgentCore Memory is the managed memory option: AWS runs extraction, storage, and retrieval, and there is no memory infrastructure to operate. The trade is opacity and propagation delay. You cannot inspect why a record was extracted, and a fact only becomes recallable after the background pipeline finishes.

[Module 8](../08-neo4j-memory-demo/) is the inspectable alternative: agent memory stored in the same Neo4j graph as the hotel domain data. Its explicit preference is queryable, carries provenance back to its source message, links to the real `Hotel`, and is recalled through an actor-anchored read. The application remains responsible for authenticating actors and authorizing session IDs. Writes are visible immediately, with no asynchronous extraction wait.

**When to choose which:** choose AgentCore Memory when you want managed extraction with nothing to operate and can accept the propagation delay; choose Neo4j graph memory when you need explicit writes, immediate visibility, and a memory store you can inspect, query, and connect to your domain graph.

## Cleanup

To delete the Memory resource:
```python
agentcore_control.delete_memory(memoryId=MEMORY_ID)
```

To delete the memory-enabled agent:
```python
agentcore.delete_agent_runtime(agentRuntimeId=MEMORY_RUNTIME_ID)
```
