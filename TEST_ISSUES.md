# Test Issues for Smart Agent with Case Editing

**Use these issue descriptions to test the agent's ability to match, edit, and manage cases.**

---

## Test Case 1: Update Priority (INTENT_EDIT)

**Account ID:** ACC-001

**Issue Description:**
```
This billing issue is critical and needs urgent attention. 
Please mark it as high priority now.
```

**Expected Behavior:**
- Agent fetches recent_open_cases for ACC-001
- Matches "billing issue" to recent case: "Billing discrepancy"
- Extracts intent: INTENT_EDIT
- Recommends: `edit_case` with `{"Priority": "High"}`
- Updates Salesforce case priority

**Expected Output:**
```json
{
  "confidence_score": 9,
  "analysis": "Customer wants to elevate priority of their billing issue to urgent status.",
  "recommended_actions": ["edit_case"],
  "edit_case_payload": {
    "case_id": "MOCK-ACC-001-CASE-001",
    "field_updates": {"Priority": "High"},
    "account_id": "ACC-001"
  }
}
```

---

## Test Case 2: Add Comment/Note (INTENT_COMMENT)

**Account ID:** ACC-002

**Issue Description:**
```
Hi, regarding the feature request case - I've verified that the API 
rate limit increase is needed for our production migration scheduled 
next week. Please add this urgency context to the case.
```

**Expected Behavior:**
- Agent fetches recent_open_cases for ACC-002
- Matches "feature request" to recent case: "Feature request - API rate limits"
- Extracts intent: INTENT_COMMENT
- Recommends: `add_comment_to_case` with customer message
- Adds comment to Salesforce case

**Expected Output:**
```json
{
  "confidence_score": 8,
  "analysis": "Customer is providing update on existing feature request case regarding API rate limits.",
  "recommended_actions": ["add_comment_to_case"],
  "add_comment_payload": {
    "case_id": "MOCK-ACC-002-CASE-002",
    "comment_body": "I've verified that the API rate limit increase is needed for our production migration scheduled next week. Please add this urgency context to the case.",
    "account_id": "ACC-002"
  }
}
```

---

## Test Case 3: Update Status (INTENT_EDIT)

**Account ID:** ACC-003

**Issue Description:**
```
We've started working on the resolution. Please update the case 
status to 'In Progress' so the team knows work has begun.
```

**Expected Behavior:**
- Agent fetches recent_open_cases for ACC-003
- Matches generic issue to first/most recent case
- Extracts intent: INTENT_EDIT
- Recommends: `edit_case` with `{"Status": "In Progress"}`
- Updates Salesforce case status

**Expected Output:**
```json
{
  "confidence_score": 7,
  "analysis": "Customer is updating case status to reflect work in progress.",
  "recommended_actions": ["edit_case"],
  "edit_case_payload": {
    "case_id": "MOCK-ACC-003-CASE-001",
    "field_updates": {"Status": "In Progress"},
    "account_id": "ACC-003"
  }
}
```

---

## Test Case 4: Close Case (INTENT_CLOSE)

**Account ID:** ACC-004

**Issue Description:**
```
The billing issue has been resolved. The duplicate charge has been 
refunded and credited back to our account. Please close this case now.
```

**Expected Behavior:**
- Agent fetches recent_open_cases for ACC-004
- Matches "billing issue" to recent case
- Extracts intent: INTENT_CLOSE
- Recommends: `close_case` with reason
- Closes Salesforce case

**Expected Output:**
```json
{
  "confidence_score": 9,
  "analysis": "Customer confirms issue resolution and requests case closure.",
  "recommended_actions": ["close_case"],
  "close_case_payload": {
    "case_id": "MOCK-ACC-004-CASE-001",
    "reason": "Duplicate charge refunded and credited. Issue resolved.",
    "account_id": "ACC-004"
  }
}
```

---

## Test Case 5: Multiple Actions (INTENT_EDIT + INTENT_BILLING)

**Account ID:** ACC-005

**Issue Description:**
```
This is urgent - we've been double-charged $150. Please:
1. Mark the case as High priority
2. Issue a refund of $150 immediately
```

**Expected Behavior:**
- Extracts intent: INTENT_EDIT + INTENT_BILLING
- Recommends: `edit_case` + `call_billing_api`
- Updates priority AND processes refund

