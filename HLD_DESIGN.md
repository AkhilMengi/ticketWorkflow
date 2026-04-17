# High-Level Design (HLD) - Intelligent Salesforce Agent

## 1. System Overview

**Application Name:** Intelligent Salesforce Agent / Ticket Workflow

**Purpose:** An intelligent ticket management and support system that leverages AI agents to automatically classify, prioritize, and create Salesforce support cases based on user issues. The system uses LangGraph to orchestrate complex multi-step workflows and integrates with Salesforce as the backend CRM.

**Key Capabilities:**
- Asynchronous job processing for support tickets
- AI-driven issue classification and priority assignment
- Customer profile enrichment and context retrieval
- Automatic Salesforce case creation
- Conversational memory management (per-user context tracking)
- Event-driven architecture with detailed audit logs

---

## 2. System Architecture

### 2.1 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                             │
│                    (External API Consumers)                       │
└────────────────────────────┬──────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API GATEWAY LAYER                           │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  FastAPI Routes                                            │ │
│  │  - POST /api/jobs (Create Job)                             │ │
│  │  - GET /api/jobs/{job_id} (Get Status)                     │ │
│  │  - GET /api/jobs/{job_id}/events (Stream Events)           │ │
│  │  - GET /api/memory (User Memory)                           │ │
│  └────────────────────────────────────────────────────────────┘ │
└────────┬──────────────────────────────────────┬──────────────────┘
         │                                      │
         ▼                                      ▼
    ┌─────────────┐                    ┌──────────────────┐
    │Job Service  │                    │Memory Service    │
    │             │                    │                  │
    │- Create Job │                    │- Store Context   │
    │- Update Job │                    │- Retrieve History│
    │- Get Status │                    │- User Profiles   │
    └─────────────┘                    └──────────────────┘
         │                                      │
         ▼                                      ▼
    ┌─────────────────────────────────────────────────────────┐
    │             DATABASE LAYER (SQLite/PostgreSQL)          │
    │  ┌──────────┐  ┌────────┐  ┌────────┐  ┌────────────┐  │
    │  │  Jobs    │  │ Events │  │ Memory │  │Job History │  │
    │  │ (Status, │  │(Audit  │  │(User   │  │(Queries)   │  │
    │  │ Payload) │  │ Logs)  │  │Context)│  │            │  │
    │  └──────────┘  └────────┘  └────────┘  └────────────┘  │
    └─────────────────────────────────────────────────────────┘
         │
         ▼
    ┌───────────────────────────────────────────┐
    │      QUEUE & WORKER LAYER                 │
    │  ┌──────────────────────────────────────┐ │
    │  │  Job Queue (FIFO)                    │ │
    │  │  - Enqueue job with initial state    │ │
    │  │  - Worker thread processes jobs      │ │
    │  │  - Handles failures and retries      │ │
    │  └──────────────────────────────────────┘ │
    └──────────────────────────┬────────────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
                ▼                             ▼
    ┌──────────────────────────┐  ┌────────────────────────────┐
    │   ORCHESTRATION LAYER    │  │  INTEGRATION LAYER         │
    │  (LangGraph Agent)       │  │  (External Services)       │
    │                          │  │                            │
    │- Agent Graph Compiler   │  │┌──────────────────────────┐│
    │- State Management       │  ││ Salesforce Client        ││
    │- Node Execution        │  ││ - OAuth2 Authentication  ││
    │- Conditional Routing   │  ││ - Case Management API    ││
    │                          │  ││ - Query Customer Data    ││
    │┌────────────────────────┐│  │└──────────────────────────┘│
    ││ Agent Nodes:           ││  │                            │
    ││ 1. Decision Node       ││  │┌──────────────────────────┐│
    ││ 2. Fetch Profile Node  ││  ││ External Data Sources    ││
    ││ 3. Fetch Logs Node     ││  ││ - Customer Profiles      ││
    ││ 4. Classify Node       ││  ││ - Payment/Error Logs     ││
    ││ 5. Create Case Node    ││  ││ - LLM (OpenAI)          ││
    ││                        ││  │└──────────────────────────┘│
    ││ Flow Control:          ││  │                            │
    ││ Decision → (Fetch Prof │  │                            │
    ││            → Fetch Logs│  │                            │
    ││            → Classify) │  │                            │
    ││            → Create Case                               │
    │└────────────────────────┘│  │                            │
    └──────────────────────────┘  └────────────────────────────┘
