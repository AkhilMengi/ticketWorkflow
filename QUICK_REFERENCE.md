# Agentic Issue Resolution System — Documentation Index & Quick Reference

## 📚 Documentation Overview

This project contains comprehensive documentation split into multiple files for clarity:

| Document | Purpose | Key Content |
|----------|---------|------------|
| **HLD.md** | High-Level Design | Overall architecture, components, data flow, tech stack |
| **WORKFLOW_DIAGRAM.md** | Detailed Workflows | ASCII and step-by-step diagrams of all processes |
| **ARCHITECTURE_DIAGRAMS.md** | Visual Diagrams | Mermaid diagrams for system & process visualization |
| **QUICK_REFERENCE.md** | This file | Quick lookup, key concepts, and developer guide |

---

## 🎯 Quick System Overview

### What Does This System Do?

**Agentic Issue Resolution** is an AI-powered customer support automation platform that:

1. **Receives** a customer issue report (account ID + description)
2. **Analyzes** the issue intelligently using OpenAI GPT-4o-mini
3. **Decides** what actions to take (create Salesforce case, process billing credit, etc.)
4. **Executes** those actions across integrated systems
5. **Summarizes** the resolution for the customer

### Key Innovation: Confidence-Based Gating

- LLM provides confidence score (0-10) for understanding the issue
- **If confidence < 5**: Skip API calls, return "unable to understand"
- **If confidence >= 5**: Execute recommended actions
- **Prevents expensive mistakes** from unclear issues

---

## 🏗️ System Architecture in One Picture

```
Client → FastAPI Routes → LangGraph Agent → Services → External APIs
        ↓                                      ↓
    Pydantic                           Salesforce + Billing
    Validation                         Configuration
        ↓                              ↓
    AgentState                    Mock for local dev
    (TypedDict)
```

---

## 🔄 Core Workflow (Simplified)

```
START
  ↓
1. fetch_account_node     → Load account context
  ↓
2. analyze_issue_node     → LLM analyzes + confidence scoring
  ↓
3. Conditional routing    → Based on confidence & actions
  ├─ If can't understand  → Skip to 5 (error response)
  └─ If confident & actions needed → Go to 4
  ↓
4. execute_actions_node   → Call SF API + Billing API
  ↓
5. summarize_node         → Compile human-readable response
  ↓
END → HTTP 200 with IssueResponse JSON
```

---

## 📁 Project Structure

```
ticketWorkflow/
├── HLD.md                           ← Main architecture doc
├── WORKFLOW_DIAGRAM.md              ← Detailed ASCII workflows
├── ARCHITECTURE_DIAGRAMS.md         ← Mermaid visual diagrams
├── QUICK_REFERENCE.md               ← This file
│
├── main.py                          ← FastAPI entry point
├── dashboard.py                     ← Streamlit observability UI
├── requirements.txt                 ← Python dependencies
│
├── app/
│   ├── __init__.py
│   ├── config.py                    ← Environment configuration
│   │
│   ├── api/
│   │   ├── routes.py                ← REST endpoints
│   │   └── schemas.py               ← Pydantic models
│   │
│   ├── agent/
│   │   ├── graph.py                 ← LangGraph state machine
│   │   ├── nodes.py                 ← Node functions (4 nodes)
│   │   ├── state.py                 ← AgentState TypedDict
│   │   ├── prompts.py               ← LLM system prompt
│   │   └── tracing.py               ← Execution tracing
│   │
│   └── services/
│       ├── salesforce.py            ← SF API wrapper
│       └── billing.py               ← Billing API wrapper
│
├── suggestions/                     ← Business rules directory
└── billing_tasks_log.json           ← Task logging
```

---

## 🛠️ Key Technologies

| Component | Technology | Why |
|-----------|-----------|-----|
| Web Framework | FastAPI + Uvicorn | Fast, async, auto-API docs |
| Workflow | LangGraph | Agentic workflows with conditional routing |
| LLM | OpenAI GPT-4o-mini | Intelligent analysis + cost-effective |
| Validation | Pydantic | Type-safe, auto-docs |
| Observability | Streamlit + Plotly | Dashboard, metrics visualization |
| State Mgmt | TypedDict | Type-safe shared state |
| External APIs | Requests | HTTP client for SF & Billing |

---

## 📌 Core Concepts

