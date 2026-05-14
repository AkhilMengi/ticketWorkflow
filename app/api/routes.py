"""
FastAPI routes for the agentic issue-resolution workflow.

Endpoints
─────────
POST /api/v1/resolve-issue          — run the full LangGraph agent, return JSON
POST /api/v1/resolve-issue/stream   — same agent, stream progress via SSE
POST /api/v1/update-sheet           — update Excel/Sheet value (button-triggered)
GET  /api/v1/actions                — list supported action types
GET  /api/v1/traces                 — get agent execution traces (Mock LangSmith)
GET  /api/v1/traces/metrics         — get aggregate metrics
"""
import json
import logging
import time
from datetime import datetime
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.api.schemas import IssueRequest, IssueResponse, BillingTaskRequest, BillingTaskResponse, SheetUpdateRequest, SheetUpdateResponse
from app.agent.graph import agent_graph
from app.agent.tracing import AgentTrace
from app.services.billing import call_billing_api, get_all_tasks, get_task_by_id
from app.services.sheet import update_sheet

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_initial_state(req: IssueRequest) -> dict:
    return {
        "account_id": req.account_id,
        "issue_description": req.issue_description,
        "account_details": {},
        "issue_analysis": "",
        "action_reasoning": "",
        "confidence_score": 0,
        "can_understand_issue": True,
        "recommended_actions": [],
        "sf_case_payload": {},
        "billing_payloads": [],
        "sf_case_result": None,
        "billing_results": None,
        "actions_executed": [],
        "final_summary": "",
        "error": None,
    }


def _state_to_response(state: dict) -> IssueResponse:
    return IssueResponse(
        account_id=state["account_id"],
        issue_description=state["issue_description"],
        issue_analysis=state.get("issue_analysis", ""),
        action_reasoning=state.get("action_reasoning", ""),
        recommended_actions=state.get("recommended_actions", []),
        actions_executed=state.get("actions_executed", []),
        sf_case_result=state.get("sf_case_result"),
        billing_result=state.get("billing_result"),
        final_summary=state.get("final_summary", ""),
        error=state.get("error"),
    )


# ── POST /resolve-issue ───────────────────────────────────────────────────────

@router.post(
    "/resolve-issue",
    response_model=IssueResponse,
    summary="Resolve an account issue",
    description=(
        "Runs the LangGraph agentic workflow: fetches account context, "
        "uses an LLM to analyse the issue and map it to business suggestions, "
        "then creates a Salesforce case and/or calls the billing API as needed."
    ),
)
async def resolve_issue(request: IssueRequest) -> IssueResponse:
    logger.info(
        "resolve-issue | account=%s | issue='%s'",
        request.account_id,
        request.issue_description[:80],
    )

    try:
        start_time = time.time()
        final_state = await agent_graph.ainvoke(_build_initial_state(request))
        duration = time.time() - start_time
        
        # Record trace for dashboard
        AgentTrace.record_execution(
            account_id=final_state.get("account_id", ""),
            issue_description=final_state.get("issue_description", ""),
            confidence_score=final_state.get("confidence_score", 0),
            issue_analysis=final_state.get("issue_analysis", ""),
            recommended_actions=final_state.get("recommended_actions", []),
            actions_executed=final_state.get("actions_executed", []),
            final_summary=final_state.get("final_summary", ""),
            duration_seconds=duration,
            sf_case_result=final_state.get("sf_case_result"),
            billing_result=final_state.get("billing_result"),
            error=final_state.get("error"),
        )
        
        return _state_to_response(final_state)
    except Exception as exc:
        logger.error("Agent workflow error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent workflow failed: {exc}")


# ── POST /resolve-issue/stream ────────────────────────────────────────────────

@router.post(
    "/resolve-issue/stream",
    summary="Resolve an account issue (streaming SSE)",
    description=(
        "Same as /resolve-issue but streams progress events via Server-Sent Events "
        "so a UI can show real-time agent steps."
    ),
)
async def resolve_issue_stream(request: IssueRequest) -> EventSourceResponse:
    """
    Emits SSE events for every completed graph node plus a final
    'workflow_complete' event containing the full result.
    """
    TRACKED_NODES = {
        "fetch_account": "Fetching account details",
        "analyze_issue": "Analysing issue with LLM",
        "execute_actions": "Executing actions (SF + Billing)",
        "summarize": "Generating summary",
    }

    async def event_generator() -> AsyncGenerator[dict, None]:
        try:
            final_state = None

            async for event in agent_graph.astream_events(
                _build_initial_state(request), version="v2"
            ):
                kind = event.get("event", "")
                name = event.get("name", "")

                # ── Capture final cumulative state from the graph's own end event ──
                if kind == "on_chain_end" and name == "LangGraph":
                    final_state = event.get("data", {}).get("output", None)

                # ── Emit progress when each tracked node finishes ──────────────
                if kind == "on_chain_end" and name in TRACKED_NODES:
                    output = event.get("data", {}).get("output", {})
                    yield {
                        "event": "node_complete",
                        "data": json.dumps(
                            {
                                "node": name,
                                "label": TRACKED_NODES[name],
                                "output_keys": list(output.keys()) if isinstance(output, dict) else [],
                            }
                        ),
                    }

            # ── Emit final result using state captured from the stream ──────────
            # Falls back to a single ainvoke only if the state wasn't captured
            if final_state is None:
                logger.warning("Final state not captured from stream — falling back to ainvoke")
                final_state = await agent_graph.ainvoke(_build_initial_state(request))

            # Record trace for dashboard (same as /resolve-issue endpoint)
            AgentTrace.record_execution(
                account_id=final_state.get("account_id", ""),
                issue_description=final_state.get("issue_description", ""),
                confidence_score=final_state.get("confidence_score", 0),
                issue_analysis=final_state.get("issue_analysis", ""),
                recommended_actions=final_state.get("recommended_actions", []),
                actions_executed=final_state.get("actions_executed", []),
                final_summary=final_state.get("final_summary", ""),
                duration_seconds=0,  # stream doesn't track duration, set to 0
                sf_case_result=final_state.get("sf_case_result"),
                billing_result=final_state.get("billing_result"),
                error=final_state.get("error"),
            )

            yield {
                "event": "workflow_complete",
                "data": _state_to_response(final_state).model_dump_json(),
            }

        except Exception as exc:
            logger.error("Stream error: %s", exc, exc_info=True)
            yield {
                "event": "error",
                "data": json.dumps({"detail": str(exc)}),
            }

    return EventSourceResponse(event_generator())

