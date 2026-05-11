# Agentic Issue Resolution System — High-Level Design

## Executive Summary

The **Agentic Issue Resolution System** is an AI-powered customer support automation platform that uses LangGraph-based agent orchestration to intelligently analyze customer issues and execute resolution actions across multiple systems (Salesforce, Billing API). The system combines FastAPI for request handling, LangChain/OpenAI for intelligent analysis, and LangGraph for workflow orchestration.

---

## System Architecture

### 1. **High-Level Architecture Diagram**

```
┌──────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                │
│                                                                      │
│  ┌────────────────┐         ┌────────────────┐                      │
│  │  Web Client    │ HTTP    │  Dashboard     │ (Streamlit)          │
│  │ (Swagger UI)   │ ◄──────►│  (LangSmith    │                      │
│  └────────────────┘         │   Style)       │                      │
│                             └────────────────┘                      │
└──────────────────────────────────────────────────────────────────────┘
                                    │ HTTP/REST
                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       API LAYER (FastAPI)                           │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │ Endpoints:                                                 │    │
│  │  • POST /api/v1/resolve-issue              (JSON)          │    │
│  │  • POST /api/v1/resolve-issue/stream       (SSE)           │    │
│  │  • GET  /api/v1/actions                    (list)          │    │
│  │  • GET  /api/v1/traces                     (history)       │    │
│  │  • GET  /api/v1/traces/metrics             (analytics)     │    │
│  │  • GET  /health                            (healthcheck)   │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ├─ Request Validation (Pydantic)                                   │
│  ├─ State Management (IssueRequest → AgentState)                    │
│  └─ Response Serialization (IssueResponse)                          │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│              AGENT ORCHESTRATION LAYER (LangGraph)                  │
│                                                                      │
│                          StateGraph                                 │
│                         ┌─────────────┐                             │
│                         │    START    │                             │
│                         └──────┬──────┘                              │
│                                │                                    │
│                 ┌──────────────▼──────────────┐                     │
│                 │    fetch_account_node       │                     │
│                 │  (Load account from DB)     │                     │
│                 └──────────────┬──────────────┘                      │
│                                │                                    │
│                 ┌──────────────▼──────────────┐                     │
│                 │    analyze_issue_node       │                     │
│                 │  (LLM → Confidence Score)   │                     │
│                 └─┬────────────────────────┬──┘                     │
│                   │                        │                        │
│         (confidence >= 5 &      (cannot understand │                │
│          actions needed)         or no actions)   │                │
│                   │                        │        │              │
│    ┌──────────────▼──────────────┐        │        │               │
│    │  execute_actions_node        │        │        │              │
│    │  (SF Case + Billing API)     │        │        │               │
│    └──────────────┬───────────────┘        │        │              │
│                   │                        │        │              │
│                   └────────────┬────────────┘        │              │
│                                │                    │              │
│                    ┌───────────▼────────────┐        │              │
│                    │   summarize_node       │◄───────┘              │
│                    │ (Compile response)     │                       │
│                    └───────────┬────────────┘                       │
│                                │                                    │
│                         ┌──────▼──────┐                             │
│                         │     END     │                             │
│                         └─────────────┘                             │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                         ┌──────────┴──────────┐
                         │                     │
                         ▼                     ▼
┌──────────────────────────────┐  ┌──────────────────────────────┐
│  EXTERNAL SERVICE LAYER      │  │  OBSERVABILITY LAYER         │
│                              │  │                              │
│ ┌─────────────────────────┐  │  │ ┌───────────────────────────┐│
│ │  SALESFORCE API         │  │  │ │  Agent Tracing (AgentTrace)   │
│ │  • OAuth 2.0 Auth       │  │  │ │  • Record executions       │
│ │  • Create Case          │  │  │ │  • Track confidence scores │
│ │  • Case tracking        │  │  │ │  • Store metrics           │
│ └─────────────────────────┘  │  │ └───────────────────────────┘
│                              │  │
│ ┌─────────────────────────┐  │  │ ┌───────────────────────────┐
│ │  BILLING API            │  │  │ │ Logging & Monitoring      │
│ │  • Task creation        │  │  │ │ • Structured logs         │
│ │  • action_type:         │  │  │ │ • Execution timing        │
│ │    refund/credit/rebill │  │  │ │ • Error tracking          │
│ │    /adjustment          │  │  │ │                           │
│ │  • Task storage         │  │  │ │                           │
│ └─────────────────────────┘  │  │ └───────────────────────────┘
│                              │  │
│ ┌─────────────────────────┐  │  │
│ │  CRM/Database           │  │  │
│ │  • Account lookup       │  │  │
│ │  • Account details      │  │  │
│ │  • Payment history      │  │  │
│ └─────────────────────────┘  │  │
└──────────────────────────────┘  └──────────────────────────────┘
```

