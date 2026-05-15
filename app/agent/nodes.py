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
from app.services.salesforce import create_sf_case
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

def _load_suggestions() -> tuple[str, Dict[str, Any]]:
    """Load business suggestions from suggestions.txt (YAML format).
    
    Returns:
        Tuple of (formatted_string, raw_data_dict) 
        formatted_string: for display in prompt
        raw_data_dict: for metadata lookup when generating payloads
    """
    try:
        with open("suggestions.txt", "r") as fh:
            data = yaml.safe_load(fh.read())
        
        lines = []
        for suggestion_key, value in data.items():
            title = value.get("title", "")
            desc = value.get("description", "")
            lines.append(f"  • {title}: {desc}")
            
            # Add optional metadata hint if present
            optional_fields = []
            if "action_type" in value:
                optional_fields.append(f"action_type={value['action_type']}")
            if "reason" in value:
                optional_fields.append(f"reason={value['reason']}")
            if "notes" in value:
                optional_fields.append(f"notes={value['notes'][:50]}...")
            if "initiated_for" in value:
                optional_fields.append(f"initiated_for={value['initiated_for']}")
            
            if optional_fields:
                lines.append(f"    ({', '.join(optional_fields)})")
        
        result = "\n".join(lines)
        logger.info("✅ suggestions.txt loaded (%d suggestions):\n%s", len(data), result)
        return result, data
    except Exception as exc:
        logger.warning("⚠️  Could not load suggestions.txt: %s", exc)
        default_str = (
            "  • Check customer details: Verify account information and payment history.\n"
            "  • Rebill the account: Reprocess billing or apply credits/adjustments.\n"
            "  • Close the case: Mark the issue as resolved."
        )
        return default_str, {}


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
    This mock returns realistic data; replace with a real DB/API call.
    """
    account_id = state["account_id"]
    logger.info("Fetching account details for %s", account_id)

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

    suggestions_str, suggestions_data = _load_suggestions()
    prompt = ANALYZE_ISSUE_PROMPT.format(
        account_id=state["account_id"],
        account_details=json.dumps(state["account_details"], indent=2),
        issue_description=state["issue_description"],
        suggestions=suggestions_str,
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
            "billing_payloads": [],
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
        "billing_payloads": result.get("billing_payloads", []) if can_understand else [],
    }


# ── Node 3: execute_actions_node ──────────────────────────────────────────────

def execute_actions_node(state: AgentState) -> Dict[str, Any]:
    """
    Execute every action the LLM recommended.

    Supports:
      • create_sf_case   → calls Salesforce REST API
      • call_billing_api → calls billing micro-service

    Both can run in the same pass if the LLM selected both.
    """
    recommended = state.get("recommended_actions", [])
    logger.info("Executing actions: %s", recommended)

    actions_executed = []
    sf_result = None
    billing_result = None

    if "create_sf_case" in recommended:
        logger.info("Creating Salesforce case…")
        sf_result = create_sf_case(state.get("sf_case_payload", {}))
        if sf_result.get("success"):
            actions_executed.append("create_sf_case")
            logger.info("SF case created: id=%s", sf_result.get("id"))
        else:
            logger.warning("SF case creation failed: %s", sf_result.get("error"))

    if "call_billing_api" in recommended:
        logger.info("Calling billing API…")
        billing_payloads = state.get("billing_payloads", [])
        billing_results = []  # Array to store results from all payloads
        
        for i, payload in enumerate(billing_payloads, 1):
            logger.info(f"Executing billing payload {i}/{len(billing_payloads)}: {payload.get('initiated_for')}")
            result = call_billing_api(payload)
            billing_results.append(result)
            if result.get("success"):
                task = result.get("billing_task", {})
                logger.info("Billing txn %d: %s", i, task.get("transaction_id"))
            else:
                logger.warning("Billing API %d failed: %s", i, result.get("error"))
        
        # Only mark as executed if we had payloads and at least one succeeded
        if billing_payloads and any(r.get("success") for r in billing_results):
            actions_executed.append("call_billing_api")
        
        billing_result = billing_results  # Store results array

    return {
        "sf_case_result": sf_result,
        "billing_results": billing_result,
        "actions_executed": actions_executed,
        "confidence_score": state.get("confidence_score", 0),
    }


# ── Node 4: summarize_node ────────────────────────────────────────────────────

def summarize_node(state: AgentState) -> Dict[str, Any]:
    """
    Compile a human-readable summary of everything the agent did.
    
    NEW: Handles both successful cases and cases where agent can't understand the issue.
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

    billing_results = state.get("billing_results", [])
    if billing_results:
        for i, br in enumerate(billing_results, 1):
            if br.get("success"):
                task = br.get("billing_task", {})
                parts.append(
                    f"Billing Action {i}: {task.get('action_type')} processed "
                    f"(txn={task.get('transaction_id')}, amount={task.get('amount')} "
                    f"{task.get('currency', 'USD')}, reason={task.get('reason')}, "
                    f"for={task.get('initiated_for')})"
                )
            else:
                parts.append(f"Billing Action {i}: FAILED – {br.get('error')}")

    return {
        "final_summary": " | ".join(parts),
        "confidence_score": state.get("confidence_score", 0),
    }
