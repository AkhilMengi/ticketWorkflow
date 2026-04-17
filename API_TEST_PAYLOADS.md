# API Test Payloads

## Base URL
```
http://localhost:8000/api
```

---

## CONTRACT ENDPOINTS

### 1. Create Contract Job
**Method**: `POST /contracts`

**Description**: Create a new contract creation job

**Payload**:
```json
{
  "user_id": "user123",
  "account_id": "001xx000003DHP",
  "tenant_name": "John Doe",
  "property_address": "123 Main Street, Apt 4B, New York, NY 10001",
  "move_in_date": "2026-05-15",
  "move_out_date": "2027-05-14",
  "rent_amount": 2500.00
}
```

**Expected Response** (201):
```json
{
  "job_id": "job_abc123xyz",
  "status": "queued"
}
```

**Test Cases**:

**Case 1: Minimal Valid Contract**
```json
{
  "user_id": "user001",
  "account_id": "001xx000003DHP",
  "tenant_name": "Alice Johnson",
  "property_address": "456 Oak Avenue, Los Angeles, CA 90001",
  "move_in_date": "2026-06-01",
  "move_out_date": "2027-05-31",
  "rent_amount": 3500.00
}
```

**Case 2: Long-term Lease (2 years)**
```json
{
  "user_id": "user002",
  "account_id": "001xx000003DHQ",
  "tenant_name": "Bob Smith",
  "property_address": "789 Elm Street, Suite 200, Chicago, IL 60601",
  "move_in_date": "2026-07-01",
  "move_out_date": "2028-06-30",
  "rent_amount": 1800.50
}
```

**Case 3: High-value Property**
```json
{
  "user_id": "user003",
  "account_id": "001xx000003DHR",
  "tenant_name": "Carol Martinez",
  "property_address": "9999 Luxury Lane, Penthouse Suite, San Francisco, CA 94102",
  "move_in_date": "2026-08-15",
  "move_out_date": "2027-08-14",
  "rent_amount": 8500.00
}
```

**Case 4: Invalid - Move-out before Move-in (Should Fail)**
```json
{
  "user_id": "user004",
  "account_id": "001xx000003DHS",
  "tenant_name": "David Lee",
  "property_address": "111 Test Street, Boston, MA 02101",
  "move_in_date": "2026-12-01",
  "move_out_date": "2026-01-01",
  "rent_amount": 2200.00
}
```

**Case 5: Invalid - Zero Rent (Should Fail)**
```json
{
  "user_id": "user005",
  "account_id": "001xx000003DHT",
  "tenant_name": "Emma Wilson",
  "property_address": "222 Test Ave, Seattle, WA 98101",
  "move_in_date": "2026-09-01",
  "move_out_date": "2027-08-31",
  "rent_amount": 0.00
}
```

---

### 2. Get Contract Job Status
**Method**: `GET /contracts/{job_id}`

**Description**: Get the current status and result of a contract creation job

**URL**: 
```
http://localhost:8000/api/contracts/job_abc123xyz
```

**No Payload Required**

**Expected Response** (200):
```json
{
  "job_id": "job_abc123xyz",
  "status": "completed",
  "result": {
    "status": "success",
    "contract_id": "a0E2X000000IZ3ZUAW",
    "tenant_name": "John Doe",
    "property_address": "123 Main Street, Apt 4B, New York, NY 10001",
    "move_in_date": "2026-05-15",
    "move_out_date": "2027-05-14",
    "rent_amount": 2500.00,
    "message": "Contract #a0E2X000000IZ3ZUAW created successfully"
  }
}
```

**Status Values**:
- `queued` - Job waiting to be processed
- `processing` - Job currently being processed
- `completed` - Job finished successfully
- `failed` - Job failed with error

---

### 3. Update Contract
**Method**: `PATCH /contracts/{contract_id}`

**Description**: Update an existing contract

**URL**:
```
http://localhost:8000/api/contracts/a0E2X000000IZ3ZUAW
```

**Payloads**:

**Case 1: Update Status to Active**
```json
{
  "contract_id": "a0E2X000000IZ3ZUAW",
  "status": "Active"
}
```

**Case 2: Extend Move-Out Date**
```json
{
  "contract_id": "a0E2X000000IZ3ZUAW",
  "move_out_date": "2026-06-30"
}
```

**Case 3: Increase Rent Amount**
```json
{
  "contract_id": "a0E2X000000IZ3ZUAW",
  "rent_amount": 2600.00
}
```

**Case 4: Update All Fields**
```json
{
  "contract_id": "a0E2X000000IZ3ZUAW",
  "status": "Active",
  "move_out_date": "2026-12-31",
  "rent_amount": 2750.00
}
```

**Expected Response** (200):
```json
{
  "success": true,
  "contract_id": "a0E2X000000IZ3ZUAW",
  "message": "Contract a0E2X000000IZ3ZUAW updated successfully"
}
```

---

## CASE/TICKET ENDPOINTS (Existing)

### 1. Create Support Case Job
**Method**: `POST /jobs`

**Description**: Create a new support ticket/case job

