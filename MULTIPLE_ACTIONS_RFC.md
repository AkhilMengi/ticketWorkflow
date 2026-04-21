# Multiple Actions Implementation - RFC

## Issue Summary
Previously, the agent routing system only selected **one action** from multiple suggestions, even when several complementary actions could be taken.

**Before:**
```
Issue: "Customer charged twice"
Suggestions: [rebill, create case, escalate team]
Result: Only ONE action selected (e.g., "create_case")
```

**After:**
```
Issue: "Customer charged twice"
Suggestions: [rebill, create case, escalate team]
Result: MULTIPLE ACTIONS selected (e.g., ["apply_billing_adjustment", "create_case"])
```

## Changes Made

### 1. **intelligent_action_service.py** - LLM Prompt Updated
**Change:** Modified the semantic action selection prompt to request multiple actions instead of just one.

**Key Updates:**
- Changed `selected_action` (singular) to `selected_actions` (array)
- Added "IMPORTANT RULES" section emphasizing execution of MULTIPLE actions
- Examples show multi-action scenarios:
  - Double charged → `[apply_billing_adjustment, create_case]`
  - Complex issue → `[apply_billing_adjustment, escalate_to_team, create_case]`
- Added `overall_confidence` for the entire decision

**Response Format:**
```json
{
  "issue_summary": "...",
  "selected_actions": [
    {
      "action_type": "apply_billing_adjustment|create_case|escalate_to_team",
      "priority": "primary|secondary|tertiary",
      "reasoning": "...",
      "confidence": 0.0-1.0,
      "action_parameters": {...}
    }
  ],
  "overall_confidence": 0.0-1.0
}
```

### 2. **intelligent_action_service.py** - Response Parsing Enhanced
**Change:** Updated JSON parsing to handle both:
- **Old format** (single action) - automatically converted to new format
- **New format** (multiple actions) - processed directly

**Backward Compatibility:**
```python
if "selected_action" in action_selection and "selected_actions" not in action_selection:
    # Convert old format to new format automatically
    action_selection["selected_actions"] = [{...}]
```

### 3. **routing_nodes.py** - intelligent_action_routing_node Updated
**Change:** Modified to process and prepare all recommended actions for execution.

**Key Updates:**
- Loops through ALL `selected_actions` from LLM
- Creates a `recommended_actions` array with all actions
- Each action includes:
  - `action_type`: create_case, apply_billing_adjustment, escalate_to_team
  - `confidence`: Per-action confidence score
  - `priority`: primary, secondary, tertiary
  - `reasoning`: Why this action is needed
  - `action_parameters`: Parameters for execution

**Issue Severity Logic:**
- If **2+ actions** selected → Severity = "high" (complex issue requiring multiple steps)
- If confidence > 0.8 → Severity = "high"
- Otherwise → Severity = "medium"

## Workflow Diagram

```
┌─────────────────────────────────────────────┐
│  Issue + Suggestions from Customer          │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  intelligent_action_routing_node            │
│                                             │
│  1. Load suggestions from file              │
│  2. Call LLM to analyze issue               │
│  3. LLM returns 2-3 recommended actions     │
│  4. Map to system action types              │
│  5. Prepare all actions for execution       │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  recommended_actions: [                     │
│    { action_type: "apply_billing_..." }     │
│    { action_type: "create_case" }           │
│    { action_type: "escalate_to_team" }      │
│  ]                                          │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  intelligent_actions_execution_node         │
│                                             │
│  ✓ Execute Action 1 (apply_billing_...)    │
│  ✓ Execute Action 2 (create_case)          │
│  ✓ Execute Action 3 (escalate_to_team)     │
│                                             │
│  Returns:                                   │
│  [                                          │
│    {status: "success", case_id: "..."},     │
│    {status: "success", amount: 50.00},      │
│    {status: "pending_human_review"}         │
│  ]                                          │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  aggregation_node                           │
│  → Combine results into customer response   │
└─────────────────────────────────────────────┘
```

