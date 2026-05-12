# Enhanced Smart Agent - Technical Documentation

## Overview

The Smart Agent has been enhanced to support **6 intelligent actions** instead of 2. The agent now uses a **robust intent classification layer** with **entity extraction** to handle complex customer support scenarios involving Salesforce case management and billing operations.

---

## Architecture Changes

### 1. **Intent Classification Layer** (`app/agent/prompts.py`)

The LLM now classifies customer intents into 6 categories before recommending actions:

| Intent | Purpose | Example |
|--------|---------|---------|
| `INTENT_CREATE` | Customer reports a NEW problem | "I was double-charged $99" |
| `INTENT_COMMENT` | Add narrative update to EXISTING case | "Case #12345: Please add that I also..." |
| `INTENT_CLOSE` | Mark EXISTING case as CLOSED | "My case #54321 is now fixed" |
| `INTENT_EDIT` | Update EXISTING case fields | "Case #789 priority should be High" |
| `INTENT_BILLING` | Execute financial operations | "Please refund the duplicate charge" |
| `INTENT_NONE` | No action needed | "How does your billing cycle work?" |

**Key Differentiation**: `COMMENT` vs `EDIT`
- **COMMENT**: Appends narrative text (case_id optional)
- **EDIT**: Modifies structured fields like Priority/Subject (case_id REQUIRED)

---

### 2. **Entity Extraction Module** (`app/agent/entity_extractor.py`)

Parses natural language to extract critical entities:

#### `extract_case_id(text: str) -> str`
Extracts case IDs from patterns like:
- "Case #12345"
- "case ID 67890"
- "case 5071-0012345"

#### `extract_amount(text: str) -> float`
Extracts monetary amounts:
- "$99", "$99.50", "99 USD", "amount: $100"

#### `extract_field_updates(text: str) -> Dict[str, Any]`
Extracts Salesforce field changes:
- "priority to High" → `{"Priority": "High"}`
- "subject to 'New Issue'" → `{"Subject": "New Issue"}`

#### `extract_billing_reason(text: str) -> str`
Maps natural language to billing codes:
- "double charge" → `"DUPLICATE_CHARGE"`
- "failed payment" → `"FAILED_PAYMENT"`
- "credit the account" → `"ACCOUNT_CREDIT"`

#### `validate_action_entities(action: str, entities: Dict) -> Tuple[bool, str]`
Validates required entities before API calls:
- `close_case`: case_id REQUIRED
- `edit_case`: case_id REQUIRED
- `add_comment_to_case`: case_id OPTIONAL

---

### 3. **API Router Dispatcher** (`app/agent/nodes.py::execute_actions_node`)

Clean dispatcher pattern routes to 6 internal executors:

```python
def execute_actions_node(state: AgentState) -> Dict[str, Any]:
    for action in recommended:
        if action == "create_sf_case":
            result = _execute_create_sf_case(state)
        elif action == "add_comment_to_case":
            result = _execute_add_comment(state)
        elif action == "close_case":
            result = _execute_close_case(state)
        # ... etc for all 6 actions
```

Each executor:
1. Validates required entities
2. Calls the appropriate service
3. Handles errors gracefully
4. Logs results

---

### 4. **Extended Salesforce Service** (`app/services/salesforce.py`)

**New Methods**:

#### `add_comment_to_case(payload: Dict[str, Any]) -> Dict[str, Any]`
```json
{
  "case_id": "5071-0012345",
  "comment_body": "Customer reports additional issues in logs",
  "account_id": "ACC-1001"
}
```
**Response**:
```json
{
  "success": true,
  "case_id": "5071-0012345",
  "comment_id": "00X5P000000....",
  "message": "Comment added to case successfully."
}
```

#### `close_case(payload: Dict[str, Any]) -> Dict[str, Any]`
```json
{
  "case_id": "5071-0067890",
  "reason": "Issue resolved after refund",
  "account_id": "ACC-1001"
}
```
**Response**:
```json
{
  "success": true,
  "case_id": "5071-0067890",
  "status": "Closed",
  "message": "Case closed successfully."
}
```

