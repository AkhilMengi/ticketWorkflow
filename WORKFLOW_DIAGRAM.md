# Agentic Issue Resolution — Detailed Workflow Diagrams

## 1. High-Level Request Flow

```
┌─────────────────────┐
│  Client Request     │
│                     │
│ POST /resolve-     │
│ issue              │
│ {account_id,       │
│  issue_desc}       │
└──────────┬──────────┘
           │
           ▼
   ┌───────────────┐
   │ API Validation│
   │ (Pydantic)    │
   └───────┬───────┘
           │
           ▼
   ┌──────────────────────┐
   │ Initialize            │
   │ AgentState            │
   │ + AgentTrace          │
   └───────┬───────────────┘
           │
           ▼
   ┌──────────────────────────────────────┐
   │  LangGraph Agent Execution           │
   │  (Described in detail below)          │
   └───────┬──────────────────────────────┘
           │
           ▼
   ┌──────────────────────┐
   │ Serialize Response    │
   │ (IssueResponse)       │
   └───────┬───────────────┘
           │
           ▼
┌─────────────────────────┐
│ Return to Client        │
│ 200 OK + JSON Response  │
│ or                      │
│ 500 Error               │
└─────────────────────────┘
```

---

## 2. LangGraph Agent State Machine

```
                          START
                           │
                           ▼
                ┌──────────────────────┐
                │  fetch_account_node   │
                │                      │
                │ Input: account_id    │
                │ Output: account_     │
                │         details      │
                │                      │
                │ Action:              │
                │ • Load from DB/CRM   │
                │ • Mock: realistic    │
                │   customer data      │
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────────────────┐
                │   analyze_issue_node              │
                │                                  │
                │ Input: account_details,          │
                │        issue_description        │
                │                                  │
                │ Output: issue_analysis,          │
                │         action_reasoning,       │
                │         confidence_score,       │
                │         recommended_actions,    │
                │         [payloads...]           │
                │                                  │
                │ Action: Call GPT-4o-mini         │
                │         with structured prompt  │
                │         and business rules      │
                └──────────┬───────────────────────┘
                           │
                ┌──────────┴──────────┐
                │                     │
         ┌──────┴─────┐        ┌────┴──────┐
         │ CAS <= 5?  │        │ >= 5?     │
         │ no actions │        │ + actions │
         └──────┬──────┘        └────────┬─┘
                │                        │
    ╔═══════════╩════════════════════════╩════════╗
    ║ CRITICAL GATE: Confidence Score    │         ║
    ║ • If confidence < 5:               │         ║
    ║   Skip to summarize               │         ║
    ║ • If confidence >= 5 & actions: │         ║
    ║   Execute them                  │         ║
    ║ • If confidence >= 5 & no actions:│        ║
    ║   Skip to summarize             │         ║
    ╚═══════════╤════════════════════════╤════════╝
                │                        │
                │                        │
           [No actions]           [Has actions &
            OR                      confidence >=5]
           [Cannot                      │
            understand]                 ▼
                │          ┌──────────────────────────┐
                │          │ execute_actions_node    │
                │          │                         │
                │          │ For each action in      │
                │          │ recommended_actions:    │
                │          │                         │
                │          │ ├─ "create_sf_case"     │
                │          │ │  └─ call SF REST API  │
                │          │ │     → sf_case_result  │
                │          │ │                       │
                │          │ └─ "call_billing_api"   │
                │          │    └─ call Billing API  │
                │          │       → billing_result  │
                │          │                         │
                │          │ Output: actions_executed│
                │          └────────┬────────────────┘
                │                   │
                └───────────┬───────┘
                            │
                            ▼
                ┌──────────────────────────────────┐
                │    summarize_node                │
                │                                  │
                │ Input: state (from previous      │
                │        nodes)                    │
                │                                  │
                │ Output: final_summary (string)   │
                │         error (if any)           │
                │                                  │
                │ Action:                          │
                │ • If couldn't understand:        │
                │   "I am not able to understand"  │
                │ • Else: Compile action results   │
                │         into human-readable      │
                │         response                 │
                └──────────┬───────────────────────┘
                           │
                           ▼
                          END
                           │
                           ▼
                  ┌─────────────────────┐
                  │ State returned to    │
                  │ API layer            │
                  │ (serialized as JSON) │
                  └─────────────────────┘
```

---

## 3. Conditional Routing Logic

