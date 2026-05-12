"""
LangGraph nodes — each function transforms the AgentState.

Flow (see graph.py):
  START
    └── fetch_account_node      (load account details from CRM / DB)
          └── analyze_issue_node  (LLM reads issue + suggestions → decides actions)
                └── [conditional routing]
                      ├── execute_actions_node  (runs SF case + billing API)
                      │       └── summarize_node
                      └── summarize_node  (if no actions needed)
                              └── END
"""
import json
import logging
import yaml
from typing import Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from app.agent.state import AgentState
from app.agent.prompts import ANALYZE_ISSUE_PROMPT
from app.agent.api_validator import validate_action_entities
from app.services.salesforce import (
    create_sf_case,
    add_comment_to_case,
    close_case,
    edit_case,
)
from app.services.billing import call_billing_api
from app.config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

# ── LLM (lazy singleton) ──────────────────────────────────────────────────────

_llm: ChatOpenAI | None = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=OPENAI_API_KEY,
        )
    return _llm


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_suggestions() -> str:
    """Load business suggestions from suggestions.txt (YAML format)."""
    try:
        with open("suggestions.txt", "r") as fh:
            data = yaml.safe_load(fh.read())
        lines = []
        for value in data.values():
            title = value.get("title", "")
            desc = value.get("description", "")
            lines.append(f"  • {title}: {desc}")
        result = "\n".join(lines)
        logger.info("✅ suggestions.txt loaded (%d suggestions):\n%s", len(data), result)
        return result
    except Exception as exc:
        logger.warning("⚠️  Could not load suggestions.txt: %s", exc)
        return (
            "  • Check customer details: Verify account information and payment history.\n"
            "  • Rebill the account: Reprocess billing or apply credits/adjustments.\n"
            "  • Close the case: Mark the issue as resolved."
        )


def _parse_llm_json(content: str) -> Dict[str, Any]:
    """Strip optional markdown fences and parse JSON."""
    text = content.strip()
    if text.startswith("```"):
        # remove ```json ... ``` wrapper
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    return json.loads(text)


# ── Node 1: fetch_account_node ────────────────────────────────────────────────

def fetch_account_node(state: AgentState) -> Dict[str, Any]:
    """
    Retrieve account details from CRM / database.
    Also fetches recent open cases from Salesforce.
    """
    account_id = state["account_id"]
    logger.info("Fetching account details and recent cases for %s", account_id)

    # TODO: replace with actual CRM / DB lookup
    account_details: Dict[str, Any] = {
        "account_id": account_id,
        "name": f"Customer_{account_id}",
        "email": f"customer_{account_id.lower()}@example.com",
        "plan": "Premium",
        "status": "Active",
        "billing_cycle": "Monthly",
        "outstanding_balance": 0.00,
        "last_payment_date": "2026-04-01",
        "last_payment_amount": 99.00,
        "open_tickets": 0,
        "account_age_months": 18,
    }

    # Fetch recent open cases from Salesforce
    from app.services.salesforce import fetch_recent_cases
    
    cases_result = fetch_recent_cases(account_id, limit=5)
    if cases_result.get("success"):
        # Transform cases to make field names crystal clear for LLM
        recent_cases = []
        for case in cases_result.get("cases", []):
            recent_cases.append({
                "case_id": case.get("id"),              # ← Use this for API calls (18-char ID)
                "case_number": case.get("case_number"), # ← This is for display only
                "subject": case.get("subject"),
                "description": case.get("description"),
                "priority": case.get("priority"),
                "status": case.get("status"),
                "created_date": case.get("created_date"),
                "last_modified_date": case.get("last_modified_date"),
            })
        account_details["recent_open_cases"] = recent_cases
        logger.info("✅ Fetched %d recent cases for %s", len(recent_cases), account_id)
    else:
        logger.warning("⚠️  Could not fetch recent cases: %s", cases_result.get("error", "Unknown error"))
        account_details["recent_open_cases"] = []

    return {"account_details": account_details}


# ── Node 2: analyze_issue_node ────────────────────────────────────────────────

