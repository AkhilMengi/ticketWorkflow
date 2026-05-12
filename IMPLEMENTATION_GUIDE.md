# Smart Agent Enhancement - Implementation Guide

## Quick Reference

### 6 Supported Actions

| Action | Input | Output | Requirement |
|--------|-------|--------|-------------|
| `create_sf_case` | subject, description, priority, status, origin | case_id, case_number | None |
| `add_comment_to_case` | case_id, comment_body | comment_id | case_id (LLM extracts) |
| `close_case` | case_id, reason | status="Closed" | case_id (REQUIRED) |
| `edit_case` | case_id, field_updates {Priority, Subject, Status, etc.} | updated_fields list | case_id (REQUIRED) |
| `call_billing_api` | action_type, amount, reason, notes | transaction_id | None |
| **no_action** | - | - | - |

---

## Files Modified

### Core Agent Files
- **[app/agent/state.py](app/agent/state.py)** - Added 3 new payload fields + 3 result fields
- **[app/agent/prompts.py](app/agent/prompts.py)** - Enhanced LLM prompt with intent classification + entity extraction instructions
- **[app/agent/nodes.py](app/agent/nodes.py)** - Dispatcher with 6 action handlers + validation
- **[app/agent/entity_extractor.py](app/agent/entity_extractor.py)** - NEW: Entity parsing + validation module

### Service Files
- **[app/services/salesforce.py](app/services/salesforce.py)** - Added 3 new SF methods (add_comment, close, edit)

### API Layer
- **[app/api/routes.py](app/api/routes.py)** - Updated initial state + response builder
- **[app/api/schemas.py](app/api/schemas.py)** - Added result fields to IssueResponse

---

## API Examples

### Request: Simple Comment Addition
```bash
curl -X POST http://localhost:8000/api/v1/resolve-issue \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "ACC-1001",
    "issue_description": "Case #12345: Also seeing issues with API rate limiting"
  }'
```

### Response:
```json
{
  "account_id": "ACC-1001",
  "issue_description": "Case #12345: Also seeing issues with API rate limiting",
  "issue_analysis": "Customer providing additional context on an existing case",
  "action_reasoning": "Extracted case ID 12345. User is adding a comment about API rate limiting.",
  "recommended_actions": ["add_comment_to_case"],
  "actions_executed": ["add_comment_to_case"],
  "add_comment_result": {
    "success": true,
    "case_id": "5071-0012345",
    "comment_id": "00X5P000000IZzz",
    "message": "Comment added to case successfully."
  },
  "final_summary": "Analysis: Customer providing additional context ... | Add Comment: posted to case ... (comment_id=00X5P000000IZzz)",
  "error": null
}
```

---

### Request: Case Priority + Refund
```bash
curl -X POST http://localhost:8000/api/v1/resolve-issue \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "ACC-5002",
    "issue_description": "Case #99999: This is critical! Also please refund $150 for the service outage."
  }'
```

### Response Actions:
- `edit_case`: Updates Priority to "High"
- `call_billing_api`: Issues $150 refund

---

### Request: Data Validation (Missing Case ID)
```bash
curl -X POST http://localhost:8000/api/v1/resolve-issue \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "ACC-1001",
    "issue_description": "Please close my case and resolve this."
  }'
```

### Response:
```json
{
  "recommended_actions": ["close_case"],
  "actions_executed": [],
  "close_case_result": {
    "success": false,
    "error": "case_id is required for close_case"
  },
  "final_summary": "... | Close Case: FAILED – case_id is required for close_case"
}
```

---

## Code Examples

### Using Entity Extractor Directly
```python
from app.agent.entity_extractor import extract_entities, validate_action_entities

# Extract all entities from customer input
entities = extract_entities(
    "Case #12345: Set priority to High and process a $99 refund",
    intent="INTENT_EDIT"
)

print(entities)
# Output:
# {
#   "case_id": "12345",
#   "amount": 99.0,
#   "field_updates": {"Priority": "High"},
#   "comment_body": "Case #12345: Set priority to High and process a $99 refund",
#   "billing_reason": "REFUND"
# }

# Validate entities for specific action
is_valid, error = validate_action_entities("close_case", entities)
# Returns: (False, "case_id is required for close_case")  [empty case_id]
```

---

### Calling Salesforce Methods Directly
```python
from app.services.salesforce import add_comment_to_case, close_case, edit_case

# Add comment
result = add_comment_to_case({
    "case_id": "5071-0012345",
    "comment_body": "Customer reports resolved status",
    "account_id": "ACC-1001"
})

# Close case
result = close_case({
    "case_id": "5071-0012345",
    "reason": "Issue resolved",
    "account_id": "ACC-1001"
})

# Edit case
result = edit_case({
    "case_id": "5071-0012345",
    "field_updates": {
        "Priority": "High",
        "Subject": "URGENT: Customer Impact"
    },
    "account_id": "ACC-1001"
})
```

---

## Mock Mode Testing

All new methods support mock mode (set `MOCK_SALESFORCE=true` in .env):

```python
# When MOCK_SALESFORCE=true:
result = add_comment_to_case({...})
# Returns:
# {
#   "success": true,
#   "case_id": "5071-0012345",
#   "comment_id": "MOCK-5071-0012345-COMMENT-001",
#   "message": "Mock comment added successfully."
# }
```