```
┌────────────────────────────────────────────────────────────┐
│ _route_after_analysis(state: AgentState) → str             │
│                                                             │
│ Decision logic after LLM analysis:                          │
└────────────────────────────────────────────────────────────┘
                         │
                         ▼
         ┌───────────────────────────────┐
         │ Check: can_understand_issue?  │
         └───────┬─────────────────┬─────┘
                 │                 │
              FALSE             TRUE
                 │                 │
                 │                 ▼
                 │      ┌────────────────────────────┐
                 │      │ Check: any recommended_    │
                 │      │        actions?            │
                 │      └────┬──────────────┬────────┘
                 │           │              │
                 │         TRUE           FALSE
                 │           │              │
                 │ ┌─────────┘              │
                 │ │                        │
                 ▼ ▼                        ▼
         ┌──────────────────┐     ┌──────────────────┐
         │ ROUTE TO:        │     │ ROUTE TO:        │
         │ execute_actions  │     │ summarize        │
         │                  │     │                  │
         │ Will:            │     │ Will:            │
         │ • Call SF API    │     │ • Compile final  │
         │ • Call Billing   │     │   response       │
         │   API            │     │ • No API calls   │
         │ • Then go to     │     │ • Return summary │
         │   summarize      │     │                  │
         └──────────────────┘     └──────────────────┘
```

---

## 4. Detailed Node Operations

### 4.1 fetch_account_node

```
╔════════════════════════════════════════════════════╗
║         FETCH_ACCOUNT_NODE                         ║
╚════════════════════════════════════════════════════╝

INPUT
─────
AgentState.account_id = "ACC-1001"

PROCESSING
──────────
┌────────────────────────────────────┐
│ 1. Extract account_id from state   │
└─────────────┬──────────────────────┘
              │
              ▼
┌────────────────────────────────────┐
│ 2. Log: "Fetching account for..."  │
└─────────────┬──────────────────────┘
              │
              ▼
┌────────────────────────────────────────────────┐
│ 3. Mock DB lookup (replace with real call):    │
│    {                                           │
│      "account_id": "ACC-1001",                 │
│      "name": "Customer_1001",                  │
│      "email": "customer_1001@example.com",     │
│      "plan": "Premium",                        │
│      "status": "Active",                       │
│      "billing_cycle": "Monthly",               │
│      "outstanding_balance": 0.00,              │
│      "last_payment_date": "2026-04-01",        │
│      "last_payment_amount": 99.00              │
│    }                                           │
└─────────────┬──────────────────────────────────┘
              │
OUTPUT
──────
AgentState updated:
  account_details = {account data}

NEXT NODE
─────────
analyze_issue_node
```

### 4.2 analyze_issue_node

```
╔════════════════════════════════════════════════════════════╗
║         ANALYZE_ISSUE_NODE                                 ║
║  (The intelligence center — calls LLM)                    ║
╚════════════════════════════════════════════════════════════╝

INPUT
─────
AgentState:
  • account_id
  • issue_description
  • account_details

PROCESSING
──────────
┌──────────────────────────────────┐
│ 1. Load business suggestions     │
│    from suggestions.txt          │
│    (YAML format)                 │
└─────────────┬────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────┐
│ 2. Construct structured LLM prompt with:            │
│    • Account context (details)                      │
│    • Issue description (customer complaint)         │
│    • Business suggestions (knowledge base)          │
│    • Available actions explanation                  │
│    • Confidence scoring guidelines (0-10)           │
│    • Decision rules (when to take action)           │
│    • CRITICAL RULE: "If confidence < 5:             │
│                     Return empty actions"           │
└─────────────┬──────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────┐
│ 3. Call OpenAI GPT-4o-mini API                      │
│    Model: gpt-4o-mini                               │
│    Temperature: 0 (deterministic)                   │
│    Response format: JSON                            │
└─────────────┬──────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────┐
│ 4. Parse LLM Response JSON:                         │
│    {                                                │
│      "issue_analysis": "...",                       │
│      "action_reasoning": "...",                     │
│      "confidence_score": 8,                         │
│      "recommended_actions": [                       │
│        "create_sf_case",                            │
│        "call_billing_api"                           │
│      ],                                             │
│      "sf_case_payload": {                           │
│        "subject": "Duplicate charge...",            │
│        "description": "...",                        │
│        "priority": "High",                          │
│        "status": "New"                              │
│      },                                             │
│      "billing_payload": {                           │
│        "account_id": "ACC-1001",                    │
│        "action_type": "refund",                     │
│        "amount": 99.0,                              │
│        "reason": "DUPLICATE_CHARGE",                │
│        "notes": "..."                               │
│      }                                              │
│    }                                                │
└─────────────┬──────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────┐
│ 5. Validate confidence_score                        │
│    • If < 5: Set can_understand_issue = False       │
│    • If >= 5: Set can_understand_issue = True       │
└─────────────┬──────────────────────────────────────┘
              │
OUTPUT
──────
AgentState updated:
  • issue_analysis
  • action_reasoning  
  • confidence_score (0-10)
  • can_understand_issue (Boolean)
  • recommended_actions (List[str])
  • sf_case_payload (Dict)
  • billing_payload (Dict)

CONDITIONAL ROUTING
───────────────────
_route_after_analysis() determines next node:
  ├─ If can_understand_issue = False
  │  └─> SUMMARIZE (error response)
  ├─ Else if recommended_actions is empty
  │  └─> SUMMARIZE (no actions needed)
  └─ Else
     └─> EXECUTE_ACTIONS
```

