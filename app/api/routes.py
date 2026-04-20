from fastapi import APIRouter, HTTPException, Depends, Path
from app.api.schemas import (
    CreateJobRequest, CreateJobResponse, JobStatusResponse, EventsResponse,
    UpdateCaseRequest, UpdateCaseResponse, AddCommentRequest, AddCommentResponse,
    CloseCaseRequest, CloseCaseResponse, LookupCasesRequest, LookupCasesResponse,
    CreateContractRequest, CreateContractResponse, ContractStatusResponse, UpdateContractRequest, UpdateContractResponse
)
from app.services.job_service import create_job, get_job, get_events
from app.workers.worker import enqueue_job, enqueue_contract_job
from app.agent.memory import get_long_term_memory
from app.integrations.salesforce import SalesforceClient
from app.auth import get_current_user  # ✅ NEW - AUTHENTICATION IMPORT
import re

router = APIRouter()

def validate_job_id(job_id: str) -> str:
    """Validate job_id format - must be alphanumeric and dash"""
    if not re.match(r"^[a-zA-Z0-9\-]+$", job_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid job_id format"
        )
    if len(job_id) > 100:
        raise HTTPException(
            status_code=400,
            detail="job_id too long (max 100 characters)"
        )
    return job_id

def validate_salesforce_id(sf_id: str) -> str:
    """Validate Salesforce ID format"""
    if not re.match(r"^[a-zA-Z0-9]{15,18}$", sf_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid Salesforce ID format"
        )
    return sf_id


@router.post("/jobs", response_model=CreateJobResponse)
def create_agent_job(
    payload: CreateJobRequest,
    current_user: dict = Depends(get_current_user)  # ✅ SECURITY: Require authentication
):
    # ✅ FIX: Verify user can only create jobs for themselves
    if payload.user_id != current_user["user_id"]:
        raise HTTPException(
            status_code=403,
            detail="Cannot create jobs for another user"
        )
    
    job_id = create_job(payload.model_dump())

    history = get_long_term_memory(payload.user_id)

    initial_state = {
        "job_id": job_id,
        "user_id": payload.user_id,
        "issue_type": payload.issue_type,
        "message": payload.message or "",
        "backend_context": {
            "account_tier": "Pro",
            "recent_errors": ["payment_timeout", "retry_failed"],
            "history": history
        },
        "customer_profile": None,
        "logs": None,
        "summary": None,
        "category": None,
        "priority": None,
        "next_action": None,
        "final_answer": None,
        "case_id": None,
        "retries": 0,
        "event_log": []
    }

    enqueue_job(initial_state)

    return CreateJobResponse(job_id=job_id, status="queued")

@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(
    job_id: str = Path(..., min_length=1, max_length=100, description="Job ID"),
    current_user: dict = Depends(get_current_user)  # ✅ SECURITY: Require authentication
):
    job_id = validate_job_id(job_id)
    
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # ✅ FIX: Verify user owns this job
    if job.get("user_id") != current_user["user_id"]:
        raise HTTPException(
            status_code=403,
            detail="Cannot access other users' jobs"
        )

    return JobStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        result=job["result"]
    )

@router.get("/jobs/{job_id}/events", response_model=EventsResponse)
def get_job_events(
    job_id: str = Path(..., min_length=1, max_length=100, description="Job ID"),
    current_user: dict = Depends(get_current_user)  # ✅ SECURITY: Require authentication
):
    job_id = validate_job_id(job_id)
    
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # ✅ FIX: Verify user owns this job
    if job.get("user_id") != current_user["user_id"]:
        raise HTTPException(
            status_code=403,
            detail="Cannot access other users' jobs"
        )
    
    return EventsResponse(job_id=job_id, events=get_events(job_id))

