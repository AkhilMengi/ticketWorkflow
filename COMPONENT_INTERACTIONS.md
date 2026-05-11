# Component Interaction & Data Flow Guide

## 1. HTTP Request → API Layer → Agent Execution

### Detailed Interaction Flow

```
CLIENT (Browser/curl)
    │
    │ POST /api/v1/resolve-issue
    │ Headers: Content-Type: application/json
    │ Body: {
    │   "account_id": "ACC-1001",
    │   "issue_description": "Double-charged..."
    │ }
    │
    ▼
┌─────────────────────────────────────────────┐
│           FASTAPI ROUTE HANDLER              │
│     routes.py::resolve_issue()               │
│                                              │
│  1. Receive IssueRequest body                │
│  2. @router.post("/resolve-issue") validates │
│     using Pydantic (IssueRequest model)      │
│  3. If validation fails:                     │
│     Return: HTTP 422 Unprocessable Entity    │
│                                              │
│  4. If validation passes:                    │
│     _build_initial_state() creates dict:     │
│     {                                        │
│       "account_id": "ACC-1001",              │
│       "issue_description": "...",            │
│       "account_details": {},                 │
│       "issue_analysis": "",                  │
│       "confidence_score": 0,                 │
│       ... (all fields initialized)           │
│     }                                        │
│                                              │
│  5. Create AgentTrace reference:             │
│     trace_ref = None  # Will be populated    │
│                       # after execution      │
│                                              │
│  6. Call: agent_graph.invoke(initial_state)  │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
        ┌──────────────────────────┐
        │  AGENT GRAPH             │
        │  (StateGraph compiled)   │
        │                          │
        │  Executes 4 nodes in     │
        │  sequence, each updating │
        │  the state dict          │
        └──────────────┬───────────┘
                      │
                      ▼ (Graph returns), complete state
┌─────────────────────────────────────────────┐
│        RESPONSE SERIALIZATION                │
│     routes.py::_state_to_response()          │
│                                              │
│  Takes final state dict and converts to      │
│  Pydantic IssueResponse model:               │
│  {                                           │
│    "account_id": "ACC-1001",                 │
│    "issue_description": "...",               │
│    "issue_analysis": "...",                  │
│    "confidence_score": 8,                    │
│    "recommended_actions": [...],             │
│    "actions_executed": [...],                │
│    "sf_case_result": {...},                  │
│    "billing_result": {...},                  │
│    "final_summary": "...",                   │
│    "error": null                             │
│  }                                           │
│                                              │
│  5. Record in AgentTrace:                    │
│     AgentTrace.record_execution(...)         │
│                                              │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
        ┌──────────────────────────┐
        │  HTTP RESPONSE           │
        │  200 OK                  │
        │  Content-Type:           │
        │   application/json       │
        │                          │
        │  [IssueResponse JSON]    │
        └──────────────┬───────────┘
                      │
                      ▼
               CLIENT receives response
```

---

## 2. Agent Graph Execution Sequence

### Node Execution Flow with State Mutations