### 4.3 execute_actions_node

```
╔════════════════════════════════════════════════════════════╗
║         EXECUTE_ACTIONS_NODE                              ║
║  (Calls external APIs based on LLM decisions)             ║
╚════════════════════════════════════════════════════════════╝

INPUT
─────
AgentState:
  • recommended_actions (List[str])
  • sf_case_payload (Dict)
  • billing_payload (Dict)

PROCESSING
──────────
For each action in recommended_actions:

┌──────────────────────────────────────────────────┐
│ ACTION 1: "create_sf_case"                       │
├──────────────────────────────────────────────────┤
│ IF action in recommended_actions:                │
│  └─ Call salesforce.create_sf_case()             │
│                                                  │
│  ┌──────────────────────────────────────┐        │
│  │ SF Service Flow:                     │        │
│  │ 1. Check if MOCK_SALESFORCE = true   │        │
│  │    ├─ Yes: Return mock response      │        │
│  │    └─ No: Continue to real API       │        │
│  │                                      │        │
│  │ 2. OAuth 2.0 auth:                   │        │
│  │    POST /services/oauth2/token       │        │
│  │    with client_id + client_secret    │        │
│  │    → Get access_token                │        │
│  │                                      │        │
│  │ 3. Create case:                      │        │
│  │    POST /services/data/v59.0/        │        │
│  │         sobjects/Case                │        │
│  │    Headers: {Authorization: Bearer}  │        │
│  │    Body: {Subject, Description,      │        │
│  │           Priority, Status, Origin}  │        │
│  │                                      │        │
│  │ 4. Return result:                    │        │
│  │    {                                 │        │
│  │      "success": true,                │        │
│  │      "id": "5001a...",               │        │
│  │      "case_number": "00001001"       │        │
│  │    }                                 │        │
│  └──────────────────────────────────────┘        │
│                                                  │
│  Update: sf_case_result = result                │
│  Add to: actions_executed                       │
└──────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────┐
│ ACTION 2: "call_billing_api"                     │
├──────────────────────────────────────────────────┤
│ IF action in recommended_actions:                │
│  └─ Call billing.call_billing_api()              │
│                                                  │
│  ┌──────────────────────────────────────┐        │
│  │ Billing Service Flow:                │        │
│  │ 1. Check if MOCK_BILLING = true      │        │
│  │    ├─ Yes: Return mock response      │        │
│  │    └─ No: Continue to real API       │        │
│  │                                      │        │
│  │ 2. Build BillingTask:                │        │
│  │    • transaction_id = TXN-{account}  │        │
│  │                      -{uuid}         │        │
│  │    • account_id                      │        │
│  │    • action_type                     │        │
│  │    • amount, currency                │        │
│  │    • reason, notes                   │        │
│  │    • initiated_by = "intelligent-    │        │
│  │                     agent"           │        │
│  │    • created_at = ISO timestamp      │        │
│  │    • status = "pending"              │        │
│  │                                      │        │
│  │ 3. Store in _task_store              │        │
│  │    (in-memory or DB)                 │        │
│  │                                      │        │
│  │ 4. POST to Billing API:              │        │
│  │    POST {BILLING_API_URL}/           │        │
│  │         api/v1/billing/tasks         │        │
│  │    Body: BillingTask                 │        │
│  │                                      │        │
│  │ 5. Return result:                    │        │
│  │    {                                 │        │
│  │      "success": true,                │        │
│  │      "message": "...",               │        │
│  │      "billing_task": {...}           │        │
│  │    }                                 │        │
│  └──────────────────────────────────────┘        │
│                                                  │
│  Update: billing_result = result                │
│  Add to: actions_executed                       │
└──────────────────────────────────────────────────┘

OUTPUT
──────
AgentState updated:
  • sf_case_result (None if not called, else API response)
  • billing_result (None if not called, else API response)
  • actions_executed (List of successful actions)
  • error (Any error that occurred)

NEXT NODE
─────────
summarize_node
```