---

## 2. Component Details

### 2.1 API Layer (`app/api/`)

#### **routes.py**
Defines REST endpoints for issue resolution and observability:
- **POST /resolve-issue**: Synchronous full workflow execution
- **POST /resolve-issue/stream**: Streaming workflow with Server-Sent Events (SSE)
- **GET /actions**: Returns list of supported action types
- **GET /traces**: Retrieves execution history/traces
- **GET /traces/metrics**: Returns aggregate metrics (success rate, avg confidence, etc.)

#### **schemas.py**
Pydantic models for request/response validation:
- `IssueRequest`: Account ID + issue description
- `IssueResponse`: Full workflow result with analysis and actions
- `BillingTask`: Structured billing operation document
- `BillingTaskRequest/Response`: Billing API contract
- `AgentEvent`: Server-Sent Event payload (node start, complete, error)

---

### 2.2 Agent Layer (`app/agent/`)

#### **state.py (AgentState TypedDict)**
Central state management for workflow:

```
Input:
  • account_id: Customer identifier
  • issue_description: Plain-language problem statement
  
Context:
  • account_details: Fetched CRM/DB data
  
Analysis (from LLM):
  • issue_analysis: Human-readable breakdown
  • action_reasoning: Explanation of chosen actions
  • confidence_score: 0-10 confidence in understanding
  • can_understand_issue: Boolean (true if confidence >= 5)
  
Decisions:
  • recommended_actions: ["create_sf_case", "call_billing_api"]
  • sf_case_payload: Salesforce case data
  • billing_payload: Billing API task data
  
Results:
  • sf_case_result: SF API response
  • billing_result: Billing API response
  • actions_executed: List of successful actions
  
Output:
  • final_summary: Human-readable resolution summary
  • error: Any error encountered
```

#### **graph.py (Workflow Orchestration)**
LangGraph StateGraph definition:
- **Router function**: `_route_after_analysis()` - determines next node based on confidence & available actions
- **Compilation**: Builds optimized graph (cached singleton)
- **Conditional edges**: Routes to `execute_actions` or skip directly to `summarize`
- **Confidence gating**: If confidence < 5, skips action execution automatically

#### **nodes.py (Workflow Nodes)**

1. **fetch_account_node**
   - Loads account context from DB/CRM
   - Mock implementation returns realistic account data
   - *TODO: Replace with actual DB lookup*

2. **analyze_issue_node**
   - Calls OpenAI GPT-4o-mini with structured prompt
   - Parses LLM response (JSON) to extract:
     - Issue analysis
     - Action reasoning
     - Confidence score
     - Recommended actions
   - Loads business suggestions from `suggestions.txt` for context
   - Sets `can_understand_issue` flag (confidence >= 5)

3. **execute_actions_node**
   - Iterates through `recommended_actions`
   - **For "create_sf_case"**: Calls `salesforce.create_sf_case()`
   - **For "call_billing_api"**: Calls `billing.call_billing_api()`
   - Collects results and updates `actions_executed`