**Expected Output:**
```json
{
  "confidence_score": 9,
  "analysis": "Customer reports duplicate charge ($150) and requests urgent priority on their case while billing action is needed.",
  "recommended_actions": ["edit_case", "call_billing_api"],
  "edit_case_payload": {
    "case_id": "MOCK-ACC-005-CASE-001",
    "field_updates": {"Priority": "High"},
    "account_id": "ACC-005"
  },
  "billing_payload": {
    "account_id": "ACC-005",
    "action_type": "refund",
    "amount": 150.00,
    "currency": "USD",
    "reason": "DUPLICATE_CHARGE",
    "notes": "Double-charged $150. Customer requests immediate refund."
  }
}
```

---

## Test Case 6: Escalation (INTENT_EDIT)

**Account ID:** ACC-006

**Issue Description:**
```
This case needs management attention. The customer is threatening 
to cancel their contract. Please escalate this immediately.
```

**Expected Behavior:**
- Extracts intent: INTENT_EDIT (escalation flag)
- Recommends: `edit_case` with escalation metadata
- Flags case for escalation

**Expected Output:**
```json
{
  "confidence_score": 8,
  "analysis": "High-risk customer retention issue requiring immediate escalation to management.",
  "recommended_actions": ["edit_case"],
  "edit_case_payload": {
    "case_id": "MOCK-ACC-006-CASE-001",
    "field_updates": {"Priority": "High", "Type": "Escalation"},
    "account_id": "ACC-006"
  }
}
```

---

## Test Case 7: No Case Match (INTENT_CREATE)

**Account ID:** ACC-007

**Issue Description:**
```
We just discovered a critical bug in the API integration. 
The authentication endpoint is returning 500 errors randomly.
This is affecting our production environment.
```

**Expected Behavior:**
- Agent fetches recent_open_cases for ACC-007 (no matching cases)
- Extracts intent: INTENT_CREATE
- Recommends: `create_sf_case` (not edit)
- Creates NEW case since no match found

**Expected Output:**
```json
{
  "confidence_score": 9,
  "analysis": "New critical production issue requiring case creation for tracking and resolution.",
  "recommended_actions": ["create_sf_case"],
  "sf_case_payload": {
    "subject": "Critical API Bug - Authentication endpoint 500 errors",
    "description": "The authentication endpoint is returning 500 errors randomly, affecting production environment. API integration is broken.",
    "priority": "High",
    "status": "New",
    "origin": "Web",
    "account_id": "ACC-007"
  }
}
```

---

## Quick Test Script

Run these in sequence to test the agent:

```bash
# Test 1: Priority Update
curl -X POST http://localhost:8000/api/issue \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "ACC-001",
    "issue_description": "This billing issue is critical and needs urgent attention. Please mark it as high priority now."
  }'

# Test 2: Add Comment
curl -X POST http://localhost:8000/api/issue \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "ACC-002",
    "issue_description": "Hi, regarding the feature request case - I have verified that the API rate limit increase is needed for our production migration scheduled next week."
  }'

# Test 3: Status Update
curl -X POST http://localhost:8000/api/issue \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "ACC-003",
    "issue_description": "We have started working on the resolution. Please update the case status to In Progress so the team knows work has begun."
  }'

# Test 4: Close Case
curl -X POST http://localhost:8000/api/issue \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "ACC-004",
    "issue_description": "The billing issue has been resolved. The duplicate charge has been refunded and credited back to our account. Please close this case now."
  }'

# Test 5: Multiple Actions
curl -X POST http://localhost:8000/api/issue \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "ACC-005",
    "issue_description": "This is urgent - we have been double charged $150. Please mark the case as High priority and issue a refund of $150 immediately."
  }'
```

---

## Key Points to Verify

✅ **Case matching** - Does agent find correct case from recent_open_cases?
✅ **Intent classification** - Does agent identify INTENT_EDIT, INTENT_COMMENT, INTENT_CLOSE correctly?
✅ **Field extraction** - Does LLM extract correct Priority, Status, Amount values?
✅ **Payload generation** - Are payloads properly formatted for API calls?
✅ **Validation** - Does api_validator catch missing case_id before API call?
✅ **Action execution** - Does Salesforce mock return success responses?
✅ **No duplicate actions** - When case_id matches, does agent NOT create new case?
