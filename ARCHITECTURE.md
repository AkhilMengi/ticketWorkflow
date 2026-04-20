# Recommended Actions - Architecture & Flow

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER / AGENT APPLICATION                    │
│                                                                 │
│  - Agent logic                                                  │
│  - UI/Button click                                              │
│  - Business rules                                               │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ HTTP POST
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│         POST /api/recommended-actions                           │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ routes.process_recommended_actions_endpoint()          │   │
│  │ • Validate request                                      │   │
│  │ • Parse file OR use JSON actions                        │   │
│  └──────────────────┬──────────────────────────────────────┘   │
│                     │                                            │
│                     ▼                                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ action_service.process_recommended_actions()           │   │
│  │ • Iterate through actions                               │   │
│  │ • Execute each action                                   │   │
│  └──────────────────┬──────────────────────────────────────┘   │
│                     │                                            │
│         ┌───────────┼───────────┐                               │
│         ▼           ▼           ▼                               │
│  ┌──────────────┐ ┌───────────┐ ┌──────────────────┐          │
│  │ Salesforce   │ │ Billing   │ │ Human In Loop    │          │
│  │ Case         │ │ Actions   │ │ Escalation       │          │
│  │ Creation     │ │           │ │                  │          │
│  │              │ │ (TODO:    │ │ (TODO:           │          │
│  │ ✓ Works      │ │  connect  │ │  connect your    │          │
│  │              │ │  your     │ │  ticketing       │          │
│  │ Returns:     │ │  billing) │ │  system)         │          │
│  │ • case_id    │ │           │ │                  │          │
│  │ • case_no    │ │ Returns:  │ │ Returns:         │          │
│  └──────────────┘ │ • txn_id  │ │ • escalation_id  │          │
│                   │           │ │ • team           │          │
│                   └───────────┘ │ • priority       │          │
│                                 └──────────────────┘          │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Aggregate Results                                       │   │
│  │ • Status for each action                                │   │
│  │ • Errors (if any)                                       │   │
│  │ • Summary counts                                        │   │
│  └──────────────────┬──────────────────────────────────────┘   │
│                     │                                            │
└─────────────────────┼────────────────────────────────────────────┘
                      │
                      │ HTTP Response (JSON)
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                   RESPONSE TO CALLER                            │
│                                                                 │
│  {                                                              │
│    "job_id": "...",                                            │
│    "results": [                                                │
│      {action_1_result},                                        │
│      {action_2_result},                                        │
│      {action_3_result}                                         │
│    ],                                                          │
│    "summary": {                                                │
│      "successful": 2,                                          │
│      "failed": 0,                                              │
│      "pending_review": 1                                       │
│    }                                                           │
│  }                                                             │
└─────────────────────────────────────────────────────────────────┘
```

## Request/Response Flow

```
CLIENT REQUEST
│
├─ Option A: File-based
│  {
│    "user_id": "cust_123",
│    "file_path": "./recommended_actions.txt"
│  }
│
└─ Option B: JSON-based
   {
     "user_id": "cust_123",
     "actions": [
       {
         "action_type": "salesforce_case",
         "description": "...",
         "parameters": {...}
       },
       ...
     ]
   }
        │
        ▼
ENDPOINT PROCESSING
│
├─ Step 1: Validate request
├─ Step 2: Parse actions (file or JSON)
├─ Step 3: For each action:
│  ├─ Handle salesforce_case
│  ├─ Handle billing
│  └─ Handle human_in_loop
├─ Step 4: Collect results
├─ Step 5: Build summary
│
        │
        ▼
