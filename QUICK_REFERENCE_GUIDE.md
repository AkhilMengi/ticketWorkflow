# TicketWorkflow - Architecture Quick Reference

**One-page summary of all core elements and workflows**

---

## 🎯 What is TicketWorkflow?

An **intelligent request routing engine** that:
- Routes customer requests to **Salesforce** (support), **Billing** (payments), or **Manual Review**
- Uses **LangGraph** state machines for orchestration (not LangChain)
- Executes **multi-action intelligent workflows** (primary + secondary + tertiary actions)
- Maintains **100% audit trail** with confidence scores and decision logs
- Processes requests **asynchronously** with worker threads

---

## 🏗️ Core Architecture (4 Layers)

```
┌───────────────────────────────────────┐
│  LAYER 1: API                         │
│  FastAPI endpoints (POST /request)    │
└───────────────────────────────────────┘
           ↓
┌───────────────────────────────────────┐
│  LAYER 2: QUEUE                       │
│  Job Service + SQLite (async queue)   │
└───────────────────────────────────────┘
           ↓
┌───────────────────────────────────────┐
│  LAYER 3: WORKERS                     │
│  Thread pool (async execution)        │
└───────────────────────────────────────┘
           ↓
┌───────────────────────────────────────┐
│  LAYER 4: LANGGRAPH                   │
│  State machine orchestration          │
└───────────────────────────────────────┘
           ↓
┌───────────────────────────────────────┐
│  LAYER 5: ADAPTERS                    │
│  SF + Billing + DB integration        │
└───────────────────────────────────────┘
```

---

## 📊 Why LangGraph (Not LangChain)?

| Feature | LangChain | LangGraph | TicketWorkflow |
|---------|-----------|-----------|----------------|
| State Management | Hidden | Explicit TypedDict | ✅ Central state |
| Routing | Sequential | Conditional edges | ✅ Classification-driven |
| Debugging | Difficult | Clear node paths | ✅ Full visibility |
| Dependencies | Heavy | Minimal | ✅ Only FastAPI + OpenAI |
| Testing | Hard | Easy per-node | ✅ Testable units |

**Decision**: Use LangGraph because it's a **state machine** (perfect for conditional routing), not a **chain** (sequential execution).

---

## 🔄 Three Workflow Types

### Workflow 1: Simple Routing
```
Request → Classify → Route to SF/Billing → Execute → Return
Suitable for: Clear-cut issues (bugs, billing)
Speed: ~2-3 seconds
```

### Workflow 2: Intelligent Routing (Recommended)
```
Request → Enrich (profile, logs) → Classify → Parse AI Suggestions
  → Map to Actions (Primary + Secondary + Tertiary) → Execute Multi-Action
Suitable for: Complex issues
Speed: ~4-5 seconds
Result: 3 coordinated actions executed
```

### Workflow 3: Contract Generation
```
Request → Validate (dates, fields) → Prepare → Create → Summarize
Suitable for: Automated contract generation
Speed: ~1-2 seconds
Result: contract_id + PDF
```

---

## 🔌 Core Components Map

```
┌─────────────────────────────────────────────────────────┐
│                   REQUEST FLOW                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. FastAPI receives POST /api/request                 │
│  2. Job Service creates record + queues               │
│  3. Worker picks up from queue                        │
│  4. Invoke Routing Graph (LangGraph)                  │
│  5. enrichment_node                                   │
│     ├─ fetch_profile (Customer data)                 │
│     └─ fetch_logs (Issue history)                    │
│  6. routing_node (Classify issue)                     │
│     └─ If SF/Billing/Manual?                         │
│  7. Execute branch (3 routes):                        │
│     ├─ sf_execution_node                             │
│     ├─ billing_execution_node                        │
│     └─ intelligent_action_routing_node (Recommended) │
│  8. Aggregation node (Combine results)               │
│  9. Update Job record with results                   │
│  10. Client polls GET /api/results/{job_id}          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 🎯 Data Flow Summary

```
ENRICHED STATE EXAMPLE:
{
  "user_id": "customer_001",
  "issue_type": "billing",
  "message": "Double charged",
  "context": {...},
  
  ↓ After enrichment:
  "customer_profile": {...},
  "issue_logs": [...],
  
  ↓ After classification:
  "classification": "billing",
  "confidence": 0.96,
  
  ↓ After intelligent routing:
  "primary_action": {
    "type": "PROCESS_REFUND",
    "result": {"refund_id": "ref_123"},
    "confidence": 0.96
  },
  "secondary_action": {...},
  "tertiary_action": {...},
  
  ↓ Final result:
  "status": "resolved",
  "audit_trail": [...]
}
```

---

## 🛠️ Service Adapter Pattern

**Purpose**: Decouple business logic from system integration

```
Action Request → Adapter Router → SalesforceAdapter or BillingAdapter
                                          ↓
                                  Execute on external system
                                          ↓
                                    Return result

Supported Actions:
- Salesforce: CREATE_CASE, UPDATE_CASE, ADD_COMMENT, CLOSE_CASE
- Billing: PROCESS_REFUND, APPLY_CREDIT, UPDATE_ACCOUNT
```

---

## 🤖 Intelligent Action Service

**How it works:**
```
Customer Issue
    ↓
Parse suggestions.txt (generic business suggestions)
    ├─ "Check customer details"
    ├─ "Rebill the account"
    ├─ "Escalate to team"
    └─ ...
    ↓
Send to OpenAI GPT-4 with issue + context
    ↓
LLM analyzes: "This suggestion means CREATE_CASE for SF"
    ↓
Map to specific action with confidence score
    ↓
Execute action via adapter
    ↓
