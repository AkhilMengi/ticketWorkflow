from langgraph.graph import StateGraph, END
from app.agent.contract_state import ContractAgentState
from app.agent.contract_nodes import (
    validation_node,
    prepare_contract_node,
    create_contract_node,
    summarize_contract_result_node
)

builder = StateGraph(ContractAgentState)

# Add nodes
builder.add_node("validate", validation_node)
builder.add_node("prepare", prepare_contract_node)
builder.add_node("create", create_contract_node)
builder.add_node("summarize", summarize_contract_result_node)

# Add a final node that ensures state is returned
def finalize_node(state):
    """Final node to ensure state is always returned"""
    return state

builder.add_node("finalize", finalize_node)

# Set entry point
builder.set_entry_point("validate")


def route_validation(state):
    """Route based on validation result"""
    action = state.get("next_action")
    
    if action == "reject":
        # Validation failed, go to finalize
        return "finalize"
    elif action == "create":
        # Validation passed, proceed to prepare
        return "prepare"
    else:
        return "finalize"


def route_preparation(state):
    """Route based on preparation result"""
    action = state.get("next_action")
    
    if action == "create":
        return "create"
    elif action == "clarify":
        # Could retry or ask for clarification
        return "finalize"
    else:
        return "create"


def route_contract_creation(state):
    """Route based on contract creation result"""
    if state.get("contract_id"):
        # Success, summarize
        return "summarize"
    else:
        # Failed, finalize
        return "finalize"


# Add edges
builder.add_conditional_edges(
    "validate",
    route_validation,
    {
        "prepare": "prepare",
        "finalize": "finalize"
    }
)

builder.add_conditional_edges(
    "prepare",
    route_preparation,
    {
        "create": "create",
        "finalize": "finalize"
    }
)

builder.add_conditional_edges(
    "create",
    route_contract_creation,
    {
        "summarize": "summarize",
        "finalize": "finalize"
    }
)

builder.add_edge("summarize", "finalize")
builder.add_edge("finalize", END)

# Compile the graph
contract_agent_graph = builder.compile()