# ── GET /billing-tasks ────────────────────────────────────────────────────────

@router.get(
    "/billing-tasks",
    summary="List all billing tasks created this session",
    description="Returns every billing task the agent or UI has created since the server started.",
)
async def list_billing_tasks():
    tasks = get_all_tasks()
    return {
        "total": len(tasks),
        "tasks": tasks,
    }


@router.get(
    "/billing-tasks/{transaction_id}",
    summary="Get a specific billing task by transaction ID",
)
async def get_billing_task(transaction_id: str):
    task = get_task_by_id(transaction_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{transaction_id}' not found.")
    return task

# ── POST /billing-task ───────────────────────────────────────────────────────

@router.post(
    "/billing-task",
    response_model=BillingTaskResponse,
    summary="Create a billing task directly",
    description=(
        "Create a structured billing task and post it to the billing micro-service. "
        "Can be called directly from the UI (bypassing the full agent) when the "
        "action is already known. Returns the full task document including "
        "transaction_id, account_id, change_suggested, action_type, amount, and "
        "all other key components."
    ),
)
async def create_billing_task(request: BillingTaskRequest) -> BillingTaskResponse:
    logger.info(
        "billing-task | account=%s action=%s amount=%s reason=%s",
        request.account_id, request.action_type, request.amount, request.reason,
    )

    # Map the request into the billing service payload format
    payload = {
        "account_id":  request.account_id,
        "action_type": request.action_type,
        "amount":      request.amount,
        "currency":    request.currency,
        "reason":      request.reason,
        "notes":       request.change_suggested + (f" | {request.notes}" if request.notes else ""),
    }

    result = call_billing_api(payload)

    if not result.get("success"):
        raise HTTPException(
            status_code=502,
            detail=result.get("error", "Billing service failed"),
        )

    return BillingTaskResponse(
        success=True,
        message=result["message"],
        billing_task=result["billing_task"],
    )

# ── POST /update-sheet ────────────────────────────────────────────────────────

@router.post(
    "/update-sheet",
    response_model=SheetUpdateResponse,
    summary="Update an Excel/Sheet cell (button-triggered)",
    description=(
        "Simple button-triggered endpoint to update a single cell in an Excel sheet "
        "via the external Sheet API. Used for quick updates without full agent workflow."
    ),
)
async def update_sheet_endpoint(request: SheetUpdateRequest) -> SheetUpdateResponse:
    logger.info(
        "update-sheet | account=%s | field=%s | value=%s",
        request.account_id,
        request.field_name,
        request.field_value,
    )

    try:
        payload = {
            "account_id": request.account_id,
            "field_name": request.field_name,
            "field_value": request.field_value,
            "context": request.context or "",
        }
        
        result = update_sheet(payload)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=502,
                detail=result.get("error", "Sheet service failed"),
            )
        
        return SheetUpdateResponse(
            success=True,
            message=result.get("message", "Sheet updated successfully"),
            error=None,
            updated_at=result.get("updated_at"),
            previous_value=result.get("previous_value"),
            new_value=result.get("new_value"),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Sheet update error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Sheet update failed: {exc}")

# ── GET /actions ──────────────────────────────────────────────────────────────

@router.get(
    "/actions",
    summary="List supported agent actions",
)
async def list_actions():
    return {
        "supported_actions": [
            {
                "id": "create_sf_case",
                "label": "Create Salesforce Case",
                "description": "Opens a new support case in Salesforce for tracking and follow-up.",
            },
            {
                "id": "call_billing_api",
                "label": "Call Billing API",
                "description": "Applies a credit, refund, rebill, or adjustment to the account.",
            },
        ]
    }


# ── GET /traces (Mock LangSmith) ──────────────────────────────────────────────

@router.get(
    "/traces",
    summary="Get all agent execution traces (Mock LangSmith Dashboard)",
    description="Returns all agent execution traces for visualization and debugging.",
)
async def get_traces(account_id: str = None, limit: int = 100):
    """Retrieve execution traces for the dashboard."""
    if account_id:
        traces = AgentTrace.get_traces_by_account(account_id)
    else:
        traces = AgentTrace.get_all_traces(limit)
    
    return {
        "total": len(traces),
        "traces": traces,
    }


@router.get(
    "/traces/metrics",
    summary="Get aggregate metrics (Mock LangSmith Metrics)",
    description="Returns metrics about agent performance and decisions.",
)
async def get_traces_metrics():
    """Get metrics from all traces."""
    metrics = AgentTrace.get_metrics()
    return {
        "metrics": metrics,
        "timestamp": datetime.utcnow().isoformat(),
    }
