"""
FastAPI routes for the agentic issue-resolution workflow.

Endpoints
─────────
POST /api/v1/resolve-issue          — run the full LangGraph agent, return JSON
POST /api/v1/resolve-issue/stream   — same agent, stream progress via SSE
GET  /api/v1/actions                — list supported action types
"""
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.api.schemas import IssueRequest, IssueResponse
from app.agent.graph import agent_graph

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
        "recommended_actions": [],
        "sf_case_payload": {},
        "billing_payload": {},
        "sf_case_result": None,
        "billing_result": None,
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
        final_state = await agent_graph.ainvoke(_build_initial_state(request))
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
            async for event in agent_graph.astream_events(
                _build_initial_state(request), version="v2"
            ):
                kind = event.get("event", "")
                name = event.get("name", "")

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

            # ── Re-invoke synchronously to get full final state ────────────────
            # (astream_events doesn't expose the last cumulative state easily)
            final_state = await agent_graph.ainvoke(_build_initial_state(request))
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