```
ENTRY: _build_initial_state() creates state dict
│
├─ State keys initialized:
│  ├─ account_id: "ACC-1001" (from request)
│  ├─ issue_description: "..." (from request)
│  ├─ account_details: {} (empty, will be filled)
│  ├─ issue_analysis: "" (empty)
│  ├─ action_reasoning: "" (empty)
│  ├─ confidence_score: 0 (default)
│  ├─ can_understand_issue: True (default)
│  ├─ recommended_actions: [] (empty)
│  ├─ sf_case_payload: {} (empty)
│  ├─ billing_payload: {} (empty)
│  ├─ sf_case_result: None
│  ├─ billing_result: None
│  ├─ actions_executed: [] (empty)
│  ├─ final_summary: "" (empty)
│  └─ error: None
│
▼
NODE 1: fetch_account_node(state) → state
│
├─ Input to node:
│  └─ state["account_id"] = "ACC-1001"
│
├─ Node execution:
│  ├─ Calls: _fetch_from_db_or_crm("ACC-1001")
│  └─ Returns: account_details dict
│
├─ Output: Updates state
│  └─ state["account_details"] = {
│       "account_id": "ACC-1001",
│       "name": "Customer_1001",
│       "email": "customer_1001@example.com",
│       "plan": "Premium",
│       "status": "Active",
│       "outstanding_balance": 0.00,
│       ...
│     }
│
├─ State after node 1:
│  ├─ account_details: POPULATED ✓
│  └─ (other fields unchanged)
│
▼
EDGE: fetch_account → analyze_issue
│
├─ Node input: Complete state (including new account_details)
│
▼
NODE 2: analyze_issue_node(state) → state
│
├─ Input to node:
│  ├─ state["account_id"]
│  ├─ state["issue_description"]
│  └─ state["account_details"] (just populated)
│
├─ Node execution (complex):
│  ├─ 1. Load suggestions from suggestions.txt
│  ├─ 2. Build LLM prompt with:
│  │    ├─ Account context
│  │    ├─ Issue description
│  │    ├─ Business suggestions
│  │    ├─ Action definitions
│  │    └─ Confidence guidelines
│  │
│  ├─ 3. Call LLM: ChatOpenAI.invoke(prompt)
│  │    └─ Receives JSON response
│  │
│  └─ 4. Parse JSON and extract:
│       ├─ issue_analysis: str
│       ├─ action_reasoning: str
│       ├─ confidence_score: int (0-10)
│       ├─ recommended_actions: List[str]
│       ├─ sf_case_payload: Dict
│       └─ billing_payload: Dict
│
├─ Output: Updates state with analysis
│  ├─ state["issue_analysis"] = "The customer reports..."
│  ├─ state["action_reasoning"] = "Confidence is 8/10..."
│  ├─ state["confidence_score"] = 8
│  ├─ state["can_understand_issue"] = True (confidence >= 5)
│  ├─ state["recommended_actions"] = ["create_sf_case", "call_billing_api"]
│  ├─ state["sf_case_payload"] = {...}
│  └─ state["billing_payload"] = {...}
│
├─ State after node 2:
│  ├─ issue_analysis: POPULATED ✓
│  ├─ confidence_score: POPULATED ✓
│  ├─ recommended_actions: POPULATED ✓
│  └─ (other fields remain/unchanged)
│
▼
CONDITIONAL EDGE: _route_after_analysis(state) → str
│
├─ Decision function:
│  │
│  └─ if not can_understand_issue:
│     └─ return "summarize"  (skip actions)
│
│  └─ elif recommended_actions is empty:
│     └─ return "summarize"  (no actions needed)
│
│  └─ else:
│     └─ return "execute_actions"  (have actions, understand issue)
│
├─ In this example:
│  ├─ can_understand_issue = True ✓
│  ├─ recommended_actions = ["create_sf_case", "call_billing_api"] (not empty) ✓
│  └─ Decision: Route to "execute_actions"
│
▼
NODE 3: execute_actions_node(state) → state
│
├─ Input to node:
│  ├─ state["recommended_actions"] = ["create_sf_case", "call_billing_api"]
│  ├─ state["sf_case_payload"] = {...}
│  └─ state["billing_payload"] = {...}
│
├─ Node execution:
│  ├─ for action in recommended_actions:
│  │
│  │  ACTION 1: "create_sf_case"
│  │  └─ Calls: salesforce.create_sf_case(sf_case_payload)
│  │     ├─ If MOCK_SALESFORCE = true:
│  │     │  └─ Returns: {"success": true, "id": "MOCK-...", ...}
│  │     └─ Else:
│  │        ├─ _get_access_token() → OAuth flow
│  │        ├─ POST /services/data/v59.0/sobjects/Case
│  │        └─ Returns: {"id": "5001a...", "case_number": "00001001"}
│  │
│  │  ACTION 2: "call_billing_api"
│  │  └─ Calls: billing.call_billing_api(billing_payload)
│  │     ├─ If MOCK_BILLING = true:
│  │     │  ├─ Builds BillingTask dict with transaction_id
│  │     │  ├─ Adds to _task_store (in-memory)
│  │     │  └─ Returns: {"success": true, "billing_task": {...}}
│  │     └─ Else:
│  │        ├─ Builds BillingTask dict
│  │        ├─ POST {BILLING_API_URL}/api/v1/billing/tasks
│  │        └─ Returns: {"success": true, "billing_task": {...}}
│  │
│  └─ Collect results
│
├─ Output: Updates state with execution results
│  ├─ state["sf_case_result"] = {"success": true, "id": "..."}
│  ├─ state["billing_result"] = {"success": true, "billing_task": {...}}
│  └─ state["actions_executed"] = ["create_sf_case", "call_billing_api"]
│
├─ State after node 3:
│  ├─ sf_case_result: POPULATED ✓
│  ├─ billing_result: POPULATED ✓
│  └─ actions_executed: POPULATED ✓
│
▼
EDGE: execute_actions → summarize
│
├─ Node input: Complete state (including API results)
│
▼
NODE 4: summarize_node(state) → state
│
├─ Input to node:
│  └─ state (complete with all previous updates)
│
├─ Node execution:
│  ├─ Check: state["can_understand_issue"]
│  ├─ If False:
│  │  └─ Generate error response:
│  │     final_summary = "I am not able to understand the issue..."
│  │     error = "Cannot understand issue - confidence score..."
│  │
│  └─ If True:
│     ├─ Compile all information:
│     │  ├─ issue_analysis
│     │  ├─ action_reasoning
│     │  ├─ actions_executed
│     │  ├─ sf_case_result
│     │  └─ billing_result
│     │
│     └─ Generate human-readable final_summary:
│        "Duplicate charge identified. Refund of $99 processed. 
│         Case #00001001 created for audit trail."
│
├─ Output: Updates state
│  ├─ state["final_summary"] = "Duplicate charge..."
│  └─ state["error"] = None (or error message if failed)
│
├─ State after node 4:
│  ├─ final_summary: POPULATED ✓
│  └─ error: SET ✓
│
▼
EDGE: summarize → END
│
├─ Final state returned from graph
│
▼
EXIT: agent_graph.invoke() returns final state
│
└─ All state fields are now populated with results
```