---

## Intent Classification Examples

### Classify: Create New Case
**Input**: "I was billed twice for my subscription this month"

**LLM Classification**:
```
INTENT_CREATE → recommend: create_sf_case, call_billing_api
```

**Entities Extracted**:
```python
{
  "amount": 0.0,  # Not specified, will ask
  "billing_reason": "DUPLICATE_CHARGE",
  # No case_id (new case)
}
```

---

### Classify: Comment + Close Case
**Input**: "Case #9999: Fixed! Please close it and refund the $50 I spent on workaround services"

**LLM Classification**:
```
INTENT_COMMENT + INTENT_CLOSE + INTENT_BILLING
→ recommend: [add_comment_to_case, close_case, call_billing_api]
```

**Entities Extracted**:
```python
{
  "case_id": "9999",
  "comment_body": "Fixed! Please close it and refund...",
  "amount": 50.0,
  "billing_reason": "REFUND_REQUEST"
}
```

---

### Classify: Edit Case Field
**Input**: "Case #7777: Change this from Low priority to High - it's urgent now"

**LLM Classification**:
```
INTENT_EDIT → recommend: edit_case
```

**Entities Extracted**:
```python
{
  "case_id": "7777",
  "field_updates": {"Priority": "High"}
}
```

---

### Classify: No Action
**Input**: "How does your billing work?"

**LLM Classification**:
```
INTENT_NONE → recommended_actions: []
```

---

## Validation Rules

### Case ID Validation
```python
from app.agent.entity_extractor import validate_case_id

# Valid
validate_case_id("5071-0012345")  # (True, "")
validate_case_id("SFR-99999")     # (True, "")

# Invalid
validate_case_id("")              # (False, "case_id is empty...")
validate_case_id("123")           # (False, "case_id is too short...")
validate_case_id("CASE!@#")       # (False, "contains invalid characters...")
```

### Action Entity Validation
```python
from app.agent.entity_extractor import validate_action_entities

# Validate close_case
is_valid, error = validate_action_entities("close_case", {
    "case_id": "5071-0012345",
    "reason": "Resolved"
})
# Returns: (True, "")

# Missing case_id
is_valid, error = validate_action_entities("close_case", {
    "case_id": "",
    "reason": "Resolved"
})
# Returns: (False, "case_id is required for close_case")
```

---

## Logging & Debugging

### Enable Debug Output
```python
import logging

# Set agent module to DEBUG
logging.getLogger("app.agent").setLevel(logging.DEBUG)
logging.getLogger("app.agent.nodes").setLevel(logging.DEBUG)
logging.getLogger("app.services.salesforce").setLevel(logging.DEBUG)
```

### Check Entity Extraction Logs
```
DEBUG:app.agent.entity_extractor:Extracted case_id: 12345
DEBUG:app.agent.entity_extractor:Extracted amount: 99.0
DEBUG:app.agent.entity_extractor:Extracted field_updates: {'Priority': 'High'}
DEBUG:app.agent.entity_extractor:Entities extracted for intent 'INTENT_EDIT': {...}
```

### Check Action Execution Logs
```
INFO:app.agent.nodes:Executing actions: ['edit_case', 'call_billing_api']
INFO:app.agent.nodes:Editing case…
INFO:app.services.salesforce:SF case updated: case_id=5071-0012345, fields=['Priority']
INFO:app.agent.nodes:Case edited: case_id=5071-0012345, fields=['Priority']
INFO:app.agent.nodes:Calling billing API…
INFO:app.services.billing:Billing txn: TXN-2026-05-12-001
```

---

## Exception Handling

### Try-Catch Pattern
```python
try:
    result = close_case(payload)
    if result.get("success"):
        # Handle success
        case_id = result.get("case_id")
    else:
        # Handle API error
        error = result.get("error")
        logger.warning(f"Close case failed: {error}")
except Exception as exc:
    logger.error(f"Unexpected error: {exc}", exc_info=True)
```

---

## Performance Considerations

1. **Entity Extraction**: O(n) regex parsing - typically < 1ms for normal inputs
2. **Validation**: O(1) string checks - validates before API calls
3. **Parallel Execution**: Non-dependent actions can run in parallel (future enhancement)
4. **Caching**: Consider caching case metadata to reduce SF API calls

---

## Migration from Old Implementation

### Before (2 actions):
```json
{
  "recommended_actions": ["create_sf_case", "call_billing_api"]
}
```

### After (6 actions):
```json
{
  "recommended_actions": ["create_sf_case", "add_comment_to_case", "call_billing_api"]
}
```

**No breaking changes** - Old workflows continue to work, new capabilities are additive.

---

## Production Deployment Checklist

- [ ] Test all 6 actions with real Salesforce instance
- [ ] Test error scenarios (invalid case_id, API timeouts, etc.)
- [ ] Verify mock mode works for CI/CD pipelines
- [ ] Monitor SF API rate limits with new actions
- [ ] Review and adjust LLM prompt based on real usage
- [ ] Set up alerts for action execution failures
- [ ] Document any custom SF field mappings (if needed)
- [ ] Train support team on new agent capabilities

