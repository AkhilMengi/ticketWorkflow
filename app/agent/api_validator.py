"""
API Validator — validates payloads before Salesforce/Billing API calls.

Safety layer that ensures required entities are present and properly formatted
before actions are executed.
"""
import re
import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)


def validate_case_id(case_id: str) -> Tuple[bool, str]:
    """
    Validate that case_id is in a valid format.
    
    Returns:
      (is_valid, error_message)
    """
    if not case_id or not isinstance(case_id, str):
        return False, "case_id is empty or not a string"
    
    # Case ID should be alphanumeric (may contain dashes)
    if not re.match(r"^[A-Za-z0-9\-]+$", case_id):
        return False, f"case_id contains invalid characters: {case_id}"
    
    if len(case_id) < 4:
        return False, f"case_id is too short: {case_id}"
    
    return True, ""


def validate_action_entities(action: str, entities: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate that required entities are present for the action.
    
    Ensures payload has all required fields before API call is made:
      • add_comment_to_case  → requires case_id + comment_body
      • close_case           → requires case_id
      • edit_case            → requires case_id + field_updates
      • create_sf_case       → no specific entity validation
      • call_billing_api     → no specific entity validation
    
    Args:
      action: Action name (string)
      entities: Payload dict with extracted entities
    
    Returns:
      (is_valid, error_message) tuple
    """
    case_id = entities.get("case_id", "").strip()
    comment_body = entities.get("comment_body", "").strip()
    field_updates = entities.get("field_updates", {})
    
    if action == "add_comment_to_case":
        if not case_id:
            return False, "case_id is required for add_comment_to_case"
        if not comment_body:
            return False, "comment_body is required for add_comment_to_case"
        return validate_case_id(case_id)
    
    elif action == "close_case":
        if not case_id:
            return False, "case_id is required for close_case"
        return validate_case_id(case_id)
    
    elif action == "edit_case":
        if not case_id:
            return False, "case_id is required for edit_case"
        if not field_updates:
            return False, "field_updates is required for edit_case"
        return validate_case_id(case_id)
    
    # Other actions (create_sf_case, call_billing_api) don't need case_id validation
    return True, ""