#### `edit_case(payload: Dict[str, Any]) -> Dict[str, Any]`
```json
{
  "case_id": "5071-0012345",
  "field_updates": {
    "Priority": "High",
    "Subject": "URGENT: Duplicate Charge Investigation"
  },
  "account_id": "ACC-1001"
}
```
**Response**:
```json
{
  "success": true,
  "case_id": "5071-0012345",
  "updated_fields": ["Priority", "Subject"],
  "message": "Case updated successfully with fields: Priority, Subject"
}
```

---

### 5. **Enhanced Agent State** (`app/agent/state.py`)

```python
class AgentState(TypedDict):
    # ... existing fields ...
    
    # NEW payload fields for 4 new actions
    add_comment_payload: Dict[str, Any]
    close_case_payload: Dict[str, Any]
    edit_case_payload: Dict[str, Any]
    
    # NEW result fields for 4 new actions
    add_comment_result: Optional[Dict[str, Any]]
    close_case_result: Optional[Dict[str, Any]]
    edit_case_result: Optional[Dict[str, Any]]
```

---

## Complete Workflow

```
Customer Issue Input
        ↓
    [fetch_account] → Load account details from CRM/DB
        ↓
   [analyze_issue] → LLM classifies intent + extracts entities
        ↓
   [Intent Classification]
   ├─ INTENT_CREATE → recommend: create_sf_case (+ billing if needed)
   ├─ INTENT_COMMENT → recommend: add_comment_to_case
   ├─ INTENT_CLOSE → recommend: close_case
   ├─ INTENT_EDIT → recommend: edit_case
   ├─ INTENT_BILLING → recommend: call_billing_api (+ create_sf_case if needed)
   └─ INTENT_NONE → recommended_actions = []
        ↓
   [Route after Analysis]
   ├─ Confidence >= 5 → execute_actions
   └─ Confidence < 5 → go to summarize with error
        ↓
 [execute_actions] → Dispatcher routes to 6 executors
   ├─ _execute_create_sf_case()
   ├─ _execute_add_comment()
   ├─ _execute_close_case()
   ├─ _execute_edit_case()
   ├─ _execute_billing_api()
   └─ Error handling + validation
        ↓
  [summarize] → Compile human-readable summary
        ↓
    Final Response (JSON)
```

---

## Error Handling Strategy

### Validation Errors
```python
# Missing case_id for actions requiring it
if not case_id:
    return {"success": False, "error": "case_id is required for close_case"}
```

### API Errors
```python
# HTTP errors from Salesforce
try:
    resp.raise_for_status()
except requests.HTTPError as exc:
    return {"success": False, "error": str(exc), "detail": exc.response.text}
```

### Graceful Degradation
- Mock mode enables testing without real APIs
- Validation happens BEFORE API calls
- Each action fails independently without cascading

---

## JSON Output Format

### LLM Response (analyze_issue_node)
```json
{
  "confidence_score": 8,
  "analysis": "Customer wants to add a note to their open case and close it once resolved.",
  "reasoning": "Extracted case ID 12345. User is asking for comment + closure.",
  "recommended_actions": ["add_comment_to_case", "close_case"],
  "add_comment_payload": {
    "case_id": "5071-0012345",
    "comment_body": "New development: issue also affects API calls",
    "account_id": "ACC-1001"
  },
  "close_case_payload": {
    "case_id": "5071-0012345",
    "reason": "Issue resolved per customer",
    "account_id": "ACC-1001"
  }
}
```

### Final API Response (IssueResponse)
```json
{
  "account_id": "ACC-1001",
  "issue_description": "Case #12345: ...",
  "issue_analysis": "Customer wants to add a note and close case",
  "action_reasoning": "Extracted case ID. User is asking for comment + closure.",
  "recommended_actions": ["add_comment_to_case", "close_case"],
  "actions_executed": ["add_comment_to_case", "close_case"],
  "add_comment_result": {
    "success": true,
    "case_id": "5071-0012345",
    "comment_id": "00X5P..."
  },
  "close_case_result": {
    "success": true,
    "case_id": "5071-0012345",
    "status": "Closed"
  },
  "sf_case_result": null,
  "billing_result": null,
  "final_summary": "Analysis: ... | ... | Add Comment: posted to case ... | Close Case: case ... marked as Closed",
  "error": null
}
```

