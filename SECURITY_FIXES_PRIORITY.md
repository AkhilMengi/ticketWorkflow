# 🚨 Critical Security Fixes - Priority Action Plan

## Quick Summary
Your app has **21 issues** identified: 7 critical, 8 high, 4 medium, 2 low.

**Most critical issues need fixing IMMEDIATELY:**

---

## 🔴 PHASE 1: CRITICAL (Fix in next 48 hours)

### 1️⃣ SQL Injection in SOQL Query
**File**: `app/integrations/salesforce.py` → `lookup_cases_by_user()` method  
**Risk**: Attackers can extract all Salesforce data  
**Fix**: Escape user inputs before SOQL query

```python
# ❌ BEFORE (VULNERABLE)
query = f"SELECT Id FROM Case WHERE External_User_Id__c = '{user_id}'"

# ✅ AFTER (FIXED)
from html import escape
escaped_user_id = escape(user_id).replace("'", "\\'")
query = f"SELECT Id FROM Case WHERE External_User_Id__c = '{escaped_user_id}'"
```

---

### 2️⃣ Credentials Logged in Plain Text
**File**: `app/integrations/salesforce.py` → `login()` method  
**Risk**: Access tokens exposed in logs, can be stolen  
**Fix**: Never log response body containing tokens

```python
# ❌ BEFORE (VULNERABLE)
logger.info(f"Salesforce response body: {response.text}")  # LOGS TOKEN!

# ✅ AFTER (FIXED)
# Don't log response body
if response.status_code == 200:
    logger.info("Successfully authenticated with Salesforce")
else:
    logger.error(f"Auth failed with status {response.status_code}")
```

---

### 3️⃣ No Authentication on API Routes
**File**: `app/api/routes.py` → All endpoints  
**Risk**: Anyone can access/modify anyone's data  
**Fix**: Add authentication middleware

```python
# ❌ BEFORE (VULNERABLE)
@router.post("/jobs")
def create_agent_job(payload: CreateJobRequest):
    # NO AUTH CHECK - ANYONE CAN CALL THIS

# ✅ AFTER (FIXED)
from fastapi import Depends, HTTPException, status

def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization")
    token = authorization.replace("Bearer ", "")
    # Validate JWT token here
    return verify_jwt_token(token)

@router.post("/jobs")
def create_agent_job(payload: CreateJobRequest, user = Depends(get_current_user)):
    # NOW Protected
    if payload.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Cannot access other users' data")
```

---

### 4️⃣ Case Parameter Bypass
**File**: `app/api/routes.py` → `update_case()` endpoint  
**Risk**: Users can modify other users' cases  
**Fix**: Verify path parameter matches body, check ownership

```python
# ❌ BEFORE (VULNERABLE)
@router.patch("/cases/{case_id}")
def update_case(case_id: str, payload: UpdateCaseRequest):
    sf_client.update_case(case_id=payload.case_id)  # Uses payload, not path!

# ✅ AFTER (FIXED)
@router.patch("/cases/{case_id}")
def update_case(case_id: str, payload: UpdateCaseRequest, user = Depends(get_current_user)):
    if case_id != payload.case_id:
        raise HTTPException(400, "Path and body case_id must match")
    
    # Verify user owns this case
    case = sf_client.get_case(case_id)
    if case["External_User_Id__c"] != user.user_id:
        raise HTTPException(403, "Cannot modify cases you don't own")
    
    sf_client.update_case(case_id=case_id, ...)
```

---

### 5️⃣ No Input Validation (Buffer Overflow Risk)
**File**: `app/api/schemas.py`  
**Risk**: Huge payloads can crash the server  
**Fix**: Add max length constraints

```python
# ❌ BEFORE (VULNERABLE)
class CreateJobRequest(BaseModel):
    user_id: str           # ⚠️ No limit, could be 10MB
    message: str           # ⚠️ No limit, could be 100MB

# ✅ AFTER (FIXED)
from pydantic import BaseModel, Field

class CreateJobRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., max_length=5000)
    issue_type: str = Field(..., max_length=50)
```

---

### 6️⃣ Race Condition in Worker
**File**: `app/workers/worker.py`  
**Risk**: Jobs processed twice, data corruption  
**Fix**: Use database transactions with locks