**Payload**:
```json
{
  "user_id": "user_support_001",
  "issue_type": "payment_error",
  "message": "I'm getting a payment timeout error when trying to process my subscription renewal"
}
```

**Expected Response** (201):
```json
{
  "job_id": "job_support_123",
  "status": "queued"
}
```

**Test Cases**:

**Case 1: Billing Issue**
```json
{
  "user_id": "user_001",
  "issue_type": "billing",
  "message": "I was charged twice for my subscription this month"
}
```

**Case 2: Technical Issue**
```json
{
  "user_id": "user_002",
  "issue_type": "technical_error",
  "message": "The application crashes when I try to upload a file larger than 10MB"
}
```

**Case 3: Account Issue**
```json
{
  "user_id": "user_003",
  "issue_type": "account_access",
  "message": "I can't reset my password. The reset email is not arriving"
}
```

---

### 2. Get Case Job Status
**Method**: `GET /jobs/{job_id}`

**Description**: Get the status of a case creation job

**URL**:
```
http://localhost:8000/api/jobs/job_support_123
```

**No Payload Required**

**Expected Response** (200):
```json
{
  "job_id": "job_support_123",
  "status": "completed",
  "result": {
    "status": "Agentic",
    "summary": "Payment processing timeout issue",
    "category": "Billing",
    "priority": "High",
    "case_id": "5001400000IZ3Z",
    "message": "Support case created successfully"
  }
}
```

---

### 3. Get Case Events
**Method**: `GET /jobs/{job_id}/events`

**Description**: Stream events from a case creation job

**URL**:
```
http://localhost:8000/api/jobs/job_support_123/events
```

**No Payload Required**

**Expected Response** (200):
```json
{
  "job_id": "job_support_123",
  "events": [
    {
      "type": "job_started",
      "job_id": "job_support_123",
      "timestamp": "2025-01-15T10:30:00Z"
    },
    {
      "type": "decision",
      "thought": "This is a billing-related issue that requires investigating customer payments",
      "action": "fetch_profile",
      "confidence": 0.95,
      "rationale": "Need to get customer tier information for proper priority assessment"
    },
    {
      "type": "tool_result",
      "tool": "get_customer_profile",
      "result": {
        "user_id": "user_support_001",
        "tier": "Pro",
        "subscription_status": "Active"
      },
      "status": "success"
    },
    {
      "type": "classification",
      "summary": "Payment timeout issue during subscription renewal",
      "category": "Billing",
      "priority": "High"
    },
    {
      "type": "case_creation",
      "status": "success",
      "case_id": "5001400000IZ3Z",
      "result": {
        "id": "5001400000IZ3Z",
        "success": true
      }
    },
    {
      "type": "job_completed",
      "job_id": "job_support_123",
      "case_id": "5001400000IZ3Z"
    }
  ]
}
```

---

### 4. Update Case
**Method**: `PATCH /cases/{case_id}`

**Description**: Update an existing support case

**URL**:
```
http://localhost:8000/api/cases/5001400000IZ3Z
```

**Payloads**:

**Case 1: Update Status**
```json
{
  "case_id": "5001400000IZ3Z",
  "status": "In Progress"
}
```

**Case 2: Update Priority**
```json
{
  "case_id": "5001400000IZ3Z",
  "priority": "Critical"
}
```

**Case 3: Update Description**
```json
{
  "case_id": "5001400000IZ3Z",
  "description": "Customer confirmed they were charged twice. Investigating transaction logs now."
}
```

**Case 4: Update Multiple Fields**
```json
{
  "case_id": "5001400000IZ3Z",
  "status": "In Progress",
  "priority": "High",
  "description": "Payment issue under investigation",
  "agent_result": {
    "status": "In Progress",
    "summary": "Investigating duplicate charges",
    "category": "Billing",
    "priority": "High"
  }
}
```

**Expected Response** (200):
```json
{
  "success": true,
  "message": "Case 5001400000IZ3Z updated successfully"
}
```

---

### 5. Add Comment to Case
**Method**: `POST /cases/{case_id}/comments`

**Description**: Add a comment/note to an existing case

**URL**:
```
http://localhost:8000/api/cases/5001400000IZ3Z/comments
```

**Payload**:
```json
{
  "case_id": "5001400000IZ3Z",
  "comment_text": "Reviewed transaction history. Found duplicate charge of $99.99 on 2025-01-10. Prepared refund request."
}
```

**Expected Response** (201):
```json
{
  "comment_id": "00a14000003Apx2AAG",
  "case_id": "5001400000IZ3Z",
  "message": "Comment added to case 5001400000IZ3Z"
}
```

**Test Cases**:

**Case 1: Resolution Comment**
```json
{
  "case_id": "5001400000IZ3Z",
  "comment_text": "Issue resolved. Refund of $99.99 has been processed and will appear in customer's account within 3-5 business days."
}
```

**Case 2: Follow-up Comment**
```json
{
  "case_id": "5001400000IZ3Z",
  "comment_text": "Reaching out to customer to confirm they received the refund and resolution is satisfactory."
}
```