```

---

## 3. Key Components

### 3.1 API Gateway (FastAPI)

**Location:** `app/api/`

**Responsibilities:**
- Handle incoming HTTP requests for job creation and status checks
- Validate input payloads using Pydantic schemas
- Enqueue jobs for asynchronous processing
- Return immediate feedback (job_id) to clients
- Expose event streams for real-time updates
- Serve memory/context endpoints

**Key Files:**
- `routes.py` - API endpoint definitions
- `schemas.py` - Request/Response models

**Endpoints:**
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/jobs` | Create and enqueue a new support ticket |
| GET | `/api/jobs/{job_id}` | Retrieve job status and results |
| GET | `/api/jobs/{job_id}/events` | Stream job execution events |
| GET | `/api/memory/{user_id}` | Get user's conversation history |

---

### 3.2 Job Service

**Location:** `app/services/job_service.py`

**Responsibilities:**
- Manage job lifecycle (created, queued, processing, completed, failed)
- Persist job metadata and payloads to database
- Store execution results
- Track events and audit logs
- Query job history

**Key Functions:**
- `create_job()` - Initialize new job with UUID
- `update_job()` - Update status and results
- `get_job()` - Retrieve job details
- `add_event()` - Log execution events

---

### 3.3 Agent Orchestration (LangGraph)

**Location:** `app/agent/`

**Responsibilities:**
- Compile and execute the agentic workflow
- Manage agent state transitions
- Coordinate multi-step decision making
- Route to appropriate action nodes
- Handle conditional logic and flow control

**Key Files:**
- `graph.py` - Graph definition and compilation
- `state.py` - Shared state schema (TypedDict)
- `nodes.py` - Individual node implementations
- `prompts.py` - LLM prompts for reasoning
- `memory.py` - User context and history
- `tools.py` - Helper utilities and integrations
- `validators.py` - State validation logic

**Agent Workflow:**
```
START
  │
  ▼
[Decision Node]
  │
  ├─── Route: FETCH_PROFILE ──► [Fetch Profile Node] ──┐
  │                                                      │
  ├─── Route: FETCH_LOGS ──────► [Fetch Logs Node] ───┤
  │                                                      │
  └─── Route: CREATE_CASE ────────┐                    │
                                   │                    │
                                   ▼                    ▼
                            [Classify Node] ◄───────────┘
                                   │
                                   ▼
                            [Create Case Node]
                                   │
                                   ▼
                                  END
```

---

### 3.4 Worker & Queue System

**Location:** `app/workers/worker.py`

**Responsibilities:**
- Operate a background worker thread
- Dequeue jobs from the job queue
- Execute agent graphs against job states
- Handle execution errors and retries
- Save results and long-term memory
- Emit completion events

**Key Functions:**
- `enqueue_job()` - Add job to queue
- `worker_loop()` - Background worker loop
- `start_worker()` - Initialize worker on app startup

**Workflow:**
1. Job is enqueued with initial state
2. Worker picks up job from FIFO queue
3. Updates job status to "processing"
4. Invokes agent graph with state
5. Collects result and events
6. Saves long-term memory
7. Updates job to "completed"
8. Emits completion events

---

### 3.5 Database Layer

**Location:** `app/integrations/db.py`

**Responsibilities:**
- Manage SQLAlchemy ORM models
- Initialize database tables
- Provide database session management
- Persist job records, events, and memory

**Database Schema:**

```sql
-- Jobs table: Stores job metadata and payloads
CREATE TABLE jobs (
    job_id VARCHAR PRIMARY KEY,
    status VARCHAR NOT NULL,              -- queued, processing, completed, failed
    input_payload TEXT,                   -- JSON input from client
    result_payload TEXT,                  -- JSON result from agent
    created_at DATETIME DEFAULT NOW(),
    updated_at DATETIME DEFAULT NOW()
);

-- Events table: Audit log for job execution
CREATE TABLE events (
    id VARCHAR PRIMARY KEY,
    job_id VARCHAR INDEX,
    event_type VARCHAR NOT NULL,          -- job_started, node_executed, job_completed
    payload TEXT,                          -- Event details as JSON
    created_at DATETIME DEFAULT NOW()
);

-- Memory table: Persistent user context
CREATE TABLE memory (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR INDEX,
    memory_type VARCHAR NOT NULL,         -- support_issue, user_profile, context
    payload TEXT,                          -- JSON memory content
    created_at DATETIME DEFAULT NOW()
);
```

