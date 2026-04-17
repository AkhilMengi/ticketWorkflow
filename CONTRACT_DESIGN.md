# Contract Creation Use Case Documentation

## Overview

This document describes the new use case for creating Salesforce contracts based on move-in and move-out dates. This is a separate, independent workflow from the ticket/case management system.

## Business Process

The contract creation use case enables automated generation of rental property contracts with the following key information:
- **Tenant Name**: Name of the tenant
- **Property Address**: Address of the rental property
- **Move-In Date**: Date when tenant takes possession (YYYY-MM-DD)
- **Move-Out Date**: Date when tenant vacates (YYYY-MM-DD)
- **Monthly Rent Amount**: Monthly rent payment

## System Architecture

### Workflow Stages

```
┌─────────────────────────────────────────────────────────────────┐
│                    CONTRACT CREATION WORKFLOW                    │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
                    ┌───────────────────┐
                    │  Validation Node  │
                    │                   │
                    │  - Date Logic     │
                    │  - Data Complete  │
                    │  - Business Rules │
                    └───────────────────┘
                            │
                    ┌───────┴───────┐
                    │               │
              ✗ (Invalid)    ✓ (Valid)
                    │               │
                    │               ▼
                    │       ┌──────────────────┐
                    │       │  Prepare Node    │
                    │       │                  │
                    │       │  - LLM Review    │
                    │       │  - Confirmation  │
                    │       │  - Summary       │
                    │       └──────────────────┘
                    │               │
                    │               ▼
                    │       ┌──────────────────┐
                    │       │  Create Node     │
                    │       │                  │
                    │       │  - Create in SF  │
                    │       │  - Get Contract  │
                    │       │  - Log Result    │
                    │       └──────────────────┘
                    │               │
                    │               ▼
                    │       ┌──────────────────┐
                    │       │ Summarize Node   │
                    │       │                  │
                    │       │  - Generate Sum  │
                    │       │  - Next Actions  │
                    │       └──────────────────┘
                    │               │
                    └───────────────┘
                            │
                            ▼
                        ┌─────────┐
                        │   END   │
                        └─────────┘
```

### Key Components

#### 1. **ContractAgentState** (`app/agent/contract_state.py`)
Defines the state structure for contract workflows:
- Input fields: tenant_name, property_address, move_in_date, move_out_date, rent_amount
- Processing fields: validation_status, validation_errors, next_action
- Output fields: contract_id, final_answer

#### 2. **Contract Tools** (`app/agent/contract_tools.py`)
Utility functions:
- `validate_contract_dates()`: Validates move-in/move-out date logic
- `validate_contract_data()`: Validates tenant info and rent amount
- `validate_and_prepare_contract()`: Comprehensive validation
- `create_salesforce_contract()`: Creates contract in Salesforce
- `lookup_existing_contracts()`: Searches for existing contracts
- `update_existing_contract()`: Updates an existing contract

#### 3. **Contract Nodes** (`app/agent/contract_nodes.py`)
Workflow nodes implemented with LLM reasoning:
- **validation_node**: Initial validation with local checks + LLM review
- **prepare_contract_node**: Prepares contract with LLM confirmation
- **create_contract_node**: Creates contract in Salesforce
- **summarize_contract_result_node**: Generates professional summary

#### 4. **Contract Graph** (`app/agent/contract_graph.py`)
LangGraph implementation defining the workflow orchestration:
- **Entry Point**: validation_node
- **Routing Logic**: 
  - Validation → Prepare → Create → Summarize → END
  - Failed validation → END
- **Conditional Edges**: Route based on validation and creation results

#### 5. **API Endpoints** (`app/api/routes.py`)
RESTful API for contract operations:
- `POST /contracts`: Create a contract job
- `GET /contracts/{job_id}`: Get contract job status
- `PATCH /contracts/{contract_id}`: Update an existing contract

#### 6. **Salesforce Integration** (`app/integrations/salesforce.py`)
New methods in SalesforceClient:
- `create_contract()`: Creates Contract object in Salesforce
- `update_contract()`: Updates contract status, dates, or rent amount

#### 7. **Worker** (`app/workers/worker.py`)
Asynchronous job processing:
- Separate contract_queue for contract jobs
- contract_worker_loop processes contract jobs
- Events and results logged to database

## API Usage

### Create Contract

**Endpoint**: `POST /contracts`

**Request Body**:
```json
{
  "user_id": "user123",
  "tenant_name": "John Doe",
  "property_address": "123 Main Street, Apt 4B, New York, NY 10001",
  "move_in_date": "2025-01-15",
  "move_out_date": "2026-01-14",
  "rent_amount": 2500.00
}
```

**Response**:
```json
{
  "job_id": "job_abc123",
  "status": "queued"
}
```

### Check Contract Job Status

**Endpoint**: `GET /contracts/{job_id}`