---

## 3. Service Integration Details

### Salesforce Service Interaction

```
execute_actions_node
    │
    │ Calls: salesforce.create_sf_case(payload)
    │ Payload: {
    │   "subject": "Duplicate charge...",
    │   "description": "...",
    │   "priority": "High",
    │   "status": "New",
    │   "origin": "Web"
    │ }
    │
    ▼
┌─────────────────────────────────────────┐
│     salesforce.py::create_sf_case()      │
│                                          │
│  1. Check: MOCK_SALESFORCE env var       │
│                                          │
│  ├─ If true:                             │
│  │  └─ Return mock response:             │
│  │     {                                 │
│  │       "success": true,                │
│  │       "id": "MOCK-ACC-1001-001",      │
│  │       "case_number": "00001001",      │
│  │       "message": "Mock SF case..."    │
│  │     }                                 │
│  │                                       │
│  └─ If false:                            │
│     ├─ 2a. Get OAuth token:              │
│     │  └─ _get_access_token()            │
│     │     ├─ sf_client_id (env)          │
│     │     ├─ sf_client_secret (env)      │
│     │     └─ sf_login_url (env)          │
│     │        │                           │
│     │        ▼                           │
│     │     POST {SF_LOGIN_URL}/           │
│     │         services/oauth2/token      │
│     │     Params: {grant_type:            │
│     │              client_credentials,   │
│     │              client_id,            │
│     │              client_secret}        │
│     │        │                           │
│     │        ▼                           │
│     │     Returns: {                     │
│     │       "access_token": "...",       │
│     │       "instance_url": "..."        │
│     │     }                              │
│     │                                    │
│     ├─ 2b. Create case with token:       │
│     │  └─ POST {instance_url}/           │
│     │         services/data/v59.0/       │
│     │         sobjects/Case              │
│     │     Headers: {                     │
│     │       "Authorization":             │
│     │       "Bearer {access_token}",     │
│     │       "Content-Type":              │
│     │       "application/json"           │
│     │     }                              │
│     │     Body: {                        │
│     │       "Subject": "...",            │
│     │       "Description": "...",        │
│     │       "Priority": "High",          │
│     │       "Status": "New",             │
│     │       "Origin": "Web"              │
│     │     }                              │
│     │        │                           │
│     │        ▼                           │
│     │     Returns: {                     │
│     │       "id": "5001a000...",         │
│     │       "success": true,             │
│     │       "errors": [...]              │
│     │     }                              │
│     │                                    │
│     └─ 3. Return result                  │
│
└─────────────────────┬──────────────────┘
                      │
                      ▼
Returns to execute_actions_node:
{
  "success": true,
  "id": "5001a000009OzrAAE",
  "case_number": "00001001",
  "message": "..."
}
```

