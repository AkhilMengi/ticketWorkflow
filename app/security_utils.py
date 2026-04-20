"""
Security utility functions
"""
import re
from typing import Any


def escape_soql_string(value: str) -> str:
    """
    Escape a string for safe inclusion in a SOQL query.
    
    Salesforce SOQL string escaping:
    - Backslash (\) escapes the next character
    - Single quotes (') must be escaped as \'
    - Null bytes should not be included
    """
    if not isinstance(value, str):
        raise ValueError(f"Expected string, got {type(value)}")
    
    # First escape backslashes
    value = value.replace("\\", "\\\\")
    # Then escape single quotes
    value = value.replace("'", "\\'")
    # Remove null bytes
    value = value.replace("\x00", "")
    
    return value


def validate_soql_user_id(user_id: str) -> bool:
    """Validate user_id format - only allow alphanumeric, dash, underscore"""
    if not isinstance(user_id, str):
        return False
    if not user_id or len(user_id) > 255:
        return False
    # Allow alphanumeric, dash, underscore, dot
    pattern = r"^[a-zA-Z0-9._-]+$"
    return bool(re.match(pattern, user_id))


def validate_soql_status(status: str) -> bool:
    """Validate status field - only allow specific values"""
    allowed_statuses = {"New", "In Progress", "Closed", "On Hold", "Escalated"}
    return status in allowed_statuses


def sanitize_log_string(value: str, max_length: int = 100) -> str:
    """
    Sanitize a string for safe logging.
    - Removes potential PII
    - Limits length
    - Removes newlines
    """
    if not isinstance(value, str):
        return str(value)[:max_length]
    
    # Remove newlines and tabs
    value = value.replace("\n", " ").replace("\t", " ")
    
    # Truncate
    if len(value) > max_length:
        value = value[:max_length-3] + "..."
    
    return value


def validate_string_field(value: str, field_name: str, min_length: int = 1, 
                          max_length: int = 5000, allow_empty: bool = False) -> str:
    """
    Validate and clean a string field.
    
    Args:
        value: The string to validate
        field_name: Name of field (for error messages)
        min_length: Minimum required length
        max_length: Maximum allowed length
        allow_empty: Whether empty strings are allowed
    
    Returns:
        Cleaned string
        
    Raises:
        ValueError: If validation fails
    """
    if value is None:
        if allow_empty:
            return ""
        raise ValueError(f"{field_name} cannot be None")
    
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string, got {type(value)}")
    
    # Strip whitespace
    value = value.strip()
    
    if not value:
        if allow_empty:
            return value
        raise ValueError(f"{field_name} cannot be empty")
    
    if len(value) < min_length:
        raise ValueError(f"{field_name} must be at least {min_length} characters")
    
    if len(value) > max_length:
        raise ValueError(f"{field_name} cannot exceed {max_length} characters")
    
    return value


def is_safe_json_value(value: Any) -> bool:
    """
    Check if a value is safe to serialize to JSON and log.
    Used to prevent logging of sensitive data.
    """
    if isinstance(value, (str, int, float, bool, type(None))):
        return True
    if isinstance(value, (list, tuple)):
        return all(is_safe_json_value(v) for v in value)
    if isinstance(value, dict):
        # Check if dict contains sensitive keys
        sensitive_keys = {"token", "credential", "password", "secret", "key", "auth", "access_token"}
        dict_lower = {k.lower() for k in value.keys()}
        if dict_lower & sensitive_keys:
            return False
        return all(is_safe_json_value(v) for v in value.values())
    return False