def analyze_issue_node(state: AgentState) -> Dict[str, Any]:
    """
    LLM analyses the issue + account context + business suggestions and
    decides which system actions are required, generating exact payloads.
    
    NEW: LLM rates confidence (0-10) in understanding the issue.
    If confidence < 5, agent will NOT recommend any actions and will 
    respond with "I am not able to understand the issue".
    """
    logger.info("Analyzing issue for account %s with LLM…", state["account_id"])

    suggestions = _load_suggestions()
    prompt = ANALYZE_ISSUE_PROMPT.format(
        account_id=state["account_id"],
        account_details=json.dumps(state["account_details"], indent=2),
        issue_description=state["issue_description"],
        suggestions=suggestions,
    )

    try:
        response = _get_llm().invoke([HumanMessage(content=prompt)])
        result = _parse_llm_json(response.content)
    except json.JSONDecodeError as exc:
        logger.error("LLM returned invalid JSON: %s", exc)
        # Safe fallback — low confidence when we can't parse
        result = {
            "confidence_score": 2,
            "analysis": "I am not able to understand the issue",
            "reasoning": "Failed to parse analysis response (technical error).",
            "recommended_actions": [],
            "sf_case_payload": {},
            "billing_payload": {},
        }

    # Extract confidence score and check if we can understand the issue
    confidence_score = result.get("confidence_score", 5)
    can_understand = confidence_score >= 5
    
    logger.info(
        "Confidence: %d/10  |  Understanding: %s  |  Analysis: %s",
        confidence_score,
        "✓ Yes" if can_understand else "✗ No",
        result.get("analysis", "")[:100],
    )

    # If confidence is too low, don't recommend any actions
    actions = result.get("recommended_actions", []) if can_understand else []

    return {
        "issue_analysis": result.get("analysis", ""),
        "action_reasoning": result.get("reasoning", ""),
        "confidence_score": confidence_score,
        "can_understand_issue": can_understand,
        "recommended_actions": actions,
        "sf_case_payload": result.get("sf_case_payload", {}) if can_understand else {},
        "billing_payload": result.get("billing_payload", {}) if can_understand else {},
        "add_comment_payload": result.get("add_comment_payload", {}) if can_understand else {},
        "close_case_payload": result.get("close_case_payload", {}) if can_understand else {},
        "edit_case_payload": result.get("edit_case_payload", {}) if can_understand else {},
    }


# ── Node 3: execute_actions_node ──────────────────────────────────────────────

def execute_actions_node(state: AgentState) -> Dict[str, Any]:
    """
    Execute every action the LLM recommended using a clean dispatcher pattern.

    Supported actions:
      • create_sf_case        → creates new Salesforce case
      • add_comment_to_case   → appends comment to existing case
      • close_case            → marks case as closed
      • edit_case             → updates case fields (Priority, Subject, etc.)
      • call_billing_api      → executes billing operations (refund, credit, etc.)

    The dispatcher validates required entities for each action before execution.
    """
    recommended = state.get("recommended_actions", [])
    logger.info("Executing actions: %s", recommended)

    # Initialize result containers
    results = {
        "sf_case_result": None,
        "add_comment_result": None,
        "close_case_result": None,
        "edit_case_result": None,
        "billing_result": None,
    }
    actions_executed = []

    # ── Action Dispatcher ──────────────────────────────────────────────────────
    
    for action in recommended:
        try:
            if action == "create_sf_case":
                results["sf_case_result"] = _execute_create_sf_case(state)
                if results["sf_case_result"].get("success"):
                    actions_executed.append(action)
            
            elif action == "add_comment_to_case":
                results["add_comment_result"] = _execute_add_comment(state)
                if results["add_comment_result"].get("success"):
                    actions_executed.append(action)
            
            elif action == "close_case":
                results["close_case_result"] = _execute_close_case(state)
                if results["close_case_result"].get("success"):
                    actions_executed.append(action)
            
            elif action == "edit_case":
                results["edit_case_result"] = _execute_edit_case(state)
                if results["edit_case_result"].get("success"):
                    actions_executed.append(action)
            
            elif action == "call_billing_api":
                results["billing_result"] = _execute_billing_api(state)
                if results["billing_result"].get("success"):
                    actions_executed.append(action)
            
            else:
                logger.warning(f"Unknown action: {action}")
        
        except Exception as exc:
            logger.error(f"Error executing action '{action}': {exc}", exc_info=True)

    return {
        **results,
        "actions_executed": actions_executed,
        "confidence_score": state.get("confidence_score", 0),
    }


# ── Action Executors (Internal) ────────────────────────────────────────────────

def _execute_create_sf_case(state: AgentState) -> Dict[str, Any]:
    """Execute create_sf_case action."""
    logger.info("Creating Salesforce case…")
    payload = state.get("sf_case_payload", {})
    
    if not payload:
        return {"success": False, "error": "sf_case_payload is empty"}
    
    result = create_sf_case(payload)
    if result.get("success"):
        logger.info("SF case created: id=%s", result.get("id"))
    else:
        logger.warning("SF case creation failed: %s", result.get("error"))
    
    return result


def _execute_add_comment(state: AgentState) -> Dict[str, Any]:
    """Execute add_comment_to_case action with validation."""
    logger.info("Adding comment to case…")
    payload = state.get("add_comment_payload", {})
    
    if not payload:
        return {"success": False, "error": "add_comment_payload is empty"}
    
    # Validate required entities
    is_valid, error_msg = validate_action_entities("add_comment_to_case", payload)
    if not is_valid:
        logger.warning(f"add_comment_to_case validation failed: {error_msg}")
        return {"success": False, "error": error_msg}
    
    result = add_comment_to_case(payload)
    if result.get("success"):
        logger.info("Comment added: case_id=%s, comment_id=%s", 
                   payload.get("case_id"), result.get("comment_id"))
    else:
        logger.warning("Add comment failed: %s", result.get("error"))
    
    return result