### Billing Service Interaction

```
execute_actions_node
    │
    │ Calls: billing.call_billing_api(payload)
    │ Payload: {
    │   "account_id": "ACC-1001",
    │   "action_type": "refund",
    │   "amount": 99.0,
    │   "currency": "USD",
    │   "reason": "DUPLICATE_CHARGE",
    │   "notes": "..."
    │ }
    │
    ▼
┌─────────────────────────────────────────┐
│      billing.py::call_billing_api()      │
│                                          │
│  1. Generate unique transaction_id:      │
│     transaction_id = f"TXN-{account_id}- │
│                       {uuid4.hex[:8]}"  │
│     Example: TXN-ACC-1001-a1b2c3d4      │
│                                          │
│  2. Build BillingTask struct:            │
│     _build_task_payload(payload,         │
│                         transaction_id)  │
│     └─ Returns: {                        │
│       "transaction_id": "TXN-...",       │
│       "account_id": "ACC-1001",          │
│       "change_suggested": "...",         │
│       "action_type": "refund",           │
│       "reason": "DUPLICATE_CHARGE",      │
│       "amount": 99.0,                    │
│       "currency": "USD",                 │
│       "notes": "...",                    │
│       "initiated_by": "intelligent-      │
│                         agent",          │
│       "created_at": "2026-05-11T...",    │
│       "status": "pending"                │
│     }                                    │
│                                          │
│  3. Check: MOCK_BILLING env var          │
│                                          │
│  ├─ If true:                             │
│  │  ├─ Set task["status"] = "processed"  │
│  │  ├─ Add to _task_store (in-memory)    │
│  │  └─ Return mock response:             │
│  │     {                                 │
│  │       "success": true,                │
│  │       "message": "Billing task        │
│  │                   'refund' created",  │
│  │       "billing_task": {...}           │
│  │     }                                 │
│  │                                       │
│  └─ If false:                            │
│     ├─ POST {BILLING_API_URL}/           │
│     │     api/v1/billing/tasks           │
│     │  Headers: {                        │
│     │    "Content-Type":                 │
│     │    "application/json"              │
│     │  }                                 │
│     │  Body: BillingTask                 │
│     │     │                              │
│     │     ▼                              │
│     │  Returns: {                        │
│     │    "success": true,                │
│     │    "message": "...",               │
│     │    "billing_task": {...}           │
│     │  }                                 │
│     │                                    │
│     └─ Add to _task_store (in-memory)    │
│        (for dashboard queries)           │
│                                          │
│  4. Return result                        │
│
└─────────────────────┬──────────────────┘
                      │
                      ▼
Returns to execute_actions_node:
{
  "success": true,
  "message": "Refund task created for account ACC-1001",
  "billing_task": {
    "transaction_id": "TXN-ACC-1001-a1b2c3d4",
    "account_id": "ACC-1001",
    "action_type": "refund",
    "amount": 99.0,
    "status": "processed",
    ...
  }
}
```