### 1. **AgentState (TypedDict)**
Central data structure passed through workflow:
```python
AgentState = {
    # Input
    account_id: str,
    issue_description: str,
    
    # Processing
    account_details: Dict,
    issue_analysis: str,
    confidence_score: int,
    recommended_actions: List[str],
    
    # Results
    sf_case_result: Dict,
    billing_result: Dict,
    actions_executed: List[str],
    final_summary: str,
    error: Optional[str],
}
```

### 2. **Confidence Scoring (0-10)**
- **9-10**: Crystal clear problem
- **6-8**: Pretty clear, enough details
- **4-5**: Unclear, missing info
- **0-3**: Cannot understand
- **Threshold**: >= 5 required to execute actions

### 3. **Recommended Actions**
LLM can recommend:
- `"create_sf_case"` → Create Salesforce support case
- `"call_billing_api"` → Execute billing operation
  - action_type: refund | credit | rebill | adjustment

### 4. **Conditional Routing**
```python
if confidence < 5:
    route_to("summarize")  # Error response
elif recommended_actions:
    route_to("execute_actions")  # Run APIs
else:
    route_to("summarize")  # Summary only
```

---

## 🚀 Running the System

### Local Development

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create .env file with:
OPENAI_API_KEY=sk-...
MOCK_SALESFORCE=true
MOCK_BILLING=true

# 3. Run API server
uvicorn main:app --reload --port 8000

# 4. In another terminal, run dashboard
streamlit run dashboard.py

# 5. Access:
#    - Swagger UI: http://localhost:8000/docs
#    - Dashboard: http://localhost:8501
#    - ReDoc: http://localhost:8000/redoc
```

### Example API Call

```bash
curl -X POST "http://localhost:8000/api/v1/resolve-issue" \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "ACC-1001",
    "issue_description": "Customer was double-charged $99 on 2026-04-15"
  }'
```

### Example Response

```json
{
  "account_id": "ACC-1001",
  "issue_description": "Customer was double-charged...",
  "issue_analysis": "The customer reports a duplicate charge...",
  "action_reasoning": "Confidence is high (8/10). Recommended creating SF case and processing refund.",
  "recommended_actions": ["create_sf_case", "call_billing_api"],
  "actions_executed": ["create_sf_case", "call_billing_api"],
  "sf_case_result": {
    "success": true,
    "id": "5001a000009OzrAAE",
    "case_number": "00001001"
  },
  "billing_result": {
    "success": true,
    "billing_task": {
      "transaction_id": "TXN-ACC-1001-a1b2c3d4",
      "action_type": "refund",
      "amount": 99.0,
      "status": "processed"
    }
  },
  "final_summary": "Duplicate charge identified. Refund of $99 processed. Case created for audit.",
  "error": null
}
```

---

## 📊 API Endpoints

### Issue Resolution

| Endpoint | Method | Purpose | Response |
|----------|--------|---------|----------|
| `/api/v1/resolve-issue` | POST | Sync issue resolution | IssueResponse JSON |
| `/api/v1/resolve-issue/stream` | POST | Streaming with SSE | Event stream (node progress) |
| `/api/v1/actions` | GET | List available actions | List[str] |
| `/health` | GET | Health check | {"status": "ok"} |

### Observability

| Endpoint | Method | Purpose | Response |
|----------|--------|---------|----------|
| `/api/v1/traces` | GET | Get execution history | List[Dict] (max 100) |
| `/api/v1/traces?account_id=ACC-1001` | GET | Filter by account | List[Dict] |
| `/api/v1/traces/metrics` | GET | Aggregate metrics | Metrics dict |

---

## 🔍 Understanding the 4 Nodes

### Node 1: fetch_account_node
```
Input:  account_id
Action: Lookup account from DB/CRM (currently mocked)
Output: account_details populated
Time:   ~25ms
```

### Node 2: analyze_issue_node ⭐ THE BRAIN
```
Input:  account_id, issue_description, account_details
Action: 1. Load business suggestions
        2. Build structured LLM prompt
        3. Call GPT-4o-mini API
        4. Parse JSON response
Output: issue_analysis, confidence_score, recommended_actions, payloads
Time:   ~2000-3000ms (dominated by LLM latency)
```

### Node 3: execute_actions_node ⚡ THE EXECUTOR
```
Input:  recommended_actions, sf_case_payload, billing_payload
Action: For each action:
          - create_sf_case → SF REST API call
          - call_billing_api → Billing API call
