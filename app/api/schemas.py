from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ── Request ───────────────────────────────────────────────────────────────────

class IssueRequest(BaseModel):
    account_id: str = Field(..., example="ACC-1001", description="Internal account identifier")
    issue_description: str = Field(
        ...,
        example="Customer was double-charged this month and is requesting a refund.",
        description="Plain-language description of the problem reported by the customer.",
    )


# ── Response ──────────────────────────────────────────────────────────────────

class IssueResponse(BaseModel):
    account_id: str
    issue_description: str

    # LLM analysis
    issue_analysis: str = Field(description="LLM's analysis of the issue")
    action_reasoning: str = Field(description="LLM's reasoning for choosing these actions")

    # Decisions
    recommended_actions: List[str] = Field(
        description="Actions the LLM recommended (create_sf_case, call_billing_api)"
    )
    actions_executed: List[str] = Field(
        description="Actions that were actually executed successfully"
    )

    # Results
    sf_case_result: Optional[Dict[str, Any]] = Field(
        None, description="Salesforce case creation result"
    )
    billing_result: Optional[Dict[str, Any]] = Field(
        None, description="Billing API call result"
    )

    # Summary
    final_summary: str = Field(description="Human-readable summary of all actions taken")
    error: Optional[str] = Field(None, description="Error message if the workflow failed")


# ── Streaming event (SSE) ─────────────────────────────────────────────────────

class AgentEvent(BaseModel):
    event: str = Field(description="Event type: node_start | node_complete | workflow_complete | error")
    node: Optional[str] = Field(None, description="Graph node name")
    data: Optional[Dict[str, Any]] = Field(None, description="Node output or error detail")
