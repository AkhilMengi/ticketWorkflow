"""
Enhanced Agent State with Intelligent Routing Capabilities

This extends the base AgentState to support routing decisions between
Salesforce and Billing systems based on request classification.
"""

from typing import TypedDict, Optional, Dict, Any, List, Literal


class RoutingMetadata(TypedDict, total=False):
    """Metadata about the routing decision"""
    keyword_matches: List[str]
    rules_triggered: List[str]
    scores: Dict[str, float]  # {"sf_score": 0.8, "billing_score": 0.2}
    llm_classification: Optional[Dict[str, Any]]


class RoutingState(TypedDict, total=False):
    """Routing-specific fields added to AgentState"""
    # Routing Decision
    target_system: Optional[Literal["salesforce", "billing", "unknown"]]
    routing_confidence: Optional[float]  # 0-1 confidence score
    routing_rationale: Optional[str]
    routing_metadata: Optional[RoutingMetadata]
    needs_manual_review: bool  # Flag if confidence too low


class EnhancedAgentState(TypedDict):
    """
    Extended Agent State combining original fields with routing capabilities.
    
    Supports three execution paths:
    1. SALESFORCE PATH: Case/ticket management
    2. BILLING PATH: Invoice/payment/refund management  
    3. UNKNOWN PATH: Manual review or escalation
    """
    
    # ==================== ORIGINAL FIELDS ====================
    job_id: str
    user_id: str
    issue_type: str
    message: str
    backend_context: Dict[str, Any]
    
    customer_profile: Optional[Dict[str, Any]]
    logs: Optional[List[str]]
    
    summary: Optional[str]
    category: Optional[str]
    priority: Optional[str]
    
    next_action: Optional[str]
    final_answer: Optional[Dict[str, Any]]
    
    case_id: Optional[str]
    retries: int
    event_log: List[Dict[str, Any]]
    
    # ==================== ROUTING FIELDS (NEW) ====================
    # Routing classification
    target_system: Optional[Literal["salesforce", "billing", "unknown"]]
    routing_confidence: Optional[float]  # 0-1 confidence score
    routing_rationale: Optional[str]
    routing_metadata: Optional[RoutingMetadata]
    needs_manual_review: bool
    
    # ==================== SYSTEM-SPECIFIC OUTPUTS ====================
    # Salesforce execution results
    sf_case_id: Optional[str]
    sf_status: Optional[str]
    sf_action_taken: Optional[str]
    sf_error: Optional[str]
    
    # Billing execution results
    billing_transaction_id: Optional[str]
    billing_status: Optional[str]
    billing_action_taken: Optional[str]
    billing_error: Optional[str]
    
    # ==================== AGGREGATION ====================
    execution_system: Optional[Literal["salesforce", "billing"]]
    aggregated_response: Optional[Dict[str, Any]]
    aggregated_status: Optional[str]


def create_enhanced_state(base_state: Dict[str, Any]) -> EnhancedAgentState:
    """
    Factory function to create an EnhancedAgentState from a base state dict.
    
    Args:
        base_state: Original agent state dictionary
        
    Returns:
        EnhancedAgentState with all routing fields initialized
    """
    enhanced_state: EnhancedAgentState = {
        # Original fields
        "job_id": base_state.get("job_id"),
        "user_id": base_state.get("user_id"),
        "issue_type": base_state.get("issue_type"),
        "message": base_state.get("message"),
        "backend_context": base_state.get("backend_context", {}),
        "customer_profile": base_state.get("customer_profile"),
        "logs": base_state.get("logs"),
        "summary": base_state.get("summary"),
        "category": base_state.get("category"),
        "priority": base_state.get("priority"),
        "next_action": base_state.get("next_action"),
        "final_answer": base_state.get("final_answer"),
        "case_id": base_state.get("case_id"),
        "retries": base_state.get("retries", 0),
        "event_log": base_state.get("event_log", []),
        
        # New routing fields - initialized to None/defaults
        "target_system": None,
        "routing_confidence": None,
        "routing_rationale": None,
        "routing_metadata": None,
        "needs_manual_review": False,
        
        # SF execution fields
        "sf_case_id": None,
        "sf_status": None,
        "sf_action_taken": None,
        "sf_error": None,
        
        # Billing execution fields
        "billing_transaction_id": None,
        "billing_status": None,
        "billing_action_taken": None,
        "billing_error": None,
        
        # Aggregation
        "execution_system": None,
        "aggregated_response": None,
        "aggregated_status": None,
    }
    
    return enhanced_state