4. **summarize_node**
   - Compiles final response from workflow result
   - If couldn't understand issue: returns structured "unable to understand" message
   - Otherwise: summarizes actions taken and their results

#### **prompts.py (LLM Prompt Engineering)**
Structured prompt template for `analyze_issue_node`:
- Account context injection
- Business suggestions (knowledge base)
- Action availability explanation
- **Confidence scoring guidelines** (0-10 scale)
- **Decision rules** based on business logic
- **Critical gating**: If confidence < 5, return empty action list

#### **tracing.py (Observability)**
In-memory trace storage (AgentTrace class):
- Records all agent executions with metadata
- Tracks confidence scores, actions, outcomes
- Provides filtering by account ID
- Calculates metrics:
  - Success rate
  - Average confidence
  - Average duration
  - Most common actions

---

### 2.3 Services Layer (`app/services/`)

#### **salesforce.py**
Salesforce Case creation:
- **Authentication**: OAuth 2.0 Client Credentials flow
- **Endpoint**: POST /services/data/{version}/sobjects/Case
- **Payload fields**: Subject, Description, Priority, Status, Origin, AccountId
- **Mock mode**: Returns deterministic mock responses when `MOCK_SALESFORCE=true`
- **Error handling**: Captures and logs API errors

#### **billing.py**
Billing task creation and management:
- **Task creation**: Builds structured `BillingTask` document with:
  - Unique `transaction_id` (TXN-{account_id}-{uuid})
  - Action type: refund | credit | rebill | adjustment
  - Financial amount & currency
  - Reason code & detailed notes
  - Timestamp & status tracking
- **Storage**: In-memory list `_task_store` (production: use database)
- **Endpoints**: 
  - POST {BILLING_API_URL}/api/v1/billing/tasks
- **Mock mode**: Returns mock success response when `MOCK_BILLING=true`

---

### 2.4 Configuration & Entry Points

#### **config.py**
Environment variable management:
```
OPENAI_API_KEY                    (LangChain/OpenAI integration)
SF_CLIENT_ID, SF_CLIENT_SECRET    (Salesforce OAuth)
SF_LOGIN_URL                      (Salesforce instance URL)
MOCK_SALESFORCE                   (true = skip real API, use mock)
MOCK_BILLING                      (true = skip real API, use mock)
BILLING_API_URL                   (Billing microservice endpoint)
DATABASE_URL                      (Future: real DB instead of in-memory)
```

#### **main.py**
FastAPI application entry point:
- Creates FastAPI app instance
- Adds CORS middleware (allow all origins)
- Includes API routes (prefix: /api/v1)
- Health check endpoint
- Auto-generated Swagger UI at /docs

#### **dashboard.py**
Streamlit observability dashboard:
- **Styling**: LangSmith-inspired dark theme with gradients
- **Pages/Tabs**: 
  - Execution history (traces)
  - Metrics & analytics (charts)
  - Detailed trace inspector
- **Real-time updates**: Fetches from API endpoints

---

## 3. Data Flow & Workflow

### Issue Resolution Flow

