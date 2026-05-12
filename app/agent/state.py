from typing import TypedDict, Optional, List, Dict, Any


class AgentState(TypedDict):
    # ── Input ──────────────────────────────────────────────────────────────────
    account_id: str
    issue_description: str

    # ── Fetched context ────────────────────────────────────────────────────────
    account_details: Dict[str, Any]

    # ── LLM analysis ──────────────────────────────────────────────────────────
    issue_analysis: str          # human-readable analysis written by LLM
    action_reasoning: str        # LLM explanation of why it chose these actions
    confidence_score: int        # LLM confidence level 0-10 in understanding the issue
    can_understand_issue: bool   # True if confidence >= 5, False otherwise
    
    # ── Decided actions & payloads ─────────────────────────────────────────────
    # e.g. ["create_sf_case", "call_billing_api", "add_comment_to_case", ...]
    recommended_actions: List[str]
    sf_case_payload: Dict[str, Any]
    billing_payload: Dict[str, Any]
    add_comment_payload: Dict[str, Any]      # NEW: for add_comment_to_case
    close_case_payload: Dict[str, Any]       # NEW: for close_case
    edit_case_payload: Dict[str, Any]        # NEW: for edit_case

    # ── Execution results ──────────────────────────────────────────────────────
    sf_case_result: Optional[Dict[str, Any]]
    billing_result: Optional[Dict[str, Any]]
    add_comment_result: Optional[Dict[str, Any]]     # NEW
    close_case_result: Optional[Dict[str, Any]]      # NEW
    edit_case_result: Optional[Dict[str, Any]]       # NEW
    actions_executed: List[str]

    # ── Final output ───────────────────────────────────────────────────────────
    final_summary: str
    error: Optional[str]