Output: sf_case_result, billing_result, actions_executed
Time:   ~300-500ms total
```

### Node 4: summarize_node 📝 THE REPORTER
```
Input:  All previous state
Action: Compile human-readable response
Output: final_summary, error (if any)
Time:   ~10ms
```

---

## 🔐 Configuration (config.py)

```python
# LLM
OPENAI_API_KEY                  # Required: sk-...

# Salesforce (Optional if MOCK_SALESFORCE=true)
SF_CLIENT_ID                    # OAuth client ID
SF_CLIENT_SECRET                # OAuth client secret
SF_LOGIN_URL                    # Usually: https://login.salesforce.com

# Billing (Optional if MOCK_BILLING=true)
BILLING_API_URL                 # External billing service

# Flags (Development)
MOCK_SALESFORCE=true            # Skip real SF API, use mock
MOCK_BILLING=true               # Skip real Billing API, use mock

# Database (Future)
DATABASE_URL                    # e.g., postgresql://...
```

---

## 🧪 Testing Strategy

### Using Mock Mode (Local Development)

```bash
# .env
MOCK_SALESFORCE=true
MOCK_BILLING=true
OPENAI_API_KEY=sk-test-...
```

**Benefits**:
- ✅ No Salesforce credentials needed
- ✅ No billing service dependencies
- ✅ Deterministic responses for testing
- ✅ Fast iteration (no API latency)

### Testing Without Real APIs

```python
# Mock responses are deterministic:

# Salesforce mock returns:
{
  "success": True,
  "id": "MOCK-ACC-1001-001",
  "case_number": "00001001"
}

# Billing mock returns:
{
  "success": True,
  "billing_task": {
    "transaction_id": "TXN-ACC-1001-<uuid>",
    "status": "processed"
  }
}
```

---

## 📈 Observability & Monitoring

### Traces (Execution History)

Each workflow execution creates a trace:
```json
{
  "timestamp": "2026-05-11T...",
  "account_id": "ACC-1001",
  "confidence_score": 8,
  "recommended_actions": ["create_sf_case", "call_billing_api"],
  "actions_executed": ["create_sf_case", "call_billing_api"],
  "status": "success",
  "duration_seconds": 3.2,
  "final_summary": "..."
}
```

### Metrics Endpoint

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

## 🚨 Error Handling

| Error Type | Handling | Response |
|-----------|----------|----------|
| Confidence < 5 | Skip actions | "Unable to understand" message |
| LLM API failure | Catch + log | error field populated |
| SF API failure | Catch + log | sf_case_result = error |
| Billing API failure | Catch + log | billing_result = error |
| JSON parse error | Catch + fallback | Treated as "cannot understand" |
| Invalid request | Pydantic validation | HTTP 422 |

---

## 🎓 Key Patterns Used

### 1. **State Machine (LangGraph)**
Each node takes state, returns updated state. Enables:
- ✅ Clear data flow
- ✅ Easy debugging (inspect state at each step)
- ✅ Reproducible workflows

### 2. **Confidence Gating**
Prevents costly mistakes when confidence < 5
- ✅ Safety: Don't execute if unsure
- ✅ Clarity: Forces explicit understanding
- ✅ UX: Users get helpful error messages

### 3. **Mock-First Architecture**
Switch to real APIs via environment variables
- ✅ Local dev without credentials
- ✅ Fast iteration
- ✅ Deterministic testing

### 4. **Lazy Singleton (LLM)**
Initialize GPT-4o-mini once, reuse:
```python
_llm: ChatOpenAI | None = None

def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(...)
    return _llm
```

### 5. **Structured Observability**
Trace every execution for:
- Metrics (success rate, avg confidence)
- Debugging (what happened at each step)
- Analytics (which actions are used most)

---

## 📝 LLM Prompt Engineering

The prompt in `prompts.py` includes:

1. **Account Context** (personalization)
   - Customer details, payment history, current status

2. **Issue Description** (the problem)
   - Exact customer complaint text

3. **Business Suggestions** (knowledge base)
   - "Check customer details"
   - "Rebill the account"
   - "Close the case"

4. **Action Availability** (what's possible)
   - create_sf_case (for tracking/escalation)
   - call_billing_api (for financial operations)

5. **Confidence Guidelines** (0-10 scale)
   - 9-10: Crystal clear
   - 6-8: Pretty clear
   - 4-5: Unclear
   - 0-3: Cannot understand

6. **Decision Rules** (logic)
   - Match issue to suggestion
   - Choose appropriate actions
   - **CRITICAL**: If confidence < 5, return empty actions

---

## 🔗 Integration Checklist

### Before Production

- [ ] Set `MOCK_SALESFORCE=false` and configure SF_CLIENT_ID, SF_CLIENT_SECRET
- [ ] Set `MOCK_BILLING=false` and configure BILLING_API_URL
- [ ] Set real OPENAI_API_KEY (not test key)
- [ ] Replace mock account lookup in fetch_account_node with real DB
- [ ] Set up PostgreSQL database (replace in-memory stores)
- [ ] Add authentication/authorization (API key or OAuth)
- [ ] Configure CORS properly (not allow all origins)
- [ ] Set up logging aggregation (not just console)
- [ ] Add SLA monitoring and alerting
- [ ] Load test with expected peak load
- [ ] Set up error tracking (Sentry, etc.)
- [ ] Configure backup/disaster recovery for traces

---

## 🎯 Success Metrics

Monitor these KPIs:

```
1. Success Rate
   = (successful_executions / total_executions) × 100
   Target: >= 95%