```
1. CLIENT SUBMITS ISSUE
   POST /api/v1/resolve-issue
   {
     "account_id": "ACC-1001",
     "issue_description": "Customer was double-charged..."
   }
                                    │
                                    ▼
2. API LAYER VALIDATION
   • Pydantic validates schema
   • Builds initial AgentState
   • Creates AgentTrace reference
                                    │
                                    ▼
3. FETCH ACCOUNT CONTEXT
   fetch_account_node
   • Loads customer details from DB
   • State updated: account_details
                                    │
                                    ▼
4. INTELLIGENT ANALYSIS
   analyze_issue_node
   • Calls GPT-4o-mini with prompt
   • LLM receives:
     - Account context
     - Issue description
     - Business suggestions
   • LLM outputs JSON:
     - issue_analysis
     - action_reasoning
     - confidence_score (0-10)
     - recommended_actions []
   • State updated: issue_analysis, confidence_score, recommended_actions
                                    │
                 ┌──────────────────┴──────────────────┐
                 │                                     │
         Confidence >= 5 & Actions?      Confidence < 5 or No Actions
                 │                                     │
                 ▼                                     ▼
5A. EXECUTE ACTIONS               5B. CANNOT UNDERSTAND
    execute_actions_node              summarize_node
    • For each recommended_action:    • Return error: "Unable to understand"
      ├─ create_sf_case              • State: final_summary (error message)
      │  └─ SF API call              └─ END
      │     └─ Track result              
      └─ call_billing_api            
         └─ Billing API call         
            └─ Track result          
    • State updated: sf_case_result,
      billing_result, actions_executed
                 │
                 ▼
6. FINALIZE RESPONSE
   summarize_node
   • Compile issue_analysis
   • Add action results
   • Generate human-readable final_summary
   • State: final_summary
                 │
                 ▼
7. RETURN TO CLIENT
   IssueResponse
   {
     "account_id": "ACC-1001",
     "issue_description": "...",
     "issue_analysis": "...",
     "confidence_score": 8,
     "recommended_actions": [...],
     "actions_executed": [...],
     "sf_case_result": {...},
     "billing_result": {...},
     "final_summary": "...",
     "error": null
   }
```

---

## 4. Key Design Patterns

### 4.1 Confidence Gating
**Purpose**: Prevent incorrect API calls when issue is unclear
- LLM provides confidence score (0-10)
- Threshold: >= 5 to proceed with actions
- If < 5: Return structured error response, don't execute any actions
- Ensures safety and prevents expensive mistakes

### 4.2 Conditional Routing
**Pattern**: LangGraph's conditional edges based on state
```python
graph.add_conditional_edges(
    "analyze_issue",
    _route_after_analysis,  # Router function
    {
        "execute_actions": "execute_actions",
        "summarize": "summarize",
    }
)
```
Router function examines `AgentState` and returns next node name

### 4.3 Lazy Singleton (LLM)
**Pattern**: GPT-4o-mini client initialized once, reused
```python
_llm: ChatOpenAI | None = None

def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(...)
    return _llm
```
Reduces API overhead and token usage

### 4.4 Mock-First Architecture
**Purpose**: Enable local development without real APIs
- Environment variables control mock mode:
  - `MOCK_SALESFORCE=true` → skips SF API, returns deterministic response
  - `MOCK_BILLING=true` → skips billing API, returns mock task
- Allows testing end-to-end without credentials

### 4.5 Stateful Workflow with TypedDict
**Pattern**: Shared state object passed through all nodes
- Type-safe (TypedDict enforces structure)
- All data visible to all nodes
- Previous node output becomes input to next node
- Simplifies debugging and observability

---

## 5. Scalability & Production Considerations

### 5.1 Current Limitations
- **In-memory storage**: `_task_store` (billing tasks), `AgentTrace.traces` (executions)
- **No authentication**: FastAPI allows all origins (CORS policy)
- **Single instance**: No clustering or load balancing
- **Mock dependencies**: Real Salesforce + Billing APIs require credentials

### 5.2 Production Roadmap
1. **Database Layer**
   - Replace in-memory stores with PostgreSQL
   - Store traces with compression
   - Index by account_id and timestamp for fast queries

2. **Authentication & Authorization**
   - API key validation (header-based)
   - Role-based access control (RBAC)
   - Audit logging for compliance

3. **Caching & Performance**
   - Cache account details (with TTL)
   - Cache LLM responses for duplicate issues
   - Implement request batching for billing API

4. **Async & Streaming**
   - Already supports SSE streaming endpoint
   - Could implement job queue (Celery) for long-running workflows
   - WebSocket support for real-time dashboard updates

5. **Error Handling & Resilience**
   - Retry logic with exponential backoff (already using Tenacity)
   - Circuit breaker for external API failures
   - Dead-letter queue for failed billing tasks

