"""
Service Adapter Pattern Implementation

Provides a unified interface for executing actions across different systems
(Salesforce, Billing, etc.) while keeping them decoupled.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from enum import Enum
import json


class ActionType(Enum):
    """Supported action types"""
    # Salesforce actions
    CREATE_CASE = "create_case"
    UPDATE_CASE = "update_case"
    ADD_COMMENT = "add_comment"
    CLOSE_CASE = "close_case"
    
    # Billing actions
    PROCESS_INVOICE = "process_invoice"
    APPLY_CREDIT = "apply_credit"
    PROCESS_REFUND = "process_refund"
    UPDATE_BILLING_ACCOUNT = "update_billing_account"


class ServiceAdapter(ABC):
    """
    Abstract base class for service adapters.
    
    Each system (Salesforce, Billing) implements this interface to provide
    a consistent way to execute actions and handle results.
    """
    
    @abstractmethod
    def validate_action(self, action_type: ActionType) -> bool:
        """
        Check if this adapter can handle the given action.
        
        Args:
            action_type: The action to validate
            
        Returns:
            True if this adapter can execute the action
        """
        pass
    
    @abstractmethod
    def execute_action(self, action_type: ActionType, action_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an action in this system.
        
        Args:
            action_type: Type of action to execute
            action_payload: Action-specific parameters
            
        Returns:
            Result dict with keys:
                - success: bool
                - result_id: str (e.g., case_id, transaction_id)
                - status: str (e.g., "created", "updated")
                - details: Dict[str, Any]
                - error: Optional[str] (if failed)
        """
        pass
    
    @abstractmethod
    def handle_error(self, error: Exception, action_type: ActionType) -> Dict[str, Any]:
        """
        Handle system-specific errors and provide recovery suggestions.
        
        Args:
            error: The exception that occurred
            action_type: The action that failed
            
        Returns:
            Recovery action dict with keys:
                - should_retry: bool
                - fallback_action: Optional[ActionType]
                - escalation_required: bool
                - error_message: str
        """
        pass
    
    @abstractmethod
    def get_system_name(self) -> str:
        """Return the name of this system"""
        pass
    
    def get_supported_actions(self) -> List[ActionType]:
        """Return list of ActionTypes this adapter supports"""
        return [
            action for action in ActionType
            if self.validate_action(action)
        ]