---

### 3.6 Salesforce Integration

**Location:** `app/integrations/salesforce.py`

**Responsibilities:**
- Authenticate with Salesforce via OAuth2 Client Credentials
- Create support cases in Salesforce
- Fetch customer data from Salesforce
- Handle Salesforce API errors with retry logic
- Manage Salesforce access tokens

**Key Methods:**
- `login()` - Authenticate and obtain access token
- `create_case()` - Create a Case object in Salesforce
- `get_customer()` - Query customer records
- `get_logs()` - Retrieve customer activity logs

**Authentication Flow:**
```
App
  │
  ├─ Settings (SF_CLIENT_ID, SF_CLIENT_SECRET)
  │
  ▼
Salesforce OAuth2 Token Endpoint
  │
  ├─ Request: grant_type=client_credentials
  │
  ▼
Get: access_token, instance_url
  │
  ▼
Use Bearer token for API calls
```

---

## 4. Data Flow

### 4.1 Request-to-Response Flow

```
Client Request
  │
  ▼
[API Route: POST /api/jobs]
  ├─ Validate request payload (Pydantic)
  │
  ▼
[Job Service: create_job()]
  ├─ Generate UUID (job_id)
  ├─ Serialize input payload
  ├─ Save to DB with status="queued"
  │
  ▼
[Memory Service: get_long_term_memory()]
  ├─ Retrieve user's conversation history
  ├─ Enrich with account context
  │
  ▼
[Build Initial Agent State]
  ├─ job_id, user_id, issue_type, message
  ├─ backend_context (history, errors, tier)
  │
  ▼
[Worker: enqueue_job()]
  ├─ Add to FIFO queue
  │
  ▼
[Return CreateJobResponse]
  └─ job_id, status="queued"

═══════════════════════════════════════════════════════════════

[Background: Worker Processing]

Worker picks up job from queue
  │
  ▼
[Job Service: update_job("processing")]
  │
  ▼
[Agent Graph: invoke(initial_state)]
  │
  ├─ [Decision Node] - Analyze issue, decide next steps
  │
  ├─ Conditional branches:
  │  ├─ Fetch customer profile from external data
  │  ├─ Fetch payment/error logs
  │  ├─ Classify issue and assign priority
  │
  ├─ [Create Case Node] - Call Salesforce integration
  │
  ▼
[Collect Results & Events]
  ├─ Extract summary, category, priority
  ├─ Get case_id from Salesforce
  │
  ▼
[Job Service: update_job("completed", result)]
  │
  ▼
[Memory Service: save_long_term_memory()]
  ├─ Store issue summary for future context
  │
  ▼
[Job Service: add_event("job_completed")]
  │
  ▼
[Client polls or uses SSE to get updates]
```

### 4.2 Agent State Evolution

```
Initial State:
{
  job_id: "uuid",
  user_id: "user123",
  issue_type: "payment",
  message: "Payment failed",
  backend_context: {account_tier, recent_errors, history},
  customer_profile: null,
  logs: null,
  summary: null,
  category: null,
  priority: null,
  next_action: null,
  final_answer: null,
  case_id: null,
  retries: 0,
  event_log: []
}
         │
         ▼
Decision Node Updates:
{
  ...
  next_action: "fetch_profile"
}
         │
         ▼
Fetch Profile Node Updates:
{
  ...
  customer_profile: {name, tier, subscription_status},
  next_action: "fetch_logs"
}
         │
         ▼
Fetch Logs Node Updates:
{
  ...
  logs: ["payment_timeout", "retry_failed"],
  next_action: "create_case"
}
         │
         ▼
Classify Node Updates:
{
  ...
  summary: "Payment processing failure",
  category: "Billing",
  priority: "High"
}
         │
         ▼
Create Case Node Updates:
{
  ...
  case_id: "5001x00000XXXXX",
  final_answer: {status: "Created", case_id: ...},
  event_log: [...]
}
```