2. Average Confidence
   = sum(confidence_scores) / count(executions)
   Target: >= 7.0/10

3. Average Duration
   = sum(execution_times) / count(executions)
   Target: < 5 seconds

4. Action Execution Rate
   = (actions_executed / recommended_actions) × 100
   Target: >= 99%

5. User Satisfaction
   = positive_feedback_count / total_issues
   Target: >= 90%
```

---

## 🔮 Future Enhancements

### Phase 1 (Short-term)
- [ ] Real database integration (PostgreSQL)
- [ ] User authentication (API keys)
- [ ] Enhanced error retry logic (exponential backoff)
- [ ] Webhook notifications for case creation

### Phase 2 (Medium-term)
- [ ] Multi-tenant support (multiple customer orgs)
- [ ] Custom business rules engine
- [ ] Advanced analytics dashboard
- [ ] LangSmith integration for tracing
- [ ] Distributed tracing (OpenTelemetry)

### Phase 3 (Long-term)
- [ ] Fine-tuned model for specific domain
- [ ] Agentic loop (agent can ask follow-ups)
- [ ] Multi-modal input (voice, documents)
- [ ] Real-time notification system
- [ ] A/B testing framework for prompts

---

## 📚 Documentation Navigation

- **For system design**: Read [HLD.md](HLD.md)
- **For workflow details**: Read [WORKFLOW_DIAGRAM.md](WORKFLOW_DIAGRAM.md)
- **For visual diagrams**: Read [ARCHITECTURE_DIAGRAMS.md](ARCHITECTURE_DIAGRAMS.md)
- **For quick answers**: Read this file

---

## ❓ Common Questions

### Q: Why TypedDict instead of a class?
**A**: TypedDict provides type hints at runtime without runtime overhead. Perfect for state data structures that don't need methods.

### Q: Can we skip the confidence check?
**A**: Not recommended. It's a safety mechanism. If confidence < 5, the LLM itself should return empty actions. The gating is defensive.

### Q: How do we handle API timeouts?
**A**: Use exponential backoff with `tenacity` library. Currently configured in imports but can be enhanced.

### Q: Can we run multiple agents in parallel?
**A**: Yes, FastAPI supports async. Graph execution per request is synchronous, but multiple requests run in parallel.

### Q: What if OpenAI API is unavailable?
**A**: Exception is caught, logged, state marked with error, response sent with error field populated.

### Q: How is data persisted?
**A**: Currently in-memory (resets on server restart). Use DATABASE_URL config to enable PostgreSQL persistence in production.

---

## 🤝 Contributing

When adding new features:

1. **New Node**: Add to `nodes.py`, register in `graph.py`
2. **New Action**: Update ANALYZE_ISSUE_PROMPT, add to execute_actions_node
3. **New Service**: Create in `services/`, import in nodes.py
4. **New Endpoint**: Create in `routes.py`, add schema to `schemas.py`
5. **Tests**: Test with MOCK_SALESFORCE=true, MOCK_BILLING=true

---

## 📞 Support

- **Architecture Questions**: See [HLD.md](HLD.md)
- **How Things Work**: See [WORKFLOW_DIAGRAM.md](WORKFLOW_DIAGRAM.md)
- **Quick Lookup**: Read this file
- **Debugging**: Check logs in console output

---

**Last Updated**: May 11, 2026  
**System Version**: 1.0.0  
**Python Version**: 3.10+  
**LangGraph**: >= 0.1.0  
**FastAPI**: Latest
