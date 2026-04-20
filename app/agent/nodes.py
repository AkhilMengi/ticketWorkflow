import json
from openai import OpenAI
from app.config import settings
from app.agent.validators import AgentDecision, ClassificationResult
from app.agent.prompts import DECISION_PROMPT, CLASSIFICATION_PROMPT
from app.agent.tools import get_customer_profile, get_payment_logs, create_salesforce_case, lookup_existing_case

client = OpenAI(api_key=settings.OPENAI_API_KEY)

def decision_node(state):
    # Check for existing cases
    existing_cases = lookup_existing_case(state["user_id"], state["issue_type"])
    
    # ⚠️ PREVENT INFINITE LOOPS: If both profile and logs exist, move to create_case
    has_profile = state["customer_profile"] is not None
    has_logs = state["logs"] is not None
    has_classification = state["summary"] is not None
    retries = state.get("retries", 0)
    
    # If we have all necessary data and have retried too many times, force create_case
    if has_profile and has_logs and retries > 3:
        print(f"[LOOP PREVENTION] Forcing create_case after {retries} retries")
        return {
            "next_action": "create_case",
            "retries": retries + 1,
            "event_log": state["event_log"] + [{
                "type": "decision",
                "thought": "Loop prevention: Have all data, forcing create_case",
                "action": "create_case",
                "confidence": 0.95,
                "rationale": "Prevention of infinite fetch_logs loop - all required data available"
            }]
        }
    
    # Format prompt with actual context
    prompt_context = DECISION_PROMPT.format(
        user_id=state["user_id"],
        issue_type=state["issue_type"],
        message=state.get("message", "")[:200],
        has_profile=has_profile,
        has_logs=has_logs,
        has_classification=has_classification,
        existing_cases_count=existing_cases.get("case_count", 0)
    )
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": prompt_context},
            {"role": "user", "content": f"Customer profile: {json.dumps(state['customer_profile'])}\nLogs: {json.dumps(state['logs'])}\nContext: {json.dumps(state['backend_context'])}"}
        ],
        response_format={"type": "json_object"}
    )

    parsed = json.loads(response.choices[0].message.content)

    return {
        "next_action": parsed["action"],
        "retries": retries + 1,
        "event_log": state["event_log"] + [{
            "type": "decision",
            "thought": parsed.get("thought", ""),
            "action": parsed["action"],
            "confidence": parsed.get("confidence", 0.5),
            "rationale": parsed.get("rationale", "")
        }]
    }

def fetch_profile_node(state):
    profile = get_customer_profile(state["user_id"])

    if not isinstance(profile, dict) or "tier" not in profile:
        raise ValueError("Invalid customer profile response")

    return {
        "customer_profile": profile,
        "event_log": state["event_log"] + [{
            "type": "tool_result",
            "tool": "get_customer_profile",
            "result": profile,
            "status": "success"
        }]
    }

def fetch_logs_node(state):
    logs = get_payment_logs(state["user_id"])

    if not isinstance(logs, list):
        raise ValueError("Invalid payment logs response")

    return {
        "logs": logs,
        "event_log": state["event_log"] + [{
            "type": "tool_result",
            "tool": "get_payment_logs",
            "result": logs,
            "status": "success"
        }]
    }

def classify_node(state):
    # Format prompt with actual context
    profile_str = json.dumps(state["customer_profile"]) if state["customer_profile"] else "None"
    
    prompt_context = CLASSIFICATION_PROMPT.format(
        issue_type=state["issue_type"],
        message=state.get("message", "")[:500],
        tier=state["customer_profile"].get("tier", "Unknown") if state["customer_profile"] else "Unknown",
        profile=profile_str[:200]
    )
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": prompt_context},
            {"role": "user", "content": f"Issue category: {state['issue_type']}\nMessage: {state.get('message', '')}\nLogs: {json.dumps(state['logs'])}"}
        ],
        response_format={"type": "json_object"}
    )

    parsed = json.loads(response.choices[0].message.content)

    return {
        "summary": parsed["summary"],
        "category": parsed["category"],
        "priority": parsed["priority"],
        "event_log": state["event_log"] + [{
            "type": "classification",
            "summary": parsed["summary"],
            "category": parsed.get("category", "other"),
            "priority": parsed["priority"],
            "priority_score": parsed.get("priority_score", 5),
            "reasoning": parsed.get("reasoning", ""),
            "escalation_needed": parsed.get("escalation_needed", False),
            "tags": parsed.get("tags", [])
        }]
    }

def create_case_node(state):
    result = create_salesforce_case(state)

    if "id" not in result:
        raise ValueError("Salesforce case creation failed")

    return {
        "case_id": result["id"],
        "final_answer": {
            "summary": state.get("summary"),
            "category": state.get("category"),
            "priority": state.get("priority"),
            "case_id": result["id"]
        },
        "event_log": state["event_log"] + [{
            "type": "tool_result",
            "tool": "create_salesforce_case",
            "result": result,
            "status": "success"
        }]
    }