Repeat for secondary + tertiary actions
```

---

## 📋 State Management (TypedDict)

```python
class EnhancedAgentState(TypedDict):
    # Input
    user_id: str
    issue_type: str
    message: str
    context: Dict[str, Any]
    
    # Enrichment results
    customer_profile: Dict
    issue_logs: List
    
    # Classification results
    classification: str
    confidence: float
    classification_reason: str
    
    # Execution results
    primary_action: Dict
    secondary_action: Dict
    tertiary_action: Dict
    
    # Control flow
    next_action: str
    status: str
    
    # Audit trail
    decisions: List[str]
    actions_executed: List[Dict]
    execution_time: float
```

---

## 🔍 LangGraph Building Blocks

### Node
```
A function that reads state, does work, updates state
- decide_node: Analyze request type
- fetch_profile_node: Enrich customer data
- routing_node: Classify issue
- sf_execution_node: Execute Salesforce action
- aggregation_node: Combine all results
```

### Conditional Edge
```
Router function that determines next node based on state
if state["classification"] == "sf":
    return "sf_execution"
elif state["classification"] == "billing":
    return "billing_execution"
else:
    return "manual_review"
```

### State
```
TypedDict that flows through graph
Every node reads entire state
Every node returns updated state
Nodes are atomic + deterministic
```

---

## ⏱️ Request Timeline

```
0ms      - Request arrives at FastAPI
10ms     - Schema validation
50ms     - Job created in DB
100ms    - Queued to worker
150ms    - Worker picks up
300ms    - Fetch customer profile
500ms    - Fetch issue logs
1000ms   - Send to classifier
2000ms   - Receive classification
2100ms   - Route to executor
3000ms   - Execute primary action
3500ms   - Execute secondary action
4000ms   - Execute tertiary action
4200ms   - Aggregate results
4300ms   - Update job DB
─────────
4.3s     - Total async time (API returns in <100ms)
```

---

## 📚 File Structure

```
app/
├── main.py                 ← FastAPI entry point
│
├── api/
│   ├── routes.py          ← HTTP endpoints
│   └── schemas.py         ← Pydantic models
│
├── agent/
│   ├── routing_graph.py    ← Main LangGraph (Routing)
│   ├── routing_state.py    ← State definition
│   ├── routing_nodes.py    ← Node implementations
│   ├── contract_graph.py   ← Secondary graph (Contracts)
│   ├── contract_nodes.py   ← Contract node implementations
│   ├── adapters.py         ← Service adapter pattern
│   ├── tools.py            ← Action executors
│   └── prompts.py          ← AI prompts
│
├── services/
│   ├── job_service.py      ← Job queue management
│   └── intelligent_action_service.py
│
├── workers/
│   └── worker.py           ← Worker thread pool
│
├── integrations/
│   ├── salesforce.py       ← SF API client
│   ├── db.py               ← Database queries
│   └── billing.py          ← Billing system
│
└── config.py               ← Configuration
```

---

## 🚀 Key Advantages

| Advantage | Benefit |
|-----------|---------|
| **State-Driven** | Every decision visible in state |
| **Conditional Routing** | Smart classification → correct system |
| **Multi-Action** | 2-3 coordinated actions per request |
| **Auditable** | 100% decision trail with confidence |
| **Scalable** | Workers handle parallel requests |
| **Async** | Non-blocking API responses |
| **Extensible** | New workflows = new graphs |
| **Testable** | Each node independently verifiable |

---

## 💡 Decision Logic (Classification)

```
If issue has payment/billing keywords:
  Class = BILLING
  Confidence = 0.90-0.98
  Route to: BillingAdapter

Else if issue is technical/support:
  Class = SALESFORCE
  Confidence = 0.85-0.95
  Route to: SalesforceAdapter

Else if low confidence / ambiguous:
  Class = MANUAL_REVIEW
  Confidence = <0.70
  Route to: Manual team
  
All decisions include confidence score
All decisions logged for audit
```

---

## 📊 Example Execution

**INPUT:**
```json
{
  "user_id": "cust_123",
  "issue_type": "billing",
  "message": "Charged twice on my account",
  "context": {"amount": 99.99}
}
```

**WORKFLOW:**
```
1. ✅ Enriched: Got customer history + recent charges
2. ✅ Classified: BILLING (confidence: 0.96)
3. ✅ Intelligent routing triggered
4. ✅ AI suggestions parsed:
     - PRIMARY: Refund $99.99 (PROCESS_REFUND)
     - SECONDARY: Verify account (UPDATE_ACCOUNT)
     - TERTIARY: Create case (CREATE_CASE in SF for audit)
5. ✅ Executed 3 actions successfully
```

**OUTPUT:**
```json
{
  "status": "resolved",
  "routed_to": "billing",
  "primary_result": {
    "type": "refund",
    "refund_id": "ref_xyz123",
    "amount": 99.99
  },
  "confidence": 0.96,
  "audit_trail": [...]
}
```

---

## 🔗 Key Connections

| Component | Purpose | Technology |
|-----------|---------|-----------|
| **API Layer** | HTTP entry point | FastAPI |
| **Job Queue** | Async management | SQLite + Python queue |
| **Worker Pool** | Execution threads | Python threading |
| **LangGraph** | Workflow orchestration | LangGraph |
| **Classification** | Route intelligence | OpenAI GPT-4 |
| **Adapters** | System integration | Abstract Base Classes |
| **State** | Central flow data | TypedDict |
| **Audit** | Decision logging | Python logging |

---

## ✨ Next Steps

To extend the system:

1. **Add new workflow**: Create new graph in `agent/` folder
2. **Add new system**: Create new adapter in `adapters.py`
3. **Add new action**: Define in `ActionType` enum, implement in adapter
4. **Modify classification**: Update LLM prompt in `routing_nodes.py`
5. **Change routing logic**: Update conditional edges in graph building

All changes maintain the same architectural pattern.