---

## 4. LLM Interaction (analyze_issue_node)

### Prompt Construction & Response Parsing

```
analyze_issue_node
    │
    ▼
┌────────────────────────────────────────────────────┐
│        PROMPT CONSTRUCTION                          │
│  prompts.py::ANALYZE_ISSUE_PROMPT                   │
│                                                    │
│  Template string with placeholders:                │
│  ────────────────────────────────────────────────  │
│  "You are an expert customer-support AI agent...   │
│                                                    │
│  ━━━━━━━━  ACCOUNT CONTEXT  ━━━━━━━━              │
│  Account ID: {account_id}                          │
│  Account Details:                                  │
│  {account_details}                                 │
│                                                    │
│  ━━━━━━━━  CUSTOMER ISSUE  ━━━━━━━━               │
│  {issue_description}                               │
│                                                    │
│  ━━━━━━━━  KNOWLEDGE BASE  ━━━━━━━━               │
│  {suggestions}                                     │
│  [Business rules: Check customer details,          │
│   Rebill the account, Close the case]             │
│                                                    │
│  ━━━━━━━━  AVAILABLE ACTIONS  ━━━━━━━━             │
│  ACTION 1: create_sf_case                          │
│    Purpose: Open support case for tracking         │
│    Use when: Issue needs escalation/review         │
│                                                    │
│  ACTION 2: call_billing_api                        │
│    Purpose: Execute financial operation            │
│    action_type: refund|credit|rebill|adjustment    │
│                                                    │
│  ━━━━━━━━  CONFIDENCE SCORING  ━━━━━━━━            │
│  9-10: Crystal clear (explicit problem)            │
│   6-8: Pretty clear (sufficient info)              │
│   4-5: Unclear (missing details)                   │
│   0-3: Cannot understand (too vague)               │
│                                                    │
│  ⚠️  CRITICAL: If confidence < 5:                  │
│      Set recommended_actions = []                  │
│      Return: 'I am not able to understand...'      │
│                                                    │
│  ━━━━━━━━  DECISION RULES  ━━━━━━━━                │
│  IF confidence < 5                                 │
│    → Do NOT recommend any actions                  │
│  ELSE IF matches 'Check customer details'          │
│    → Use create_sf_case ONLY                       │
│  ELSE IF matches 'Rebill the account'              │
│    → Always call_billing_api                       │
│    → Also create_sf_case if significant            │
│  ELSE IF matches 'Close the case'                  │
│    → Use create_sf_case                            │
│    → Add call_billing_api if correction needed     │
│                                                    │
│  Format your response as JSON:                     │
│  {                                                 │
│    'issue_analysis': '...',                        │
│    'action_reasoning': '...',                      │
│    'confidence_score': <0-10>,                     │
│    'recommended_actions': [...],                   │
│    'sf_case_payload': {...},                       │
│    'billing_payload': {...}                        │
│  }                                                 │
│  ────────────────────────────────────────────────  │
│                                                    │
│  Fill placeholders:                                │
│  ├─ {account_id}: "ACC-1001"                       │
│  ├─ {account_details}: "name: Customer_1001..."    │
│  ├─ {issue_description}: "Double-charged..."       │
│  ├─ {suggestions}: "• Check customer details..."   │
│  └─ (others already in template)                   │
│                                                    │
└────────────────────────────────────────────────────┘
    │
    │ Final prompt string (~2000 tokens) →
    │
    ▼
┌────────────────────────────────────────────────────┐
│        LLM INVOCATION                               │
│  ChatOpenAI(                                        │
│    model="gpt-4o-mini",                             │
│    temperature=0,      # Deterministic             │
│    api_key=OPENAI_API_KEY                          │
│  ).invoke(HumanMessage(prompt))                     │
│                                                    │
│  ├─ Network latency: 50-200ms                      │
│  ├─ LLM processing: 1000-2500ms                    │
│  ├─ Token consumption:                             │
│  │  ├─ Input: ~1000-2000 tokens                    │
│  │  └─ Output: ~200-500 tokens                     │
│  └─ Cost: ~$0.001-0.005 per request               │
│                                                    │
└────────────────────────────────────────────────────┘
    │
    │ Response string with JSON:
    │ {
    │   "issue_analysis": "The customer reports...",
    │   "action_reasoning": "Confidence is high...",
    │   "confidence_score": 8,
    │   "recommended_actions": ["create_sf_case", "call_billing_api"],
    │   "sf_case_payload": {...},
    │   "billing_payload": {...}
    │ }
    │
    ▼
┌────────────────────────────────────────────────────┐
│        JSON PARSING                                 │
│  _parse_llm_json(response_content)                  │
│                                                    │
│  1. Strip markdown fences (if present):            │
│     ├─ Input: "```json\n{...}\n```"               │
│     └─ Output: "{...}"                             │
│                                                    │
│  2. Parse JSON string:                             │
│     response_dict = json.loads(text)               │
│                                                    │
│  3. Extract fields:                                │
│     ├─ issue_analysis = response_dict.get(...)     │
│     ├─ action_reasoning = response_dict.get(...)   │
│     ├─ confidence_score = response_dict.get(...)   │
│     ├─ recommended_actions = response_dict.get(..) │
│     ├─ sf_case_payload = response_dict.get(...)    │
│     └─ billing_payload = response_dict.get(...)    │
│                                                    │
│  4. Validate confidence_score:                     │
│     ├─ If < 5:                                     │
│     │  └─ can_understand_issue = False             │
│     └─ If >= 5:                                    │
│        └─ can_understand_issue = True              │
│                                                    │
└────────────────────────────────────────────────────┘
    │
    ▼
Returns to analyze_issue_node:
{
  "issue_analysis": "The customer reports a duplicate charge...",
  "action_reasoning": "Since confidence is 8/10, recommend...",
  "confidence_score": 8,
  "can_understand_issue": True,
  "recommended_actions": ["create_sf_case", "call_billing_api"],
  "sf_case_payload": {
    "subject": "Duplicate charge - refund requested",
    "description": "Customer was charged $99 twice on...",
    "priority": "High",
    "status": "New",
    "origin": "Web"
  },
  "billing_payload": {
    "account_id": "ACC-1001",
    "action_type": "refund",
    "amount": 99.0,
    "currency": "USD",
    "reason": "DUPLICATE_CHARGE",
    "notes": "Customer double-charged on 2026-04-15..."
  }
}
```