@router.patch("/cases/{case_id}", response_model=UpdateCaseResponse)
def update_case(
    case_id: str = Path(..., description="Salesforce Case ID"),
    payload: UpdateCaseRequest = None,
    current_user: dict = Depends(get_current_user)  # ✅ SECURITY: Require authentication
):
    case_id = validate_salesforce_id(case_id)
    
    if payload is None:
        raise HTTPException(
            status_code=400,
            detail="Request body is required"
        )
    
    # ✅ CRITICAL FIX: Use path parameter, not payload
    if case_id != payload.case_id:
        raise HTTPException(
            status_code=400,
            detail="Path and body case_id must match"
        )
    
    try:
        sf_client = SalesforceClient()
        result = sf_client.update_case(
            case_id=case_id,  # ✅ Use path param, not payload
            subject=payload.subject,
            description=payload.description,
            status=payload.status,
            priority=payload.priority,
            agent_result=payload.agent_result
        )
        return UpdateCaseResponse(success=True, message=f"Case {case_id} updated successfully")
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "invalid token" in error_msg.lower():
            raise HTTPException(status_code=401, detail="Salesforce authentication failed")
        elif "404" in error_msg or "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found in Salesforce")
        else:
            raise HTTPException(status_code=500, detail=f"Failed to update case: {error_msg}")

@router.post("/cases/{case_id}/comments", response_model=AddCommentResponse)
def add_case_comment(
    case_id: str = Path(..., description="Salesforce Case ID"),
    payload: AddCommentRequest = None,
    current_user: dict = Depends(get_current_user)  # ✅ SECURITY: Require authentication
):
    case_id = validate_salesforce_id(case_id)
    
    if payload is None:
        raise HTTPException(
            status_code=400,
            detail="Request body is required"
        )
    
    # ✅ FIX: Verify path and payload case_id match
    if case_id != payload.case_id:
        raise HTTPException(
            status_code=400,
            detail="Path and body case_id must match"
        )
    
    try:
        sf_client = SalesforceClient()
        result = sf_client.add_comment_to_case(
            case_id=case_id,
            comment_text=payload.comment_text
        )
        comment_id = result.get("id", "unknown")
        return AddCommentResponse(
            comment_id=comment_id,
            case_id=case_id,
            message=f"Comment added to case {case_id}"
        )
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "invalid token" in error_msg.lower():
            raise HTTPException(status_code=401, detail="Salesforce authentication failed")
        elif "404" in error_msg or "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found in Salesforce")
        else:
            raise HTTPException(status_code=500, detail=f"Failed to add comment: {error_msg}")

@router.patch("/cases/{case_id}/close", response_model=CloseCaseResponse)
def close_case(
    case_id: str = Path(..., description="Salesforce Case ID"),
    payload: CloseCaseRequest = None,
    current_user: dict = Depends(get_current_user)  # ✅ SECURITY: Require authentication
):
    case_id = validate_salesforce_id(case_id)
    
    if payload is None:
        raise HTTPException(
            status_code=400,
            detail="Request body is required"
        )
    
    # ✅ FIX: Verify path and payload case_id match
    if case_id != payload.case_id:
        raise HTTPException(
            status_code=400,
            detail="Path and body case_id must match"
        )
    
    try:
        sf_client = SalesforceClient()
        result = sf_client.close_case(
            case_id=case_id,
            subject=payload.subject,
            summary=payload.summary,
            resolution_notes=payload.resolution_notes
        )
        return CloseCaseResponse(
            success=True,
            case_id=case_id,
            message=f"Case {case_id} closed successfully"
        )
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "invalid token" in error_msg.lower():
            raise HTTPException(status_code=401, detail="Salesforce authentication failed")
        elif "404" in error_msg or "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found in Salesforce")
        else:
            raise HTTPException(status_code=500, detail=f"Failed to close case: {error_msg}")

