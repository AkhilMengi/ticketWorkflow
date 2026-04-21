"""
Routing and Aggregation Nodes for LangGraph

These nodes orchestrate the intelligent routing between Salesforce and Billing systems,
and aggregate results into a unified response.
"""

import json
import logging
import os
import time
from typing import Dict, Any, Optional
from openai import OpenAI

from app.config import settings
from app.agent.router import classify_and_route, RoutingSystem
from app.agent.adapters import ActionType, AdapterRegistry, SalesforceAdapter, BillingAdapter
from app.services.action_service import parse_actions_from_file
from app.services.intelligent_action_service import analyze_issue_and_select_action

logger = logging.getLogger(__name__)

# Initialize OpenAI client
llm_client = OpenAI(api_key=settings.OPENAI_API_KEY)


def intelligent_action_routing_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    ⭐ Intelligent Action Routing Node with Suggestions
    
    Flow:
    1. Get issue description
    2. Load suggested actions from file
    3. Pass issue + suggestions to LLM
    4. LLM decides what ACTION to take
    5. Return selected action with parameters
    
    Examples:
    - Issue: "Usage higher than expected" + Suggestions → LLM decides: "create_case"
    - Issue: "Double charged" + Suggestions → LLM decides: "apply_billing_adjustment"
    - Issue: "Complex issue" + Suggestions → LLM decides: "escalate_to_team"
    
    Input: Issue description, user info
    Output: Selected action + parameters + reasoning
    """
    
    node_start_time = time.time()
    logger.info(f"[INTELLIGENT_ROUTING] Starting intelligent routing for user {state.get('user_id')}")
    
    try:
        issue_description = state.get("message") or state.get("issue_type") or ""
        user_id = state.get("user_id") or "unknown"
        
        # Ensure strings
        if not isinstance(issue_description, str):
            issue_description = str(issue_description) if issue_description else ""
        if not isinstance(user_id, str):
            user_id = str(user_id) if user_id else "unknown"
        
        # Step 1: Load suggested actions from file
        load_start = time.time()
        try:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            file_path = os.path.join(project_root, "recommended_actions_sample.txt")
            all_suggestions = parse_actions_from_file(file_path)
        except Exception as e:
            logger.error(f"[INTELLIGENT_ROUTING] Error reading suggestions file: {e}")
            all_suggestions = []
        
        load_elapsed = time.time() - load_start
        logger.info(f"[INTELLIGENT_ROUTING] Loaded {len(all_suggestions)} suggestions in {load_elapsed:.3f}s")
        
        # Step 2: Pass issue + suggestions to LLM for action selection
        logger.info(f"[INTELLIGENT_ROUTING] Calling LLM to decide actions...")
        action_selection = analyze_issue_and_select_action(
            issue_description=issue_description,
            user_id=user_id,
            suggestions=all_suggestions
        )
        
        selected_actions = action_selection.get("selected_actions", [])
        issue_summary = action_selection.get("issue_summary", "")
        overall_confidence = action_selection.get("overall_confidence", 0.5)
        
        logger.info(f"[INTELLIGENT_ROUTING] LLM selected {len(selected_actions)} action(s) (overall confidence: {overall_confidence:.2%})")
        
        # Step 3: Map each action type to system action handlers
        action_type_map = {
            "create_case": "create_case",
            "apply_billing_adjustment": "apply_billing_adjustment",
            "escalate_to_team": "escalate_to_team",
            "send_notification": "send_notification",
            "do_nothing": "do_nothing"
        }
        
        # Step 4: Prepare recommended actions for execution (multiple actions)
        recommended_actions = []
        
        for action_item in selected_actions:
            action_type = action_item.get("action_type", "do_nothing")
            final_action = action_type_map.get(action_type, "create_case")
            confidence = action_item.get("confidence", 0.5)
            priority = action_item.get("priority", "primary")
            reasoning = action_item.get("reasoning", "")
            action_params = action_item.get("action_parameters", {})
            
            if final_action != "do_nothing":
                recommended_actions.append({
                    "action_type": final_action,
                    "confidence": confidence,
                    "reasoning": reasoning,
                    "issue_summary": issue_summary,
                    "action_parameters": action_params,
                    "priority": action_params.get("priority", "Medium"),
                    "action_priority": priority,  # primary, secondary, tertiary
                    "action": {
                        "action_type": final_action,
                        "description": reasoning,
                        "parameters": action_params
                    }
                })
                logger.info(f"[INTELLIGENT_ROUTING] Action prepared ({priority}): {final_action} (confidence: {confidence:.2%})")
        
        if not recommended_actions:
            logger.info(f"[INTELLIGENT_ROUTING] No actions needed based on LLM decision")
        
        # Log the routing event
        routing_event = {
            "type": "intelligent_action_routing_with_suggestions",
            "issue_summary": issue_summary,
            "suggestions_count": len(all_suggestions),
            "selected_actions_count": len(recommended_actions),
            "actions": [{"type": a["action_type"], "priority": a["action_priority"], "confidence": a["confidence"]} for a in recommended_actions],
            "overall_confidence": overall_confidence,
            "reasoning": " | ".join([f"{a['action_priority']}: {a['reasoning']}" for a in recommended_actions])
        }
        
        # Ensure event_log is safe
        event_log = state.get("event_log") or []
        if not isinstance(event_log, list):
            event_log = []
        
        node_elapsed = time.time() - node_start_time
        logger.info(f"[INTELLIGENT_ROUTING] Node completed in {node_elapsed:.2f}s - Selected {len(recommended_actions)} action(s)")
        
        # Determine issue severity based on multiple actions and confidence
        action_confidences = [a["confidence"] for a in recommended_actions]
        avg_confidence = sum(action_confidences) / len(action_confidences) if action_confidences else overall_confidence
        
        if len(recommended_actions) >= 2:
            issue_severity = "high"  # Multiple actions needed → high severity
        elif avg_confidence > 0.8:
            issue_severity = "high"
        else:
            issue_severity = "medium"
        
        # Build action_decisions dict for all actions
        action_decisions = {}
        for action in recommended_actions:
            action_decisions[action["action_type"]] = {
                "selected": True,
                "reasoning": action["reasoning"],
                "confidence": action["confidence"],
                "priority": action["action_priority"]
            }
        
        return {
            "issue_severity": issue_severity,
            "ai_analysis": " | ".join([a["reasoning"] for a in recommended_actions]) if recommended_actions else "No action needed",
            "recommended_actions": recommended_actions,
            "action_decisions": action_decisions,
            "routing_type": "intelligent_actions_with_suggestions",
            "event_log": event_log + [routing_event]
        }
        
    except Exception as e:
        node_elapsed = time.time() - node_start_time
        logger.error(f"[INTELLIGENT_ROUTING] Error after {node_elapsed:.2f}s: {str(e)}", exc_info=True)
        # Return safe default state if intelligent routing fails
        event_log_safe = state.get("event_log", []) or []
        if not isinstance(event_log_safe, list):
            event_log_safe = []
        
        return {
            "issue_severity": "unknown",
            "ai_analysis": f"Error during analysis: {str(e)}",
            "recommended_actions": [],
            "action_decisions": {},
            "routing_type": "intelligent_actions_with_suggestions",
            "event_log": event_log_safe + [{
                "type": "intelligent_action_routing_error",
                "error": str(e)
            }]
        }


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


def intelligent_actions_execution_node(
    state: Dict[str, Any], 
    sf_adapter: SalesforceAdapter,
    billing_adapter: BillingAdapter
) -> Dict[str, Any]:
    """
    ⭐ Intelligent Actions Execution Node
    
    Executes the AI-recommended actions determined by intelligent_action_routing_node.
    
    Handles BOTH old and new action type names:
    - OLD: salesforce_case, billing, human_in_loop
    - NEW (Semantic): create_case, apply_billing_adjustment, escalate_to_team
    
    Input: State with recommended_actions from intelligent routing
    Output: Execution results for each action
    """
    
    logger.info(f"[INTELLIGENT_EXEC] Executing recommended actions for user {state.get('user_id')}")
    
    recommended_actions = state.get("recommended_actions", [])
    execution_results = []
    final_status = "completed"
    total_successful = 0
    total_failed = 0
    
    if not recommended_actions:
        logger.info(f"[INTELLIGENT_EXEC] No actions recommended")
        return {
            "intelligent_action_results": [],
            "intelligent_status": "no_actions",
            "execution_summary": {"total": 0, "successful": 0, "failed": 0}
        }
    
    # Execute each recommended action
    for action_item in recommended_actions:
        # Handle both old and new structure
        # Old: action_item = {"action": {...}, "priority": "...", "decision_reason": "..."}
        # New: action_item = {"action_type": "create_case", "confidence": 0.9, "reasoning": "..."}
        
        # Try to get action from nested "action" field (old structure)
        action = action_item.get("action", {})
        
        # Get action_type - could be at top level (new) or nested (old)
        action_type = action_item.get("action_type")
        if not action_type:
            action_type = action.get("action_type", "unknown")
        
        # Normalize action type names: map new names to action types
        # NEW: create_case → salesforce_case
        # NEW: apply_billing_adjustment → billing
        # NEW: escalate_to_team → human_in_loop
        action_type_normalized = action_type
        if action_type == "create_case":
            action_type_normalized = "salesforce_case"
        elif action_type == "apply_billing_adjustment":
            action_type_normalized = "billing"
        elif action_type == "escalate_to_team":
            action_type_normalized = "human_in_loop"
        
        priority = action_item.get("priority") or action.get("priority", "medium")
        decision_reason = action_item.get("reasoning") or action_item.get("decision_reason") or \
                         action.get("decision_reason", "Action recommended by AI")
        confidence = action_item.get("confidence", 1.0)
        
        # Get suggested parameters from new structure
        suggested_params = action_item.get("suggested_parameters", {})
        
        # Merge with action parameters from old structure
        action_params = action.get("parameters", {})
        all_params = {**action_params, **suggested_params}
        
        # Ensure all values are strings, not None
        if not action_type_normalized:
            action_type_normalized = "unknown"
        if not priority:
            priority = "medium"
        if not decision_reason:
            decision_reason = "Action recommended by AI"
        
        result = {
            "action_type": action_type,  # Keep original name in result
            "action_type_normalized": action_type_normalized,  # Store normalized for tracking
            "priority": priority,
            "reason": decision_reason,
            "confidence": confidence,
            "status": "unknown",
            "details": {}
        }
        
        try:
            if action_type_normalized == "salesforce_case":
                # Execute SF case creation
                logger.info(f"[INTELLIGENT_EXEC] Creating Salesforce case (from {action_type})...")
                
                # Ensure priority has a safe value  
                priority_value = priority if priority else "medium"
                
                action_payload = {
                    "subject": f"[{priority_value.upper()}] {action.get('description', 'Support Case')}",
                    "description": action.get("description", "Support case created by AI"),
                    "user_id": state.get("user_id"),
                    "backend_context": {
                        **state.get("backend_context", {}),
                        "ai_severity": state.get("issue_severity"),
                        "ai_decision_reason": decision_reason,
                        "ai_confidence": confidence
                    },
                    "agent_result": {
                        "status": "Agentic",
                        "summary": action.get("description", "Support Case"),
                        "category": all_params.get("category", "Support"),
                        "priority": all_params.get("priority", priority_value.capitalize())
                    }
                }
                
                sf_result = sf_adapter.execute_action(ActionType.CREATE_CASE, action_payload)
                
                result["status"] = "success" if sf_result["success"] else "failed"
                result["details"] = {
                    "case_id": sf_result.get("result_id"),
                    "case_number": sf_result.get("details", {}).get("CaseNumber"),
                    "error": sf_result.get("error")
                }
                
            elif action_type_normalized == "billing":
                # Execute billing action
                logger.info(f"[INTELLIGENT_EXEC] Processing billing action (from {action_type})...")
                
                action_payload = {
                    "user_id": state.get("user_id"),
                    "amount": all_params.get("amount", 0),
                    "reason": all_params.get("reason", decision_reason)
                }
                
                billing_result = billing_adapter.execute_action(ActionType.APPLY_CREDIT, action_payload)
                
                result["status"] = "success" if billing_result["success"] else "failed"
                result["details"] = {
                    "transaction_id": billing_result.get("result_id", "Unknown"),
                    "amount": all_params.get("amount", 0),
                    "error": billing_result.get("error", "")
                }
                
            elif action_type_normalized == "human_in_loop":
                # Create escalation record (typically doesn't execute via adapter, logged for manual handling)
                logger.info(f"[INTELLIGENT_EXEC] Creating escalation for human review (from {action_type})...")
                
                result["status"] = "pending_human_review"
                result["details"] = {
                    "escalation_team": all_params.get("team", "Support"),
                    "escalation_priority": all_params.get("priority", "normal"),
                    "escalation_reason": decision_reason
                }
            
            else:
                result["status"] = "unknown_action"
                logger.warning(f"[INTELLIGENT_EXEC] Unknown action type: {action_type} (normalized: {action_type_normalized})")
            
            # Count results
            if result["status"] == "success":
                total_successful += 1
            elif result["status"] == "failed":
                total_failed += 1
                if final_status != "partial_failure":
                    final_status = "partial_failure"
            
            execution_results.append(result)
            
        except Exception as e:
            logger.error(f"[INTELLIGENT_EXEC] Error executing {action_type}: {str(e)}")
            result["status"] = "failed"
            result["details"]["error"] = str(e)
            total_failed += 1
            final_status = "partial_failure"
            execution_results.append(result)
    
    # Prepare summary
    execution_summary = {
        "total_actions": len(recommended_actions),
        "successful": total_successful,
        "failed": total_failed,
        "pending_review": sum(1 for r in execution_results if r["status"] == "pending_human_review")
    }
    
    logger.info(f"[INTELLIGENT_EXEC] Execution complete: {execution_summary}")
    
    return {
        "intelligent_action_results": execution_results,
        "intelligent_status": final_status,
        "execution_summary": execution_summary,
        "routing_type": "intelligent_actions",
        "event_log": state.get("event_log", []) + [{
            "type": "intelligent_actions_execution",
            "summary": execution_summary,
            "final_status": final_status
        }]
    }


def aggregation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Aggregation Node
    
    Combines results from Salesforce and/or Billing execution paths
    into a unified customer-facing response.
    
    Now also handles intelligent actions execution results.
    
    Input: State with SF and/or Billing execution results, or intelligent action results
    Output: Aggregated response and status
    """
    
    logger.info(f"[AGGREGATION] Combining results for user {state.get('user_id')}")
    
    execution_system = state.get("execution_system")
    routing_type = state.get("routing_type", "traditional")
    aggregated_response = {}
    aggregated_status = "unknown"
    
    # Ensure event_log is a list for safety
    current_event_log = state.get("event_log") or []
    if not isinstance(current_event_log, list):
        current_event_log = []
    
    # Handle intelligent actions routing
    if routing_type == "intelligent_actions":
        intelligent_results = state.get("intelligent_action_results", [])
        intelligent_status = state.get("intelligent_status", "completed")
        execution_summary = state.get("execution_summary", {})
        
        logger.info(f"[AGGREGATION] Intelligent actions executed: {execution_summary}")
        
        # Build response based on execution results
        action_descriptions = []
        for result in intelligent_results:
            action_type = result.get("action_type", "unknown")
            status = result.get("status", "unknown")
            details = result.get("details", {})
            
            if action_type == "salesforce_case" and status == "success":
                case_id = details.get('case_id', 'Unknown')
                action_descriptions.append(f"✓ Created support case (Case ID: {case_id})")
            elif action_type == "billing" and status == "success":
                amount = details.get('amount', 'Unknown')
                action_descriptions.append(f"✓ Applied billing credit (Amount: ${amount})")
            elif action_type == "human_in_loop":
                team = details.get('escalation_team', 'Support')
                action_descriptions.append(f"✓ Escalated to {team} team for review")
            elif status == "failed":
                action_descriptions.append(f"✗ Failed to execute {action_type}")
        
        if execution_summary.get("failed", 0) == 0 and execution_summary.get("total_actions", 0) > 0:
            aggregated_status = "completed"
            aggregated_response = {
                "status": "success",
                "message": "Your issue has been processed with the following actions:",
                "actions_taken": action_descriptions,
                "summary": execution_summary,
                "ai_severity": state.get("issue_severity"),
                "details": intelligent_results
            }
        elif execution_summary.get("total_actions", 0) == 0:
            aggregated_status = "no_actions"
            aggregated_response = {
                "status": "no_actions",
                "message": "No actions were recommended for your issue",
                "ai_analysis": state.get("ai_analysis"),
                "issue_severity": state.get("issue_severity")
            }
        else:
            aggregated_status = "partial_failure"
            aggregated_response = {
                "status": "partial_success",
                "message": "Your issue was partially processed. Please review:",
                "actions_taken": action_descriptions,
                "summary": execution_summary,
                "details": intelligent_results,
                "note": "Some actions failed. Please contact support if you need further assistance."
            }
    
    # Build response based on which system executed (traditional routing)
    elif execution_system == "salesforce":
        if state.get("sf_error"):
            aggregated_status = "failed"
            aggregated_response = {
                "status": "error",
                "system": "Salesforce",
                "error_message": state.get("sf_error", "Unknown error"),
                "message": "Failed to create/update support case. Please try again or contact support."
            }
        else:
            aggregated_status = state.get("sf_status", "completed")
            sf_case_id = state.get("sf_case_id", "Unknown")
            sf_action = state.get("sf_action_taken", "updated")
            aggregated_response = {
                "status": "success",
                "system": "Salesforce Support",
                "case_id": sf_case_id,
                "action": sf_action,
                "message": f"Your case has been {sf_action} successfully. "
                          f"Case ID: {sf_case_id}. "
                          f"Our support team will get back to you soon."
            }
    
    elif execution_system == "billing":
        if state.get("billing_error"):
            aggregated_status = "failed"
            aggregated_response = {
                "status": "error",
                "system": "Billing",
                "error_message": state.get("billing_error", "Unknown error"),
                "message": "Failed to process billing request. Please try again or contact billing support."
            }
        else:
            aggregated_status = state.get("billing_status", "completed")
            action = state.get("billing_action_taken", "processed")
            transaction_id = state.get("billing_transaction_id", "Unknown")
            
            aggregated_response = {
                "status": "success",
                "system": "Billing",
                "transaction_id": transaction_id,
                "action": action,
                "message": f"Your billing request has been {action.replace('_', ' ')} successfully. "
                          f"Transaction ID: {transaction_id}. "
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
        "event_log": current_event_log + [agg_event]
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
    
    # Ensure event_log is a list
    current_event_log = state.get("event_log") or []
    if not isinstance(current_event_log, list):
        current_event_log = []
    
    return {
        "aggregated_status": "escalated",
        "aggregated_response": {
            "status": "escalated",
            "message": "Your request requires manual review. A team member will contact you shortly.",
            "reference_id": state.get("job_id")
        },
        "event_log": current_event_log + [review_event]
    }