---

## 5. Observability: Tracing & Metrics

### AgentTrace Recording

```
After workflow completion:

routes.py::_state_to_response()
    │
    │ After serializing to IssueResponse
    │
    ▼
┌────────────────────────────────────────┐
│   TRACING & OBSERVABILITY               │
│   routes.py (after returning response)  │
│                                         │
│  AgentTrace.record_execution(           │
│    account_id="ACC-1001",               │
│    issue_description="...",             │
│    confidence_score=8,                  │
│    issue_analysis="...",                │
│    recommended_actions=[...],           │
│    actions_executed=[...],              │
│    final_summary="...",                 │
│    duration_seconds=3.2,                │
│    sf_case_result={...},                │
│    billing_result={...},                │
│    error=None                           │
│  )                                      │
│                                         │
│  ├─ Builds trace dict:                  │
│  │  {                                   │
│  │    "timestamp": "2026-05-11T...",    │
│  │    "account_id": "ACC-1001",         │
│  │    "issue_description": "...",       │
│  │    "confidence_score": 8,            │
│  │    "issue_analysis": "...",          │
│  │    "recommended_actions": [...],     │
│  │    "actions_executed": [...],        │
│  │    "final_summary": "...",           │
│  │    "duration_seconds": 3.2,          │
│  │    "sf_case_result": {...},          │
│  │    "billing_result": {...},          │
│  │    "status": "success",              │
│  │    "error": null                     │
│  │  }                                   │
│  │                                      │
│  └─ Appends to: AgentTrace.traces []    │
│     (In-memory list, lost on restart)   │
│                                         │
│  Logging:                               │
│  logger.info(                           │
│    f"Trace recorded for {account_id}"   │
│    f" (confidence: {confidence}/10)"    │
│  )                                      │
│                                         │
└────────────────────────────────────────┘
    │
    ▼
Trace available via GET /api/v1/traces
│
├─ Calls: AgentTrace.get_all_traces(limit=100)
├─ Returns: List of traces, sorted by timestamp (latest first)
└─ Example response:
   [
     {
       "timestamp": "2026-05-11T10:30:45.123456",
       "account_id": "ACC-1001",
       "confidence_score": 8,
       "status": "success",
       "duration_seconds": 3.2,
       ...
     },
     {
       "timestamp": "2026-05-11T10:25:12.987654",
       "account_id": "ACC-1002",
       "confidence_score": 4,
       "issue_analysis": "I am not able to understand...",
       "status": "failure",
       "recommended_actions": [],
       ...
     },
     ...
   ]
```