### 4.4 summarize_node

```
╔════════════════════════════════════════════════════════════╗
║         SUMMARIZE_NODE                                     ║
║  (Final output compilation)                               ║
╚════════════════════════════════════════════════════════════╝

INPUT
─────
Complete AgentState after all processing

PROCESSING
──────────
┌──────────────────────────────────────┐
│ 1. Check: can_understand_issue?      │
└───────┬──────────────────┬───────────┘
        │                  │
     FALSE               TRUE
        │                  │
        ▼                  ▼
┌─────────────────┐  ┌──────────────────────┐
│ Generate ERROR  │  │ Generate SUCCESS     │
│ RESPONSE:       │  │ RESPONSE:            │
│                 │  │                      │
│ "I am not able  │  │ • Restate issue      │
│  to understand  │  │ • Include analysis   │
│  the issue."    │  │ • List actions taken │
│                 │  │ • Show results:      │
│ + Ask for more  │  │   ├─ SF case #      │
│   details       │  │   └─ Billing task   │
│                 │  │ • Thank customer    │
│ Set error =     │  │                      │
│ "Cannot         │  │ final_summary =      │
│  understand..."  │  │ "[Comprehensive     │
│                 │  │  human-readable      │
│                 │  │  summary]"           │
│                 │  │                      │
│                 │  │ error = None         │
└────────┬────────┘  └──────────┬───────────┘
         │                      │
         └──────────┬───────────┘
                    │
OUTPUT
──────
AgentState updated:
  • final_summary (String - human readable)
  • error (String or None)

NEXT NODE
─────────
END (Workflow complete)

RESULT
──────
State serialized to IssueResponse via API layer
```

---

## 5. State Flow Diagram

```
AgentState Evolution Through Workflow
────────────────────────────────────────────────────────────────

[START] ──(Client creates AgentState)──► {
                                          account_id: "ACC-1001",
                                          issue_description: "...",
                                          account_details: {},
                                          ...all fields initialized
                                        }
                │
                ▼
        fetch_account_node
                │
                ▼─────────────────────────► {
                │                            + account_details: {...}
                │
                ▼
        analyze_issue_node
                │
                ▼─────────────────────────► {
                │                            + issue_analysis: "...",
                │                            + action_reasoning: "...",
                │                            + confidence_score: 8,
                │                            + can_understand: true,
                │                            + recommended_actions: [...],
                │                            + sf_case_payload: {...},
                │                            + billing_payload: {...}
                │
     (Conditional routing)
                │
        ┌───────┴────────┐
        │                │
   (if can't       (if recommendation
    understand)     exist & confident)
        │                │
        ▼                ▼
   SUMMARIZE       execute_actions
        │                │
        │                ▼──────────────► {
        │                │                 + sf_case_result: {...},
        │                │                 + billing_result: {...},
        │                │                 + actions_executed: [...]
        │                │
        │                ▼
        │            SUMMARIZE
        │                │
        └────────┬───────┘
                 │
                 ▼──────────────────────► {
                                          + final_summary: "...",
                                          + error: null (or error msg)
                                        }
                 │
                [END]
```

---

## 6. Error Handling Flow