---

## 5. Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Framework** | FastAPI | HTTP API framework |
| **Web Server** | Uvicorn | ASGI server |
| **Orchestration** | LangGraph | Agent workflow orchestration |
| **LLM** | OpenAI API | AI reasoning and classification |
| **ORM** | SQLAlchemy | Database abstraction |
| **Database** | SQLite / PostgreSQL | Data persistence |
| **Auth** | OAuth2 | Salesforce authentication |
| **HTTP Client** | Requests | External API calls |
| **Resilience** | Tenacity | Retry logic |
| **Config** | python-dotenv | Environment management |
| **Streaming** | sse-starlette | Server-Sent Events (optional) |
| **Validation** | Pydantic | Input/Output validation |

---

## 6. Key Features

### 6.1 Asynchronous Job Processing
- Non-blocking job submission
- FIFO queue ensures ordered processing
- Clients can poll for results or use SSE for real-time updates

### 6.2 Multi-Step Agent Workflow
- LangGraph provides graph-based execution
- Conditional routing based on agent decisions
- Flexible state management
- Clear node responsibilities

### 6.3 Resilience & Retry Logic
- Tenacity-based retries for Salesforce API calls
- Exponential backoff strategy
- Error logging and tracking
- Failed job recovery

### 6.4 Conversational Memory
- Per-user long-term memory storage
- Issue history tracking
- Context enrichment for future tickets
- Support for proactive recommendations

### 6.5 Event Audit Trail
- Detailed event logging for compliance
- Real-time event streaming
- Complete job execution history
- Debugging and troubleshooting support

### 6.6 Seamless Salesforce Integration
- OAuth2 Client Credentials flow
- Automatic case creation
- Context-aware metadata
- Agent results embedded in cases

---

## 7. Detailed Workflow

### 7.1 Ticket Processing Workflow

```
Step 1: Client submits issue
  Input: {user_id, issue_type, message}
  Output: {job_id, status="queued"}

Step 2: Decision Node
  - Analyze issue type and customer history
  - Determine next steps: fetch_profile, fetch_logs, or create_case
  - Update state.next_action

Step 3: Fetch Profile Node (if needed)
  - Query customer database
  - Retrieve: name, tier, subscription status
  - Update state.customer_profile

Step 4: Fetch Logs Node (if needed)
  - Query payment/error logs
  - Retrieve: recent transactions, system errors
  - Update state.logs

Step 5: Classify Node
  - Use LLM to analyze gathered context
  - Assign: category, priority, summary
  - Update: state.{category, priority, summary}

Step 6: Create Case Node
  - Call Salesforce API
  - Create Case with metadata from agent state
  - Receive: case_id
  - Update state.{case_id, final_answer}

Step 7: Completion
  - Save user memory for future context
  - Update job to "completed"
  - Emit completion event
  - Client receives notification
```

---

## 8. API Contract

### 8.1 Create Job Request
```json
POST /api/jobs
Content-Type: application/json

{
  "user_id": "user123",
  "issue_type": "payment|technical|billing|account",
  "message": "Customer's issue description",
  "context": {} // optional additional context
}
```

### 8.2 Create Job Response
```json
200 OK
Content-Type: application/json

{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued"
}
```

### 8.3 Get Job Status
```json
GET /api/jobs/550e8400-e29b-41d4-a716-446655440000

Response:
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "result": {
    "summary": "Payment processing failure",
    "category": "Billing",
    "priority": "High",
    "case_id": "5001x00000XXXXX",
    "final_answer": {
      "status": "Created",
      "case_id": "5001x00000XXXXX"
    }
  }
}
```

### 8.4 Stream Job Events
```
GET /api/jobs/{job_id}/events

Response: Server-Sent Events stream
data: {"type": "job_started", "timestamp": "2024-01-01T00:00:00Z"}
data: {"type": "node_executed", "node": "fetch_profile", "timestamp": "..."}
data: {"type": "node_executed", "node": "classify", "timestamp": "..."}
data: {"type": "job_completed", "case_id": "...", "timestamp": "..."}
```

---

## 9. Database Schema Details

