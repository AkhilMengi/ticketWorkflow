# High-Level Design — Agentic Issue Resolution System

## Table of Contents
1. [System Overview](#1-system-overview)
2. [What is LangChain and How It Is Used Here](#2-what-is-langchain-and-how-it-is-used-here)
3. [What is LangGraph and How It Is Used Here](#3-what-is-langgraph-and-how-it-is-used-here)
4. [LangChain Inside LangGraph — The Relationship Explained](#4-langchain-inside-langgraph--the-relationship-explained)
5. [Architecture — Three-Tier Overview](#5-architecture--three-tier-overview)
6. [LangGraph Workflow — Node-by-Node Walkthrough](#6-langgraph-workflow--node-by-node-walkthrough)
7. [Full Data Flow — Step-by-Step Trace](#7-full-data-flow--step-by-step-trace)
8. [Component Responsibility Table](#8-component-responsibility-table)
9. [API Endpoints Reference](#9-api-endpoints-reference)

---

## 1. System Overview

**Purpose:** When a customer reports an issue (e.g. "I was double-charged $150"), this system automatically decides — using an LLM — whether to open a Salesforce support case, trigger a billing correction, or both. A human never needs to manually triage the issue.

**Core Technologies:**

| Layer | Technology | Role |
|---|---|---|
| API Gateway | FastAPI + Uvicorn | Receives HTTP requests, serves JSON and SSE responses |
| AI Decision Engine | LangChain (`ChatOpenAI`) | Wraps GPT-4o-mini, formats prompts, returns structured decisions |
| Workflow Orchestrator | LangGraph (`StateGraph`) | Executes nodes in sequence, routes conditionally, manages shared state |
| CRM Integration | Salesforce REST API | Creates support cases via OAuth2 |
| Billing Integration | Billing Microservice HTTP | Posts structured billing tasks via REST |

---

## 2. What is LangChain and How It Is Used Here

### What LangChain Is

LangChain is an **AI integration library**. It gives you ready-made Python classes to:
- Connect to LLMs (OpenAI, Anthropic, etc.) through a uniform interface
- Format prompts and messages that LLMs can understand
- Parse, validate, and work with LLM responses
- Chain multiple AI operations together

Think of LangChain as the **"AI toolkit"** — it handles the low-level mechanics of speaking to an LLM so you don't have to.

### What LangChain Does in This System

LangChain is used **only in one place** — inside `analyze_issue_node` in `app/agent/nodes.py`. Here is exactly what happens:

```
Step 1: Import LangChain components
─────────────────────────────────────────────────────────────
from langchain_openai import ChatOpenAI       # LLM wrapper
from langchain_core.messages import HumanMessage  # Message formatter

Step 2: Create the LLM instance (once, reused via singleton)
─────────────────────────────────────────────────────────────
_llm = ChatOpenAI(
    model="gpt-4o-mini",    # Which OpenAI model to call
    temperature=0,          # 0 = deterministic, no creativity, consistent decisions
    api_key=OPENAI_API_KEY, # Auth from .env
)

Step 3: Build the prompt with account context + suggestions
─────────────────────────────────────────────────────────────
prompt = ANALYZE_ISSUE_PROMPT.format(
    account_id=state["account_id"],
    account_details=json.dumps(state["account_details"], indent=2),
    issue_description=state["issue_description"],
    suggestions=_load_suggestions(),   # reads suggestions.txt
)

Step 4: Wrap prompt in a HumanMessage and call the LLM
─────────────────────────────────────────────────────────────
response = await _llm.ainvoke([HumanMessage(content=prompt)])

Step 5: Parse the LLM's JSON response into structured data
─────────────────────────────────────────────────────────────
parsed = _parse_llm_json(response.content)
# parsed now contains:
# {
#   "analysis": "...",
#   "reasoning": "...",
#   "recommended_actions": ["create_sf_case", "call_billing_api"],
#   "sf_case_payload": { ... },
#   "billing_payload": { ... }
# }
```

### What LangChain Does NOT Do Here

LangChain does **not** control the flow of execution. It does not decide which step runs next. It only calls the LLM and returns a response. Everything outside of that single `ainvoke` call is handled by LangGraph.

---

## 3. What is LangGraph and How It Is Used Here

### What LangGraph Is

LangGraph is a **workflow orchestration framework** built on top of LangChain. It lets you define a multi-step process as a **directed graph** where:
- **Nodes** are Python functions (each one does a specific job)
- **Edges** define which node runs after which
- **Conditional edges** allow dynamic routing (e.g. "if the LLM recommends actions, go to execute_actions; otherwise go to summarize")
- **State** is a shared TypedDict that flows through every node and accumulates results

Think of LangGraph as the **"workflow engine"** — it decides what runs, in what order, and what data gets passed between steps.

### How LangGraph Is Set Up in This System

Defined in `app/agent/graph.py`:

```
from langgraph.graph import StateGraph, START, END
from app.agent.state import AgentState          # the shared TypedDict
from app.agent.nodes import (
    fetch_account_node,
    analyze_issue_node,
    execute_actions_node,
    summarize_node,
)

# 1. Create a new graph with AgentState as shared memory
graph_builder = StateGraph(AgentState)

# 2. Register the 4 nodes
graph_builder.add_node("fetch_account",    fetch_account_node)
graph_builder.add_node("analyze_issue",    analyze_issue_node)
graph_builder.add_node("execute_actions",  execute_actions_node)
graph_builder.add_node("summarize",        summarize_node)

# 3. Define the fixed edges (always run in this order)
graph_builder.add_edge(START,            "fetch_account")
graph_builder.add_edge("fetch_account",  "analyze_issue")
graph_builder.add_edge("execute_actions","summarize")
graph_builder.add_edge("summarize",      END)

# 4. Define the conditional edge (dynamic routing after LLM analysis)
graph_builder.add_conditional_edges(
    "analyze_issue",          # source node
    _route_after_analysis,    # routing function that reads state
    {
        "execute_actions": "execute_actions",   # if actions recommended
        "summarize":       "summarize",         # if no actions needed
    }
)

# 5. Compile the graph into an executable object
agent_graph = graph_builder.compile()
```

### The Shared State — AgentState

Every node reads from and writes to the same `AgentState` TypedDict. Nodes never call each other directly — they just update state, and LangGraph passes it forward.

```
class AgentState(TypedDict):
    # Input
    account_id:          str
    issue_description:   str

    # After fetch_account_node
    account_details:     dict          # CRM data about the customer

    # After analyze_issue_node (LangChain writes these)
    issue_analysis:      str           # LLM's explanation of the issue
    action_reasoning:    str           # LLM's reasoning for chosen actions
    recommended_actions: list[str]     # e.g. ["create_sf_case", "call_billing_api"]
    sf_case_payload:     dict          # Salesforce case fields
    billing_payload:     dict          # Billing task fields

    # After execute_actions_node
    sf_case_result:      dict | None   # SF case ID and URL
    billing_result:      dict | None   # Transaction ID and billing task

    # After summarize_node
    final_summary:       str           # Human-readable outcome
    error:               str | None
```

---

## 4. LangChain Inside LangGraph — The Relationship Explained

This is the most important concept to understand. **LangGraph contains LangChain** — they operate at different layers.

```
┌─────────────────────────────────────────────────────────┐
│                     LangGraph                           │
│          (workflow engine — controls WHAT runs WHEN)    │
│                                                         │
│   ┌────────────┐    ┌──────────────────────────────┐   │
│   │   Node 1   │    │          Node 2               │   │
│   │fetch_account│──►│      analyze_issue            │   │
│   │            │    │                               │   │
│   │  (pure     │    │  ┌──────────────────────┐     │   │
│   │  Python,   │    │  │      LangChain        │     │   │
│   │  no AI)    │    │  │  (AI toolkit)          │     │   │
│   └────────────┘    │  │                       │     │   │
│                     │  │  ChatOpenAI.ainvoke()  │     │   │
│                     │  │  → calls GPT-4o-mini   │     │   │
│                     │  │  → returns JSON        │     │   │
│                     │  └──────────────────────┘     │   │
│                     └──────────────────────────────┘   │
│                                ↓                        │
│                     conditional routing                  │
│                         ↙       ↘                       │
│   ┌────────────┐   ┌──────────────────┐                 │
│   │   Node 4   │◄──│     Node 3       │                 │
│   │  summarize │   │ execute_actions  │                 │
│   │            │   │ (SF + billing)   │                 │
│   └────────────┘   └──────────────────┘                 │
└─────────────────────────────────────────────────────────┘
```

### Key Distinction

| Aspect | LangChain | LangGraph |
|---|---|---|
| **Job** | Call the LLM and get a response | Orchestrate the multi-step workflow |
| **Knows about workflow?** | No — it just processes a message | Yes — it manages all 4 nodes |
| **Knows about LangChain?** | N/A | No — nodes are plain Python functions |
| **Where used?** | Inside `analyze_issue_node` only | Across the entire workflow |
| **What it returns** | `response.content` — raw LLM text | `AgentState` — fully populated state dict |
| **Who calls it?** | `analyze_issue_node` (a LangGraph node) | FastAPI route via `agent_graph.ainvoke()` |

### The Execution Chain

```
FastAPI route
     │
     │  agent_graph.ainvoke(initial_state)
     ▼
LangGraph starts executing the compiled graph
     │
     ├──► Node 1: fetch_account_node(state)
     │         Pure Python. No AI. Just builds a dict of account info.
     │         Writes account_details into state.
     │
     ├──► Node 2: analyze_issue_node(state)
     │         Calls LangChain here ─────────────────────────────┐
     │              prompt = ANALYZE_ISSUE_PROMPT.format(...)     │
     │              msg = HumanMessage(content=prompt)            │
     │              response = await _llm.ainvoke([msg])          │ LangChain
     │              parsed = json.loads(response.content)         │ boundary
     │         ◄────────────────────────────────────────────────  ┘
     │         Writes recommended_actions, sf_case_payload,
     │         billing_payload, issue_analysis, action_reasoning
     │         into state and returns to LangGraph.
     │
     ├──► LangGraph reads state["recommended_actions"]
     │    If non-empty  → route to execute_actions_node
     │    If empty      → route directly to summarize_node
     │
     ├──► Node 3: execute_actions_node(state)   [if actions needed]
     │         Pure Python. Reads payloads from state.
     │         Calls create_sf_case() → external SF REST API
     │         Calls call_billing_api() → external Billing server
     │         Writes sf_case_result, billing_result into state.
     │
     └──► Node 4: summarize_node(state)
               Pure Python. Reads all state fields.
               Builds a human-readable final_summary string.
               LangGraph returns the completed state to FastAPI.
```

---

## 5. Architecture — Three-Tier Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                │
│                                                                     │
│   Web UI / Postman / curl                                           │
│                                                                     │
│   POST /api/v1/resolve-issue           (JSON response)              │
│   POST /api/v1/resolve-issue/stream    (SSE streaming)              │
│   POST /api/v1/billing-task            (direct billing, bypass AI)  │
│   GET  /api/v1/billing-tasks           (query billing tasks)        │
└────────────────────────┬────────────────────────────────────────────┘
                         │ HTTP
┌────────────────────────▼────────────────────────────────────────────┐
│                       API LAYER — FastAPI (port 8000)               │
│                                                                     │
│   routes.py                                                         │
│   ├── Validates request (Pydantic schemas)                          │
│   ├── Builds initial AgentState dict                                │
│   ├── Calls agent_graph.ainvoke() or agent_graph.astream_events()   │
│   └── Converts final state → IssueResponse JSON                    │
│                                                                     │
│   schemas.py                                                        │
│   ├── IssueRequest, IssueResponse                                   │
│   ├── BillingTask, BillingTaskRequest, BillingTaskResponse          │
└────────────────────────┬────────────────────────────────────────────┘
                         │ Python function call
┌────────────────────────▼────────────────────────────────────────────┐
│                  AGENT LAYER — LangGraph + LangChain                │
│                                                                     │
│   graph.py ─ StateGraph (compiled once, reused every request)       │
│                                                                     │
│   Node 1: fetch_account_node                                        │
│   └── Simulates CRM lookup → returns account_details dict          │
│                                                                     │
│   Node 2: analyze_issue_node  ◄── LangChain lives here             │
│   └── Builds prompt (account + issue + suggestions)                 │
│   └── ChatOpenAI.ainvoke() → GPT-4o-mini → JSON decision           │
│   └── Extracts: recommended_actions, sf_case_payload, billing_payload│
│                                                                     │
│   Conditional Router: _route_after_analysis()                       │
│   └── Reads recommended_actions from state                          │
│   └── Routes to execute_actions OR directly to summarize            │
│                                                                     │
│   Node 3: execute_actions_node                                      │
│   └── Reads sf_case_payload  → calls salesforce.create_sf_case()   │
│   └── Reads billing_payload  → calls billing.call_billing_api()     │
│                                                                     │
│   Node 4: summarize_node                                            │
│   └── Builds final_summary string from all state fields             │
│                                                                     │
│   prompts.py ─ ANALYZE_ISSUE_PROMPT with {account_id},             │
│               {account_details}, {issue_description}, {suggestions} │
│                                                                     │
│   state.py   ─ AgentState TypedDict (shared across all nodes)       │
└──────────────┬─────────────────────────────┬───────────────────────┘
               │ HTTPS                        │ HTTP POST
┌──────────────▼──────────┐   ┌──────────────▼──────────────────────┐
│  Salesforce REST API     │   │  Billing Microservice (port 9000)   │
│  (OAuth2 Client Creds)   │   │  POST /api/v1/billing/tasks         │
│  POST /sobjects/Case     │   │  Returns task receipt + tx ID        │
│  Returns Case ID + URL   │   │  Logs to billing_tasks_log.json     │
└─────────────────────────┘   └─────────────────────────────────────┘
```

---

## 6. LangGraph Workflow — Node-by-Node Walkthrough

### Graph Topology

```
START
  │
  ▼
┌─────────────────────┐
│  fetch_account_node  │
│  ─────────────────  │   Input : account_id (from request)
│  Tech: pure Python   │   Output: account_details{} written to state
│  AI:   NO            │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  analyze_issue_node  │
│  ─────────────────  │   Input : account_details + issue_description
│  Tech: LangChain     │            + suggestions.txt content
│  AI:   YES ← GPT-4o │   Output: recommended_actions[], sf_case_payload{},
└──────────┬──────────┘            billing_payload{}, issue_analysis, reasoning
           │
           ▼  (LangGraph reads state["recommended_actions"])
     ╔═════╧═════╗
     ║  ROUTER   ║
     ╚═════╤═════╝
      ┌────┴───────────────────────┐
      │ non-empty                  │ empty list []
      ▼                            ▼
┌─────────────────────┐           ╔══════════════════════╗
│ execute_actions_node │           ║  (jump to summarize) ║
│  ─────────────────  │           ╚══════════════════════╝
│  Tech: pure Python   │   Input : sf_case_payload, billing_payload
│  AI:   NO            │   Output: sf_case_result{}, billing_result{}
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   summarize_node     │
│  ─────────────────  │   Input : entire state (all fields)
│  Tech: pure Python   │   Output: final_summary string
│  AI:   NO            │
└──────────┬──────────┘
           │
           ▼
          END
```

### Node Details

#### Node 1 — fetch_account_node
- **What it does:** Simulates a CRM database lookup to get account information
- **In production:** Replace the mock dict with an actual SQL query or CRM API call
- **Why it exists:** The LLM needs account context (plan, balance, payment history) to make an intelligent decision. Without it, the LLM would only have the issue description — which isn't enough.
- **LangChain used:** No

#### Node 2 — analyze_issue_node ← This is where LangChain runs
- **What it does:** Combines account data, the issue description, and business suggestions into a structured prompt, sends it to GPT-4o-mini, and parses the response
- **The prompt (`ANALYZE_ISSUE_PROMPT`) contains:**
  - Account context (ID, plan, balance, payment history)
  - Issue description (verbatim from the customer)
  - Business suggestions from `suggestions.txt` (acts as a knowledge base)
  - Available system actions (create_sf_case, call_billing_api) with `Use when:` rules
  - Decision rules (explicit per-suggestion mapping)
  - Output format (strict JSON schema)
- **What the LLM outputs:** JSON with `recommended_actions`, `sf_case_payload`, `billing_payload`, analysis, and reasoning
- **LangChain used:** Yes — `ChatOpenAI.ainvoke([HumanMessage(content=prompt)])`

#### Node 3 — execute_actions_node
- **What it does:** Reads the LLM's chosen actions and payloads from state, then actually executes them against real external systems
- **Salesforce path:** Calls `create_sf_case(state["sf_case_payload"])` → authenticates via OAuth2 → POSTs to Salesforce REST API → returns Case ID and URL
- **Billing path:** Calls `call_billing_api(state["billing_payload"])` → builds enriched task document → POSTs to billing server at `BILLING_API_URL` → returns transaction ID
- **LangChain used:** No

#### Node 4 — summarize_node
- **What it does:** Collects all results from state and builds a human-readable summary string
- **Output example:** `"SF Case: 5001Q000008abcAAA (High) | Billing Action: refund | Tx: TXN-abc123-... | Amount: $150.00 USD | Reason: DUPLICATE_CHARGE"`
- **LangChain used:** No

---

## 7. Full Data Flow — Step-by-Step Trace

**Example request:** Account `ACC-1005`, Issue: `"I was double-charged $150 this month"`

```
[1] CLIENT sends HTTP POST
────────────────────────────────────────────────────────────────────
POST /api/v1/resolve-issue
{
  "account_id": "ACC-1005",
  "issue_description": "I was double-charged $150 this month"
}

[2] FastAPI validates and builds initial state
────────────────────────────────────────────────────────────────────
AgentState = {
  "account_id":          "ACC-1005",
  "issue_description":   "I was double-charged $150 this month",
  "account_details":     {},           ← empty, filled by Node 1
  "recommended_actions": [],           ← empty, filled by Node 2
  "sf_case_payload":     {},
  "billing_payload":     {},
  ...
}

[3] LangGraph starts: Node 1 — fetch_account_node runs
────────────────────────────────────────────────────────────────────
Reads:  state["account_id"] = "ACC-1005"
Writes: state["account_details"] = {
          "name": "Customer_ACC-1005",
          "email": "customer_acc-1005@example.com",
          "plan": "Premium",
          "status": "Active",
          "billing_cycle": "Monthly",
          "last_payment_amount": 99.00,
          ...
        }

[4] LangGraph: Node 2 — analyze_issue_node runs
────────────────────────────────────────────────────────────────────
Step 4a. Load suggestions.txt (YAML file):
  suggestions.txt contains:
  ┌────────────────────────────────────────────────────────────┐
  │ suggestion_1:                                              │
  │   title: "Check customer details"                         │
  │   description: "Verify account information and history"   │
  │ suggestion_2:                                             │
  │   title: "Rebill the account"                             │
  │   description: "Reprocess billing or apply adjustments"   │
  │ suggestion_3:                                             │
  │   title: "Close the case"                                 │
  │   description: "Mark the issue as resolved"               │
  └────────────────────────────────────────────────────────────┘

Step 4b. Build prompt by substituting placeholders:
  ANALYZE_ISSUE_PROMPT.format(
    account_id       = "ACC-1005",
    account_details  = "{ plan: Premium, last_payment: 99.00, ... }",
    issue_description= "I was double-charged $150 this month",
    suggestions      = "• Check customer details: ...\n• Rebill the account: ..."
  )

Step 4c. LangChain wraps prompt and calls OpenAI:
  ┌──────────────────────────────────────────────────────────┐
  │  LangChain boundary                                      │
  │                                                          │
  │  msg = HumanMessage(content=prompt)   ← format for GPT  │
  │  response = await _llm.ainvoke([msg]) ← HTTP to OpenAI  │
  │  content = response.content           ← raw JSON text    │
  └──────────────────────────────────────────────────────────┘

Step 4d. GPT-4o-mini returns JSON (because DECISION RULES matched
         "Rebill the account" for a double-charge):
  {
    "analysis":    "Customer ACC-1005 reports being charged $150
                   twice this month. Account is Premium with $99/mo plan.",
    "reasoning":   "Suggestion 'Rebill the account' matches — a financial
                   correction (refund) is needed. Suggestion 'Close the case'
                   also applies — a SF case should track the resolution.",
    "recommended_actions": ["create_sf_case", "call_billing_api"],
    "sf_case_payload": {
      "subject":    "Double charge – $150 – ACC-1005",
      "description":"Customer charged twice. Refund of $150 initiated.",
      "priority":   "High",
      "status":     "New",
      "origin":     "Web",
      "account_id": "ACC-1005"
    },
    "billing_payload": {
      "account_id":  "ACC-1005",
      "action_type": "refund",
      "amount":      150.00,
      "currency":    "USD",
      "reason":      "DUPLICATE_CHARGE",
      "notes":       "Customer ACC-1005 (Premium) double-charged $150."
    }
  }

Step 4e. Node writes back to state:
  state["recommended_actions"] = ["create_sf_case", "call_billing_api"]
  state["sf_case_payload"]     = { subject: "Double charge...", ... }
  state["billing_payload"]     = { action_type: "refund", amount: 150.0, ... }
  state["issue_analysis"]      = "Customer ACC-1005 reports being charged..."
  state["action_reasoning"]    = "Suggestion 'Rebill the account' matches..."

[5] LangGraph conditional router runs
────────────────────────────────────────────────────────────────────
_route_after_analysis(state):
  state["recommended_actions"] = ["create_sf_case", "call_billing_api"]  ← non-empty
  → returns "execute_actions"  → LangGraph routes to Node 3

[6] LangGraph: Node 3 — execute_actions_node runs
────────────────────────────────────────────────────────────────────
Action A — Salesforce case:
  create_sf_case(state["sf_case_payload"])
  → GET Salesforce OAuth2 token (client_credentials)
  → POST https://yourorg.salesforce.com/services/data/v59.0/sobjects/Case
     body: { Subject: "Double charge...", Priority: "High", ... }
  ← Response: { id: "5001Q000008abcAAA", success: true }
  state["sf_case_result"] = {
    "success": true,
    "case_id": "5001Q000008abcAAA",
    "case_url": "https://yourorg.salesforce.com/.../5001Q000008abcAAA"
  }

Action B — Billing API:
  call_billing_api(state["billing_payload"])
  → _build_task_payload() creates enriched task document:
     {
       "transaction_id": "TXN-a3b4c5d6-...",
       "account_id":     "ACC-1005",
       "action_type":    "refund",
       "amount":         150.00,
       "currency":       "USD",
       "reason":         "DUPLICATE_CHARGE",
       "change_suggested": "Customer ACC-1005 (Premium) double-charged $150.",
       "initiated_by":   "agent",
       "created_at":     "2026-05-01T10:30:00Z",
       "status":         "pending"
     }
  → POST http://localhost:9000/api/v1/billing/tasks
  ← Response: { transaction_id: "TXN-a3b4c5d6-...", status: "received" }
  state["billing_result"] = { success: true, billing_task: { ... } }

[7] LangGraph: Node 4 — summarize_node runs
────────────────────────────────────────────────────────────────────
Reads sf_case_result, billing_result from state.
Builds:
  "SF Case: 5001Q000008abcAAA (High) | Billing Action: refund |
   Tx: TXN-a3b4c5d6-... | Amount: $150.00 USD | Reason: DUPLICATE_CHARGE"
state["final_summary"] = above string

[8] LangGraph returns completed state to FastAPI
────────────────────────────────────────────────────────────────────

[9] FastAPI converts state → IssueResponse and returns HTTP 200
────────────────────────────────────────────────────────────────────
{
  "account_id": "ACC-1005",
  "issue_description": "I was double-charged $150 this month",
  "issue_analysis": "Customer ACC-1005 reports being charged $150 twice...",
  "action_reasoning": "Suggestion 'Rebill the account' matches...",
  "recommended_actions": ["create_sf_case", "call_billing_api"],
  "actions_executed": ["create_sf_case", "call_billing_api"],
  "sf_case_result": {
    "success": true,
    "case_id": "5001Q000008abcAAA",
    "case_url": "https://yourorg.salesforce.com/.../5001Q000008abcAAA"
  },
  "billing_result": {
    "success": true,
    "message": "Billing task created",
    "billing_task": {
      "transaction_id": "TXN-a3b4c5d6-...",
      "action_type": "refund",
      "amount": 150.00,
      "currency": "USD",
      "reason": "DUPLICATE_CHARGE"
    }
  },
  "final_summary": "SF Case: 5001Q000008abcAAA (High) | Billing Action: refund | ...",
  "error": null
}
```

---

## 8. Component Responsibility Table

| Component | File | What It Owns | What It Does NOT Own |
|---|---|---|---|
| `AgentState` | `agent/state.py` | Shared data schema across all nodes | Execution logic |
| `ANALYZE_ISSUE_PROMPT` | `agent/prompts.py` | Prompt text, decision rules, output format | LLM calls, routing |
| `fetch_account_node` | `agent/nodes.py` | CRM data retrieval | AI decisions |
| `analyze_issue_node` | `agent/nodes.py` | **LangChain call + prompt assembly + JSON parse** | Workflow routing |
| `execute_actions_node` | `agent/nodes.py` | Calling SF and billing external APIs | Deciding which actions |
| `summarize_node` | `agent/nodes.py` | Building human-readable summary | Any side effects |
| `graph.py` | `agent/graph.py` | Node wiring, edges, conditional routing | Node logic |
| `ChatOpenAI` | LangChain library | LLM API communication, model config | Graph structure |
| `HumanMessage` | LangChain library | Chat-format prompt wrapping | Business logic |
| `StateGraph` | LangGraph library | Graph compile, execution, streaming | AI model calls |
| `salesforce.py` | `services/salesforce.py` | OAuth2 auth + SF REST Case API | Agent logic |
| `billing.py` | `services/billing.py` | Task payload assembly + HTTP POST + in-memory store | Agent logic |
| `routes.py` | `api/routes.py` | HTTP endpoints, request validation, SSE streaming | Agent internals |
| `schemas.py` | `api/schemas.py` | Pydantic models for API contracts | Business processing |
| `suggestions.txt` | root | Business knowledge base (YAML) | Code/logic |

---

## 9. API Endpoints Reference

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/resolve-issue` | Run full agent, return complete JSON response |
| `POST` | `/api/v1/resolve-issue/stream` | Run full agent, stream progress as Server-Sent Events |
| `POST` | `/api/v1/billing-task` | Directly create a billing task (bypass agent, for UI use) |
| `GET` | `/api/v1/billing-tasks` | List all billing tasks created this session |
| `GET` | `/api/v1/billing-tasks/{transaction_id}` | Get one billing task by transaction ID |
| `GET` | `/api/v1/actions` | List supported action types |
| `GET` | `/docs` | Interactive Swagger UI (auto-generated by FastAPI) |

### Streaming Endpoint — how SSE works

```
Client connects to POST /api/v1/resolve-issue/stream

LangGraph emits events via astream_events(version="v2"):

  event: node_start    → {"node": "fetch_account", "status": "started"}
  event: node_start    → {"node": "analyze_issue",  "status": "started"}
  event: node_complete → {"node": "analyze_issue",  "recommended_actions": [...]}
  event: node_start    → {"node": "execute_actions","status": "started"}
  event: node_complete → {"node": "execute_actions","actions_executed": [...]}
  event: node_complete → {"node": "summarize",      "final_summary": "..."}
  event: complete      → full final JSON (IssueResponse)

Client (UI) can render progress in real time as each node completes.
```

---

*Generated: May 2026 | Stack: FastAPI + LangChain `ChatOpenAI` + LangGraph `StateGraph` + GPT-4o-mini + Salesforce REST + Billing HTTP*
