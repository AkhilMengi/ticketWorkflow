"""
Enhanced Agent Graph with Intelligent Routing

This is the updated LangGraph implementation that includes intelligent routing
between Salesforce and Billing systems, replacing the original single-path graph.

Usage:
1. Import this graph as the main agent graph
2. Pass EnhancedAgentState to the graph
3. The routing node will automatically classify and route requests
"""

from langgraph.graph import StateGraph, END
from app.agent.routing_state import EnhancedAgentState
from app.agent.nodes import (
    decision_node,
    fetch_profile_node,
    fetch_logs_node,
    classify_node,
    create_case_node
)
from app.agent.routing_nodes import (
    routing_node,
    sf_execution_node,
    billing_execution_node,
    aggregation_node,
    manual_review_node
)
from app.agent.adapters import SalesforceAdapter, BillingAdapter
from app.integrations.salesforce import SalesforceClient

# Initialize adapters
sf_client = SalesforceClient()
sf_adapter = SalesforceAdapter(sf_client)
billing_adapter = BillingAdapter()  # Pass actual billing client when available


def build_routing_graph():
    """
    Build the enhanced LangGraph with intelligent routing.
    
    Graph Flow:
    
    START
      │
      ├─→ enrichment_phase (fetch profile + logs)
      │
      ├─→ ROUTING_NODE (intelligent classification)
      │       │
      │       ├─→ SF_EXECUTION_NODE (if Salesforce)
      │       │       │
      │       │       └─→ AGGREGATION_NODE
      │       │
      │       ├─→ BILLING_EXECUTION_NODE (if Billing)
      │       │       │
      │       │       └─→ AGGREGATION_NODE
      │       │
      │       └─→ MANUAL_REVIEW_NODE (if Unknown/Low Confidence)
      │               │
      │               └─→ AGGREGATION_NODE
      │
      └─→ END
    """
    
    builder = StateGraph(EnhancedAgentState)
    
    # ==================== ENRICHMENT PHASE ====================
    # Original nodes - gather context before routing
    builder.add_node("decide", decision_node)
    builder.add_node("fetch_profile", fetch_profile_node)
    builder.add_node("fetch_logs", fetch_logs_node)
    builder.add_node("classify", classify_node)
    
    # ==================== ROUTING PHASE ====================
    # New routing nodes - intelligent decision making
    builder.add_node("routing", routing_node)
    
    # ==================== EXECUTION PHASE ====================
    # System-specific execution
    def sf_exec_wrapper(state):
        """Wrapper to pass adapter to SF execution node"""
        return sf_execution_node(state, sf_adapter)
    
    def billing_exec_wrapper(state):
        """Wrapper to pass adapter to Billing execution node"""
        return billing_execution_node(state, billing_adapter)
    
    builder.add_node("sf_execution", sf_exec_wrapper)
    builder.add_node("billing_execution", billing_exec_wrapper)
    builder.add_node("manual_review", manual_review_node)
    
    # ==================== AGGREGATION PHASE ====================
    builder.add_node("aggregation", aggregation_node)
    
    # ==================== EDGE CONFIGURATION ====================
    
    # Entry point
    builder.set_entry_point("decide")
    
    # Original enrichment flow
    def route_decision(state):
        action = state.get("next_action")
        if action == "fetch_profile":
            return "fetch_profile"
        elif action == "fetch_logs":
            return "fetch_logs"
        elif action == "finish":
            return "routing"  # Move to routing instead of END
        else:
            return "routing"
    
    builder.add_conditional_edges(
        "decide",
        route_decision,
        {
            "fetch_profile": "fetch_profile",
            "fetch_logs": "fetch_logs",
            "routing": "routing"
        }
    )
    
    # Profile and logs loop back to decision
    builder.add_edge("fetch_profile", "decide")
    builder.add_edge("fetch_logs", "decide")
    
    # Classification still happens for enrichment
    builder.add_edge("classify", "routing")
    
    # ==================== ROUTING EDGES ====================
    # After enrichment, route based on system classification
    def route_by_system(state):
        target_system = state.get("target_system")
        needs_review = state.get("needs_manual_review", False)
        
        if needs_review:
            return "manual_review"
        elif target_system == "salesforce":
            return "sf_execution"
        elif target_system == "billing":
            return "billing_execution"
        else:
            return "manual_review"
    
    builder.add_conditional_edges(
        "routing",
        route_by_system,
        {
            "sf_execution": "sf_execution",
            "billing_execution": "billing_execution",
            "manual_review": "manual_review"
        }
    )
    
    # ==================== EXECUTION TO AGGREGATION ====================
    # All execution paths lead to aggregation
    builder.add_edge("sf_execution", "aggregation")
    builder.add_edge("billing_execution", "aggregation")
    builder.add_edge("manual_review", "aggregation")
    
    # ==================== FINAL EDGE ====================
    builder.add_edge("aggregation", END)
    
    return builder.compile()


# Create the main routing graph
routing_graph = build_routing_graph()


# ==================== ALTERNATIVE: MINIMAL INTEGRATION ====================
# If you want to keep the existing graph and just add routing capability,
# use this function to inject routing into the existing flow:

def inject_routing_into_existing_graph():
    """
    Alternative approach: Inject routing into existing graph at decision point.
    
    Use this if you want to minimize changes to the existing graph structure.
    """
    from app.agent.graph import builder as original_builder
    
    # Add routing node
    original_builder.add_node("routing", routing_node)
    
    # Inject routing between "classify" and "create_case"
    def route_to_system(state):
        target_system = state.get("target_system")
        if target_system == "salesforce":
            return "create_case"
        elif target_system == "billing":
            return "billing_execution"
        else:
            return "create_case"  # Default fallback
    
    # Replace the edge from classify to create_case with routing-first edge
    original_builder.add_conditional_edges(
        "classify",
        route_to_system,
        {
            "create_case": "create_case",
            "billing_execution": "billing_execution"
        }
    )
    
    return original_builder.compile()


# ==================== DEBUGGING UTILITIES ====================

def print_graph_structure():
    """Print the graph structure for debugging"""
    print("=" * 60)
    print("ROUTING AGENT GRAPH STRUCTURE")
    print("=" * 60)
    
    nodes = routing_graph.nodes
    edges = routing_graph.edges
    
    print("\nNODES:")
    for node in nodes:
        print(f"  • {node}")
    
    print("\nEDGES:")
    for source, target in edges:
        print(f"  {source} → {target}")
    
    print("\n" + "=" * 60)


def trace_execution(initial_state):
    """Trace graph execution for a given state"""
    print(f"\n[TRACE] Starting execution with state:")
    print(f"  User: {initial_state.get('user_id')}")
    print(f"  Issue: {initial_state.get('issue_type')}")
    print(f"  Message: {initial_state.get('message', '')[:50]}...")
    
    result = routing_graph.invoke(initial_state)
    
    print(f"\n[TRACE] Execution completed:")
    print(f"  Target System: {result.get('target_system')}")
    print(f"  Routing Confidence: {result.get('routing_confidence')}")
    print(f"  Execution System: {result.get('execution_system')}")
    print(f"  Final Status: {result.get('aggregated_status')}")
    print(f"  Events: {len(result.get('event_log', []))} events logged")
    
    return result