```python
# ❌ BEFORE (VULNERABLE)
def worker_loop():
    while True:
        state = job_queue.get()
        update_job(job_id, "processing")
        try:
            agent_graph.invoke(state)  # Process can crash here
        except Exception:
            update_job(job_id, "failed")
        # If process crashes between states = data inconsistent

# ✅ AFTER (FIXED)
from sqlalchemy import func

def worker_loop():
    while True:
        state = job_queue.get()
        job_id = state["job_id"]
        
        with db_transaction():
            # Lock the row
            job = db.query(JobRecord).filter(
                JobRecord.job_id == job_id
            ).with_for_update().first()
            
            if job.status != "queued":
                continue  # Already processed by another worker
            
            job.status = "processing"
            db.flush()
        
        try:
            result = agent_graph.invoke(state)
            with db_transaction():
                job = db.query(JobRecord).filter(
                    JobRecord.job_id == job_id
                ).with_for_update().first()
                job.status = "completed"
                job.result = result
        except Exception as e:
            with db_transaction():
                job = db.query(JobRecord).filter(
                    JobRecord.job_id == job_id
                ).with_for_update().first()
                job.status = "failed"
                job.error = str(e)
```

---

### 7️⃣ Hardcoded Salesforce API Version
**File**: `app/integrations/salesforce.py` (appears 7 times)  
**Risk**: Service breaks if Salesforce deprecates API  
**Fix**: Move to configuration

```python
# ❌ BEFORE (VULNERABLE)
url = f"{instance_url}/services/data/v61.0/sobjects/Case"  # Hardcoded!

# ✅ AFTER (FIXED)
# In config.py
SF_API_VERSION = os.getenv("SF_API_VERSION", "v61.0")

# Then in salesforce.py
url = f"{self.instance_url}/services/data/{settings.SF_API_VERSION}/sobjects/Case"
```

---

## 🟠 PHASE 2: HIGH (Fix within 1 week)

| # | Issue | File | Quick Fix |
|---|-------|------|-----------|
| 1 | Unvalidated user ID format | `salesforce.py` | Add regex validation: `^[a-zA-Z0-9_-]{1,255}$` |
| 2 | Type confusion in results | `worker.py` | Validate result is dict before processing |
| 3 | No error handling in LLM | `nodes.py` | Wrap `json.loads()` in try/except |
| 4 | DB connections not closed | `job_service.py` | Use context manager `with db` |
| 5 | No rate limiting | `routes.py` | Add `@limiter.limit("100/hour")` |
| 6 | Unlimited memory retrieval | `memory.py` | Add `.limit(100)` to query |
| 7 | Missing parameter validation | `salesforce.py` | Check `subject != ""` before API call |
| 8 | Broad exception handling | `router.py` | Catch specific exceptions, not all |

---

## 🟡 PHASE 3: MEDIUM (Fix within 2 weeks)

1. **No CORS validation** - Add specific allowed origins
2. **Weak token generation** - Use `secrets.token_urlsafe()`
3. **No audit logging** - Log all sensitive operations
4. **Missing OpenAPI auth** - Add security scheme to FastAPI docs

---

## 📋 Action Checklist

- [ ] **48 hours**: Fix all 7 CRITICAL issues (authentication, SQL injection, race conditions)
- [ ] **1 week**: Fix all 8 HIGH issues (validation, error handling, rate limiting)
- [ ] **2 weeks**: Fix all 4 MEDIUM issues (logging, CORS, tokens)
- [ ] **1 month**: Implement automated security testing

---

## 🛡️ Testing the Fixes

After implementing fixes, test with these scenarios:

```bash
# Test 1: SQL Injection
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user123\" OR 1=1 --", "message": "test"}'
# Should validate and reject

# Test 2: Authentication
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "message": "test"}'
# Should return 401 Unauthorized

# Test 3: Authorization
# User A tries to access User B's data - should return 403

# Test 4: Rate Limiting
# Make 101 requests in 1 hour - 101st should return 429 Too Many Requests

# Test 5: Input Validation
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"user_id": "' + ('x' * 10000) + '", "message": "test"}'
# Should return 422 Validation Error
```

---

## 📞 Need Help?

The complete audit report is in `SECURITY_AUDIT_REPORT.md` with:
- Exact line numbers
- Full code examples
- Detailed explanations
- CWE references
- Attack scenarios