### Metrics Calculation

```
GET /api/v1/traces/metrics
    │
    ▼
┌────────────────────────────────────────┐
│   METRICS CALCULATION                   │
│   tracing.py::AgentTrace.get_metrics()  │
│                                         │
│  Input: AgentTrace.traces list         │
│  (all traces recorded in session)       │
│                                         │
│  Calculations:                          │
│  ├─ total_executions                    │
│  │  = len(traces)                       │
│  │  Example: 42                         │
│  │                                      │
│  ├─ success_count                       │
│  │  = count of traces where              │
│  │    status == "success"                │
│  │  Example: 38                         │
│  │                                      │
│  ├─ failure_count                       │
│  │  = total - success                   │
│  │  Example: 4                          │
│  │                                      │
│  ├─ success_rate (%)                    │
│  │  = (success_count / total) × 100      │
│  │  Example: 90.5%                      │
│  │                                      │
│  ├─ avg_confidence (0-10)                │
│  │  = sum(confidence_scores) / count    │
│  │  Example: 7.43                       │
│  │                                      │
│  ├─ avg_duration (seconds)               │
│  │  = sum(durations) / count            │
│  │  Example: 3.21 sec                   │
│  │                                      │
│  └─ most_common_action                   │
│     = action that appears most            │
│       in all recommended_actions          │
│     Example: "create_sf_case"            │
│                                         │
│  Return: {                              │
│    "total_executions": 42,              │
│    "avg_confidence": 7.43,              │
│    "success_count": 38,                 │
│    "failure_count": 4,                  │
│    "success_rate": 90.5,                │
│    "avg_duration": 3.21,                │
│    "most_common_action": "create_sf_case"
│  }                                      │
│                                         │
└────────────────────────────────────────┘
    │
    ▼
Dashboard (Streamlit):
├─ Fetches metrics from GET /api/v1/traces/metrics
├─ Renders cards:
│  ├─ "Success Rate: 90.5%"
│  ├─ "Avg Confidence: 7.43/10"
│  ├─ "Avg Duration: 3.21s"
│  └─ "Total Executions: 42"
└─ Updates in real-time (polling)
```

---

## 6. Configuration & Environment

### Environment Variables Flow