class SalesforceAdapter(ServiceAdapter):
    """Adapter for Salesforce case management operations"""
    
    def __init__(self, sf_client):
        """
        Args:
            sf_client: SalesforceClient instance
        """
        self.sf_client = sf_client
        self.supported_actions = {
            ActionType.CREATE_CASE,
            ActionType.UPDATE_CASE,
            ActionType.ADD_COMMENT,
            ActionType.CLOSE_CASE
        }
    
    def validate_action(self, action_type: ActionType) -> bool:
        """Check if action is supported by Salesforce adapter"""
        return action_type in self.supported_actions
    
    def execute_action(self, action_type: ActionType, action_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Salesforce action.
        
        action_payload varies by action_type:
        - create_case: {subject, description, user_id, priority, ...}
        - update_case: {case_id, subject, description, status, ...}
        - add_comment: {case_id, comment_text}
        - close_case: {case_id, resolution_notes}
        """
        try:
            if action_type == ActionType.CREATE_CASE:
                result = self.sf_client.create_case(
                    subject=action_payload.get("subject"),
                    description=action_payload.get("description"),
                    user_id=action_payload.get("user_id"),
                    backend_context=action_payload.get("backend_context"),
                    agent_result=action_payload.get("agent_result")
                )
                return {
                    "success": True,
                    "result_id": result.get("id"),
                    "status": "created",
                    "details": result,
                    "error": None
                }
            
            elif action_type == ActionType.UPDATE_CASE:
                result = self.sf_client.update_case(
                    case_id=action_payload.get("case_id"),
                    subject=action_payload.get("subject"),
                    description=action_payload.get("description"),
                    status=action_payload.get("status"),
                    priority=action_payload.get("priority"),
                    agent_result=action_payload.get("agent_result")
                )
                return {
                    "success": True,
                    "result_id": action_payload.get("case_id"),
                    "status": "updated",
                    "details": result,
                    "error": None
                }
            
            elif action_type == ActionType.ADD_COMMENT:
                # Add implementation for comments
                return {
                    "success": True,
                    "result_id": action_payload.get("case_id"),
                    "status": "comment_added",
                    "details": {"comment": action_payload.get("comment_text")},
                    "error": None
                }
            
            elif action_type == ActionType.CLOSE_CASE:
                result = self.sf_client.update_case(
                    case_id=action_payload.get("case_id"),
                    status="Closed",
                    description=action_payload.get("resolution_notes")
                )
                return {
                    "success": True,
                    "result_id": action_payload.get("case_id"),
                    "status": "closed",
                    "details": result,
                    "error": None
                }
        
        except Exception as e:
            return {
                "success": False,
                "result_id": None,
                "status": "failed",
                "details": {},
                "error": str(e)
            }
    
    def handle_error(self, error: Exception, action_type: ActionType) -> Dict[str, Any]:
        """Handle Salesforce-specific errors"""
        error_msg = str(error)
        
        # Determine if we should retry
        should_retry = "timeout" in error_msg.lower() or "connection" in error_msg.lower()
        
        # Suggest fallback action
        fallback_action = None
        escalation_required = True
        
        # For create failures, suggest updating instead if case exists
        if action_type == ActionType.CREATE_CASE and "duplicate" in error_msg.lower():
            fallback_action = ActionType.UPDATE_CASE
            escalation_required = False
        
        return {
            "should_retry": should_retry,
            "fallback_action": fallback_action,
            "escalation_required": escalation_required,
            "error_message": error_msg
        }
    
    def get_system_name(self) -> str:
        return "salesforce"


class BillingAdapter(ServiceAdapter):
    """Adapter for billing system operations"""
    
    def __init__(self, billing_client=None):
        """
        Args:
            billing_client: BillingClient instance (to be implemented)
        """
        self.billing_client = billing_client
        self.supported_actions = {
            ActionType.PROCESS_INVOICE,
            ActionType.APPLY_CREDIT,
            ActionType.PROCESS_REFUND,
            ActionType.UPDATE_BILLING_ACCOUNT
        }
    
    def validate_action(self, action_type: ActionType) -> bool:
        """Check if action is supported by Billing adapter"""
        return action_type in self.supported_actions
    
    def execute_action(self, action_type: ActionType, action_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute billing action.
        
        action_payload varies by action_type:
        - process_invoice: {invoice_id, user_id, amount, ...}
        - apply_credit: {user_id, amount, reason}
        - process_refund: {transaction_id, amount, reason}
        - update_billing_account: {user_id, account_data}
        """
        try:
            if action_type == ActionType.APPLY_CREDIT:
                # Call billing service to apply credit
                transaction_id = self._generate_transaction_id()
                return {
                    "success": True,
                    "result_id": transaction_id,
                    "status": "credit_applied",
                    "details": {
                        "user_id": action_payload.get("user_id"),
                        "amount": action_payload.get("amount"),
                        "reason": action_payload.get("reason"),
                        "transaction_id": transaction_id
                    },
                    "error": None
                }
            
            elif action_type == ActionType.PROCESS_INVOICE:
                transaction_id = self._generate_transaction_id()
                return {
                    "success": True,
                    "result_id": transaction_id,
                    "status": "invoice_processed",
                    "details": {
                        "invoice_id": action_payload.get("invoice_id"),
                        "user_id": action_payload.get("user_id"),
                        "amount": action_payload.get("amount"),
                        "transaction_id": transaction_id
                    },
                    "error": None
                }
            
            elif action_type == ActionType.PROCESS_REFUND:
                transaction_id = self._generate_transaction_id()
                return {
                    "success": True,
                    "result_id": transaction_id,
                    "status": "refund_processed",
                    "details": {
                        "original_transaction_id": action_payload.get("transaction_id"),
                        "refund_amount": action_payload.get("amount"),
                        "reason": action_payload.get("reason"),
                        "refund_transaction_id": transaction_id
                    },
                    "error": None
                }
            
            elif action_type == ActionType.UPDATE_BILLING_ACCOUNT:
                return {
                    "success": True,
                    "result_id": action_payload.get("user_id"),
                    "status": "account_updated",
                    "details": action_payload.get("account_data"),
                    "error": None
                }
        
        except Exception as e:
            return {
                "success": False,
                "result_id": None,
                "status": "failed",
                "details": {},
                "error": str(e)
            }
    
    def handle_error(self, error: Exception, action_type: ActionType) -> Dict[str, Any]:
        """Handle billing-specific errors"""
        error_msg = str(error)
        
        # Determine if we should retry
        should_retry = "timeout" in error_msg.lower() or "temporarily" in error_msg.lower()
        
        # For billing, escalation is usually needed
        escalation_required = True
        fallback_action = None
        
        return {
            "should_retry": should_retry,
            "fallback_action": fallback_action,
            "escalation_required": escalation_required,
            "error_message": error_msg
        }
    
    def get_system_name(self) -> str:
        return "billing"
    
    def _generate_transaction_id(self) -> str:
        """Generate a unique transaction ID"""
        import uuid
        return f"TXN_{uuid.uuid4().hex[:12].upper()}"


class AdapterRegistry:
    """
    Registry to manage available adapters.
    
    Provides discovery and routing of actions to appropriate adapters.
    """
    
    def __init__(self):
        self.adapters: List[ServiceAdapter] = []
    
    def register_adapter(self, adapter: ServiceAdapter) -> None:
        """Register a new adapter"""
        self.adapters.append(adapter)
    
    def get_adapter_for_action(self, action_type: ActionType) -> Optional[ServiceAdapter]:
        """
        Get the adapter that can handle this action.
        
        Args:
            action_type: The action to execute
            
        Returns:
            The adapter that supports this action, or None if not found
        """
        for adapter in self.adapters:
            if adapter.validate_action(action_type):
                return adapter
        return None
    
    def execute_action(self, action_type: ActionType, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an action through the appropriate adapter.
        
        Args:
            action_type: The action to execute
            payload: Action-specific payload
            
        Returns:
            Execution result from the adapter
        """
        adapter = self.get_adapter_for_action(action_type)
        if not adapter:
            return {
                "success": False,
                "result_id": None,
                "status": "failed",
                "details": {},
                "error": f"No adapter found for action {action_type}"
            }
        
        return adapter.execute_action(action_type, payload)
    
    def get_adapters_for_system(self, system_name: str) -> List[ServiceAdapter]:
        """Get all adapters for a specific system"""
        return [a for a in self.adapters if a.get_system_name() == system_name]