---

### 6. Close Case
**Method**: `PATCH /cases/{case_id}/close`

**Description**: Close an existing support case

**URL**:
```
http://localhost:8000/api/cases/5001400000IZ3Z/close
```

**Payload**:
```json
{
  "case_id": "5001400000IZ3Z",
  "subject": "[RESOLVED] Payment Error - Duplicate Charge",
  "summary": "Duplicate charge identified and refunded successfully",
  "resolution_notes": "Customer was charged twice due to a system timeout error. Refund of $99.99 processed. Case closed."
}
```

**Expected Response** (200):
```json
{
  "success": true,
  "case_id": "5001400000IZ3Z",
  "message": "Case 5001400000IZ3Z closed successfully"
}
```

---

### 7. Lookup Cases by User
**Method**: `POST /cases/lookup`

**Description**: Find existing open cases for a user

**URL**:
```
http://localhost:8000/api/cases/lookup
```

**Payload**:
```json
{
  "user_id": "user_support_001",
  "status": "New"
}
```

**Expected Response** (200):
```json
{
  "user_id": "user_support_001",
  "case_count": 2,
  "cases": [
    {
      "id": "5001400000IZ3Z",
      "case_number": "00001234",
      "subject": "Payment Error - Duplicate Charge",
      "status": "New"
    },
    {
      "id": "5001400000IZ3A",
      "case_number": "00001235",
      "subject": "Upload File Issue",
      "status": "New"
    }
  ]
}
```

**Test Cases**:

**Case 1: Get All Open Cases**
```json
{
  "user_id": "user_001",
  "status": "New"
}
```

**Case 2: Get In Progress Cases**
```json
{
  "user_id": "user_001",
  "status": "In Progress"
}
```

---

## CURL Commands for Testing

### Create Contract
```bash
curl -X POST http://localhost:8000/api/contracts \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "tenant_name": "John Doe",
    "property_address": "123 Main Street, Apt 4B, New York, NY 10001",
    "move_in_date": "2026-05-15",
    "move_out_date": "2027-05-14",
    "rent_amount": 2500.00
  }'
```

### Get Contract Status
```bash
curl -X GET http://localhost:8000/api/contracts/job_abc123xyz
```

### Update Contract
```bash
curl -X PATCH http://localhost:8000/api/contracts/a0E2X000000IZ3ZUAW \
  -H "Content-Type: application/json" \
  -d '{
    "contract_id": "a0E2X000000IZ3ZUAW",
    "status": "Active",
    "rent_amount": 2600.00
  }'
```

### Create Support Case
```bash
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_support_001",
    "issue_type": "payment_error",
    "message": "I'"'"'m getting a payment timeout error"
  }'
```

### Get Case Status
```bash
curl -X GET http://localhost:8000/api/jobs/job_support_123
```

### Get Case Events
```bash
curl -X GET http://localhost:8000/api/jobs/job_support_123/events
```

### Add Case Comment
```bash
curl -X POST http://localhost:8000/api/cases/5001400000IZ3Z/comments \
  -H "Content-Type: application/json" \
  -d '{
    "case_id": "5001400000IZ3Z",
    "comment_text": "Issue has been resolved. Refund processed."
  }'
```

### Close Case
```bash
curl -X PATCH http://localhost:8000/api/cases/5001400000IZ3Z/close \
  -H "Content-Type: application/json" \
  -d '{
    "case_id": "5001400000IZ3Z",
    "subject": "[RESOLVED] Payment Error",
    "summary": "Duplicate charge refunded",
    "resolution_notes": "Issue resolved successfully"
  }'
```

---

## Testing Flow

### Recommended Testing Sequence:

**1. Create Contract**
```
POST /contracts → Get job_id
```

**2. Poll Contract Status**
```
GET /contracts/{job_id} → Wait for completion
```

**3. Update Contract**
```
PATCH /contracts/{contract_id} → Verify update
```

**4. Create Support Case**
```
POST /jobs → Get job_id
```

**5. Poll Case Status**
```
GET /jobs/{job_id} → Wait for completion
```

**6. Get Case Events**
```
GET /jobs/{job_id}/events → View workflow events
```

**7. Add Comment**
```
POST /cases/{case_id}/comments → Add resolution notes
```

**8. Close Case**
```
PATCH /cases/{case_id}/close → Close case
```

---

## Common Status Codes

| Code | Meaning | 
|------|---------|
| 200 | OK - Request successful |
| 201 | Created - Resource created |
| 400 | Bad Request - Invalid payload |
| 401 | Unauthorized - Auth failed |
| 404 | Not Found - Resource not found |
| 500 | Internal Server Error |

---

## Tips for Testing

1. **Use UUIDs**: Job IDs are typically UUID format (36 characters)
2. **Check Timestamps**: All jobs have timestamps for tracking
3. **Poll Status**: Jobs are asynchronous, poll GET endpoints periodically
4. **Date Format**: Always use YYYY-MM-DD for dates
5. **Phone/Email**: Some fields may require validation
6. **Error Messages**: Check response messages for validation details