**Response**:
```json
{
  "job_id": "job_abc123",
  "status": "completed",
  "result": {
    "status": "success",
    "contract_id": "contract_001",
    "tenant_name": "John Doe",
    "property_address": "123 Main Street, Apt 4B, New York, NY 10001",
    "move_in_date": "2025-01-15",
    "move_out_date": "2026-01-14",
    "rent_amount": 2500.00,
    "message": "Contract #contract_001 created successfully"
  }
}
```

### Update Contract

**Endpoint**: `PATCH /contracts/{contract_id}`

**Request Body**:
```json
{
  "contract_id": "contract_001",
  "status": "Active",
  "move_out_date": "2026-06-30",
  "rent_amount": 2600.00
}
```

**Response**:
```json
{
  "success": true,
  "contract_id": "contract_001",
  "message": "Contract contract_001 updated successfully"
}
```

## Salesforce Object Configuration

### Contract Custom Fields Required

The following custom fields should be configured in Salesforce Contract object:

| Field Name | API Name | Type | Required | Description |
|------------|----------|------|----------|-------------|
| Tenant Name | Tenant_Name__c | Text | Yes | Name of the tenant |
| Property Address | Property_Address__c | Text (Long) | Yes | Full property address |
| Move-In Date | Move_In_Date__c | Date | Yes | Tenant move-in date |
| Move-Out Date | Move_Out_Date__c | Date | No | Tenant move-out date |
| Monthly Rent | Monthly_Rent__c | Currency | Yes | Monthly rent amount |
| External User ID | External_User_Id__c | Text | No | Reference to external user system |
| Source App | Source_App__c | Text | No | Application creating the contract |
| Backend Context | Backend_Context__c | Text (Long) | No | JSON context from backend |

### Sample SOQL Query

```soql
SELECT Id, Tenant_Name__c, Property_Address__c, Move_In_Date__c, Move_Out_Date__c, Monthly_Rent__c, Status 
FROM Contract 
WHERE External_User_Id__c = 'user123' 
ORDER BY CreatedDate DESC
```

## Validation Rules

### Date Validation
- Move-out date must be after move-in date
- Move-in date cannot be in the past (can be configured)
- Both dates required and in YYYY-MM-DD format

### Data Validation
- Tenant name: Required, max 255 characters
- Property address: Required, max 500 characters
- Monthly rent amount: Required, must be > 0

### Business Logic (via LLM)
- Contract duration reasonableness check
- Data completeness verification
- Custom business rules enforcement

## Error Handling

### Common Error Scenarios

| Scenario | HTTP Code | Resolution |
|----------|-----------|-----------|
| Invalid date format | 400 | Use YYYY-MM-DD format |
| Move-out before move-in | 400 | Swap or correct dates |
| Missing required fields | 400 | Provide all required fields |
| Salesforce auth failed | 401 | Check SF credentials |
| Contract ID not found | 404 | Verify contract exists in SF |
| Rent amount ≤ 0 | 400 | Provide positive rent amount |

## Event Logging

Contract jobs log the following events to the database:

```
contract_job_started
├── validation
│   ├── passed / rejected
│   ├── errors (if any)
│   └── confidence (if LLM used)
├── preparation
│   ├── prepared
│   ├── summary
│   └── next_steps
├── contract_creation
│   ├── success / failed
│   ├── contract_id
│   └── result/error
├── summary
│   ├── completed
│   └── summary content
└── contract_job_completed
    ├── job_id
    ├── contract_id
    └── status
```

## Integration with Memory System

Contract creation is logged to the long-term memory system:
- **Memory Type**: contract_creation
- **Stored Information**:
  - Tenant details
  - Property information
  - Dates and rent amount
  - Contract ID
  - Creation status

This enables future reference to past contracts for the same user.

## Future Enhancements

Potential expansions for the contract workflow:
1. Tenant screening/validation integration
2. Document generation (PDF contracts)
3. E-signature integration
4. Payment schedule templates
5. Auto-renewal logic
6. Late payment notifications
7. Renewal reminders based on move-out date
8. Integration with property management systems

## Testing

### Test Contract Creation

```bash
curl -X POST http://localhost:8000/api/contracts \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user_1",
    "tenant_name": "Jane Smith",
    "property_address": "456 Oak Avenue, Los Angeles, CA 90001",
    "move_in_date": "2025-02-01",
    "move_out_date": "2026-01-31",
    "rent_amount": 3500.00
  }'
```

### Check Job Status

```bash
curl -X GET http://localhost:8000/api/contracts/{job_id}
```

## Summary

The contract creation use case provides a robust, AI-driven workflow for automatically generating rental property contracts in Salesforce. It validates input data, uses LLM reasoning for business logic, and integrates seamlessly with the existing system's asynchronous job processing and memory management capabilities.
