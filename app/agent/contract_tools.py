from app.integrations.salesforce import SalesforceClient
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

sf = SalesforceClient()

def validate_contract_dates(move_in_date: str, move_out_date: str) -> dict:
    """Validate move-in and move-out dates"""
    errors = []
    
    try:
        # Parse dates (expecting YYYY-MM-DD format)
        move_in = datetime.strptime(move_in_date, "%Y-%m-%d")
        move_out = datetime.strptime(move_out_date, "%Y-%m-%d")
        
        # Check that move-out is after move-in
        if move_out <= move_in:
            errors.append("Move-out date must be after move-in date")
        
        # Check that move-in is not in the past - use date only, not datetime
        today = datetime.now().date()
        if move_in.date() < today:
            errors.append("Move-in date cannot be in the past")
            
    except ValueError as e:
        errors.append(f"Invalid date format. Please use YYYY-MM-DD format. Error: {e}")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors
    }


def validate_contract_data(tenant_name: str, property_address: str, rent_amount: float) -> dict:
    """Validate contract data fields"""
    errors = []
    
    # Validate tenant name
    if not tenant_name or len(tenant_name.strip()) == 0:
        errors.append("Tenant name is required")
    elif len(tenant_name) > 255:
        errors.append("Tenant name cannot exceed 255 characters")
    
    # Validate property address
    if not property_address or len(property_address.strip()) == 0:
        errors.append("Property address is required")
    elif len(property_address) > 500:
        errors.append("Property address cannot exceed 500 characters")
    
    # Validate rent amount
    if rent_amount is None:
        errors.append("Monthly rent amount is required")
    elif rent_amount <= 0:
        errors.append("Monthly rent amount must be greater than 0")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors
    }


def validate_and_prepare_contract(state):
    """Comprehensive validation of all contract fields"""
    all_errors = []
    
    # Validate dates
    date_validation = validate_contract_dates(state["move_in_date"], state["move_out_date"])
    all_errors.extend(date_validation["errors"])
    
    # Validate data fields
    data_validation = validate_contract_data(
        state["tenant_name"],
        state["property_address"],
        state["rent_amount"]
    )
    all_errors.extend(data_validation["errors"])
    
    return {
        "valid": len(all_errors) == 0,
        "errors": all_errors
    }


def create_salesforce_contract(state):
    """Create a contract in Salesforce"""
    result = sf.create_contract(
        account_id=state['account_id'],
        tenant_name=state['tenant_name'],
        property_address=state['property_address'],
        move_in_date=state['move_in_date'],
        move_out_date=state['move_out_date'],
        rent_amount=state['rent_amount'],
        user_id=state.get("user_id"),
        backend_context=state.get("backend_context", {})
    )
    return result


def lookup_existing_contracts(user_id: str):
    """Look up existing contracts for this user"""
    # This would query Salesforce for existing contracts
    # Implementation depends on how Salesforce is queried
    # For now, returning a basic structure
    return {
        "existing_contracts_found": False,
        "contract_count": 0,
        "contracts": []
    }


def update_existing_contract(state, contract_id):
    """Update an existing contract instead of creating new one"""
    result = sf.update_contract(
        contract_id=contract_id,
        status=state.get("status", "Draft"),
        move_out_date=state.get("move_out_date"),
        rent_amount=state.get("rent_amount")
    )
    return result