```
┌─────────────────────────────────────────────────────────┐
│  ERROR HANDLING THROUGHOUT WORKFLOW                     │
└─────────────────────────────────────────────────────────┘

ERROR POINT                  HANDLING
─────────────────────────────────────────────────────────
1. Fetch Account             └─ Log warning, continue with
   Failure                      empty account_details

2. LLM API Call              └─ Log error, catch exception
   (GPT-4o-mini)                Set can_understand = False
                                → Route to summarize with
                                  error message

3. SF API Error              └─ Catch exception
   (OAuth or Case)              Log error
                                sf_case_result = error
                                Skip SF call if SF is failing

4. Billing API Error         └─ Catch exception
                                Log error
                                billing_result = error
                                Skip billing call if API fails

5. Confidence < 5            └─ NOT AN ERROR
                                Intentional gating
                                Route to summarize
                                Response: "Unable to
                                understand"

6. JSON Parse Error          └─ Catch and log
   (from LLM response)           Try alternative parsing
                                or treat as "cannot understand"

─────────────────────────────────────────────────────────

FINAL STATE if ANY error:
  • error field is populated with description
  • Actions are skipped/partial
  • final_summary explains what went wrong
  • HTTP 200 returned (not 500) with error details
    in response body
```

---

## 7. API Request/Response Flow

```
┌──────────────┐
│   CLIENT     │
└──────┬───────┘
       │ POST /api/v1/resolve-issue
       │ {account_id, issue_description}
       ▼
┌────────────────────────────────┐
│  API LAYER                     │
│  routes.py::resolve_issue()    │
│                                │
│  1. Validate IssueRequest ────┐│
│  2. Build initial AgentState   ││
│  3. Record AgentTrace ref      ││
│  4. Execute: agent_graph.      ││
│     invoke(state)              ││
│  5. Serialize to IssueResponse ││
└────────────────┬───────────────┘│
                 │                │
                 ▼                │
        ┌─────────────────────┐   │
        │  LANGGRAPH AGENT    │   │
        │  (described above)  │   │
        └─────────┬───────────┘   │
                  │                │
                  ▼                │
        (Final state returned)    │
                  │                │
                  └────────────────┘
                  │
                  ▼
       IssueResponse {
         account_id,
         issue_description,
         issue_analysis,
         action_reasoning,
         confidence_score,
         recommended_actions,
         actions_executed,
         sf_case_result,
         billing_result,
         final_summary,
         error
       }
       │
       ▼
┌──────────────────────────┐
│  HTTP RESPONSE           │
│  200 OK                  │
│  Content-Type: app/json  │
│                          │
│  [JSON response body]    │
└──────────────────────────┘
       │
       ▼
┌──────────────┐
│   CLIENT     │
│   Received!  │
└──────────────┘
```

---

## 8. Streaming Response Flow (SSE)

```
┌──────────────┐
│   CLIENT     │
└──────┬───────┘
       │ POST /api/v1/resolve-issue/stream
       │ [Same request as above]
       ▼
┌────────────────────────────────┐
│  API LAYER                     │
│  routes.py::resolve_issue_stream()
│                                │
│  1. Validate request ┐         │
│  2. Setup response ──┼──────┐  │
│     async generator  │      │  │
│  3. Yield SSE events ├──────┼──────────────┐
│                      │      │              │
│  STREAMING:          │      │              │
│                      │      │              │
│  Each node execution:│      │              │
│  yields AgentEvent:  │      │              │
│  ├─ "node_start"    │      │              │
│  ├─ [node output]   │      │              │
│  └─ "node_complete" │      │              │
│    (for each node)   │      │              │
│                      │      │              │
│  Final:              │      │              │
│  └─ "workflow_      │      │              │
│     complete"        │      │              │
│     [full state]     │      │              │
└────────────────────┤│      │              │
                     │└──────┤──────────────┘
                     ▼       │
          (Graph executes    │
           in background)    │
                     │       │
                     ▼       │
        ┌──────────────────┐ │
        │  Client receives │ │
        │  event stream:   │ │
        │                  │ │
        │ data: {          │ │
        │   "event":       │ │
        │    "node_start", │ │
        │   "node":        │ │
        │    "fetch_      │ │
        │     account"     │ │
        │ }               │ │
        │ \n              │ │
        │ data: {          │ │
        │   ...output...   │ │
        │ }               │ │
        │ \n              │ │
        │ ... more events│ │
        │ ... streaming   │ │
        │                  │ │
        │ data: {          │ │
        │   "event":       │ │
        │    "workflow_   │ │
        │     complete",   │ │
        │   "data":({final_summary, ...})
        │ }               │ │
        │ \n              │ │
        └──────────────────┘ │
             (client       │
              parses and   │
              displays)    │
                           │
```

---

## 9. Execution Timeline Example

