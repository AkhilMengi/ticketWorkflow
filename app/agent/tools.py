from app.integrations.salesforce import SalesforceClient

sf = SalesforceClient()

def get_customer_profile(user_id: str):
    return {
        "user_id": user_id,
        "tier": "Pro",
        "subscription_status": "Active"
    }

def get_payment_logs(user_id: str):
    return ["payment_timeout", "retry_failed"]

def lookup_existing_case(user_id: str, issue_type: str):
    """Look up existing open cases for this user"""
    cases = sf.lookup_cases_by_user(user_id, status="New")
    if cases:
        return {
            "existing_case_found": True,
            "case_count": len(cases),
            "cases": [
                {
                    "id": case["Id"],
                    "case_number": case["CaseNumber"],
                    "subject": case["Subject"],
                    "status": case["Status"]
                }
                for case in cases
            ]
        }
    return {
        "existing_case_found": False,
        "case_count": 0,
        "cases": []
    }

def create_salesforce_case(state):
    result = sf.create_case(
        subject=f"Support issue for {state['user_id']}",
        description=state["message"] or f"Issue type: {state['issue_type']}",
        user_id=state["user_id"],
        backend_context=state["backend_context"],
        agent_result={
            "status": "Agentic",
            "summary": state["summary"] or f"{state['issue_type']} issue",
            "category": state["category"] or state["issue_type"],
            "priority": state["priority"] or "Medium"
        }
    )
    return result

def update_existing_case(state, case_id):
    """Update an existing case instead of creating new one"""
    result = sf.update_case(
        case_id=case_id,
        subject=f"[Updated] {state.get('summary', state['issue_type'])}",
        description=state["message"] or f"Updated: {state['issue_type']}",
        status="In Progress",
        agent_result={
            "status": "Agentic",
            "summary": state["summary"] or f"{state['issue_type']} issue updated",
            "category": state["category"] or state["issue_type"],
            "priority": state["priority"] or "Medium"
        }
    )
    return result