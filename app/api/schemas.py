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


# ── Billing task ──────────────────────────────────────────────────────────────

class BillingTask(BaseModel):
    """The structured task document sent to (and stored in) the billing tool."""
    transaction_id:   str   = Field(description="Unique ID for this billing operation")
    account_id:       str   = Field(description="Customer account being acted on")
    change_suggested: str   = Field(description="LLM's plain-English recommendation / full notes")
    action_type:      str   = Field(description="rebill | credit | refund | adjustment")
    reason:           str   = Field(description="Short reason code e.g. DUPLICATE_CHARGE")
    amount:           float = Field(description="Financial amount to apply")
    currency:         str   = Field(description="ISO currency code e.g. USD")
    notes:            str   = Field(description="Full context notes")
    initiated_by:     str   = Field(description="Who triggered this task (intelligent-agent)")
    initiated_for:    str   = Field(description="What this task was initiated for (e.g., refund, meter-update, configuration-change)")
    created_at:       str   = Field(description="ISO 8601 UTC timestamp")
    status:           str   = Field(description="pending | processed | failed")


class BillingTaskRequest(BaseModel):
    """Direct billing task creation — called by the UI or the agent."""
    account_id:       str   = Field(..., example="ACC-1001")
    action_type:      str   = Field(..., example="refund", description="rebill | credit | refund | adjustment")
    amount:           float = Field(..., example=99.0)
    currency:         str   = Field(default="USD", example="USD")
    reason:           str   = Field(..., example="DUPLICATE_CHARGE", description="Short reason code")
    initiated_for:    str   = Field(default="", example="refund", description="What this action is for (e.g., refund, meter-update, config-change)")
    change_suggested: str   = Field(
        ...,
        example="Customer was double charged. Issue a full refund of $99.",
        description="Human-readable description of what should happen",
    )
    notes:            str   = Field(default="", description="Additional context")


class BillingTaskResponse(BaseModel):
    """Response returned from POST /billing-task."""
    success:      bool
    message:      Optional[str] = None
    billing_task: Optional[BillingTask] = None
    error:        Optional[str]         = None


# ── Issue resolution response ─────────────────────────────────────────────────

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
    billing_results: Optional[List[BillingTaskResponse]] = Field(
        None, description="Array of billing task results (one per matching suggestion)"
    )

    # Summary
    final_summary: str = Field(description="Human-readable summary of all actions taken")
    error: Optional[str] = Field(None, description="Error message if the workflow failed")


# ── Streaming event (SSE) ─────────────────────────────────────────────────────

class AgentEvent(BaseModel):
    event: str = Field(description="Event type: node_start | node_complete | workflow_complete | error")
    node: Optional[str] = Field(None, description="Graph node name")
    data: Optional[Dict[str, Any]] = Field(None, description="Node output or error detail")


# ── Sheet update (simple button-triggered action) ─────────────────────────────

class SheetUpdateRequest(BaseModel):
    """Request to update a single value in Excel/Sheet."""
    account_id: str = Field(..., example="ACC-1001", description="Account identifier")
    field_name: str = Field(..., example="status", description="Column name to update")
    field_value: str = Field(..., example="Resolved", description="New value for the field")
    context: Optional[str] = Field(
        None,
        example="Billing task completed",
        description="Optional context about why this update is happening"
    )


class SheetUpdateResponse(BaseModel):
    """Response from sheet update operation."""
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None
    updated_at: Optional[str] = None
    account_id: str
    field_name: Optional[str] = None
    previous_value: Optional[Any] = None
    new_value: Optional[Any] = None
