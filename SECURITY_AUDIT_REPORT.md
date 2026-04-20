# Security and Bug Audit Report - Ticket Workflow Application

**Date**: April 20, 2026  
**Application**: Intelligent Salesforce Agent (ticketWorkflow)  
**Severity Levels**: CRITICAL | HIGH | MEDIUM | LOW

---

## Executive Summary

This comprehensive security and bug audit identified **21 critical issues** across the application spanning security vulnerabilities, data validation gaps, error handling deficiencies, and code quality concerns. The most critical findings involve SQL injection vulnerabilities, credential exposure, race conditions, and missing authorization checks.

**Key Statistics:**
- CRITICAL: 7 issues
- HIGH: 8 issues  
- MEDIUM: 4 issues
- LOW: 2 issues

---

## 1. CRITICAL SECURITY VULNERABILITIES

### 1.1 SQL Injection in Salesforce SOQL Query

**Location**: [app/integrations/salesforce.py](app/integrations/salesforce.py#L185-L195)  
**Severity**: 🔴 CRITICAL  
**CWE**: CWE-89 (SQL Injection)

**Vulnerable Code**:
```python
def lookup_cases_by_user(self, user_id, status="New"):
    """Query Salesforce for existing cases by user"""
    if not self.access_token:
        self.login()

    # Query for recent open cases for this user
    query = f"SELECT Id, CaseNumber, Subject, Status, CreatedDate FROM Case WHERE External_User_Id__c = '{user_id}' AND Status = '{status}' ORDER BY CreatedDate DESC LIMIT 5"
    url = f"{self.instance_url}/services/data/v61.0/query"
    
    headers = {
        "Authorization": f"Bearer {self.access_token}",
        "Content-Type": "application/json"
    }
    
    params = {"q": query}
```

**Problem**: User-supplied `user_id` and `status` are directly interpolated into the SOQL query string without any escaping or parameterization. An attacker can inject SOQL expressions.

**Attack Example**:
```
user_id = "user123' OR '1'='1"
status = "New' UNION SELECT Id, Name, Phone, Type, CreatedDate FROM Account LIMIT 5 --"
```

**Impact**: 
- Unauthorized data access (cases, accounts, contacts)
- Data exfiltration
- Potential data modification

**Recommendation**:
1. Use Salesforce's escape functions for SOQL
2. Implement parameterized queries if available
3. Validate and sanitize all inputs

**Fix**:
```python
from salesforce_bulk2.handlers.bulk_api_handler import escape_soql_string

def lookup_cases_by_user(self, user_id, status="New"):
    if not self.access_token:
        self.login()
    
    # Escape the string values
    escaped_user_id = escape_soql_string(user_id)
    escaped_status = escape_soql_string(status)
    
    query = f"SELECT Id, CaseNumber, Subject, Status, CreatedDate FROM Case WHERE External_User_Id__c = '{escaped_user_id}' AND Status = '{escaped_status}' ORDER BY CreatedDate DESC LIMIT 5"
```

---

### 1.2 Credential Exposure in Logs

**Location**: [app/integrations/salesforce.py](app/integrations/salesforce.py#L23-L28)  
**Severity**: 🔴 CRITICAL  
**CWE**: CWE-532 (Insertion of Sensitive Information into Log File)

**Vulnerable Code**:
```python
def login(self):
    url = f"{settings.SF_LOGIN_URL}/services/oauth2/token"

    payload = {
        "grant_type": "client_credentials",
        "client_id": settings.SF_CLIENT_ID,
        "client_secret": settings.SF_CLIENT_SECRET
    }

    logger.info(f"Attempting Salesforce login at {url}")
    try:
        response = requests.post(url, data=payload, timeout=20)
        logger.info(f"Salesforce response status: {response.status_code}")
        logger.info(f"Salesforce response body: {response.text}")  # ⚠️ LOGS SENSITIVE DATA
```

**Problem**: The response body (containing access tokens) is logged. Additionally, error responses may contain sensitive information.

**Impact**:
- Access tokens exposed in logs
- Log aggregation systems may retain sensitive data
- Potential token theft

**Recommendation**:
1. Never log response bodies containing credentials
2. Sanitize logs before storage
3. Implement log filtering

**Fix**:
```python
def login(self):
    url = f"{settings.SF_LOGIN_URL}/services/oauth2/token"

    payload = {
        "grant_type": "client_credentials",
        "client_id": settings.SF_CLIENT_ID,
        "client_secret": settings.SF_CLIENT_SECRET
    }

    logger.info(f"Attempting Salesforce login at {url}")
    try:
        response = requests.post(url, data=payload, timeout=20)
        logger.info(f"Salesforce response status: {response.status_code}")
        # Don't log response body if it contains tokens
        
        response.raise_for_status()
        data = response.json()
        self.access_token = data.get("access_token")  # Store securely
        self.instance_url = data.get("instance_url")
        logger.info(f"Successfully authenticated with Salesforce")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Salesforce login failed: {type(e).__name__}")
        # Don't log response details
        raise
```

---

### 1.3 Insufficient Authorization Checks on API Routes

**Location**: [app/api/routes.py](app/api/routes.py#L16-L48)  
**Severity**: 🔴 CRITICAL  
**CWE**: CWE-285 (Improper Authorization)

**Vulnerable Code**:
```python
@router.post("/jobs", response_model=CreateJobResponse)
def create_agent_job(payload: CreateJobRequest):
    # No auth checks! Anyone can create jobs
    job_id = create_job(payload.model_dump())
    
    history = get_long_term_memory(payload.user_id)  # ⚠️ Can query ANY user's history
    
    initial_state = {
        "job_id": job_id,
        "user_id": payload.user_id,  # ⚠️ Client supplies their own user_id
        ...
    }
```

**Problem**: 
- No authentication middleware
- No authorization checks
- Users can supply arbitrary `user_id`
- Users can access any user's memory

**Impact**:
- Unauthorized job creation
- Cross-user data access
- Unlimited API usage

**Recommendation**:
1. Implement authentication (JWT, OAuth2)
2. Verify user identity from token
3. Enforce authorization on all endpoints
4. Add rate limiting

**Fix**:
```python
from fastapi import Depends, HTTPException, status
from app.auth import verify_token, get_current_user

@router.post("/jobs", response_model=CreateJobResponse)
def create_agent_job(payload: CreateJobRequest, current_user = Depends(get_current_user)):
    # Verify the user_id in payload matches authenticated user
    if payload.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create jobs for another user"
        )
    
    job_id = create_job(payload.model_dump())
    history = get_long_term_memory(current_user.user_id)
    ...
```

---

### 1.4 Case ID Parameter Mismatch - Authorization Bypass

**Location**: [app/api/routes.py](app/api/routes.py#L52-L74)  
**Severity**: 🔴 CRITICAL  
**CWE**: CWE-639 (Authorization Bypass Through User-Controlled Key)

**Vulnerable Code**:
```python
@router.patch("/cases/{case_id}", response_model=UpdateCaseResponse)
def update_case(case_id: str, payload: UpdateCaseRequest):
    try:
        sf_client = SalesforceClient()
        result = sf_client.update_case(
            case_id=payload.case_id,  # ⚠️ Uses payload.case_id, not path param!
            subject=payload.subject,
            ...
        )
        return UpdateCaseResponse(success=True, message=f"Case {case_id} updated successfully")
```

**Problem**: 
- Path parameter `case_id` is ignored
- Client can modify different case via `payload.case_id`
- No ownership verification

**Impact**:
- Privilege escalation
- Modify other users' cases
- Data manipulation

**Recommendation**:
1. Use path parameter, not request body
2. Verify case ownership
3. Validate case_id format

**Fix**:
```python
@router.patch("/cases/{case_id}", response_model=UpdateCaseResponse)
def update_case(case_id: str, payload: UpdateCaseRequest, current_user = Depends(get_current_user)):
    # Verify path parameter matches payload
    if case_id != payload.case_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="case_id in path and body must match"
        )
    
    # Verify ownership
    sf_client = SalesforceClient()
    case = sf_client.get_case(case_id)  # ⚠️ Need to implement get_case
    
    if case.get("External_User_Id__c") != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot modify this case"
        )
```

---

### 1.5 Missing Input Validation - Buffer Overflow Risk

**Location**: [app/api/schemas.py](app/api/schemas.py#L1-L30)  
**Severity**: 🔴 CRITICAL  
**CWE**: CWE-400 (Uncontrolled Resource Consumption)

**Vulnerable Code**:
```python
class CreateJobRequest(BaseModel):
    user_id: str           # ⚠️ No max length
    issue_type: str        # ⚠️ No max length
    message: Optional[str] = None  # ⚠️ No max length

class LookupCasesRequest(BaseModel):
    user_id: str
    status: str = "New"    # ⚠️ No validation
```

**Problem**:
- No maximum length constraints
- No format validation
- Attackers can send huge payloads
- Potential DoS

**Impact**:
- Memory exhaustion
- Database overload
- Service disruption

**Recommendation**:
1. Add max_length to all string fields
2. Add regex validation
3. Implement request size limits

**Fix**:
```python
from pydantic import BaseModel, Field, constr

class CreateJobRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=255, description="User identifier")
    issue_type: str = Field(..., min_length=1, max_length=50, description="Type of issue")
    message: Optional[str] = Field(None, max_length=5000, description="Issue description")

class LookupCasesRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=255)
    status: str = Field("New", regex="^(New|In Progress|Closed|On Hold)$")
```

---

### 1.6 Race Condition in Worker Queue Processing

**Location**: [app/workers/worker.py](app/workers/worker.py#L22-L50)  
**Severity**: 🔴 CRITICAL  
**CWE**: CWE-366 (Race Condition)

**Vulnerable Code**:
```python
def worker_loop():
    while True:
        state = job_queue.get()
        job_id = state["job_id"]

        try:
            update_job(job_id, "processing")  # ⚠️ State 1
            add_event(job_id, "job_started", {"job_id": job_id})

            result = agent_graph.invoke(state)  # ⚠️ Long-running, can fail

            for event in result.get("event_log", []):
                add_event(job_id, event["type"], event)

            update_job(job_id, "completed", result)  # ⚠️ State 2
            
            # State can be INCONSISTENT if process crashes between states

        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(f"Job {job_id} failed with error: {str(e)}\n{error_details}")
            update_job(job_id, "failed", {"error": str(e)})
```

**Problem**:
- No lock/transaction management
- Process can crash mid-execution
- Job state becomes inconsistent
- No idempotency

**Impact**:
- Jobs processed multiple times
- Data corruption
- Lost work

**Recommendation**:
1. Use database transactions
2. Implement idempotency keys
3. Add checkpointing

**Fix**:
```python
def worker_loop():
    while True:
        state = job_queue.get()
        job_id = state["job_id"]

        try:
            # Start transaction
            with db_transaction() as tx:
                # Check if already processing
                existing = db.query(JobRecord).filter(
                    JobRecord.job_id == job_id
                ).with_for_update().first()  # Lock the row
                
                if existing.status != "queued":
                    logger.warning(f"Job {job_id} already processed")
                    job_queue.task_done()
                    continue
                
                update_job(job_id, "processing")
                add_event(job_id, "job_started", {"job_id": job_id})
                tx.commit()
            
            # Execute outside transaction
            result = agent_graph.invoke(state)
            
            # Update with result
            with db_transaction() as tx:
                for event in result.get("event_log", []):
                    add_event(job_id, event["type"], event)
                update_job(job_id, "completed", result)
                tx.commit()
                
        except Exception as e:
            with db_transaction() as tx:
                update_job(job_id, "failed", {"error": str(e)})
                tx.commit()
```

---

### 1.7 Hardcoded Salesforce API Version

**Location**: [app/integrations/salesforce.py](app/integrations/salesforce.py#L37), [#L70], [#L110], [#L171], [#L190], [#L249]  
**Severity**: 🔴 CRITICAL  
**CWE**: CWE-798 (Use of Hard-Coded Credentials)

**Vulnerable Code**:
```python
url = f"{self.instance_url}/services/data/v61.0/sobjects/Case"  # Hardcoded!
url = f"{self.instance_url}/services/data/v61.0/sobjects/Case/{case_id}"  # Hardcoded!
```

**Problem**:
- API version hardcoded in multiple places
- Difficult to update if Salesforce deprecates API
- No flexibility for different orgs

**Impact**:
- Service failure if API deprecates
- Difficult to support multiple SF versions

**Recommendation**:
1. Move API version to configuration
2. Make it configurable per environment

**Fix**:
```python
# In config.py
SF_API_VERSION = os.getenv("SF_API_VERSION", "v61.0")

# In salesforce.py
class SalesforceClient:
    def __init__(self, api_version=None):
        self.api_version = api_version or settings.SF_API_VERSION
        self.access_token = None
        self.instance_url = None
    
    def create_case(self, ...):
        url = f"{self.instance_url}/services/data/{self.api_version}/sobjects/Case"
```

---

## 2. HIGH-SEVERITY ISSUES

### 2.1 Unvalidated External User ID in Salesforce Context

**Location**: [app/integrations/salesforce.py](app/integrations/salesforce.py#L58), [#L242]  
**Severity**: 🟠 HIGH  
**CWE**: CWE-99 (Improper Control of Resource Identifiers)

**Vulnerable Code**:
```python
payload = {
    "Subject": subject,
    "Description": description,
    "Origin": "Web",
    "Status": "New",
    "External_User_Id__c": user_id,  # ⚠️ From untrusted source
    "Source_App__c": "Agentic",
    ...
}
```

**Problem**:
- `user_id` comes directly from API request
- No validation of format
- Could contain malicious data

**Recommendation**:
1. Validate user_id format (must match your user ID pattern)
2. Verify user exists
3. Sanitize before sending to Salesforce

**Fix**:
```python
import re

def validate_user_id(user_id: str) -> bool:
    """Validate user_id format"""
    # Adjust regex based on your user ID format
    pattern = r"^[a-zA-Z0-9_-]{1,255}$"
    return bool(re.match(pattern, user_id))

def create_case(self, subject, description, user_id=None, ...):
    if user_id and not validate_user_id(user_id):
        raise ValueError(f"Invalid user_id format: {user_id}")
```

---

### 2.2 Type Inconsistency in Contract Results

**Location**: [app/workers/worker.py](app/workers/worker.py#L78-L82)  
**Severity**: 🟠 HIGH  
**CWE**: CWE-843 (Type Confusion)

**Vulnerable Code**:
```python
def contract_worker_loop():
    while True:
        state = contract_queue.get()
        job_id = state["job_id"]

        try:
            result = contract_agent_graph.invoke(state)

            # Ensure result is a dict
            if result is None:
                result = state  # ⚠️ Falls back to state

            final_answer = result.get("final_answer", {})
            if final_answer is None:
                final_answer = {}
            
            # ... later ...
            "status": final_answer.get("status") if isinstance(final_answer, dict) else "unknown"
```

**Problem**:
- Type checking happens too late
- Could be dict or string
- Fallback is non-deterministic

**Impact**:
- Incorrect status values
- Downstream processing errors

**Recommendation**:
1. Validate types early
2. Use type hints
3. Raise on type errors

**Fix**:
```python
def contract_worker_loop():
    while True:
        state = contract_queue.get()
        job_id = state["job_id"]

        try:
            result = contract_agent_graph.invoke(state)

            # Validate result type
            if not isinstance(result, dict):
                raise TypeError(f"Expected dict result, got {type(result)}")
            
            # Ensure required fields
            if "final_answer" not in result:
                result["final_answer"] = {}
            
            final_answer = result["final_answer"]
            if not isinstance(final_answer, dict):
                raise TypeError(f"final_answer must be dict, got {type(final_answer)}")
```

---

### 2.3 Missing Error Handling in Decision Node

**Location**: [app/agent/nodes.py](app/agent/nodes.py#L16-L33)  
**Severity**: 🟠 HIGH  
**CWE**: CWE-391 (Unchecked Error Condition)

**Vulnerable Code**:
```python
def decision_node(state):
    # ... setup ...
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[...],
        response_format={"type": "json_object"}
    )

    parsed = json.loads(response.choices[0].message.content)  # ⚠️ No error handling

    return {
        "next_action": parsed["action"],  # ⚠️ KeyError if "action" missing
        "event_log": state["event_log"] + [{
            "type": "decision",
            "thought": parsed.get("thought", ""),
            "action": parsed["action"],  # ⚠️ repeated KeyError
            "confidence": parsed.get("confidence", 0.5),
            "rationale": parsed.get("rationale", "")
        }]
    }
```

**Problem**:
- No try/except around LLM response
- No validation of LLM output
- No handling of partial failures
- Job can fail silently

**Impact**:
- Application crashes
- Invalid job states
- Difficult debugging

**Recommendation**:
1. Wrap LLM calls in try/except
2. Validate response structure
3. Implement fallbacks

**Fix**:
```python
def decision_node(state):
    existing_cases = lookup_existing_case(state["user_id"], state["issue_type"])
    
    prompt_context = DECISION_PROMPT.format(...)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[...],
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty LLM response")
        
        parsed = json.loads(content)
        
        # Validate required fields
        required_fields = {"action", "thought", "rationale", "confidence"}
        missing = required_fields - set(parsed.keys())
        if missing:
            raise ValueError(f"Missing fields: {missing}")
        
        # Validate action is valid
        valid_actions = {"fetch_profile", "fetch_logs", "create_case", "update_case", "finish"}
        if parsed["action"] not in valid_actions:
            raise ValueError(f"Invalid action: {parsed['action']}")
        
        return {
            "next_action": parsed["action"],
            "event_log": state["event_log"] + [{...}]
        }
        
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.error(f"Decision node failed: {e}")
        # Fallback to safe action
        return {
            "next_action": "finish",
            "event_log": state["event_log"] + [{
                "type": "decision_error",
                "error": str(e),
                "fallback": "finish"
            }]
        }
    except Exception as e:
        logger.error(f"Unexpected error in decision node: {e}")
        raise
```

---

### 2.4 Database Connection Not Closed on Exception

**Location**: [app/services/job_service.py](app/services/job_service.py#L1-L24)  
**Severity**: 🟠 HIGH  
**CWE**: CWE-402 (Transmission of Private Resources into New Sphere)

**Vulnerable Code**:
```python
def create_job(payload: dict) -> str:
    db = SessionLocal()
    try:
        job_id = str(uuid.uuid4())
        record = JobRecord(...)
        db.add(record)
        db.commit()
        return job_id
    finally:
        db.close()
```

**Problem**:
- If `db.commit()` fails, exception is not caught
- Connection may not close properly
- Finally clause will execute but may not help if connection is held

**Impact**:
- Connection pool exhaustion
- Database locks
- Service degradation

**Recommendation**:
1. Use context manager
2. Rollback on error
3. Handle specific exceptions

**Fix**:
```python
from contextlib import contextmanager

@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def create_job(payload: dict) -> str:
    with get_db() as db:
        job_id = str(uuid.uuid4())
        record = JobRecord(
            job_id=job_id,
            status="queued",
            input_payload=json.dumps(payload),
            updated_at=datetime.utcnow()
        )
        db.add(record)
        # Commit happens in context manager
        return job_id
```

---

### 2.5 No Request Rate Limiting

**Location**: [app/api/routes.py](app/api/routes.py)  
**Severity**: 🟠 HIGH  
**CWE**: CWE-770 (Allocation of Resources Without Limits)

**Problem**:
- No rate limiting on any endpoints
- Attackers can create unlimited jobs
- No protection against brute force

**Impact**:
- DoS attacks
- Resource exhaustion
- Database overload

**Recommendation**:
1. Implement rate limiting per user
2. Add token bucket algorithm
3. Return 429 when exceeded

**Fix**:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

@app.post("/jobs", response_model=CreateJobResponse)
@limiter.limit("100/hour")  # 100 requests per hour per IP
def create_agent_job(payload: CreateJobRequest, request: Request):
    ...
```

---

### 2.6 No Pagination on Memory Retrieval

**Location**: [app/agent/memory.py](app/agent/memory.py#L23-L31)  
**Severity**: 🟠 HIGH  
**CWE**: CWE-400 (Uncontrolled Resource Consumption)

**Vulnerable Code**:
```python
def get_long_term_memory(user_id: str):
    db = SessionLocal()
    try:
        records = db.query(MemoryRecord).filter(
            MemoryRecord.user_id == user_id
        ).all()  # ⚠️ No LIMIT clause
        
        return [
            {
                "id": r.id,
                "memory_type": r.memory_type,
                "payload": json.loads(r.payload) if r.payload else {}
            }
            for r in records
        ]
```

**Problem**:
- Retrieves ALL memory records
- Could be millions of records
- Memory exhaustion
- Slow performance

**Impact**:
- Out-of-memory errors
- API timeout
- DoS

**Recommendation**:
1. Add LIMIT to query
2. Implement pagination
3. Cache recent memory

**Fix**:
```python
def get_long_term_memory(user_id: str, limit: int = 100, offset: int = 0):
    db = SessionLocal()
    try:
        records = db.query(MemoryRecord).filter(
            MemoryRecord.user_id == user_id
        ).order_by(
            MemoryRecord.created_at.desc()
        ).limit(limit).offset(offset).all()
        
        return [
            {
                "id": r.id,
                "memory_type": r.memory_type,
                "payload": json.loads(r.payload) if r.payload else {}
            }
            for r in records
        ]
    finally:
        db.close()
```

---

### 2.7 Missing Validation in Schema Parsing

**Location**: [app/integrations/salesforce.py](app/integrations/salesforce.py#L55-L67)  
**Severity**: 🟠 HIGH  
**CWE**: CWE-476 (NULL Pointer Dereference)

**Vulnerable Code**:
```python
def create_case(self, subject, description, user_id=None, ...):
    if not self.access_token:
        self.login()

    url = f"{self.instance_url}/services/data/v61.0/sobjects/Case"
    headers = {
        "Authorization": f"Bearer {self.access_token}",
        "Content-Type": "application/json"
    }

    backend_context_value = json.dumps(backend_context, indent=2) if isinstance(backend_context, (dict, list)) else backend_context or ""
    agent_result = agent_result or {}  # ⚠️ Could be None still

    payload = {
        "Subject": subject,  # ⚠️ Could be None
        "Description": description,  # ⚠️ Could be None
```

**Problem**:
- No validation of required parameters
- subject/description could be None
- Salesforce API will reject silently

**Impact**:
- Silent failures
- Incomplete data
- Difficult debugging

**Recommendation**:
1. Add parameter validation
2. Use type hints
3. Raise ValueError on invalid input

**Fix**:
```python
def create_case(self, subject: str, description: str, user_id: Optional[str] = None, ...):
    """Create a new Salesforce case"""
    # Validate required parameters
    if not subject or not isinstance(subject, str):
        raise ValueError("subject is required and must be a string")
    
    if not description or not isinstance(description, str):
        raise ValueError("description is required and must be a string")
    
    if subject.strip() == "":
        raise ValueError("subject cannot be empty")
    
    if description.strip() == "":
        raise ValueError("description cannot be empty")
    
    # ... rest of method
```

---

### 2.8 Improper Exception Handling in Routing Classifier

**Location**: [app/agent/router.py](app/agent/router.py#L195-L202)  
**Severity**: 🟠 HIGH  
**CWE**: CWE-391 (Unchecked Error Condition)

**Vulnerable Code**:
```python
def classify_with_llm(self, state: Dict[str, Any], llm_client):
    prompt = f"""..."""
    
    try:
        response = llm_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        result = json.loads(response.choices[0].message.content)  # ⚠️ Could fail
        system_str = result.get("system", "unknown").lower()
        
        system_map = {
            "salesforce": RoutingSystem.SALESFORCE,
            "billing": RoutingSystem.BILLING
        }
        system = system_map.get(system_str, RoutingSystem.UNKNOWN)
        
    except Exception as e:
        logger.error(f"LLM classification failed: {e}")
        return RoutingSystem.UNKNOWN, 0.5, f"LLM error: {str(e)}"  # ⚠️ Logs error string
```

**Problem**:
- Catches all exceptions too broadly
- Returns generic error message
- Doesn't distinguish error types
- Exposes internal error details

**Impact**:
- Loss of debugging information
- Security information disclosure
- Difficult troubleshooting

**Recommendation**:
1. Catch specific exceptions
2. Log appropriate error details
3. Don't expose error strings

**Fix**:
```python
def classify_with_llm(self, state: Dict[str, Any], llm_client):
    prompt = f"""..."""
    
    try:
        response = llm_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        if not response.choices or not response.choices[0].message:
            logger.warning("Empty LLM response")
            return RoutingSystem.UNKNOWN, 0.5, "LLM returned empty response"
        
        content = response.choices[0].message.content
        result = json.loads(content)
        
        # Validate response structure
        if "system" not in result:
            logger.warning(f"LLM response missing 'system' field: {list(result.keys())}")
            return RoutingSystem.UNKNOWN, 0.5, "Invalid LLM response format"
        
        system_str = result.get("system", "unknown").lower()
        
        system_map = {
            "salesforce": RoutingSystem.SALESFORCE,
            "billing": RoutingSystem.BILLING
        }
        system = system_map.get(system_str, RoutingSystem.UNKNOWN)
        confidence = float(result.get("confidence", 0.5))
        reasoning = result.get("reasoning", "LLM classification")
        
        return system, confidence, reasoning
        
    except json.JSONDecodeError as e:
        logger.warning("LLM response was not valid JSON")
        return RoutingSystem.UNKNOWN, 0.5, "LLM response parsing failed"
    except (KeyError, TypeError, ValueError) as e:
        logger.warning(f"LLM response had unexpected format: {type(e).__name__}")
        return RoutingSystem.UNKNOWN, 0.5, "LLM response validation failed"
    except Exception as e:
        logger.error(f"Unexpected error during LLM classification", exc_info=True)
        return RoutingSystem.UNKNOWN, 0.5, "Classification service unavailable"
```

---

## 3. MEDIUM-SEVERITY ISSUES

### 3.1 Missing Timezone Handling

**Location**: [app/services/job_service.py](app/services/job_service.py#L8), [app/integrations/db.py](app/integrations/db.py#L7)  
**Severity**: 🟡 MEDIUM  
**CWE**: CWE-822 (Untrusted Pointer Dereference)

**Vulnerable Code**:
```python
updated_at=datetime.utcnow()  # Uses UTC but timezone-naive
created_at = Column(DateTime, default=datetime.utcnow)  # Timezone-naive
```

**Problem**:
- datetime.utcnow() returns naive datetime
- Stores without timezone info
- Comparisons may be wrong if system time is changed

**Recommendation**:
1. Use timezone-aware datetimes
2. Always use UTC

**Fix**:
```python
from datetime import datetime, timezone

updated_at=datetime.now(timezone.utc)
created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
```

---

### 3.2 Incomplete Data Validation in Routing Classifier

**Location**: [app/agent/router.py](app/agent/router.py#L77-L96)  
**Severity**: 🟡 MEDIUM  
**CWE**: CWE-20 (Improper Input Validation)

**Vulnerable Code**:
```python
def check_context_rules(self, state: Dict[str, Any]) -> Optional[Tuple[RoutingSystem, str]]:
    message = state.get("message", "").lower()  # Could be None
    backend_context = state.get("backend_context", {})  # Could be None
    
    # Rule 1: Payment amount mentioned
    if any(word in message for word in ["$", "amount", "total", "cost"]):
        if any(marker in str(backend_context) for marker in ["amount", "payment", "price"]):
            return RoutingSystem.BILLING, "Payment amount detected in context"
```

**Problem**:
- message could be None, raises TypeError
- backend_context could be None
- str(None) returns "None" string

**Recommendation**:
1. Add type validation
2. Handle None values
3. Add assertions

**Fix**:
```python
def check_context_rules(self, state: Dict[str, Any]) -> Optional[Tuple[RoutingSystem, str]]:
    message = state.get("message", "") or ""
    if not isinstance(message, str):
        message = str(message) if message else ""
    
    message = message.lower()
    
    backend_context = state.get("backend_context") or {}
    if not isinstance(backend_context, dict):
        logger.warning(f"backend_context is not dict: {type(backend_context)}")
        backend_context = {}
```

---

### 3.3 No Validation of Date Format in Contracts

**Location**: [app/agent/contract_tools.py](app/agent/contract_tools.py#L8-L23)  
**Severity**: 🟡 MEDIUM  
**CWE**: CWE-138 (Improper Neutralization of Special Elements used in an SQL Command)

**Vulnerable Code**:
```python
def validate_contract_dates(move_in_date: str, move_out_date: str) -> dict:
    """Validate move-in and move-out dates"""
    errors = []
    
    try:
        # Parse dates (expecting YYYY-MM-DD format)
        move_in = datetime.strptime(move_in_date, "%Y-%m-%d")
        move_out = datetime.strptime(move_out_date, "%Y-%m-%d")
        
        # Check that move-out is after move-in
        if move_out <= move_in:
            errors.append("Move-out date must be after move-in date")
        
        # Check that move-in is not in the past - use date only, not datetime
        today = datetime.now().date()
        if move_in.date() < today:
            errors.append("Move-in date cannot be in the past")  # ⚠️ Harsh rule
```

**Problem**:
- Doesn't allow today as move-in date
- No maximum duration check (could be 100 years)
- No business rule validation

**Impact**:
- Legitimate contracts rejected
- Invalid contracts accepted

**Recommendation**:
1. Allow today or future
2. Add max duration
3. Add business rules

**Fix**:
```python
from datetime import datetime, timedelta

def validate_contract_dates(move_in_date: str, move_out_date: str) -> dict:
    """Validate move-in and move-out dates"""
    errors = []
    
    try:
        move_in = datetime.strptime(move_in_date, "%Y-%m-%d")
        move_out = datetime.strptime(move_out_date, "%Y-%m-%d")
        
        # Check that move-out is after move-in (at least 1 day)
        if move_out <= move_in:
            errors.append("Move-out date must be after move-in date")
        
        # Check that move-in is not in the past (allow today or future)
        today = datetime.now().date()
        if move_in.date() < today:
            errors.append("Move-in date cannot be before today")
        
        # Check max duration (e.g., 5 years)
        max_duration = timedelta(days=365*5)
        actual_duration = move_out - move_in
        if actual_duration > max_duration:
            errors.append(f"Lease duration cannot exceed {5 * 365} days")
        
        # Check minimum duration (e.g., 1 month)
        min_duration = timedelta(days=28)
        if actual_duration < min_duration:
            errors.append("Lease duration must be at least 28 days")
            
    except ValueError as e:
        errors.append(f"Invalid date format. Please use YYYY-MM-DD format. Error: {e}")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors
    }
```

---

### 3.4 No Verification of Salesforce Response Structure

**Location**: [app/integrations/salesforce.py](app/integrations/salesforce.py#L37-L53)  
**Severity**: 🟡 MEDIUM  
**CWE**: CWE-476 (NULL Pointer Dereference)

**Vulnerable Code**:
```python
response = requests.post(url, data=payload, timeout=20)
logger.info(f"Salesforce response status: {response.status_code}")
logger.info(f"Salesforce response body: {response.text}")  # ⚠️ Logs credentials
response.raise_for_status()
data = response.json()
self.access_token = data["access_token"]  # ⚠️ Could KeyError
self.instance_url = data["instance_url"]  # ⚠️ Could KeyError
```

**Problem**:
- Doesn't verify required fields exist
- Could throw KeyError
- No validation of response format

**Impact**:
- Crashes on unexpected response
- Difficult debugging

**Recommendation**:
1. Validate response structure
2. Use get() with defaults
3. Raise meaningful errors

**Fix**:
```python
response = requests.post(url, data=payload, timeout=20)
logger.info(f"Salesforce response status: {response.status_code}")
response.raise_for_status()

try:
    data = response.json()
except json.JSONDecodeError:
    logger.error("Salesforce returned invalid JSON")
    raise ValueError("Salesforce authentication failed - invalid response")

# Validate required fields
if "access_token" not in data:
    logger.error("Salesforce response missing access_token")
    raise ValueError("Salesforce authentication failed - no access token")

if "instance_url" not in data:
    logger.error("Salesforce response missing instance_url")
    raise ValueError("Salesforce authentication failed - no instance URL")

self.access_token = data["access_token"].strip()
self.instance_url = data["instance_url"].strip()
```

---

## 4. LOW-SEVERITY ISSUES

### 4.1 Deprecated datetime.utcnow()

**Location**: Multiple files  
**Severity**: 🔵 LOW  
**CWE**: CWE-1104 (Use of Unmaintained Third Party Components)

**Recommendation**:
- `datetime.utcnow()` is deprecated in Python 3.12+
- Switch to `datetime.now(timezone.utc)`

### 4.2 Missing CORS Configuration

**Location**: [app/main.py](app/main.py)  
**Severity**: 🔵 LOW  
**CWE**: CWE-16 (Configuration)

**Problem**:
- No CORS middleware configured
- Could block browser requests

**Fix**:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "localhost").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 5. CODE QUALITY ISSUES

### 5.1 Missing Type Hints

**Location**: Multiple files  
**Issue**: Many functions lack type hints
**Recommendation**: Add comprehensive type hints

```python
# Before
def get_job(job_id):
    ...

# After
def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    ...
```

### 5.2 Insufficient Logging

**Location**: All worker threads  
**Issue**: Missing structured logging
**Recommendation**: Add structured logging with context

```python
logger.info(
    "Job processing started",
    extra={
        "job_id": job_id,
        "user_id": state.get("user_id"),
        "issue_type": state.get("issue_type")
    }
)
```

### 5.3 No Configuration Validation

**Location**: [app/config.py](app/config.py)  
**Issue**: Settings not validated on startup
**Recommendation**: Validate all required settings

```python
def validate_settings():
    required = ["OPENAI_API_KEY", "SF_CLIENT_ID", "SF_CLIENT_SECRET"]
    for key in required:
        if not getattr(settings, key):
            raise ValueError(f"Missing required setting: {key}")

# In main.py
@app.on_event("startup")
def startup():
    validate_settings()
    init_db()
```

---

## 6. DEPENDENCY ISSUES

### 6.1 Missing Version Pinning in requirements.txt

**Issue**: Dependencies not pinned to specific versions  
**Recommendation**: Pin all dependencies

```
# Current
fastapi
uvicorn

# Recommended
fastapi==0.104.1
uvicorn==0.24.0
```

---

## 7. RECOMMENDED SECURITY IMPROVEMENTS

### 7.1 Add Authentication & Authorization
```python
# Implement JWT-based auth
from fastapi_jwt_auth import AuthJWT

@app.get("/jobs/{job_id}")
def get_job(job_id: str, Authorize: AuthJWT = Depends()):
    Authorize.jwt_required()
    current_user = Authorize.get_jwt_subject()
```

### 7.2 Add Request Validation Middleware
```python
# Validate all inputs
from pydantic import ValidationError

@app.middleware("http")
async def validate_request(request: Request, call_next):
    # Check content length
    if request.headers.get("content-length"):
        length = int(request.headers["content-length"])
        if length > 1_000_000:  # 1MB limit
            return JSONResponse(
                status_code=413,
                content={"detail": "Request too large"}
            )
```

### 7.3 Add Database Connection Pooling
```python
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,  # Recycle connections after 1 hour
    connect_args={"check_same_thread": False}
)
```

### 7.4 Add Request ID Tracking
```python
import uuid
from fastapi import Request

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
```

---

## 8. TESTING RECOMMENDATIONS

### 8.1 Add Security Tests
```python
def test_sql_injection():
    """Test SOQL injection protection"""
    malicious_user_id = "user' OR '1'='1"
    # Assert properly escaped
    ...

def test_auth_required():
    """Test endpoints require auth"""
    response = client.post("/jobs", json={...})
    assert response.status_code == 401
```

### 8.2 Add Concurrency Tests
```python
def test_concurrent_job_processing():
    """Test race condition handling"""
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(create_job, payload)
            for _ in range(10)
        ]
        results = [f.result() for f in futures]
        # Assert no duplicates
        assert len(set(results)) == len(results)
```

---

## 9. REMEDIATION PRIORITY

| Priority | Issues | Timeline |
|----------|--------|----------|
| CRITICAL | SQL Injection, Auth, Race Conditions | ASAP (1-2 days) |
| HIGH | Validation, Error Handling, Rate Limiting | 1 week |
| MEDIUM | Timezone, Date Validation | 2 weeks |
| LOW | Type Hints, CORS, Logging | 4 weeks |

---

## 10. CONCLUSION

This application has significant security vulnerabilities that must be addressed immediately. The most critical issues are:

1. **SQL Injection** - Can expose all data
2. **Missing Authentication** - Anyone can access all users' data
3. **Race Conditions** - Data corruption risk
4. **Insufficient Validation** - DoS and data integrity issues

**Immediate Actions Required:**
1. Implement parameterized queries
2. Add authentication middleware
3. Fix race conditions with transactions
4. Add comprehensive input validation
5. Implement rate limiting
6. Review all logging for credential exposure

**Success Criteria:**
- All CRITICAL issues resolved
- 90% of HIGH issues resolved
- Security review passed
- Penetration test clean
- No sensitive data in logs