SERVER RESPONSE
│
{
  "job_id": "abc-123-def",
  "user_id": "cust_123",
  "total_actions": 3,
  "results": [
    {
      "action_index": 1,
      "action_type": "salesforce_case",
      "status": "success",
      "result": {
        "case_id": "5001234567",
        "case_number": "00001234"
      }
    },
    {
      "action_index": 2,
      "action_type": "billing",
      "status": "success",
      "result": {
        "billing_transaction_id": "TXN123",
        "amount": 50
      }
    },
    {
      "action_index": 3,
      "action_type": "human_in_loop",
      "status": "pending_human_review",
      "result": {
        "escalation_id": "ESC456",
        "team": "VIP Support"
      }
    }
  ],
  "summary": {
    "total_actions": 3,
    "successful": 2,
    "failed": 0,
    "pending_review": 1
  }
}
```

## File Structure

```
ticketWorkflow/
│
├── app/
│   ├── api/
│   │   ├── routes.py               ← MODIFIED: New endpoint added
│   │   └── schemas.py              ← MODIFIED: New schemas added
│   ├── services/
│   │   ├── action_service.py       ← NEW: Core action execution logic
│   │   ├── job_service.py
│   │   └── ...
│   ├── integrations/
│   │   ├── salesforce.py
│   │   └── ...
│   └── agent/
│       ├── tools.py                ← Used by: process_salesforce_case_action()
│       └── ...
│
├── recommended_actions_client.py    ← NEW: Python SDK
├── test_recommended_actions.py      ← NEW: Test suite
├── recommended_actions_sample.txt   ← NEW: Example file
│
├── QUICK_START.md                   ← NEW: 5-min guide
├── RECOMMENDED_ACTIONS_GUIDE.md     ← NEW: Full API docs
├── IMPLEMENTATION_SUMMARY.md        ← NEW: Technical docs
├── README_RECOMMENDED_ACTIONS.md    ← NEW: This project summary
│
├── run.py
├── requirements.txt
└── ...
```

## Action Execution Lifecycle

```
START: New request arrives
│
├─ Validate:
│  ├─ user_id present? ✓
│  ├─ file_path OR actions present? ✓
│  └─ Valid JSON? ✓
│
├─ Parse:
│  ├─ If file_path:
│  │  └─ Read & parse text file → action list
│  └─ If actions array:
│     └─ Use directly
│
├─ For Each Action:
│  │
│  ├─ Action 1 (Salesforce):
│  │  ├─ Extract parameters
│  │  ├─ Call create_salesforce_case()
│  │  ├─ Return case_id, case_number
│  │  └─ Status: ✓ success | ✗ failed
│  │
│  ├─ Action 2 (Billing):
│  │  ├─ Extract parameters (amount, reason, action)
│  │  ├─ Call process_billing_action()
│  │  │  └─ [TODO: Integrate real billing API]
│  │  ├─ Return transaction_id
│  │  └─ Status: ✓ success | ✗ failed
│  │
│  └─ Action 3 (Human In Loop):
│     ├─ Extract parameters (team, priority)
│     ├─ Call process_human_in_loop_action()
│     │  └─ [TODO: Integrate real ticketing system]
│     ├─ Return escalation_id
│     └─ Status: ✓ pending_human_review | ✗ failed
│
├─ Aggregate Results:
│  ├─ Collect all action results
│  ├─ Count successes/failures/pending
│  └─ Build summary
│
└─ END: Return response with all results


