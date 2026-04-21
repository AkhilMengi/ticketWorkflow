from fastapi import APIRouter, HTTPException
from app.api.schemas import (
    CreateJobRequest, CreateJobResponse, JobStatusResponse, EventsResponse,
    UpdateCaseRequest, UpdateCaseResponse, AddCommentRequest, AddCommentResponse,
    CloseCaseRequest, CloseCaseResponse, LookupCasesRequest, LookupCasesResponse,
    CreateContractRequest, CreateContractResponse, ContractStatusResponse, UpdateContractRequest, UpdateContractResponse,
    ProcessRecommendedActionsResponse, ExecuteIntelligentActionsRequest
)
from app.services.job_service import create_job, get_job, get_events
from app.workers.worker import enqueue_job, enqueue_contract_job
from app.agent.memory import get_long_term_memory
from app.agent.routing_graph import routing_graph
from app.agent.routing_state import create_enhanced_state
from app.integrations.salesforce import SalesforceClient
import uuid
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/jobs", response_model=CreateJobResponse)
def create_agent_job(payload: CreateJobRequest):
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
def get_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        result=job["result"]
    )

@router.get("/jobs/{job_id}/events", response_model=EventsResponse)
def get_job_events(job_id: str):
    return EventsResponse(job_id=job_id, events=get_events(job_id))

@router.patch("/cases/{case_id}", response_model=UpdateCaseResponse)
def update_case(case_id: str, payload: UpdateCaseRequest):
    try:
        sf_client = SalesforceClient()
        result = sf_client.update_case(
            case_id=payload.case_id,
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
def add_case_comment(case_id: str, payload: AddCommentRequest):
    try:
        sf_client = SalesforceClient()
        result = sf_client.add_comment_to_case(
            case_id=payload.case_id,
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
def close_case(case_id: str, payload: CloseCaseRequest):
    try:
        sf_client = SalesforceClient()
        result = sf_client.close_case(
            case_id=payload.case_id,
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
def lookup_cases(payload: LookupCasesRequest):
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
def create_contract_job(payload: CreateContractRequest):
    """Create a new contract job for processing"""
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
def get_contract_job_status(job_id: str):
    """Get the status of a contract creation job"""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Contract job not found")
    
    return ContractStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        result=job["result"]
    )


@router.patch("/contracts/{contract_id}", response_model=UpdateContractResponse)
def update_contract(contract_id: str, payload: UpdateContractRequest):
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


@router.post("/intelligent-actions", response_model=ProcessRecommendedActionsResponse)
def execute_intelligent_actions(payload: ExecuteIntelligentActionsRequest):
    """
    🤖 AI-POWERED ENDPOINT (LangGraph Integrated)
    
    This endpoint uses the routing graph to intelligently analyze issues and decide actions.
    
    The routing graph automatically:
    1. Checks if intelligent routing is appropriate (file exists + description present)
    2. Routes through intelligent_action_routing_node for AI analysis
    3. Executes recommended actions via intelligent_actions_execution_node
    4. Aggregates results with intelligent response formatting
    
    Workflow:
    1. Receive issue description
    2. Graph routes to intelligent routing
    3. AI analyzes severity and type
    4. AI recommends appropriate actions
    5. Execute only recommended actions
    6. Return results with AI analysis
    
    Request body:
    {
      "user_id": "customer_123",
      "issue_description": "Customer's payment keeps failing, tried 3 times"
    }
    """
    try:
        job_id = str(uuid.uuid4())
        
        logger.info(f"[INTELLIGENT_ACTIONS] Starting for user {payload.user_id}")
        
        # Create enhanced agent state with all required fields
        initial_state = create_enhanced_state({
            "job_id": job_id,
            "user_id": payload.user_id,
            "issue_type": "customer_support",
            "message": payload.issue_description,
            "backend_context": {
                "source": "intelligent_actions_api",
                "request_type": "ai_powered_routing"
            },
            "customer_profile": None,
            "logs": None,
            "summary": None,
            "category": None,
            "priority": None,
            "next_action": "routing",  # Skip enrichment, go straight to routing
            "final_answer": None,
            "case_id": None,
            "retries": 0,
            "event_log": []
        })
        
        logger.info(f"[INTELLIGENT_ACTIONS] Initial state created with keys: {list(initial_state.keys())}")
        
        # Invoke the LangGraph routing graph
        logger.info(f"[INTELLIGENT_ACTIONS] Invoking routing graph...")
        result = routing_graph.invoke(initial_state)
        
        logger.info(f"[INTELLIGENT_ACTIONS] Graph result keys: {list(result.keys())}")
        
        # Extract aggregated response from graph result
        aggregated_response = result.get("aggregated_response", {})
        execution_summary = result.get("execution_summary", {})
        intelligent_results = result.get("intelligent_action_results", [])
        
        logger.info(f"[INTELLIGENT_ACTIONS] Response summary: {execution_summary}")
        
        # Transform intelligent_results to ActionResult format
        action_results = []
        for action_result in intelligent_results:
            action_type = action_result.get("action_type", "unknown")
            status = action_result.get("status", "unknown")
            details = action_result.get("details", {})
            error = action_result.get("error")
            
            # Ensure result field has content
            result_data = details if details else {"status": status}
            if "action_type" not in result_data:
                result_data["action_type"] = action_type
            
            action_results.append({
                "action_type": action_type,
                "status": status,
                "result": result_data,
                "error": error
            })
        
        # Build API response
        response_data = {
            "job_id": job_id,
            "user_id": payload.user_id,
            "total_actions": execution_summary.get("total_actions", len(action_results)),
            "results": action_results,
            "summary": execution_summary
        }
        
        logger.info(f"[INTELLIGENT_ACTIONS] Returning response with {len(action_results)} actions")
        return ProcessRecommendedActionsResponse(**response_data)
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Error processing request: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Error processing request: {str(e)}")
    except TypeError as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"TypeError in intelligent actions: {tb}")
        raise HTTPException(status_code=500, detail=f"TypeError: {str(e)}")
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"Full exception in intelligent actions: {tb}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to execute intelligent actions: {str(e)}"
        )