6. **Observability**
   - Integration with professional tracing (LangSmith, Datadog)
   - Distributed tracing across microservices
   - SLA monitoring and alerting

---

## 6. API Specifications

### Endpoint: POST /api/v1/resolve-issue

**Request**:
```json
{
  "account_id": "ACC-1001",
  "issue_description": "Customer was double-charged $99 on 2026-04-15"
}
```

**Response** (Success):
```json
{
  "account_id": "ACC-1001",
  "issue_description": "...",
  "issue_analysis": "The customer reports a duplicate charge for their monthly subscription...",
  "action_reasoning": "Since confidence is high (8/10) and a duplicate charge is identified, the best action is to create a Salesforce case for tracking and call the billing API to process a refund.",
  "recommended_actions": ["create_sf_case", "call_billing_api"],
  "actions_executed": ["create_sf_case", "call_billing_api"],
  "sf_case_result": {
    "success": true,
    "id": "5001a000009OzrAAE",
    "case_number": "00001001"
  },
  "billing_result": {
    "success": true,
    "message": "Refund processed",
    "billing_task": {
      "transaction_id": "TXN-ACC-1001-a1b2c3d4",
      "action_type": "refund",
      "amount": 99.0,
      "status": "processed"
    }
  },
  "final_summary": "Duplicate charge identified and resolved. Refund of $99 processed and case created for audit trail.",
  "error": null
}
```

**Response** (Confidence < 5):
```json
{
  "account_id": "ACC-1001",
  "issue_description": "Something went wrong",
  "issue_analysis": "I am not able to understand the issue",
  "action_reasoning": "Issue description is too vague. Missing specific details about what went wrong.",
  "recommended_actions": [],
  "actions_executed": [],
  "sf_case_result": null,
  "billing_result": null,
  "final_summary": "Unable to process: please provide specific details about your issue (e.g., what charges, which date, expected vs actual amount)",
  "error": "Cannot understand issue - confidence score below threshold"
}
```

### Endpoint: GET /api/v1/traces/metrics

**Response**:
```json
{
  "total_executions": 42,
  "avg_confidence": 7.43,
  "success_count": 38,
  "failure_count": 4,
  "success_rate": 90.5,
  "avg_duration": 3.21,
  "most_common_action": "create_sf_case"
}
```

---

## 7. Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Web Framework** | FastAPI + Uvicorn | REST API server |
| **Agent Orchestration** | LangGraph | Workflow state machine |
| **LLM Integration** | LangChain + OpenAI | Intelligent issue analysis |
| **Data Validation** | Pydantic | Request/response schemas |
| **External APIs** | Requests | HTTP calls to SF + Billing |
| **Observability UI** | Streamlit + Plotly | Dashboard visualization |
| **Logging** | Python logging | Structured logs |
| **Environment** | python-dotenv | Configuration management |
| **Database** | SQLAlchemy (ORM) | Future DB integration |
| **Async HTTP** | SSE-Starlette | Server-Sent Events support |
| **Python Version** | 3.10+ | Modern syntax + TypedDict |

---

## 8. Deployment Instructions

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables (.env file)
OPENAI_API_KEY=sk-...
MOCK_SALESFORCE=true
MOCK_BILLING=true

# Run API server
uvicorn main:app --reload --port 8000

# In another terminal: run dashboard
streamlit run dashboard.py
```

### API Access
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Dashboard**: http://localhost:8501 (Streamlit)

---

## 9. Summary

The **Agentic Issue Resolution System** demonstrates modern AI application architecture:
- ✅ Intelligent decision-making via LLM (GPT-4o-mini)
- ✅ Robust workflow orchestration (LangGraph)
- ✅ Type-safe state management (TypedDict + Pydantic)
- ✅ Confidence gating for safety
- ✅ Multi-system integration (Salesforce + Billing API)
- ✅ Comprehensive observability (tracing + metrics + dashboard)

The modular design enables rapid iteration while maintaining production-readiness through mock modes and clear separation of concerns.