```
[00:00.000] POST /api/v1/resolve-issue
           Request body received
           {
             "account_id": "ACC-1001",
             "issue_description": "Double charged $99..."
           }

[00:00.050] API validation passes
           AgentState initialized
           AgentTrace reference created

[00:00.100] Graph execution begins
           ├─ START node entered

[00:00.150] fetch_account_node
           ├─ Log: "Fetching account for ACC-1001"
           ├─ DB query (mock): 25ms
           └─ account_details populated

[00:00.250] analyze_issue_node
           ├─ Log: "Analyzing issue with LLM"
           ├─ Load suggestions.txt: 5ms
           ├─ Construct prompt: 10ms
           ├─ OpenAI API call: ~2000-3000ms
           │  (network latency + LLM processing)
           ├─ Parse JSON response: 5ms
           ├─ Result: confidence_score = 8/10
           ├─ Recommended actions: 2
           └─ can_understand_issue = true

[03:00.350] _route_after_analysis
           ├─ Check can_understand: true ✓
           ├─ Check recommended_actions: 2 ✓
           └─ Route to: execute_actions

[03:00.400] execute_actions_node
           ├─ Action 1: create_sf_case
           │  ├─ OAuth token request: 100ms
           │  ├─ SF API call: 200ms
           │  └─ Result: Case created ID=5001a...
           │
           ├─ Action 2: call_billing_api
           │  ├─ Build BillingTask: 10ms
           │  ├─ API call: 150ms
           │  └─ Result: Task created TXN-001...
           │
           └─ actions_executed = ["create_sf_case",
                                   "call_billing_api"]

[03:00.700] summarize_node
           ├─ Compile analysis
           ├─ Add action results
           ├─ Generate final_summary: "Duplicate charge..."
           └─ error = null

[03:00.750] END node reached
           State returned to API layer

[03:00.800] Response serialized to JSON
           AgentTrace recorded:
           {
             "timestamp": "2026-05-11T...",
             "account_id": "ACC-1001",
             "confidence_score": 8,
             "actions_executed": 2,
             "duration_seconds": 3.8,
             ...
           }

[03:00.850] HTTP 200 OK
           Response body: IssueResponse JSON

[03:00.900] Client receives complete response
           Total time: 900ms
           Real LLM calls: ~500-800ms
           External API calls: ~350ms
           Processing: ~50ms
```

---

## 10. Integration Points Summary

```
┌────────────────────────────┐
│   EXTERNAL SYSTEMS         │
└─────────┬──────────────────┘

OpenAI API (GPT-4o-mini)
├─ Called by: analyze_issue_node
├─ Endpoint: https://api.openai.com/v1/chat/completions
├─ Auth: API key in OPENAI_API_KEY env var
├─ Request: Structured prompt + account context
├─ Response: JSON with analysis + confidence + actions
└─ Error: Caught and propagated to summarize

Salesforce REST API
├─ Called by: execute_actions_node (if "create_sf_case" ∈ recommended_actions)
├─ Endpoint: {instance_url}/services/data/v59.0/sobjects/Case
├─ Auth: OAuth 2.0 (client_id + client_secret in env vars)
├─ Request: {Subject, Description, Priority, Status, Origin}
├─ Response: {id, case_number, success, message}
├─ Mock: If MOCK_SALESFORCE=true, returns deterministic response
└─ Error: Caught, logged, returned in response

Billing API (External service)
├─ Called by: execute_actions_node (if "call_billing_api" ∈ recommended_actions)
├─ Endpoint: {BILLING_API_URL}/api/v1/billing/tasks
├─ Auth: (depends on implementation, not shown here)
├─ Request: BillingTask structured document
├─ Response: {success, message, billing_task}
├─ Mock: If MOCK_BILLING=true, stores in _task_store
└─ Error: Caught, logged, returned in response

Internal Database (Not yet implemented)
├─ For: account_details lookup (currently mocked)
├─ For: billing task storage (currently in-memory)
├─ For: execution traces (currently in-memory, AGENT_TRACE)
├─ Future: Replace with PostgreSQL
└─ Schema: (to be designed)
```

---

## 11. Summary

This workflow demonstrates:
- **Intelligent Decision-Making**: LLM analyzes and decides actions
- **Safety Gating**: Confidence threshold prevents wrong calls
- **Multi-System Integration**: SF + Billing APIs coordinated
- **Observability**: Traces recorded for auditing & analytics
- **Graceful Error Handling**: Partial failures don't crash system
- **Mock-First Development**: Local development without credentials