```
.env file
│
├─ OPENAI_API_KEY=sk-...
├─ SF_CLIENT_ID=...
├─ SF_CLIENT_SECRET=...
├─ SF_LOGIN_URL=https://login.salesforce.com
├─ MOCK_SALESFORCE=true
├─ MOCK_BILLING=true
├─ BILLING_API_URL=http://localhost:9000
└─ DATABASE_URL=sqlite:///./agent.db

    │
    ▼
load_dotenv() in config.py
    │
    ├─ os.getenv("OPENAI_API_KEY") → OPENAI_API_KEY (str)
    ├─ os.getenv("SF_CLIENT_ID") → SF_CLIENT_ID (str)
    ├─ os.getenv("SF_CLIENT_SECRET") → SF_CLIENT_SECRET (str)
    ├─ os.getenv("MOCK_SALESFORCE", "true").lower() == "true"
    │                               → MOCK_SALESFORCE (bool)
    ├─ os.getenv("MOCK_BILLING", "true").lower() == "true"
    │                               → MOCK_BILLING (bool)
    ├─ os.getenv("BILLING_API_URL", "http://localhost:9000")
    │                               → BILLING_API_URL (str)
    └─ os.getenv("DATABASE_URL", "sqlite:///./agent.db")
                                     → DATABASE_URL (str)

    │
    ▼
Usage in nodes:

analyze_issue_node:
├─ if not OPENAI_API_KEY:
│  └─ raise error (required)
└─ ChatOpenAI(api_key=OPENAI_API_KEY)

salesforce.py:
├─ if MOCK_SALESFORCE:
│  └─ return mock response
└─ else:
   ├─ _get_access_token():
   │  ├─ Use: SF_CLIENT_ID
   │  ├─ Use: SF_CLIENT_SECRET
   │  └─ Use: SF_LOGIN_URL
   └─ POST to {instance_url}

billing.py:
├─ if MOCK_BILLING:
│  └─ return mock response
└─ else:
   └─ POST to {BILLING_API_URL}
```

---

## 7. Error Handling & Propagation

### Error Flow Through Components

```
ERROR OCCURS ANYWHERE IN WORKFLOW
    │
    ├─ fetch_account_node: DB error
    │  └─ Logs warning, continues with empty account_details
    │
    ├─ analyze_issue_node: LLM API error
    │  ├─ Catches exception
    │  ├─ Logs error
    │  ├─ Sets: can_understand_issue = False
    │  └─ Routes to summarize with error message
    │
    ├─ execute_actions_node: API error
    │  ├─ Catches exception for each action
    │  ├─ Logs error for tracking
    │  ├─ If SF API fails:
    │  │  └─ sf_case_result = Error object
    │  ├─ If Billing API fails:
    │  │  └─ billing_result = Error object
    │  └─ Continues (doesn't stop entire workflow)
    │
    └─ summarize_node: (rarely errors)
       └─ Compiles error into final_summary

    │
    ▼
Error propagated through state:
state["error"] = error_message

    │
    ▼
serialization_layer:
├─ state["error"] is set
└─ IssueResponse.error = error_message

    │
    ▼
HTTP Response:
├─ Status: 200 OK (not 500)
│  (Errors are app logic, not system failure)
└─ Body: IssueResponse with error field
   {
     "account_id": "ACC-1001",
     "error": "Cannot understand issue - confidence score...",
     "final_summary": "Unable to process..."
   }

    │
    ▼
Client receives:
├─ Valid JSON response
├─ Error details in "error" field
└─ Can handle gracefully (no exception needed)
```

---

## Summary

This document shows how:
1. **HTTP requests** flow through FastAPI → Agent → Services → External APIs
2. **AgentState** evolves as each node updates it
3. **Services** (SF, Billing) handle external integrations
4. **LLM** provides intelligent analysis via structured prompts
5. **Tracing** captures all executions for observability
6. **Configuration** controls behavior dynamically
7. **Errors** propagate gracefully without crashing

Total workflow time: ~2.5-3.5 seconds (dominated by LLM latency)
