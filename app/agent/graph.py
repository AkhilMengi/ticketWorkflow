from langgraph.graph import StateGraph, END
from app.agent.state import AgentState
from app.agent.nodes import (
    decision_node,
    fetch_profile_node,
    fetch_logs_node,
    classify_node,
    create_case_node
)
from app.agent.tools import update_existing_case, lookup_existing_case

builder = StateGraph(AgentState)

builder.add_node("decide", decision_node)
builder.add_node("fetch_profile", fetch_profile_node)
builder.add_node("fetch_logs", fetch_logs_node)
builder.add_node("classify", classify_node)
builder.add_node("create_case", create_case_node)

builder.set_entry_point("decide")

def route_decision(state):
    action = state["next_action"]

    if action == "fetch_profile":
        return "fetch_profile"
    elif action == "fetch_logs":
        return "fetch_logs"
    elif action == "create_case" or action == "update_case":
        return "classify"
    elif action == "finish":
        return END
    else:
        return END

builder.add_conditional_edges(
    "decide",
    route_decision,
    {
        "fetch_profile": "fetch_profile",
        "fetch_logs": "fetch_logs",
        "classify": "classify",
        END: END
    }
)

def route_classification(state):
    """After classification, decide to create new or update existing case"""
    existing_cases = lookup_existing_case(state["user_id"], state["issue_type"])
    
    if existing_cases.get("existing_case_found") and existing_cases.get("case_count", 0) > 0:
        # Update existing case
        state["case_id"] = existing_cases["cases"][0]["id"]
        return "update_case"
    else:
        # Create new case
        return "create_case"

def route_case_action(state):
    """Route to create or update case based on state"""
    if state.get("case_id"):
        return "update_case"
    else:
        return "create_case"

builder.add_edge("fetch_profile", "decide")
builder.add_edge("fetch_logs", "decide")
builder.add_conditional_edges(
    "classify",
    route_case_action,
    {
        "create_case": "create_case",
        "update_case": "create_case"  # Reuse create_case node but with update_case logic
    }
)
builder.add_edge("create_case", END)

agent_graph = builder.compile()