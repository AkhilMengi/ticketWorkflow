# 🔓 Security Fixes - Implementation Guide

## ✅ FIXES ALREADY IMPLEMENTED

### 1. Salesforce Integration (salesforce.py) - ✅ COMPLETE
Fixed:
- ✅ Removed credential logging (no more token exposure)
- ✅ Added SOQL injection protection with `escape_soql_string()`
- ✅ Added input validation to all methods
- ✅ Moved API version to config (`self.api_version`)
- ✅ Improved error handling (no sensitive data in logs)
- ✅ Parameter validation for case_id, user_id, etc.

### 2. Auth Module (auth.py) - ✅ CREATED
- ✅ JWT token generation and verification
- ✅ Authorization header parsing
- ✅ Current user extraction
- ✅ Proper HTTP exception handling

### 3. Security Utils (security_utils.py) - ✅ CREATED
- ✅ SOQL string escaping function
- ✅ User ID format validation
- ✅ String field validation
- ✅ Safe logging utilities

### 4. Config (config.py) - ✅ UPDATED
- ✅ SF_API_VERSION configurable from environment
- ✅ SECRET_KEY configuration
- ✅ Token expiration settings

---

## 🔴 REMAINING CRITICAL FIXES (Step-by-Step)

### STEP 1: Update API Schemas (app/api/schemas.py)

Add max length constraints to prevent buffer overflow:

```python
# Inside schemas.py, update or add these validators:

from pydantic import BaseModel, Field, constr, validator

class CreateJobRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=255, description="User identifier")
    issue_type: str = Field(..., min_length=1, max_length=50, description="Issue type")
    message: Optional[str] = Field(None, max_length=5000, description="Request message")
    backend_context: Optional[Dict] = Field(None, description="Backend context data")
    
    @validator('user_id')
    def validate_user_id(cls, v):
        if not v or len(v) > 255:
            raise ValueError('Invalid user_id')
        return v

class UpdateCaseRequest(BaseModel):
    case_id: str = Field(..., min_length=15, max_length=18, description="Salesforce case ID")
    subject: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=4000)
    status: Optional[str] = Field(None, max_length=50)
    priority: Optional[str] = Field(None, max_length=50)
    agent_result: Optional[Dict] = None

class LookupCasesRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=255)
    status: str = Field("New", regex="^(New|In Progress|Closed|On Hold|Escalated)$")
```

---

### STEP 2: Update API Routes (app/api/routes.py)

Add authentication and authorization:

```python
from fastapi import APIRouter, HTTPException, Depends, Header
from app.auth import get_current_user  # ✅ NEW
from fastapi_limiter import FastAPILimiter  # ✅ NEW - Rate limiting
from fastapi_limiter.depends import RateLimiter

router = APIRouter()

# ✅ FIX 1: Add authentication to ALL endpoints

@router.post("/jobs", response_model=CreateJobResponse)
def create_agent_job(
    payload: CreateJobRequest, 
    current_user: Dict = Depends(get_current_user)  # ✅ NEW
):
    # ✅ FIX 2: Verify user can only create jobs for themselves
    if payload.user_id != current_user["user_id"]:
        raise HTTPException(
            status_code=403,
            detail="Cannot create jobs for another user"
        )
    
    # ... rest of function

@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(
    job_id: str,
    current_user: Dict = Depends(get_current_user)  # ✅ NEW
):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # ✅ FIX 3: Verify user owns this job
    if job["user_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=403,
            detail="Cannot access other users' jobs"
        )
    
    return JobStatusResponse(...)

# ✅ FIX 4: Fix authorization bypass in update_case

@router.patch("/cases/{case_id}", response_model=UpdateCaseResponse)
def update_case(
    case_id: str,
    payload: UpdateCaseRequest,
    current_user: Dict = Depends(get_current_user)  # ✅ NEW
):
    # ✅ CRITICAL: Use path parameter, not payload
    if case_id != payload.case_id:
        raise HTTPException(
            status_code=400,
            detail="Path and body case_id must match"
        )
    
    # ✅ NEW: Verify user owns the case
    sf_client = SalesforceClient()
    case = sf_client.get_case(case_id)  # Implement this method
    
    if case.get("External_User_Id__c") != current_user["user_id"]:
        raise HTTPException(
            status_code=403,
            detail="Cannot modify cases you don't own"
        )
    
    try:
        result = sf_client.update_case(
            case_id=case_id,  # ✅ Use case_id from path
            ...
        )
        return UpdateCaseResponse(success=True, message=f"Case {case_id} updated")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Update failed")
```

---

### STEP 3: Update Worker (app/workers/worker.py)

Fix race conditions with database transactions:

```python
# Add to worker.py:

from contextlib import contextmanager
from sqlalchemy import func

@contextmanager
def db_transaction():
    """Context manager for database transactions"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def worker_loop():
    while True:
        state = job_queue.get()
        job_id = state["job_id"]

        try:
            # ✅ FIX: Use database lock to prevent duplicate processing
            with db_transaction() as db:
                # Lock the row to prevent concurrent processing
                job_record = db.query(JobRecord).filter(
                    JobRecord.job_id == job_id
                ).with_for_update().first()
                
                if job_record.status != "queued":
                    logger.info(f"Job {job_id} already processed, skipping")
                    job_queue.task_done()
                    continue
                
                job_record.status = "processing"
                db.flush()
            
           # Process outside of transaction
            result = routing_graph.invoke(state)
            
            # ✅ FIX: Update result in transaction
            with db_transaction() as db:
                job_record = db.query(JobRecord).filter(
                    JobRecord.job_id == job_id
                ).with_for_update().first()
                
                job_record.status = "completed"
                job_record.result = json.dumps(result)
                db.flush()
                
        except Exception as e:
            with db_transaction() as db:
                job_record = db.query(JobRecord).filter(
                    JobRecord.job_id == job_id
                ).with_for_update().first()
                
                job_record.status = "failed"
                job_record.error = str(e)
                db.flush()
```

---

### STEP 4: Update Memory Service (app/agent/memory.py)

Add pagination to prevent unlimited queries:

```python
# In memory.py:

class MemoryService:
    @staticmethod
    def get_long_term_memory(user_id: str, limit: int = 100, offset: int = 0):
        """Get user's long-term memory with pagination"""
        db = SessionLocal()
        try:
            records = db.query(MemoryRecord).filter(
                MemoryRecord.user_id == user_id
            ).order_by(
                MemoryRecord.created_at.desc()
            ).limit(limit).offset(offset).all()  # ✅ Added LIMIT and OFFSET
            
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

### STEP 5: Update LLM Error Handling (app/agent/nodes.py)

Add try/except around LLM calls:

```python
# In decision_node() or similar LLM-calling functions:

def decision_node(state):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        if not response.choices or not response.choices[0].message:
            logger.warning("Empty LLM response")
            # ✅ Fallback to safe action
            return {
                "next_action": "finish",
                "event_log": state["event_log"] + [{
                    "type": "decision_error",
                    "error": "Empty LLM response",
                    "fallback_action": "finish"
                }]
            }
        
        content = response.choices[0].message.content
        parsed = json.loads(content)
        
        # ✅ Validate required fields
        required_fields = {"action", "thought", "rationale"}
        if not all(field in parsed for field in required_fields):
            raise ValueError(f"Missing required fields: {required_fields - set(parsed.keys())}")
        
        return {
            "next_action": parsed["action"],
            "event_log": state["event_log"] + [{...}]
        }
        
    except json.JSONDecodeError:
        logger.warning("LLM response was not valid JSON")
        return safe_fallback()
    except Exception as e:
        logger.error(f"Unexpected error in decision node: {type(e).__name__}")
        return safe_fallback()

def safe_fallback():
    """Safe fallback when LLM fails"""
    return {
        "next_action": "finish",
        "event_log": [{
            "type": "decision_error",
            "fallback": "finish"
        }]
    }
```

---

### STEP 6: Install Required Packages

Add to `requirements.txt`:

```
PyJWT>=2.8.0  # For JWT token handling
pydantic>=2.0  # For field validation
python-multipart>=0.0.5  # For authentication headers
```

Run:
```bash
pip install PyJWT pydantic python-multipart
```

---

## 📋 Quick Checklist

- [ ] Implement Step 1: Update schemas.py
- [ ] Implement Step 2: Update routes.py with auth
- [ ] Implement Step 3: Fix worker.py race conditions
- [ ] Implement Step 4: Add pagination to memory.py
- [ ] Implement Step 5: Add error handling to nodes.py
- [ ] Install required packages (Step 6)
- [ ] Update .env file:
  ```
  SECRET_KEY=your-random-secret-key-here
  SF_API_VERSION=v61.0
  TOKEN_EXPIRATION_HOURS=24
  ```
- [ ] Test authentication: `curl -H "Authorization: Bearer TOKEN" http://localhost:8000/api/jobs`
- [ ] Test validation: Send oversized payload, should get 422 Validation Error

---

## 🧪 Post-Implementation Testing

```bash
# Test 1: SQL Injection protection
curl -X GET "http://localhost:8000/api/cases?user_id=user' OR '1'='1"
# Expected: 422 Validation Error (should not process)

# Test 2: Auth required
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","message":"test"}'
# Expected: 401 Unauthorized

# Test 3: Input validation
curl -X POST http://localhost:8000/api/jobs \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"' + ('x' * 10000) + '", "message":"test"}'
# Expected: 422 Validation Error (too long)

# Test 4: Authorization bypass
# User A token tries to access User B's job
# Expected: 403 Forbidden
```

---

## 📝 Notes

- All CRITICAL issues require immediate implementation
- Test each step in order
- Keep .env file secure (don't commit to git)
- Rotate SECRET_KEY in production regularly