def _execute_close_case(state: AgentState) -> Dict[str, Any]:
    """Execute close_case action with validation."""
    logger.info("Closing case…")
    payload = state.get("close_case_payload", {})
    
    if not payload:
        return {"success": False, "error": "close_case_payload is empty"}
    
    # Validate required entities
    is_valid, error_msg = validate_action_entities("close_case", payload)
    if not is_valid:
        logger.warning(f"close_case validation failed: {error_msg}")
        return {"success": False, "error": error_msg}
    
    result = close_case(payload)
    if result.get("success"):
        logger.info("Case closed: case_id=%s", payload.get("case_id"))
    else:
        logger.warning("Close case failed: %s", result.get("error"))
    
    return result


def _execute_edit_case(state: AgentState) -> Dict[str, Any]:
    """Execute edit_case action with validation."""
    logger.info("Editing case…")
    payload = state.get("edit_case_payload", {})
    
    if not payload:
        return {"success": False, "error": "edit_case_payload is empty"}
    
    # Validate required entities
    is_valid, error_msg = validate_action_entities("edit_case", payload)
    if not is_valid:
        logger.warning(f"edit_case validation failed: {error_msg}")
        return {"success": False, "error": error_msg}
    
    result = edit_case(payload)
    if result.get("success"):
        logger.info("Case edited: case_id=%s, fields=%s", 
                   payload.get("case_id"), result.get("updated_fields", []))
    else:
        logger.warning("Edit case failed: %s", result.get("error"))
    
    return result


def _execute_billing_api(state: AgentState) -> Dict[str, Any]:
    """Execute call_billing_api action."""
    logger.info("Calling billing API…")
    payload = state.get("billing_payload", {})
    
    if not payload:
        return {"success": False, "error": "billing_payload is empty"}
    
    result = call_billing_api(payload)
    if result.get("success"):
        logger.info("Billing txn: %s", result.get("transaction_id"))
    else:
        logger.warning("Billing API failed: %s", result.get("error"))
    
    return result


# ── Node 4: summarize_node ────────────────────────────────────────────────────

def summarize_node(state: AgentState) -> Dict[str, Any]:
    """
    Compile a human-readable summary of everything the agent did.
    
    Handles both successful cases and cases where agent can't understand the issue.
    """
    # Check if we could understand the issue
    if not state.get("can_understand_issue", True):
        # Clear "I am not able to understand" message
        final_summary = (
            f"❌ {state.get('issue_analysis', 'I am not able to understand the issue')}\n\n"
            f"Reason: {state.get('action_reasoning', 'Insufficient information to determine the issue.')}\n\n"
            f"Please provide more details to help us better:"
        )
        return {
            "final_summary": final_summary,
            "confidence_score": state.get("confidence_score", 0),
        }
    
    # Normal successful case
    parts = [
        f"Analysis: {state.get('issue_analysis', 'N/A')}",
        f"Reasoning: {state.get('action_reasoning', 'N/A')}",
        f"Recommended: {', '.join(state.get('recommended_actions', [])) or 'none'}",
        f"Executed: {', '.join(state.get('actions_executed', [])) or 'none'}",
    ]

    sf = state.get("sf_case_result")
    if sf:
        if sf.get("success"):
            parts.append(
                f"Salesforce Case: created (id={sf.get('id')}, "
                f"case#={sf.get('case_number')})"
            )
        else:
            parts.append(f"Salesforce Case: FAILED – {sf.get('error')}")

    ac = state.get("add_comment_result")
    if ac:
        if ac.get("success"):
            parts.append(
                f"Add Comment: posted to case {ac.get('case_id')} "
                f"(comment_id={ac.get('comment_id')})"
            )
        else:
            parts.append(f"Add Comment: FAILED – {ac.get('error')}")

    cc = state.get("close_case_result")
    if cc:
        if cc.get("success"):
            parts.append(f"Close Case: case {cc.get('case_id')} marked as Closed")
        else:
            parts.append(f"Close Case: FAILED – {cc.get('error')}")

    ec = state.get("edit_case_result")
    if ec:
        if ec.get("success"):
            fields_updated = ', '.join(ec.get('updated_fields', []))
            parts.append(
                f"Edit Case: case {ec.get('case_id')} updated with fields "
                f"[{fields_updated}]"
            )
        else:
            parts.append(f"Edit Case: FAILED – {ec.get('error')}")

    br = state.get("billing_result")
    if br:
        if br.get("success"):
            task = br.get("billing_task", {})
            parts.append(
                f"Billing Action: {task.get('action_type')} processed "
                f"(txn={task.get('transaction_id')}, amount={task.get('amount')} "
                f"{task.get('currency', 'USD')}, reason={task.get('reason')})"
            )
        else:
            parts.append(f"Billing Action: FAILED – {br.get('error')}")

    return {
        "final_summary": " | ".join(parts),
        "confidence_score": state.get("confidence_score", 0),
    }