---

## Test Cases

### Test 1: Add Comment to Existing Case
**Input**:
```json
{
  "account_id": "ACC-1001",
  "issue_description": "Case #12345: Please add that I also see this issue in our API logs"
}
```

**Expected Flow**:
1. LLM classifies: `INTENT_COMMENT`
2. Entity extraction: case_id="12345"
3. Action: `add_comment_to_case`
4. Success: Comment added ✓

---

### Test 2: Close Case and Refund
**Input**:
```json
{
  "account_id": "ACC-1001",
  "issue_description": "Case #54321 is now resolved. Also please issue a $50 refund for the inconvenience."
}
```

**Expected Flow**:
1. LLM classifies: `INTENT_CLOSE` + `INTENT_BILLING`
2. Entity extraction: case_id="54321", amount=50.00, reason="INCONVENIENCE_CREDIT"
3. Actions: `["close_case", "call_billing_api"]`
4. Success: Both actions executed ✓

---

### Test 3: Edit Case Priority
**Input**:
```json
{
  "account_id": "ACC-1001",
  "issue_description": "Case #67890: This is urgent! Please change priority to High."
}
```

**Expected Flow**:
1. LLM classifies: `INTENT_EDIT`
2. Entity extraction: case_id="67890", field_updates={"Priority": "High"}
3. Action: `edit_case`
4. Success: Case updated ✓

---

### Test 4: Missing Case ID (Validation Failure)
**Input**:
```json
{
  "account_id": "ACC-1001",
  "issue_description": "Please close the case and mark it resolved."
}
```

**Expected Flow**:
1. LLM classifies: `INTENT_CLOSE`
2. Entity extraction: case_id="" (NOT FOUND)
3. Validation: FAIL - "case_id is required for close_case"
4. Result: Error returned, action not executed ✗

---

## Integration Checklist

- [x] Enhanced prompts with intent classification
- [x] Entity extraction module with validation
- [x] Three new Salesforce methods (add_comment, close_case, edit_case)
- [x] Updated AgentState with new payload fields
- [x] Action dispatcher with per-action validation
- [x] Error handling and graceful degradation
- [x] Updated API schemas and response models
- [x] Mock mode support for all new actions
- [x] Comprehensive logging for debugging
- [x] Production-ready JSON serialization

---

## Migration Notes

### Backward Compatibility
✓ All existing code continues to work
✓ Original actions (create_sf_case, call_billing_api) unchanged
✓ New actions are opt-in via prompted recommendations

### Environment Variables
No new environment variables required - uses existing SF and Billing API configs

### Testing
Run existing test suite:
```bash
pytest app/tests/
```

All tests should pass, including new dispatcher tests.

---

## Future Enhancements

1. **Multi-Step Workflows**: Chain actions based on previous results
2. **Smart Retry Logic**: Automatic retry with backoff for transient failures
3. **Async Execution**: Run non-dependent actions in parallel
4. **Case Context Caching**: Remember case history for smarter decisions
5. **Custom Actions**: Plugin architecture for business-specific actions
6. **Rate Limiting**: Queue management for Salesforce/Billing API calls

---

## Support & Debugging

### Enable Debug Logging
```python
import logging
logging.getLogger("app.agent").setLevel(logging.DEBUG)
```

### Check Entity Extraction
```python
from app.agent.entity_extractor import extract_entities
entities = extract_entities("Case #12345: Please change priority to High")
print(entities)
# Output: {"case_id": "12345", "field_updates": {"Priority": "High"}, ...}
```

### Validate Against LLM Output
Check if LLM payload matches expected structure in prompts.py validation rules.

---

## DRY Principles Applied

1. **Entity Extraction Reusability**: `extract_*()` functions used across all actions
2. **Validation Centralization**: `validate_action_entities()` enforces rules once
3. **Dispatcher Pattern**: Single entry point with consistent error handling
4. **Logging Standardization**: Consistent log formats across all executors
5. **JSON Schemas**: Single source of truth for payload structures

