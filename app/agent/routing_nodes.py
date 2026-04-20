"""
Routing and Aggregation Nodes for LangGraph

These nodes orchestrate the intelligent routing between Salesforce and Billing systems,
and aggregate results into a unified response.
"""

import json
import logging
from typing import Dict, Any, Optional
from openai import OpenAI

from app.config import settings
from app.agent.router import classify_and_route, RoutingSystem
from app.agent.adapters import ActionType, AdapterRegistry, SalesforceAdapter, BillingAdapter

logger = logging.getLogger(__name__)

# Initialize OpenAI client
llm_client = OpenAI(api_key=settings.OPENAI_API_KEY)


def routing_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Intelligent Routing Node
    
    Analyzes the request and classifies it to determine whether it should be
    routed to Salesforce or Billing system.
    
    Input: User message, issue type, context
    Output: Routing decision with confidence and rationale
    """
    
    logger.info(f"[ROUTING] Analyzing request for user {state.get('user_id')}")
    
    # Classify the request
    classification = classify_and_route(state, llm_client)
    
    target_system = classification["target_system"]
    confidence = classification["confidence"]
    rationale = classification["rationale"]
    metadata = classification.get("metadata", {})
    
    logger.info(f"[ROUTING] Classification: {target_system.value} (confidence: {confidence:.2f})")
    logger.info(f"[ROUTING] Rationale: {rationale}")
    
    # Flag for manual review if confidence too low
    needs_manual_review = confidence < 0.60 and target_system == RoutingSystem.UNKNOWN
    
    # Add routing event to log
    routing_event = {
        "type": "routing_decision",
        "target_system": target_system.value,
        "confidence": confidence,
        "rationale": rationale,
        "metadata": metadata,
        "needs_manual_review": needs_manual_review
    }
    
    return {
        "target_system": target_system.value,
        "routing_confidence": confidence,
        "routing_rationale": rationale,
        "routing_metadata": metadata,
        "needs_manual_review": needs_manual_review,
        "event_log": state.get("event_log", []) + [routing_event],
        "next_action": "route"  # Signal to follow the routing logic
    }


def sf_execution_node(state: Dict[str, Any], sf_adapter: SalesforceAdapter) -> Dict[str, Any]:
    """
    Salesforce Execution Node
    
    Executes Salesforce actions based on the classified request.
    Decisions can include:
    - Create new case
    - Update existing case
    - Add comment
    - Close case
    
    Input: Routing decision pointing to Salesforce
    Output: SF execution results
    """
    
    logger.info(f"[SF_EXEC] Executing Salesforce action for user {state.get('user_id')}")
    
    try:
        # Determine the action to take
        existing_case_id = state.get("case_id")
        
        if existing_case_id:
            # Update existing case
            action_type = ActionType.UPDATE_CASE
            action_payload = {
                "case_id": existing_case_id,
                "subject": f"[Updated] {state.get('summary', state.get('issue_type'))}",
                "description": state.get("message", ""),
                "status": "In Progress",
                "priority": state.get("priority", "Medium"),
                "agent_result": {
                    "status": "Agentic",
                    "summary": state.get("summary", ""),
                    "category": state.get("category", state.get("issue_type")),
                    "priority": state.get("priority", "Medium")
                }
            }
        else:
            # Create new case
            action_type = ActionType.CREATE_CASE
            action_payload = {
                "subject": f"Support: {state.get('summary', state.get('issue_type'))}",
                "description": state.get("message", ""),
                "user_id": state.get("user_id"),
                "backend_context": state.get("backend_context", {}),
                "agent_result": {
                    "status": "Agentic",
                    "summary": state.get("summary", state.get("issue_type")),
                    "category": state.get("category", state.get("issue_type")),
                    "priority": state.get("priority", "Medium")
                }
            }
        
        # Execute through adapter
        result = sf_adapter.execute_action(action_type, action_payload)
        
        logger.info(f"[SF_EXEC] Action {action_type.value} result: {result}")
        
        # Log execution event
        exec_event = {
            "type": "sf_execution",
            "action": action_type.value,
            "success": result["success"],
            "result_id": result.get("result_id"),
            "status": result.get("status"),
            "error": result.get("error")
        }
        
        if result["success"]:
            return {
                "sf_case_id": result.get("result_id"),
                "sf_status": result.get("status"),
                "sf_action_taken": action_type.value,
                "sf_error": None,
                "execution_system": "salesforce",
                "event_log": state.get("event_log", []) + [exec_event]
            }
        else:
            # Handle SF failure - may need fallback
            error_recovery = sf_adapter.handle_error(
                Exception(result.get("error")),
                action_type
            )
            
            logger.warning(f"[SF_EXEC] Execution failed: {result.get('error')}")
            
            return {
                "sf_error": result.get("error"),
                "sf_status": "failed",
                "needs_manual_review": error_recovery.get("escalation_required", True),
                "event_log": state.get("event_log", []) + [exec_event]
            }
    
    except Exception as e:
        logger.error(f"[SF_EXEC] Exception: {str(e)}")
        return {
            "sf_error": str(e),
            "sf_status": "failed",
            "needs_manual_review": True,
            "event_log": state.get("event_log", []) + [{
                "type": "sf_execution_error",
                "error": str(e)
            }]
        }


def billing_execution_node(state: Dict[str, Any], billing_adapter: BillingAdapter) -> Dict[str, Any]:
    """
    Billing Execution Node
    
    Executes billing-related actions based on the classified request.
    Decisions can include:
    - Apply credit/refund
    - Process invoice
    - Update billing account
    
    Input: Routing decision pointing to Billing
    Output: Billing execution results
    """
    
    logger.info(f"[BILLING_EXEC] Executing billing action for user {state.get('user_id')}")
    
    try:
        # Determine billing action based on message content
        message = state.get("message", "").lower()
        
        if any(word in message for word in ["refund", "charged twice", "duplicate"]):
            action_type = ActionType.APPLY_CREDIT
            action_payload = {
                "user_id": state.get("user_id"),
                "amount": state.get("backend_context", {}).get("amount", 0),
                "reason": state.get("message", "Credit adjustment")
            }
        
        elif any(word in message for word in ["invoice", "bill"]):
            action_type = ActionType.PROCESS_INVOICE
            action_payload = {
                "user_id": state.get("user_id"),
                "invoice_id": state.get("backend_context", {}).get("invoice_id"),
                "amount": state.get("backend_context", {}).get("amount", 0)
            }
        
        else:
            # Default to credit action
            action_type = ActionType.APPLY_CREDIT
            action_payload = {
                "user_id": state.get("user_id"),
                "amount": state.get("backend_context", {}).get("amount", 0),
                "reason": state.get("message", "Account adjustment")
            }
        
        # Execute through adapter
        result = billing_adapter.execute_action(action_type, action_payload)
        
        logger.info(f"[BILLING_EXEC] Action {action_type.value} result: {result}")
        
        # Log execution event
        exec_event = {
            "type": "billing_execution",
            "action": action_type.value,
            "success": result["success"],
            "result_id": result.get("result_id"),
            "status": result.get("status"),
            "error": result.get("error")
        }
        
        if result["success"]:
            return {
                "billing_transaction_id": result.get("result_id"),
                "billing_status": result.get("status"),
                "billing_action_taken": action_type.value,
                "billing_error": None,
                "execution_system": "billing",
                "event_log": state.get("event_log", []) + [exec_event]
            }
        else:
            logger.warning(f"[BILLING_EXEC] Execution failed: {result.get('error')}")
            
            return {
                "billing_error": result.get("error"),
                "billing_status": "failed",
                "needs_manual_review": True,
                "event_log": state.get("event_log", []) + [exec_event]
            }
    
    except Exception as e:
        logger.error(f"[BILLING_EXEC] Exception: {str(e)}")
        return {
            "billing_error": str(e),
            "billing_status": "failed",
            "needs_manual_review": True,
            "event_log": state.get("event_log", []) + [{
                "type": "billing_execution_error",
                "error": str(e)
            }]
        }


def aggregation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Aggregation Node
    
    Combines results from Salesforce and/or Billing execution paths
    into a unified customer-facing response.
    
    Input: State with SF and/or Billing execution results
    Output: Aggregated response and status
    """
    
    logger.info(f"[AGGREGATION] Combining results for user {state.get('user_id')}")
    
    execution_system = state.get("execution_system")
    aggregated_response = {}
    aggregated_status = "unknown"
    
    # Build response based on which system executed
    if execution_system == "salesforce":
        if state.get("sf_error"):
            aggregated_status = "failed"
            aggregated_response = {
                "status": "error",
                "system": "Salesforce",
                "error_message": state.get("sf_error"),
                "message": "Failed to create/update support case. Please try again or contact support."
            }
        else:
            aggregated_status = state.get("sf_status", "completed")
            aggregated_response = {
                "status": "success",
                "system": "Salesforce Support",
                "case_id": state.get("sf_case_id"),
                "action": state.get("sf_action_taken", "case_update"),
                "message": f"Your case has been {state.get('sf_action_taken', 'updated')} successfully. "
                          f"Case ID: {state.get('sf_case_id')}. "
                          f"Our support team will get back to you soon."
            }
    
    elif execution_system == "billing":
        if state.get("billing_error"):
            aggregated_status = "failed"
            aggregated_response = {
                "status": "error",
                "system": "Billing",
                "error_message": state.get("billing_error"),
                "message": "Failed to process billing request. Please try again or contact billing support."
            }
        else:
            aggregated_status = state.get("billing_status", "completed")
            action = state.get("billing_action_taken", "processed")
            
            aggregated_response = {
                "status": "success",
                "system": "Billing",
                "transaction_id": state.get("billing_transaction_id"),
                "action": action,
                "message": f"Your billing request has been {action.replace('_', ' ')} successfully. "
                          f"Transaction ID: {state.get('billing_transaction_id')}. "
                          f"The changes will be reflected in your next statement."
            }
    
    else:
        aggregated_status = "no_execution"
        aggregated_response = {
            "status": "undefined",
            "message": "Unable to route request. Manual review required.",
            "needs_manual_review": True
        }
    
    # Log aggregation event
    agg_event = {
        "type": "aggregation",
        "execution_system": execution_system,
        "aggregated_status": aggregated_status,
        "response_keys": list(aggregated_response.keys())
    }
    
    logger.info(f"[AGGREGATION] Final status: {aggregated_status}")
    
    return {
        "aggregated_response": aggregated_response,
        "aggregated_status": aggregated_status,
        "final_answer": aggregated_response,
        "event_log": state.get("event_log", []) + [agg_event]
    }


def manual_review_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Manual Review Node
    
    Triggered when routing confidence is too low or execution fails
    with escalation required. Prepares state for human intervention.
    
    Input: State with routing or execution failures
    Output: Escalation notification and metadata
    """
    
    logger.warning(f"[MANUAL_REVIEW] Escalating user {state.get('user_id')} for review")
    
    review_event = {
        "type": "manual_review_required",
        "reason": state.get("routing_rationale") or state.get("sf_error") or state.get("billing_error"),
        "routing_confidence": state.get("routing_confidence"),
        "issue_type": state.get("issue_type"),
        "message": state.get("message")
    }
    
    return {
        "aggregated_status": "escalated",
        "aggregated_response": {
            "status": "escalated",
            "message": "Your request requires manual review. A team member will contact you shortly.",
            "reference_id": state.get("job_id")
        },
        "event_log": state.get("event_log", []) + [review_event]
    }
