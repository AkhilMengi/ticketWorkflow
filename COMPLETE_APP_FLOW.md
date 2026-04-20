# Complete App Flow - Line by Line Explanation

## 📍 Table of Contents
1. [Entry Point: main.py](#1-entry-point)
2. [API Layer: routes.py](#2-api-layer)
3. [State Management: routing_state.py](#3-state-management)
4. [Classification Engine: router.py](#4-classification)
5. [Node Implementations: routing_nodes.py](#5-node-implementations)
6. [Orchestration: routing_graph.py](#6-orchestration)
7. [Service Adapters: adapters.py](#7-service-adapters)
8. [Salesforce Integration: salesforce.py](#8-salesforce-integration)
9. [Background Worker: worker.py](#9-background-worker)
10. [Live Executor: tests/live_executor.py](#10-live-executor)

---

## 1. ENTRY POINT: `app/main.py`

**Purpose:** FastAPI application bootstrap

```python
# Line 1-5: Imports FastAPI and database initialization
from fastapi import FastAPI
from app.api.routes import router
from app.integrations.db import init_db
from app.workers.worker import start_worker

# Line 7-10: Create FastAPI application instance
app = FastAPI(title="Intelligent Salesforce Agent")

# Line 12-15: STARTUP EVENT - Runs when server starts
@app.on_event("startup")
async def startup_event():
    init_db()           # Initialize SQLite database with job table
    start_worker()      # Start background worker for async job processing

# Line 17-19: Include API routes from routes.py
app.include_router(router, prefix="/api")

# Line 21-22: Health check endpoint
@app.get("/health")
async def health():
    return {"status": "ok"}
```

**What happens:**
1. Creates FastAPI app
2. On startup: Database initialized + worker starts
3. All requests to `/api/` get routed to routes.py

---

## 2. API LAYER: `app/api/routes.py`

**Purpose:** REST API endpoints that accept customer requests

### Endpoint 1: Create Job (POST /api/jobs)

```python
# Lines 45-65: CREATE JOB endpoint
@router.post("/jobs", response_model=JobResponse)
async def create_agent_job(request: CreateJobRequest):
    """
    Accepts customer request and creates async routing job
    """
    # Step 1: Generate unique job ID
    job_id = str(uuid.uuid4())
    
    # Step 2: Create job record in database
    db_job = Job(
        id=job_id,
        user_id=request.user_id,
        status="pending",
        created_at=datetime.now()
    )
    db.add(db_job)
    db.commit()
    
    # Step 3: Enqueue job to background worker
    job_queue.put({
        "job_id": job_id,
        "user_id": request.user_id,
        "message": request.message,
        "issue_type": request.issue_type,
        "backend_context": request.backend_context or {}
    })
    
    # Step 4: Return response to client (job is now processing)
    return JobResponse(
        job_id=job_id,
        status="queued",
        message="Job enqueued for processing"
    )
```

**Input:**
```json
{
  "user_id": "customer_123",
  "message": "I was charged twice",
  "issue_type": "billing_issue",
  "backend_context": {"amount": 150}
}
```

**Output:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Job enqueued for processing"
}
```

### Endpoint 2: Get Job Result (GET /api/jobs/{job_id})

```python
# Lines 67-85: GET JOB endpoint
@router.get("/jobs/{job_id}", response_model=JobDetailResponse)
async def get_job(job_id: str):
    """
    Get job status and result
    """
    # Step 1: Query database for job
    db_job = db.query(Job).filter(Job.id == job_id).first()
    
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Step 2: Return job details
    return JobDetailResponse(
        job_id=db_job.id,
        status=db_job.status,           # "pending", "processing", "completed", "failed"
        result=db_job.result,            # Final aggregated response
        created_at=db_job.created_at,
        completed_at=db_job.completed_at
    )
```

**Response when complete:**
```json
{
  "job_id": "550e8400...",
  "status": "completed",
  "result": {
    "status": "success",
    "system": "billing",
    "message": "Credit of $150 applied to your account",
    "transaction_id": "TXN_BEE801E80B5B"
  }
}
```

---

## 3. STATE MANAGEMENT: `app/agent/routing_state.py`

**Purpose:** Defines the data structure that flows through the entire system

```python
# Lines 1-50: Define EnhancedAgentState TypedDict
from typing import TypedDict, List, Dict, Optional

class EnhancedAgentState(TypedDict):
    """
    Complete state object that carries data through the entire workflow
    """
    
    # ORIGINAL FIELDS (from base agent)
    job_id: str                      # Unique request ID
    user_id: str                     # Customer ID
    message: str                     # Customer request text
    issue_type: str                  # Type hint: "billing_issue", "technical_support", etc
    backend_context: Dict            # System data: account_id, subscription, amount, etc
    
    customer_profile: Optional[Dict] # Optional: Fetched customer data
    logs: List[str]                 # Any relevant logs from backend
    summary: Optional[str]          # Initial summary from classifier
    category: Optional[str]         # Category hint
    priority: Optional[str]         # Priority level
    case_id: Optional[str]          # Existing case ID if known
    
    # ROUTING FIELDS (NEW - Added by routing_node)
    target_system: str              # "salesforce" or "billing" or "unknown"
    routing_confidence: float       # 0.0 to 1.0, how sure are we?
    routing_rationale: str          # "Why did we choose this system?"
    routing_metadata: Dict          # Details: keywords_matched, rules_triggered, scores
    needs_manual_review: bool       # Is human review needed?
    
    # EXECUTION RESULTS (Updated by sf_execution or billing_execution nodes)
    sf_case_id: Optional[str]       # Case created: "00012345678ABC"
    sf_status: Optional[str]        # SF action status: "success", "failed", "duplicate"
    sf_action_taken: Optional[str]  # "CREATE_CASE", "UPDATE_CASE", etc
    sf_error: Optional[str]         # Error message if SF failed
    
    billing_transaction_id: Optional[str]  # Transaction: "TXN_BEE801E80B5B"
    billing_status: Optional[str]          # "credit_applied", "invoice_generated", etc
    billing_action_taken: Optional[str]    # "APPLY_CREDIT", "PROCESS_INVOICE", etc
    billing_error: Optional[str]           # Error message if billing failed
    
    # FINAL AGGREGATION (Set by aggregation_node)
    aggregated_response: Dict       # Customer-facing response
    aggregated_status: str          # Overall status
    final_answer: Optional[str]     # What to tell customer
    
    # AUDIT TRAIL
    event_log: List[Dict]           # Every action logged here
    
    # CONTROL
    retries: int                    # Number of retries (for error recovery)
```

**Helper Function:**

```python
# Lines 60-90: Create state from basic request
def create_enhanced_state(base_state: Dict) -> EnhancedAgentState:
    """
    Converts a basic request dict to a full EnhancedAgentState
    """
    return EnhancedAgentState(
        job_id=base_state.get('job_id'),
        user_id=base_state.get('user_id'),
        message=base_state.get('message'),
        issue_type=base_state.get('issue_type', 'general'),
        backend_context=base_state.get('backend_context', {}),
        
        # Initialize optional fields as None/empty
        customer_profile=None,
        logs=[],
        summary=None,
        case_id=None,
        
        # Routing fields (will be filled by routing_node)
        target_system='unknown',
        routing_confidence=0.0,
        routing_rationale='',
        routing_metadata={},
        needs_manual_review=False,
        
        # Execution results (will be filled later)
        sf_case_id=None,
        sf_status=None,
        billing_transaction_id=None,
        billing_status=None,
        
        # Aggregation (will be filled by aggregation_node)
        aggregated_response={},
        aggregated_status='pending',
        final_answer=None,
        
        event_log=[],
        retries=0
    )
```

**State Flow Example:**

```
User Input (API):
{
  "user_id": "cust_123",
  "message": "I was charged $150 twice",
  "issue_type": "billing_issue"
}

↓ create_enhanced_state()

Enhanced State (passed through workflow):
{
  job_id: "550e8400...",
  user_id: "cust_123",
  message: "I was charged $150 twice",
  issue_type: "billing_issue",
  backend_context: {},
  
  target_system: "unknown",           ← Will be filled by routing_node
  routing_confidence: 0.0,            ← Will be filled by routing_node
  ...
  
  billing_transaction_id: "TXN_...",  ← Will be filled by billing_execution_node
  billing_status: "credit_applied",   ← Will be filled by billing_execution_node
  ...
}
```

---

## 4. CLASSIFICATION ENGINE: `app/agent/router.py`

**Purpose:** Intelligently decides which system (SF or Billing) should handle the request

### Main Classification Function

```python
# Lines 1-30: Import and setup
from enum import Enum
from typing import Dict, Tuple
import json
from openai import OpenAI

class System(Enum):
    SALESFORCE = "salesforce"
    BILLING = "billing"
    UNKNOWN = "unknown"

# Lines 32-50: Keyword databases
BILLING_KEYWORDS = {
    "invoice", "billing", "payment", "refund", "charge", "balance",
    "subscription", "credit", "transaction", "amount", "bill",
    "duplicate", "charged", "fee", "cost", "currency", "rate"
}

SF_KEYWORDS = {
    "bug", "issue", "problem", "ticket", "support", "feature",
    "error", "timeout", "unable", "not working", "403", "404",
    "500", "crash", "help", "request", "urgent", "case"
}

# Lines 52-80: Issue type mappings
ISSUE_TYPE_MAPPING = {
    "billing_issue": System.BILLING,
    "payment_failed": System.BILLING,
    "refund_request": System.BILLING,
    "invoice_question": System.BILLING,
    
    "technical_support": System.SALESFORCE,
    "bug_report": System.SALESFORCE,
    "feature_request": System.SALESFORCE,
    "account_access": System.SALESFORCE
}
```

### Classification Algorithm (4-Tier Priority)

```python
# Lines 82-150: Main classification method
class RoutingClassifier:
    
    def classify_and_route(self, state: EnhancedAgentState) -> Dict:
        """
        Intelligent 4-level classification with fallback
        """
        
        # TIER 1: Issue Type Mapping (HIGHEST PRIORITY - 95% confidence)
        # ================================================================
        print("[TIER 1] Checking issue type mapping...")
        if state["issue_type"] in ISSUE_TYPE_MAPPING:
            target = ISSUE_TYPE_MAPPING[state["issue_type"]]
            return {
                "target_system": target,
                "confidence": 0.95,
                "rationale": f"Determined by issue type: {state['issue_type']}",
                "metadata": {
                    "tier": 1,
                    "method": "issue_type_mapping"
                }
            }
        
        # TIER 2: Context Rules (85% confidence)
        # ================================================================
        print("[TIER 2] Checking context rules...")
        context_result = self.check_context_rules(state["backend_context"])
        if context_result:
            return {
                "target_system": context_result["system"],
                "confidence": 0.85,
                "rationale": context_result["reason"],
                "metadata": {
                    "tier": 2,
                    "method": "context_rules",
                    "rules_triggered": context_result.get("rules", [])
                }
            }
        
        # TIER 3: Keyword Scoring (70% confidence if clear winner)
        # ================================================================
        print("[TIER 3] Analyzing keywords...")
        sf_score, billing_score = self.score_keywords(state["message"])
        
        print(f"  SF Score: {sf_score:.2f}")
        print(f"  Billing Score: {billing_score:.2f}")
        
        if sf_score > 0.3 and sf_score > billing_score:
            return {
                "target_system": System.SALESFORCE,
                "confidence": min(0.85, sf_score),
                "rationale": f"Keyword analysis: {int(sf_score*100)}% confidence toward Salesforce",
                "metadata": {
                    "tier": 3,
                    "method": "keyword_scoring",
                    "sf_score": sf_score,
                    "billing_score": billing_score
                }
            }
        
        if billing_score > 0.3 and billing_score > sf_score:
            return {
                "target_system": System.BILLING,
                "confidence": min(0.85, billing_score),
                "rationale": f"Keyword analysis: {int(billing_score*100)}% confidence toward Billing",
                "metadata": {
                    "tier": 3,
                    "method": "keyword_scoring",
                    "sf_score": sf_score,
                    "billing_score": billing_score
                }
            }
        
        # TIER 4: LLM Fallback (50-70% confidence)
        # ================================================================
        print("[TIER 4] Using LLM for intelligent classification...")
        llm_result = self.classify_with_llm(state["message"])
        
        return {
            "target_system": llm_result["system"],
            "confidence": llm_result["confidence"],
            "rationale": llm_result["reasoning"],
            "metadata": {
                "tier": 4,
                "method": "llm_classification",
                "scores": {
                    "sf_score": sf_score,
                    "billing_score": billing_score
                }
            }
        }
    
    # TIER 2: Context Rules
    def check_context_rules(self, backend_context: Dict) -> Optional[Dict]:
        """
        Business logic rules based on backend context
        """
        
        # Rule 1: Large payment amounts should go to Billing
        if backend_context.get("amount", 0) > 500:
            return {
                "system": System.BILLING,
                "reason": "Large payment amount (>$500) requires billing review",
                "rules": ["amount_threshold"]
            }
        
        # Rule 2: Billing period info → Billing
        if "billing_period" in backend_context or "billing_date" in backend_context:
            return {
                "system": System.BILLING,
                "reason": "Billing context detected in backend data",
                "rules": ["billing_context"]
            }
        
        # Rule 3: Existing case ID → Salesforce (update existing case)
        if backend_context.get("case_id"):
            return {
                "system": System.SALESFORCE,
                "reason": "Existing case ID found, routing to Salesforce for update",
                "rules": ["existing_case"]
            }
        
        # Rule 4: Recent ticket references → Salesforce
        if "ticket_number" in backend_context or "support_ticket" in backend_context:
            return {
                "system": System.SALESFORCE,
                "reason": "Ticket reference found",
                "rules": ["ticket_reference"]
            }
        
        # Rule 5: Billing fields in context → Billing
        billing_fields = ["invoice_id", "subscription_id", "payment_method", "account_balance"]
        if any(field in backend_context for field in billing_fields):
            return {
                "system": System.BILLING,
                "reason": "Billing-related fields detected",
                "rules": ["billing_fields"]
            }
        
        return None
    
    # TIER 3: Keyword Scoring
    def score_keywords(self, message: str) -> Tuple[float, float]:
        """
        Returns (sf_score, billing_score) normalized to 0-1
        """
        message_lower = message.lower()
        
        # Count matches
        sf_matches = sum(1 for kw in SF_KEYWORDS if kw in message_lower)
        billing_matches = sum(1 for kw in BILLING_KEYWORDS if kw in message_lower)
        
        # Normalize by total keywords
        sf_score = sf_matches / len(SF_KEYWORDS)
        billing_score = billing_matches / len(BILLING_KEYWORDS)
        
        return sf_score, billing_score
    
    # TIER 4: LLM Classification
    def classify_with_llm(self, message: str) -> Dict:
        """
        Use GPT-4o-mini as intelligent fallback
        """
        client = OpenAI()
        
        prompt = f"""
        Classify this customer request as either SALESFORCE or BILLING.
        
        SALESFORCE handles: technical issues, bugs, feature requests, account access problems
        BILLING handles: payment issues, invoices, refunds, charges, subscriptions
        
        Request: "{message}"
        
        Respond with JSON:
        {{"system": "salesforce" or "billing", "confidence": 0.0-1.0, "reasoning": "why"}}
        """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        result = json.loads(response.choices[0].message.content)
        
        return {
            "system": System(result["system"]),
            "confidence": result["confidence"],
            "reasoning": result["reasoning"]
        }
```

**Example Classification:**

```
INPUT:
message = "I was charged $150 twice"
issue_type = "billing_issue"

CLASSIFICATION STEPS:

Tier 1: Check issue_type
  ✓ "billing_issue" → System.BILLING
  ✓ Confidence: 0.95
  ✓ Early return (no need for other tiers)

OUTPUT:
{
  "target_system": "billing",
  "confidence": 0.95,
  "rationale": "Determined by issue type: billing_issue",
  "metadata": {"tier": 1, "method": "issue_type_mapping"}
}
```

---

## 5. NODE IMPLEMENTATIONS: `app/agent/routing_nodes.py`

**Purpose:** Individual workflow nodes that process the state

### Node 1: Routing Node

```python
# Lines 1-50: Routing Node
def routing_node(state: EnhancedAgentState) -> Dict:
    """
    Classifies the request and determines target system
    """
    
    print(f"[ROUTING] Analyzing request for user {state['user_id']}")
    
    # Step 1: Create classifier instance
    classifier = RoutingClassifier()
    
    # Step 2: Classify the request
    classification = classifier.classify_and_route(state)
    
    # Step 3: Extract results
    target_system = classification["target_system"]
    confidence = classification["confidence"]
    rationale = classification["rationale"]
    metadata = classification["metadata"]
    
    print(f"[ROUTING] Classification: {target_system} (confidence: {confidence:.0%})")
    print(f"[ROUTING] Rationale: {rationale}")
    
    # Step 4: Determine if manual review needed
    needs_manual_review = confidence < 0.60
    
    if needs_manual_review:
        print("[ROUTING] ⚠️ Low confidence - flagging for manual review")
        target_system = System.UNKNOWN
    
    # Step 5: Update state with routing decision
    state["target_system"] = target_system
    state["routing_confidence"] = confidence
    state["routing_rationale"] = rationale
    state["routing_metadata"] = metadata
    state["needs_manual_review"] = needs_manual_review
    
    # Step 6: Log event
    state["event_log"].append({
        "type": "routing_decision",
        "target_system": str(target_system),
        "confidence": confidence,
        "timestamp": datetime.now().isoformat()
    })
    
    return state
```

### Node 2: Salesforce Execution Node

```python
# Lines 52-130: SF Execution Node
def sf_execution_node(state: EnhancedAgentState, sf_adapter) -> Dict:
    """
    Executes Salesforce action (create or update case)
    """
    
    if state["target_system"] != System.SALESFORCE:
        return state  # Skip if not routed to SF
    
    print(f"[SF_EXEC] Executing Salesforce action for user {state['user_id']}")
    
    try:
        # Step 1: Determine action (CREATE vs UPDATE)
        if state.get("case_id"):
            action = ActionType.UPDATE_CASE
            print(f"[SF_EXEC] Case exists: {state['case_id']} - will UPDATE")
        else:
            action = ActionType.CREATE_CASE
            print(f"[SF_EXEC] No existing case - will CREATE new case")
        
        # Step 2: Prepare payload
        payload = {
            "subject": state["message"][:255],  # SF has 255 char limit
            "description": state["message"],
            "origin": "Agentic",
            "type": state.get("category", "Problem"),
            "contact_id_or_email": state["user_id"],
            "backend_context": state["backend_context"]
        }
        
        # Step 3: Execute through adapter
        result = sf_adapter.execute_action(action, payload)
        
        # Step 4: Check if successful
        if result["success"]:
            print(f"[SF_EXEC] SUCCESS - Case: {result['result_id']}")
            
            state["sf_case_id"] = result["result_id"]  # e.g., "00012345678ABC"
            state["sf_status"] = result["status"]      # e.g., "created"
            state["sf_action_taken"] = str(action)     # e.g., "CREATE_CASE"
            state["sf_error"] = None
            
            state["execution_system"] = "salesforce"
        else:
            print(f"[SF_EXEC] FAILED - Error: {result.get('error')}")
            
            state["sf_status"] = "failed"
            state["sf_error"] = result.get("error")
            state["sf_action_taken"] = str(action)
        
        # Step 5: Log event
        state["event_log"].append({
            "type": "sf_execution",
            "action": str(action),
            "status": state["sf_status"],
            "case_id": state.get("sf_case_id"),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"[SF_EXEC] ERROR: {str(e)}")
        state["sf_status"] = "error"
        state["sf_error"] = str(e)
    
    return state
```

### Node 3: Billing Execution Node

```python
# Lines 132-210: Billing Execution Node
def billing_execution_node(state: EnhancedAgentState, billing_adapter) -> Dict:
    """
    Executes Billing action (credit, refund, invoice)
    """
    
    if state["target_system"] != System.BILLING:
        return state  # Skip if not routed to Billing
    
    print(f"[BILLING_EXEC] Executing billing action for user {state['user_id']}")
    
    try:
        # Step 1: Determine billing action based on keywords
        message_lower = state["message"].lower()
        
        if any(w in message_lower for w in ["refund", "charged twice", "duplicate"]):
            action = ActionType.APPLY_CREDIT
            print(f"[BILLING_EXEC] Detected duplicate charge - APPLY_CREDIT")
            
        elif any(w in message_lower for w in ["invoice", "bill", "statement"]):
            action = ActionType.PROCESS_INVOICE
            print(f"[BILLING_EXEC] Detected invoice question - PROCESS_INVOICE")
            
        elif any(w in message_lower for w in ["refund", "money back"]):
            action = ActionType.PROCESS_REFUND
            print(f"[BILLING_EXEC] Detected refund request - PROCESS_REFUND")
            
        else:
            action = ActionType.UPDATE_BILLING_ACCOUNT
            print(f"[BILLING_EXEC] Default to UPDATE_BILLING_ACCOUNT")
        
        # Step 2: Prepare payload
        payload = {
            "user_id": state["user_id"],
            "amount": state["backend_context"].get("amount", 0),
            "reason": state["message"],
            "timestamp": datetime.now().isoformat()
        }
        
        # Step 3: Execute through adapter
        result = billing_adapter.execute_action(action, payload)
        
        # Step 4: Check if successful
        if result["success"]:
            print(f"[BILLING_EXEC] SUCCESS - Transaction: {result['result_id']}")
            
            state["billing_transaction_id"] = result["result_id"]  # e.g., "TXN_BEE801E80B5B"
            state["billing_status"] = result["status"]              # e.g., "credit_applied"
            state["billing_action_taken"] = str(action)             # e.g., "APPLY_CREDIT"
            state["billing_error"] = None
            
            state["execution_system"] = "billing"
        else:
            print(f"[BILLING_EXEC] FAILED - Error: {result.get('error')}")
            
            state["billing_status"] = "failed"
            state["billing_error"] = result.get("error")
            state["billing_action_taken"] = str(action)
        
        # Step 5: Log event
        state["event_log"].append({
            "type": "billing_execution",
            "action": str(action),
            "status": state["billing_status"],
            "transaction_id": state.get("billing_transaction_id"),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"[BILLING_EXEC] ERROR: {str(e)}")
        state["billing_status"] = "error"
        state["billing_error"] = str(e)
    
    return state
```

### Node 4: Aggregation Node

```python
# Lines 212-280: Aggregation Node
def aggregation_node(state: EnhancedAgentState) -> Dict:
    """
    Combines execution results into customer-facing response
    """
    
    print(f"[AGGREGATION] Combining results for user {state['user_id']}")
    
    # Step 1: Determine status
    execution_system = state.get("execution_system")
    
    if execution_system == "salesforce":
        sf_status = state.get("sf_status")
        
        if sf_status == "success":
            status = "success"
            message = f"We've created a support case for your request. Case ID: {state['sf_case_id']}"
        elif sf_status == "duplicate":
            status = "success"
            message = f"Found existing case {state['sf_case_id']} and updated it with your request"
        else:
            status = "error"
            message = f"Failed to create case: {state.get('sf_error', 'Unknown error')}"
    
    elif execution_system == "billing":
        billing_status = state.get("billing_status")
        
        if billing_status == "credit_applied":
            status = "success"
            message = f"Credit has been applied to your account. Transaction: {state['billing_transaction_id']}"
        elif billing_status == "invoice_generated":
            status = "success"
            message = f"Invoice generated. You can download it shortly. Ref: {state['billing_transaction_id']}"
        else:
            status = "error"
            message = f"Failed to process billing: {state.get('billing_error', 'Unknown error')}"
    
    else:
        status = "escalated"
        message = "Your request has been escalated to our support team for personal attention"
    
    # Step 2: Build customer response
    aggregated_response = {
        "status": status,
        "system": execution_system or "manual_review",
        "message": message,
        "case_id": state.get("sf_case_id"),
        "transaction_id": state.get("billing_transaction_id"),
        "timestamp": datetime.now().isoformat()
    }
    
    # Step 3: Update state
    state["aggregated_response"] = aggregated_response
    state["aggregated_status"] = status
    state["final_answer"] = message
    
    print(f"[AGGREGATION] Final status: {status}")
    
    # Step 4: Log event
    state["event_log"].append({
        "type": "aggregation",
        "aggregated_status": status,
        "timestamp": datetime.now().isoformat()
    })
    
    return state
```

---

## 6. ORCHESTRATION: `app/agent/routing_graph.py`

**Purpose:** Combines all nodes into a LangGraph workflow

```python
# Lines 1-30: Imports and setup
from langgraph.graph import StateGraph, END
from typing import Literal
from app.agent.routing_nodes import (
    routing_node, sf_execution_node, billing_execution_node, 
    aggregation_node, manual_review_node, decide_node, 
    fetch_profile_node, fetch_logs_node
)
from app.agent.adapters import SalesforceAdapter, BillingAdapter
from app.agent.routing_state import EnhancedAgentState

# Lines 32-120: Build the graph
def build_routing_graph():
    """
    Creates complete LangGraph workflow
    """
    
    # Step 1: Create StateGraph with EnhancedAgentState
    graph = StateGraph(EnhancedAgentState)
    
    # Initialize adapters
    sf_adapter = SalesforceAdapter()
    billing_adapter = BillingAdapter()
    
    # ========== ENRICHMENT PHASE ==========
    # Step 2: Add enrichment nodes (original workflow)
    graph.add_node("decide", decide_node)
    graph.add_node("fetch_profile", fetch_profile_node)
    graph.add_node("fetch_logs", fetch_logs_node)
    
    # Add edges for enrichment loop
    graph.add_edge("decide", "fetch_profile")
    graph.add_edge("fetch_profile", "fetch_logs")
    graph.add_edge("fetch_logs", "decide")  # Loop back
    
    # Add conditional edge to exit enrichment loop
    def decide_to_route(state):
        if state.get("is_enriched"):
            return "routing"  # Go to routing phase
        else:
            return "decide"   # Continue enrichment
    
    graph.add_conditional_edges(
        "decide",
        decide_to_route,
        {"routing": "routing", "decide": "decide"}
    )
    
    # ========== ROUTING PHASE ==========
    # Step 3: Add routing node
    graph.add_node("routing", routing_node)
    graph.add_edge("fetch_logs", "routing")
    
    # ========== EXECUTION PHASE ==========
    # Step 4: Add execution nodes
    graph.add_node(
        "sf_execution",
        lambda state: sf_execution_node(state, sf_adapter)
    )
    graph.add_node(
        "billing_execution",
        lambda state: billing_execution_node(state, billing_adapter)
    )
    graph.add_node("manual_review", manual_review_node)
    
    # Step 5: Add conditional edges from routing
    def route_request(state) -> Literal["sf_execution", "billing_execution", "manual_review"]:
        """
        Determine which execution node to go to
        """
        target_system = state.get("target_system")
        confidence = state.get("routing_confidence", 0)
        
        if confidence < 0.60:
            print("[ROUTER] Low confidence - directing to manual_review")
            return "manual_review"
        
        if target_system == "salesforce":
            print("[ROUTER] Routing to Salesforce execution")
            return "sf_execution"
        elif target_system == "billing":
            print("[ROUTER] Routing to Billing execution")
            return "billing_execution"
        else:
            print("[ROUTER] Unknown system - directing to manual_review")
            return "manual_review"
    
    graph.add_conditional_edges(
        "routing",
        route_request,
        {
            "sf_execution": "sf_execution",
            "billing_execution": "billing_execution",
            "manual_review": "manual_review"
        }
    )
    
    # Step 6: All execution paths lead to aggregation
    graph.add_edge("sf_execution", "aggregation")
    graph.add_edge("billing_execution", "aggregation")
    graph.add_edge("manual_review", "aggregation")
    
    # ========== AGGREGATION PHASE ==========
    # Step 7: Add aggregation node
    graph.add_node("aggregation", aggregation_node)
    
    # Step 8: Aggregation leads to end
    graph.add_edge("aggregation", END)
    
    # Step 9: Set entry point
    graph.set_entry_point("decide")
    
    # Step 10: Compile and return
    compiled_graph = graph.compile()
    return compiled_graph

# Lines 122-130: Create global instance
routing_graph = build_routing_graph()

# Lines 132-150: Invoke function (used by worker)
def invoke_routing(state: EnhancedAgentState) -> EnhancedAgentState:
    """
    Execute the complete routing graph
    """
    print("[GRAPH] Starting routing graph execution")
    result = routing_graph.invoke(state)
    print("[GRAPH] Routing graph execution complete")
    return result
```

**Graph Visualization:**

```
                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           │
                    ┌──────▼────────┐
        ┌──────────►│    decide     │◄──────────┐
        │           └──────┬────────┘           │
        │                  │                    │
        │           ┌──────▼────────┐           │
        │           │ fetch_profile │           │
        │           └──────┬────────┘           │
        │                  │                    │
        │  Loop            │                    │
        │  (until        ┌──▼────────┐          │
        │   enriched)    │fetch_logs │          │
        │                └──┬────────┘          │
        │                   │                   │
        ├───────────────────┘                   │
        │                              Continue │
        │                              if not   │
        │                              enriched │
        │
        │ Exit when enriched
        │
        ├───────────────────────────────┐
        │                               │
        │                      ┌────────▼──────┐
        │                      │   routing     │
        │                      └────────┬──────┘
        │                               │
        │         ┌─────────────────────┼─────────────────────┐
        │         │                     │                     │
        │   ┌─────▼──────┐      ┌──────▼────────┐      ┌─────▼──────┐
        │   │sf_execution│      │billing_exec   │      │manual_review│
        │   └─────┬──────┘      └──────┬────────┘      └─────┬──────┘
        │         │                    │                     │
        └─────────┴────────────────────┴─────────────────────┘
                                │
                        ┌───────▼──────┐
                        │aggregation   │
                        └───────┬──────┘
                                │
                        ┌───────▼──────┐
                        │     END      │
                        └──────────────┘
```

---

## 7. SERVICE ADAPTERS: `app/agent/adapters.py`

**Purpose:** Decouple system-specific logic from routing core

```python
# Lines 1-50: Base Adapter Class
from abc import ABC, abstractmethod
from enum import Enum

class ActionType(Enum):
    # Salesforce actions
    CREATE_CASE = "create_case"
    UPDATE_CASE = "update_case"
    ADD_COMMENT = "add_comment"
    CLOSE_CASE = "close_case"
    
    # Billing actions
    APPLY_CREDIT = "apply_credit"
    PROCESS_INVOICE = "process_invoice"
    PROCESS_REFUND = "process_refund"
    UPDATE_BILLING_ACCOUNT = "update_billing_account"

class ServiceAdapter(ABC):
    """
    Abstract base class for system adapters
    """
    
    @abstractmethod
    def validate_action(self, action: ActionType) -> bool:
        """Check if this adapter supports the action"""
        pass
    
    @abstractmethod
    def execute_action(self, action: ActionType, payload: Dict) -> Dict:
        """
        Execute the action and return result
        
        Returns:
        {
            "success": bool,
            "result_id": str,        # Case ID or Transaction ID
            "status": str,           # Action status
            "details": Dict,         # Any additional details
            "error": Optional[str]   # Error message if failed
        }
        """
        pass
    
    @abstractmethod
    def handle_error(self, error: Exception, action: ActionType) -> Dict:
        """Handle errors gracefully"""
        pass
    
    @abstractmethod
    def get_system_name(self) -> str:
        """Return system name"""
        pass

# Lines 52-150: Salesforce Adapter
class SalesforceAdapter(ServiceAdapter):
    """
    Salesforce-specific adapter
    """
    
    def __init__(self):
        self.client = SalesforceClient()  # From app.integrations.salesforce
        self.supported_actions = {
            ActionType.CREATE_CASE,
            ActionType.UPDATE_CASE,
            ActionType.ADD_COMMENT,
            ActionType.CLOSE_CASE
        }
    
    def validate_action(self, action: ActionType) -> bool:
        return action in self.supported_actions
    
    def execute_action(self, action: ActionType, payload: Dict) -> Dict:
        """
        Execute Salesforce action
        """
        
        if not self.validate_action(action):
            return {
                "success": False,
                "error": f"Action {action} not supported by SalesforceAdapter"
            }
        
        try:
            if action == ActionType.CREATE_CASE:
                # Call SF REST API to create case
                result = self.client.create_case(
                    subject=payload["subject"],
                    description=payload["description"],
                    contact_email=payload["contact_id_or_email"]
                )
                
                return {
                    "success": True,
                    "result_id": result["id"],      # Case ID: "00012345..."
                    "status": "created",
                    "details": result
                }
            
            elif action == ActionType.UPDATE_CASE:
                # Call SF REST API to update case
                result = self.client.update_case(
                    case_id=payload["case_id"],
                    subject=payload.get("subject"),
                    description=payload.get("description")
                )
                
                return {
                    "success": True,
                    "result_id": payload["case_id"],
                    "status": "updated",
                    "details": result
                }
            
            elif action == ActionType.ADD_COMMENT:
                # Add comment to case
                result = self.client.add_comment_to_case(
                    case_id=payload["case_id"],
                    comment_body=payload["comment"]
                )
                
                return {
                    "success": True,
                    "result_id": result["id"],
                    "status": "comment_added",
                    "details": result
                }
            
            elif action == ActionType.CLOSE_CASE:
                # Close case
                result = self.client.close_case(
                    case_id=payload["case_id"],
                    resolution=payload.get("resolution")
                )
                
                return {
                    "success": True,
                    "result_id": payload["case_id"],
                    "status": "closed",
                    "details": result
                }
        
        except Exception as e:
            return self.handle_error(e, action)
    
    def handle_error(self, error: Exception, action: ActionType) -> Dict:
        """
        Handle SF errors
        """
        error_str = str(error)
        
        if "duplicate" in error_str.lower():
            return {
                "success": False,
                "error": "Duplicate case detected",
                "status": "duplicate_found"
            }
        
        if "timeout" in error_str.lower():
            return {
                "success": False,
                "error": "Salesforce connection timeout",
                "status": "timeout"
            }
        
        return {
            "success": False,
            "error": str(error),
            "status": "error"
        }
    
    def get_system_name(self) -> str:
        return "Salesforce"

# Lines 152-250: Billing Adapter
class BillingAdapter(ServiceAdapter):
    """
    Billing system adapter
    """
    
    def __init__(self):
        self.supported_actions = {
            ActionType.APPLY_CREDIT,
            ActionType.PROCESS_INVOICE,
            ActionType.PROCESS_REFUND,
            ActionType.UPDATE_BILLING_ACCOUNT
        }
    
    def validate_action(self, action: ActionType) -> bool:
        return action in self.supported_actions
    
    def execute_action(self, action: ActionType, payload: Dict) -> Dict:
        """
        Execute Billing action
        """
        
        if not self.validate_action(action):
            return {
                "success": False,
                "error": f"Action {action} not supported by BillingAdapter"
            }
        
        try:
            if action == ActionType.APPLY_CREDIT:
                # Apply credit to user account
                transaction_id = self._generate_transaction_id("CREDIT")
                
                return {
                    "success": True,
                    "result_id": transaction_id,       # e.g., "TXN_BEE801E80B5B"
                    "status": "credit_applied",
                    "details": {
                        "user_id": payload["user_id"],
                        "amount": payload["amount"],
                        "reason": payload["reason"],
                        "transaction_id": transaction_id
                    }
                }
            
            elif action == ActionType.PROCESS_INVOICE:
                # Generate or process invoice
                transaction_id = self._generate_transaction_id("INVOICE")
                
                return {
                    "success": True,
                    "result_id": transaction_id,
                    "status": "invoice_generated",
                    "details": {
                        "user_id": payload["user_id"],
                        "invoice_id": transaction_id
                    }
                }
            
            elif action == ActionType.PROCESS_REFUND:
                # Process refund
                transaction_id = self._generate_transaction_id("REFUND")
                
                return {
                    "success": True,
                    "result_id": transaction_id,
                    "status": "refund_processed",
                    "details": {
                        "user_id": payload["user_id"],
                        "amount": payload["amount"],
                        "transaction_id": transaction_id
                    }
                }
            
            elif action == ActionType.UPDATE_BILLING_ACCOUNT:
                # Update billing account
                transaction_id = self._generate_transaction_id("UPDATE")
                
                return {
                    "success": True,
                    "result_id": transaction_id,
                    "status": "account_updated",
                    "details": {
                        "user_id": payload["user_id"],
                        "transaction_id": transaction_id
                    }
                }
        
        except Exception as e:
            return self.handle_error(e, action)
    
    def handle_error(self, error: Exception, action: ActionType) -> Dict:
        return {
            "success": False,
            "error": str(error),
            "status": "error"
        }
    
    def get_system_name(self) -> str:
        return "Billing"
    
    def _generate_transaction_id(self, prefix: str) -> str:
        """Generate unique transaction ID"""
        import uuid
        return f"TXN_{prefix}_{uuid.uuid4().hex[:13].upper()}"
```

---

## 8. SALESFORCE INTEGRATION: `app/integrations/salesforce.py`

**Purpose:** Direct REST API communication with Salesforce

```python
# Lines 1-50: OAuth2 Authentication
import requests
import logging
from functools import wraps
import time

class SalesforceClient:
    """
    Direct Salesforce REST API client with OAuth2
    """
    
    def __init__(self):
        self.client_id = os.environ["SF_CLIENT_ID"]
        self.client_secret = os.environ["SF_CLIENT_SECRET"]
        self.login_url = os.environ["SF_LOGIN_URL"]
        
        self.access_token = None
        self.instance_url = None
        self.logger = logging.getLogger(__name__)
    
    def login(self):
        """
        Get OAuth2 access token using Client Credentials flow
        """
        
        self.logger.info(f"Attempting Salesforce login at {self.login_url}/services/oauth2/token")
        
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        
        response = requests.post(
            f"{self.login_url}/services/oauth2/token",
            headers=headers,
            data=payload
        )
        
        self.logger.info(f"Salesforce response status: {response.status_code}")
        self.logger.info(f"Salesforce response body: {response.json()}")
        
        if response.status_code != 200:
            raise Exception(f"Failed to authenticate with Salesforce: {response.text}")
        
        data = response.json()
        
        self.access_token = data["access_token"]
        self.instance_url = data["instance_url"]
        
        self.logger.info(f"Successfully authenticated with Salesforce: {self.instance_url}")
    
    # Lines 52-120: CRUD Operations
    
    def create_case(self, subject: str, description: str, contact_email: str) -> Dict:
        """
        CREATE case in Salesforce
        
        POST /services/data/v61.0/sobjects/Case
        """
        
        if not self.access_token:
            self.login()
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "Subject": subject,
            "Description": description,
            "ContactEmail": contact_email,
            "Origin": "Agentic",
            "Status": "New",
            "Priority": "Medium"
        }
        
        url = f"{self.instance_url}/services/data/v61.0/sobjects/Case"
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to create case: {response.text}")
        
        return response.json()  # Returns {"id": "00012345..."}
    
    def update_case(self, case_id: str, subject: str = None, description: str = None) -> Dict:
        """
        UPDATE case in Salesforce
        
        PATCH /services/data/v61.0/sobjects/Case/{id}
        """
        
        if not self.access_token:
            self.login()
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {}
        if subject:
            payload["Subject"] = subject
        if description:
            payload["Description"] = description
        
        url = f"{self.instance_url}/services/data/v61.0/sobjects/Case/{case_id}"
        
        response = requests.patch(url, headers=headers, json=payload)
        
        if response.status_code not in [200, 204]:
            raise Exception(f"Failed to update case: {response.text}")
        
        return {"success": True}
    
    def close_case(self, case_id: str, resolution: str) -> Dict:
        """
        CLOSE case in Salesforce
        """
        
        return self.update_case(
            case_id,
            subject=None,
            description=f"Resolved: {resolution}"
        )
    
    def add_comment_to_case(self, case_id: str, comment_body: str) -> Dict:
        """
        ADD COMMENT to case
        
        POST /services/data/v61.0/sobjects/CaseComment
        """
        
        if not self.access_token:
            self.login()
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "ParentId": case_id,
            "CommentBody": comment_body
        }
        
        url = f"{self.instance_url}/services/data/v61.0/sobjects/CaseComment"
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to add comment: {response.text}")
        
        return response.json()
    
    def lookup_cases_by_user(self, user_id: str) -> List[Dict]:
        """
        QUERY cases for a user
        
        GET /services/data/v61.0/query?q=...
        """
        
        if not self.access_token:
            self.login()
        
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        
        # SOQL query
        soql = f"""
        SELECT Id, Subject, Description, Status 
        FROM Case 
        WHERE External_User_Id__c = '{user_id}'
        ORDER BY CreatedDate DESC
        LIMIT 10
        """
        
        url = f"{self.instance_url}/services/data/v61.0/query?q={quote(soql)}"
        
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            raise Exception(f"Failed to query cases: {response.text}")
        
        records = response.json()["records"]
        return records
```

---

## 9. BACKGROUND WORKER: `app/workers/worker.py`

**Purpose:** Process jobs asynchronously

```python
# Lines 1-50: Worker setup
import threading
import queue
from app.agent.routing_graph import invoke_routing
from app.agent.routing_state import create_enhanced_state
from app.integrations.db import get_db

job_queue = queue.Queue()

def start_worker():
    """
    Start background worker thread
    """
    worker_thread = threading.Thread(target=worker_loop, daemon=True)
    worker_thread.start()
    print("[WORKER] Background worker started")

# Lines 52-120: Main worker loop
def worker_loop():
    """
    Continuously process jobs from queue
    """
    
    while True:
        try:
            # Step 1: Get job from queue (blocking)
            job_data = job_queue.get(timeout=1)
            
            job_id = job_data["job_id"]
            print(f"[WORKER] Processing job: {job_id}")
            
            # Step 2: Update job status in DB
            db = get_db()
            db_job = db.query(Job).filter(Job.id == job_id).first()
            db_job.status = "processing"
            db.commit()
            
            # Step 3: Create enhanced state
            state = create_enhanced_state({
                "job_id": job_id,
                "user_id": job_data["user_id"],
                "message": job_data["message"],
                "issue_type": job_data["issue_type"],
                "backend_context": job_data.get("backend_context", {})
            })
            
            # Step 4: Invoke routing graph
            print(f"[WORKER] Invoking routing graph for job {job_id}")
            result = invoke_routing(state)
            
            print(f"[WORKER] Routing complete for job {job_id}")
            
            # Step 5: Save result to DB
            db_job.status = "completed"
            db_job.result = result["aggregated_response"]
            db_job.completed_at = datetime.now()
            db_job.event_log = result["event_log"]
            db.commit()
            
            print(f"[WORKER] Job {job_id} saved to database")
        
        except queue.Empty:
            continue  # No jobs in queue, keep waiting
        
        except Exception as e:
            print(f"[WORKER] Error processing job: {str(e)}")
            # Log error and continue
            continue
```

---

## 10. LIVE EXECUTOR: `tests/live_executor.py`

**Purpose:** Interactive testing tool

```python
# Lines 1-100: Main execution function
def execute_single_request(request_data):
    """
    Execute request through routing system and display results
    """
    
    print_header(f"PROCESSING REQUEST #{request_data.get('id', '?')}")
    
    # STEP 1: Display input
    print_step(1, "INPUT REQUEST")
    print(f"   Customer ID:  {request_data.get('user_id')}")
    print(f"   Message:      {request_data.get('message')}")
    print()
    
    # STEP 2: Create enhanced state
    print_step(2, "PREPARING STATE")
    state = create_enhanced_state(request_data)
    print(f"   State created with job_id: {state['job_id']}")
    print()
    
    # STEP 3: Invoke routing graph
    print_step(3, "ROUTING ANALYSIS")
    result = routing_graph.invoke(state)
    
    # Show routing decision
    print(f"   Decision:     {result.get('target_system', 'unknown').upper()}")
    print(f"   Confidence:   {result.get('routing_confidence', 0):.0%}")
    print(f"   Rationale:    {result.get('routing_rationale', '')}")
    print()
    
    # STEP 4: Show execution
    print_step(4, "EXECUTION PATH")
    execution_system = result.get("execution_system")
    
    if execution_system == 'salesforce':
        print(f"   ✓ Routed to:  SALESFORCE")
        print(f"   Case ID:      {result.get('sf_case_id')}")
        print(f"   Status:       {result.get('sf_status')}")
    elif execution_system == 'billing':
        print(f"   ✓ Routed to:  BILLING")
        print(f"   Transaction:  {result.get('billing_transaction_id')}")
        print(f"   Status:       {result.get('billing_status')}")
    else:
        print(f"   ⚠️  Status:    MANUAL REVIEW REQUIRED")
    
    print()
    
    # STEP 5: Show customer response
    print_step(5, "RESPONSE TO CUSTOMER")
    aggregated_response = result.get('aggregated_response', {})
    print(f"   Message: {aggregated_response.get('message', 'N/A')}")
    print()
    
    # STEP 6: Show event trail
    print_step(6, "EXECUTION TRAIL")
    for i, event in enumerate(result.get('event_log', []), 1):
        print(f"   {i}. {event.get('type', '?').upper()}")
    
    print()
```

---

## 📊 Complete Data Flow Visualization

```
┌─────────────────────────────────────────┐
│       CLIENT REQUEST (REST API)         │
│  POST /api/jobs with request data       │
└────────────┬────────────────────────────┘
             │
   ┌─────────▼──────────────┐
   │ routes.py              │
   │ create_agent_job()     │
   │ - Generate job_id      │
   │ - Create DB record     │
   │ - Enqueue to worker    │
   └─────────┬──────────────┘
             │
   ┌─────────▼──────────────────────────────┐
   │ worker.py                              │
   │ worker_loop()                          │
   │ - Get job from queue                   │
   │ - Create EnhancedAgentState            │
   │ - Invoke routing_graph                 │
   └─────────┬──────────────────────────────┘
             │
   ┌─────────▼──────────────────────────────┐
   │ routing_state.py                       │
   │ create_enhanced_state()                │
   │ - Initialize state structure           │
   │ - Set initial values                   │
   └─────────┬──────────────────────────────┘
             │
   ┌─────────▼──────────────────────────────┐
   │ routing_graph.py                       │
   │ - LangGraph orchestration              │
   │ - Routes through nodes                 │
   └─────────┬──────────────────────────────┘
             │
   ┌─────────▼──────────────────────────────┐
   │ routing_nodes.py                       │
   │ decide_node() - enrichment             │
   └─────────┬──────────────────────────────┘
             │
   ┌─────────▼──────────────────────────────┐
   │ routing_nodes.py                       │
   │ routing_node()                         │
   │ - Calls router.classify_and_route()    │
   └─────────┬──────────────────────────────┘
             │
   ┌─────────▼──────────────────────────────┐
   │ router.py                              │
   │ 4-tier classification:                 │
   │ 1. Issue type mapping                  │
   │ 2. Context rules                       │
   │ 3. Keyword scoring                     │
   │ 4. LLM fallback                        │
   │ Returns: target_system, confidence     │
   └─────────┬──────────────────────────────┘
             │
   ┌─────────▼──────────────────────────────┐
   │ routing_graph.py - Conditional routing │
   │ route_request()                        │
   │ - If confidence < 60% → manual_review  │
   │ - If SF → sf_execution                 │
   │ - If Billing → billing_execution       │
   └────────┬────────────────────────────────┘
            │
     ┌──────┴──────────────────┬──────────────┐
     │                         │              │
┌────▼────────┐      ┌────────▼────┐   ┌────▼────────┐
│sf_execution │      │billing_exec │   │manual_review│
├─────────────┤      ├─────────────┤   ├─────────────┤
│adapters.py: │      │adapters.py: │   │Prepare for  │
│SalesforceA. │      │BillingAdp.  │   │human review │
│ - CREATE    │      │ - APPLY     │   │             │
│ - UPDATE    │      │ - INVOICE   │   │             │
│ - CLOSE     │      │ - REFUND    │   │             │
└────┬────────┘      └────┬────────┘   └────┬────────┘
     │                    │                  │
     │    ┌────────────────┴──────────────────┘
     │    │
┌────▼────▼─ SF calls (if SF routing)
│salesforce.py
│ SalesforceClient
│ - login() via OAuth2
│ - create_case() via REST API
│ - update_case() via REST API
│ - add_comment() via REST API
│ - close_case() via REST API
└────┬──────────────────────────────────────
     │
     │ (All paths converge)
     │
┌────▼──────────────────────────────────┐
│ routing_nodes.py                       │
│ aggregation_node()                     │
│ - Combine results                      │
│ - Create customer response             │
│ - Set final status                     │
└────┬──────────────────────────────────┘
     │
┌────▼──────────────────────────────────┐
│ worker.py                              │
│ - Save result to DB                    │
│ - Update job status to "completed"     │
└────┬──────────────────────────────────┘
     │
┌────▼──────────────────────────────────┐
│ routes.py - GET /api/jobs/{job_id}     │
│ - Fetch from DB                        │
│ - Return to client                     │
└────┬──────────────────────────────────┘
     │
┌────▼──────────────────────────────────┐
│ CLIENT - Receives response             │
│ {                                      │
│   "status": "completed",               │
│   "result": {                          │
│     "status": "success",               │
│     "system": "billing",               │
│     "message": "Credit applied",       │
│     "transaction_id": "TXN_..."        │
│   }                                    │
│ }                                      │
└───────────────────────────────────────┘
```

---

## 🎯 Summary

**Key Takeaways:**

1. **Request enters via REST API** → create job → enqueue to worker
2. **Worker processes** → creates state → invokes routing_graph
3. **Routing graph orchestrates** → enrichment → routing → execution → aggregation
4. **Router intelligently classifies** using 4-tier priority system
5. **Adapters decouple systems** → SF/Billing handled separately
6. **Salesforce integration** → direct REST API with OAuth2
7. **Results aggregated** → saved to DB → returned to client

**All files working together:**
- Entry: `main.py` → API: `routes.py` → State: `routing_state.py`
- Classification: `router.py` → Nodes: `routing_nodes.py` → Orchestration: `routing_graph.py`
- Adapters: `adapters.py` → SF: `salesforce.py` → Worker: `worker.py`

---