### Jobs Table
```python
class JobRecord(Base):
    __tablename__ = "jobs"
    
    job_id: str               # Primary key, UUID
    status: str               # queued | processing | completed | failed
    input_payload: str        # JSON serialized input
    result_payload: str       # JSON serialized agent output
    created_at: datetime      # Timestamp
    updated_at: datetime      # Last modification time
    
    # Indexes: job_id (primary), status (for filtering)
```

### Events Table
```python
class EventRecord(Base):
    __tablename__ = "events"
    
    id: str                   # Primary key, UUID
    job_id: str               # Foreign key reference
    event_type: str           # job_started | node_executed | job_completed | job_failed
    payload: str              # JSON event details
    created_at: datetime      # Timestamp
    
    # Indexes: job_id (for job history), event_type (for filtering)
```

### Memory Table
```python
class MemoryRecord(Base):
    __tablename__ = "memory"
    
    id: str                   # Primary key, UUID
    user_id: str              # Foreign key reference
    memory_type: str          # support_issue | user_profile | context
    payload: str              # JSON memory content
    created_at: datetime      # Timestamp
    
    # Indexes: user_id (for user context retrieval)
```

---

## 10. Error Handling & Resilience

### 10.1 Retry Strategy
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def salesforce_api_call():
    # Exponential backoff: 2s, 4s, 8s... max 10s
    # Retries on network errors, timeouts
```

### 10.2 Error Scenarios
- **Job Creation Failure** → Caught by service, return 500
- **Salesforce Auth Failure** → Retry 3x, then fail job
- **Job Processing Failure** → Log error, update job to "failed"
- **Database Connection Error** → Caught, raise exception
- **State Validation Error** → Caught in validators, logged

### 10.3 Observability
- Structured logging with job_id context
- Event audit trail for debugging
- Database Event Records for traceability
- Error traceback capture in job logs

---

## 11. Scalability Considerations

### 11.1 Current Architecture
- Single-threaded worker (suitable for low to medium volume)
- In-memory job queue (lost on restart)
- SQLite default (suitable for single instance)

### 11.2 Scaling Strategies

#### For Higher Volume:
1. **Replace in-memory queue with message broker**
   - Use Celery + Redis/RabbitMQ
   - Multiple worker processes/machines
   - Persistent queue

2. **Switch to production database**
   - PostgreSQL with connection pooling
   - Replicas for read queries
   - Backups and disaster recovery

3. **Horizontal scaling**
   - Multiple API instances behind load balancer
   - Shared stateless processing
   - Centralized job queue

#### Architecture v2.0:
```
Load Balancer
  ├─ API Instance 1
  ├─ API Instance N
       │
       ▼
   Redis Queue (Celery)
       │
   ┌───┴────┬──────────┐
   ▼        ▼          ▼
 Worker  Worker    Worker
  Pool     Pool     Pool

   Shared PostgreSQL + Redis Cache
```

### 11.3 Performance Optimization
- Add caching layer (Redis) for customer profiles
- Batch events before writing to DB
- Consider async database queries
- Implement rate limiting for external APIs

---

## 12. Deployment Architecture

### 12.1 Development Setup
```
Local Machine
  ├─ Python Virtual Environment
  ├─ SQLite Database
  ├─ FastAPI + Uvicorn
  ├─ Worker Thread
  └─ .env file with Salesforce credentials
```

### 12.2 Production Setup
```
Load Balancer (nginx/AWS ELB)
  │
  ├─ API Container 1 (Docker)
  ├─ API Container N
  │
  ├─ Worker Pool (Kubernetes/Container)
  │
  ├─ Message Queue (RabbitMQ/Redis)
  │
  ├─ PostgreSQL (Managed DB)
  │
  └─ Redis Cache (Session/Memory)

CI/CD Pipeline:
  Test → Build → Deploy to Staging → Deploy to Production
```

### 12.3 Environment Variables
```
# Salesforce Configuration
SF_LOGIN_URL=https://login.salesforce.com
SF_CLIENT_ID=xxxx
SF_CLIENT_SECRET=xxxx

# Database
DATABASE_URL=sqlite:///./app.db
# or: postgresql://user:pass@localhost/dbname

# LLM
OPENAI_API_KEY=sk-xxxx