## Example Scenarios

### Scenario 1: Double Billing
**Issue:** "I was charged twice for my service"

**LLM Decision:**
```json
{
  "selected_actions": [
    {
      "action_type": "apply_billing_adjustment",
      "priority": "primary",
      "confidence": 0.95,
      "reasoning": "Apply credit for duplicate charge"
    },
    {
      "action_type": "create_case",
      "priority": "secondary",
      "confidence": 0.88,
      "reasoning": "Create case to investigate billing system issue"
    }
  ]
}
```

**Execution Result:**
- ✅ Credit applied: $50.00
- ✅ Salesforce case created: CASE-001234

---

### Scenario 2: High Usage Investigation
**Issue:** "My usage is higher than expected, possible meter malfunction"

**LLM Decision:**
```json
{
  "selected_actions": [
    {
      "action_type": "create_case",
      "priority": "primary",
      "confidence": 0.92,
      "reasoning": "Document potential meter issue for investigation"
    },
    {
      "action_type": "apply_billing_adjustment",
      "priority": "secondary",
      "confidence": 0.75,
      "reasoning": "Apply temporary credit pending investigation"
    },
    {
      "action_type": "escalate_to_team",
      "priority": "tertiary",
      "confidence": 0.68,
      "reasoning": "Escalate to field service for meter inspection"
    }
  ]
}
```

**Execution Result:**
- ✅ Salesforce case created: CASE-001235
- ✅ Credit applied: $30.00
- ✅ Escalated to Field Service team

---

### Scenario 3: Unclear/Complex Issue
**Issue:** "Something is wrong but I'm not sure what"

**LLM Decision:**
```json
{
  "selected_actions": [
    {
      "action_type": "create_case",
      "priority": "primary",
      "confidence": 0.85,
      "reasoning": "Document customer report for manual investigation"
    },
    {
      "action_type": "escalate_to_team",
      "priority": "secondary",
      "confidence": 0.9,
      "reasoning": "Escalate to support team for human analysis"
    }
  ]
}
```

**Execution Result:**
- ✅ Salesforce case created: CASE-001236
- ✅ Escalated to Support Team

## Files Modified

1. **app/services/intelligent_action_service.py**
   - Updated `SEMANTIC_ACTION_SELECTION_PROMPT` (now asks for multiple actions)
   - Enhanced JSON parsing for multiple actions
   - Added backward compatibility for old format

2. **app/agent/routing_nodes.py**
   - Updated `intelligent_action_routing_node` to process multiple actions
   - Enhanced issue severity detection
   - Improved logging for each action
   - Updated return format with all recommended actions

## Backward Compatibility

✅ **Fully backward compatible!**

The system automatically converts old single-action responses to the new multi-action format, so:
- Old code continues to work
- Gradual migration path available
- No breaking changes to existing integrations

## Testing

Run the test script to verify:
```bash
python test_multiple_actions.py
```

The test demonstrates:
- Multiple actions selected for complex scenarios
- Action prioritization (primary, secondary, tertiary)
- Independent confidence scores
- Proper logging of all decisions

## Benefits

1. ✅ **Comprehensive Problem Resolution**
   - Address multiple aspects of an issue simultaneously
   - No need to wait for sequential actions

2. ✅ **Better Customer Experience**
   - Issues resolved faster
   - More thorough investigation
   - Reduced follow-up interactions

3. ✅ **Intelligent Actions**
   - Actions are complementary, not conflicting
   - Prioritized by relevance to the issue
   - Each action has confidence score

4. ✅ **Flexible Routing**
   - Can automatically trigger:
     - Billing adjustments
     - Case creation
     - Team escalation
   - In any combination as needed

## Future Enhancements

- [ ] Action conflict detection (prevent contradictory actions)
- [ ] Action dependency ordering (execute in optimal sequence)
- [ ] Cost estimation for billing actions
- [ ] Human approval flow for high-cost billings actions
- [ ] Machine learning on action effectiveness
