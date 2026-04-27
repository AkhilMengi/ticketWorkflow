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

    # ── Decided actions & payloads ─────────────────────────────────────────────
    # e.g. ["create_sf_case", "call_billing_api"]
    recommended_actions: List[str]
    sf_case_payload: Dict[str, Any]
    billing_payload: Dict[str, Any]

    # ── Execution results ──────────────────────────────────────────────────────
    sf_case_result: Optional[Dict[str, Any]]
    billing_result: Optional[Dict[str, Any]]
    actions_executed: List[str]

    # ── Final output ───────────────────────────────────────────────────────────
    final_summary: str
    error: Optional[str]