Response contains:
  • job_id (unique identifier)
  • results (array with each action's outcome)
  • summary (success/failure counts)
```

## Integration Points

```
YOUR SYSTEM
│
├─ User/Agent Interface
│  └─ Calls: POST /api/recommended-actions
│     └─ Uses: recommended_actions_client.py (optional)
│
├─ Salesforce Integration ✓
│  └─ Uses: app/integrations/salesforce.py
│     └─ Uses: app/agent/tools.py::create_salesforce_case()
│
├─ Billing System [TODO]
│  └─ Edit: app/services/action_service.py
│     └─ Function: process_billing_action()
│        └─ Add calls to: your_billing_api.charge() or similar
│
├─ Ticketing/Escalation [TODO]
│  └─ Edit: app/services/action_service.py
│     └─ Function: process_human_in_loop_action()
│        └─ Add calls to: your_ticketing_api.create_ticket() or similar
│
└─ Logging/Monitoring [Optional]
   └─ Add in: app/services/action_service.py
      └─ Log all action execution for tracking
```

## Data Flow Example: Payment Issue

```
SCENARIO: Customer has payment failure
          Agent decides to: Create case + Apply credit + Escalate

┌──────────────────────────────────────────────────────────┐
│ Agent evaluates issue                                    │
│ Decides: payment_failed → action_set_3                   │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│ Agent builds action array                                │
│                                                          │
│ [                                                        │
│   {                                                      │
│     "action_type": "salesforce_case",                   │
│     "description": "Payment failure - create case",     │
│     "parameters": {                                      │
│       "issue_type": "Payment Processing",               │
│       "priority": "High",                               │
│       "category": "Billing"                             │
│     }                                                    │
│   },                                                     │
│   {                                                      │
│     "action_type": "billing",                           │
│     "description": "Apply credit for failed txn",       │
│     "parameters": {                                      │
│       "action": "apply_credit",                         │
│       "amount": 99.99,                                  │
│       "reason": "Failed payment processing"             │
│     }                                                    │
│   },                                                     │
│   {                                                      │
│     "action_type": "human_in_loop",                     │
│     "description": "Escalate for manual review",        │
│     "parameters": {                                      │
│       "team": "VIP Support",                            │
│       "priority": "high"                                │
│     }                                                    │
│   }                                                      │
│ ]                                                        │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│ POST /api/recommended-actions                            │
│                                                          │
│ {                                                        │
│   "user_id": "customer_123",                            │
│   "actions": [...]                                       │
│ }                                                        │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
         ┌───────────┴─────────────┐
         ▼                         ▼
    ┌─────────────┐         ┌─────────────┐
    │ Create Case │         │ Apply Credit│
    │             │         │             │
    │ SF Response │         │ Billing Sys │
    │ case_id:    │         │ txn_id:     │
    │ 5001234567  │         │ TXN-99-12   │
    └──────┬──────┘         └──────┬──────┘
           │                       │
           └───────────┬───────────┘
                       │
                       ▼
            ┌─────────────────────┐
            │  Escalate to Human  │
            │                     │
            │  Ticketing Response │
            │  escalation_id:     │
            │  ESC-2024-00542     │
            └──────┬──────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────┐
│ API Response (200 OK)                                    │
│                                                          │
│ {                                                        │
│   "job_id": "abc-123",                                  │
│   "results": [                                           │
│     {                                                    │
│       "action_type": "salesforce_case",                 │
│       "status": "success",                              │
│       "result": {                                        │
│         "case_id": "5001234567",                        │
│         "case_number": "00001234"                       │
│       }                                                  │
│     },                                                   │
│     {                                                    │
│       "action_type": "billing",                         │
│       "status": "success",                              │
│       "result": {                                        │
│         "billing_transaction_id": "TXN-99-12",          │
│         "amount": 99.99                                 │
│       }                                                  │
│     },                                                   │
│     {                                                    │
│       "action_type": "human_in_loop",                   │
│       "status": "pending_human_review",                 │
│       "result": {                                        │
│         "escalation_id": "ESC-2024-00542",              │
│         "team": "VIP Support"                           │
│       }                                                  │
│     }                                                    │
│   ],                                                     │
│   "summary": {                                           │
│     "total_actions": 3,                                 │
│     "successful": 2,                                    │
│     "failed": 0,                                        │
│     "pending_review": 1                                 │
│   }                                                      │
│ }                                                        │
└──────────────────────────────────────────────────────────┘
                     │
                     ▼
            Agent receives response
            Updates customer record
            Sends notification
            Logs resolution
```

---

## Technology Stack

```
Framework:   FastAPI + Python 3.x
Integrations:
  • Salesforce (via app/integrations/salesforce.py)
  • Billing System (to be integrated)
  • Ticketing System (to be integrated)
  
Request/Response: JSON
Authentication: Inherited from main API
Database: SQLAlchemy (existing)
```

---

**For detailed usage, see: QUICK_START.md**
**For API reference, see: RECOMMENDED_ACTIONS_GUIDE.md**
**For testing, run: python test_recommended_actions.py**