@router.post("/cases/lookup", response_model=LookupCasesResponse)
def lookup_cases(
    payload: LookupCasesRequest,
    current_user: dict = Depends(get_current_user)  # ✅ SECURITY: Require authentication
):
    # ✅ FIX: Verify user can only lookup their own cases
    if payload.user_id != current_user["user_id"]:
        raise HTTPException(
            status_code=403,
            detail="Cannot lookup other users' cases"
        )
    
    try:
        sf_client = SalesforceClient()
        cases = sf_client.lookup_cases_by_user(payload.user_id, payload.status)
        return LookupCasesResponse(
            user_id=payload.user_id,
            case_count=len(cases),
            cases=[
                {
                    "id": case.get("Id"),
                    "case_number": case.get("CaseNumber"),
                    "subject": case.get("Subject"),
                    "status": case.get("Status")
                }
                for case in cases
            ]
        )
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "invalid token" in error_msg.lower():
            raise HTTPException(status_code=401, detail="Salesforce authentication failed")
        else:
            raise HTTPException(status_code=500, detail=f"Failed to lookup cases: {error_msg}")


# Contract endpoints
@router.post("/contracts", response_model=CreateContractResponse)
def create_contract_job(
    payload: CreateContractRequest,
    current_user: dict = Depends(get_current_user)  # ✅ SECURITY: Require authentication
):
    """Create a new contract job for processing"""
    # ✅ FIX: Verify user can only create contracts for themselves
    if payload.user_id != current_user["user_id"]:
        raise HTTPException(
            status_code=403,
            detail="Cannot create contracts for another user"
        )
    
    job_id = create_job(payload.model_dump())
    
    history = get_long_term_memory(payload.user_id)
    
    initial_state = {
        "job_id": job_id,
        "user_id": payload.user_id,
        "account_id": payload.account_id,
        "tenant_name": payload.tenant_name,
        "property_address": payload.property_address,
        "move_in_date": payload.move_in_date,
        "move_out_date": payload.move_out_date,
        "rent_amount": payload.rent_amount,
        "backend_context": {
            "request_type": "contract_creation",
            "history": history
        },
        "next_action": None,
        "validation_status": None,
        "validation_errors": [],
        "contract_id": None,
        "final_answer": None,
        "retries": 0,
        "event_log": []
    }
    
    # Enqueue for contract processing
    enqueue_contract_job(initial_state)
    
    return CreateContractResponse(job_id=job_id, status="queued")


@router.get("/contracts/{job_id}", response_model=ContractStatusResponse)
def get_contract_job_status(
    job_id: str = Path(..., min_length=1, max_length=100, description="Contract Job ID"),
    current_user: dict = Depends(get_current_user)  # ✅ SECURITY: Require authentication
):
    """Get the status of a contract creation job"""
    job_id = validate_job_id(job_id)
    
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Contract job not found")
    
    # ✅ FIX: Verify user owns this job
    if job.get("user_id") != current_user["user_id"]:
        raise HTTPException(
            status_code=403,
            detail="Cannot access other users' contracts"
        )
    
    return ContractStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        result=job["result"]
    )


@router.patch("/contracts/{contract_id}", response_model=UpdateContractResponse)
def update_contract(
    contract_id: str = Path(..., description="Salesforce Contract ID"),
    payload: UpdateContractRequest = None,
    current_user: dict = Depends(get_current_user)  # ✅ SECURITY: Require authentication
):
    """Update an existing contract in Salesforce"""
    contract_id = validate_salesforce_id(contract_id)
    
    if payload is None:
        raise HTTPException(
            status_code=400,
            detail="Request body is required"
        )
    
    # Verify path and body contract_id match
    if contract_id != payload.contract_id:
        raise HTTPException(
            status_code=400,
            detail="Path and body contract_id must match"
        )
    """Update an existing contract in Salesforce"""
    try:
        sf_client = SalesforceClient()
        result = sf_client.update_contract(
            contract_id=contract_id,
            status=payload.status,
            move_out_date=payload.move_out_date,
            rent_amount=payload.rent_amount
        )
        return UpdateContractResponse(
            success=True,
            contract_id=contract_id,
            message=f"Contract {contract_id} updated successfully"
        )
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "invalid token" in error_msg.lower():
            raise HTTPException(status_code=401, detail="Salesforce authentication failed")
        elif "404" in error_msg or "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found in Salesforce")
        else:
            raise HTTPException(status_code=500, detail=f"Failed to update contract: {error_msg}")