# Worker
WORKER_THREADS=1
QUEUE_SIZE=10000
```

---

## 13. Security Considerations

### 13.1 Authentication & Authorization
- Salesforce OAuth2 with client credentials
- API key validation for client requests (future enhancement)
- User ID tracking for audit logs

### 13.2 Data Protection
- Credentials stored in environment variables (never in code)
- HTTPS for API endpoints (in production)
- Sensitive data in memory marked for cleanup
- Database encryption at rest (production requirement)

### 13.3 Input Validation
- Pydantic schema validation on all API inputs
- SQL injection prevention via ORM
- XSS prevention in event payloads

---

## 14. Monitoring & Observability

### 14.1 Metrics to Track
- **Throughput:** Jobs/minute processed
- **Latency:** Job completion time (p50, p95, p99)
- **Errors:** Job failure rate, Salesforce API errors
- **Queue:** Job queue depth, processing time per job
- **Resources:** CPU, memory, database connections

### 14.2 Logging Strategy
```
Level: INFO
Format: timestamp | job_id | user_id | event | details

Example:
2024-01-01 12:00:00 | job-uuid | user123 | JOB_CREATED | issue_type=payment
2024-01-01 12:00:01 | job-uuid | user123 | NODE_EXECUTED | node=fetch_profile
2024-01-01 12:00:02 | job-uuid | user123 | SF_API_CALL | status=201, case_id=xxxx
2024-01-01 12:00:03 | job-uuid | user123 | JOB_COMPLETED | duration=3.2s
```

### 14.3 Alerting
- Failed jobs (alert after 3 retries)
- Long-running jobs (>5min → investigate)
- Salesforce API downtime
- High queue depth (> 1000 jobs)
- Database connection errors

---

## 15. Configuration & Customization

### 15.1 Configurable Aspects
- Number of retry attempts for Salesforce API
- Exponential backoff parameters
- LLM model and temperature for classification
- Job timeout thresholds
- Queue size limits
- Database connection pooling

### 15.2 Feature Flags (Future)
- Enable/disable memory persistence
- A/B test different classification models
- Toggle Salesforce integration (mock mode)
- Enable/disable event streaming

---

## 16. Summary

This **Intelligent Salesforce Agent** is a production-ready, scalable system that:

✅ **Receives** customer support issues via REST API  
✅ **Processes** them asynchronously using an AI agent  
✅ **Enriches** context from customer profiles and logs  
✅ **Classifies** issues using LLM reasoning  
✅ **Integrates** with Salesforce for case creation  
✅ **Persists** memory for continuous learning  
✅ **Tracks** execution with audit logs  
✅ **Scales** from single-server to distributed deployment  

### Next Steps for Deployment:
1. Add API authentication (JWT/API keys)
2. Set up PostgreSQL for production
3. Dockerize application
4. Implement monitoring/alerting
5. Add comprehensive test coverage
6. Document API with OpenAPI/Swagger
7. Set up CI/CD pipeline
8. Scale to message queue + worker pool if needed

---

## Appendix: File Structure Reference

```
ticketWorkflow/
├── app/
│   ├── __init__.py
│   ├── config.py                    # Settings, env vars
│   ├── main.py                      # FastAPI app initialization
│   ├── agent/
│   │   ├── graph.py                 # LangGraph compilation
│   │   ├── state.py                 # AgentState schema
│   │   ├── nodes.py                 # Node implementations
│   │   ├── prompts.py               # LLM prompts
│   │   ├── memory.py                # Memory management
│   │   ├── tools.py                 # Helper functions
│   │   └── validators.py            # State validation
│   ├── api/
│   │   ├── routes.py                # API endpoints
│   │   └── schemas.py               # Request/response models
│   ├── integrations/
│   │   ├── db.py                    # SQLAlchemy models
│   │   └── salesforce.py            # SF client
│   ├── services/
│   │   └── job_service.py           # Job lifecycle mgmt
│   └── workers/
│       └── worker.py                # Job queue worker
├── tests/
│   ├── test_sf_auth.py              # Salesforce auth tests
│   └── test_sf.py                   # Salesforce API tests
├── requirements.txt
├── run.py                            # Entry point
└── HLD_DESIGN.md                     # This document
```

