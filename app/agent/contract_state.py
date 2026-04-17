from typing import TypedDict, Optional, Dict, Any, List

class ContractAgentState(TypedDict):
    job_id: str
    user_id: str
    account_id: str  # Salesforce Account ID (parent)
    tenant_name: str
    property_address: str
    move_in_date: str
    move_out_date: str
    rent_amount: float
    backend_context: Dict[str, Any]

    # Agent decision and processing fields
    next_action: Optional[str]
    validation_status: Optional[str]
    validation_errors: List[str]

    # Result fields
    contract_id: Optional[str]
    final_answer: Optional[Dict[str, Any]]

    # Tracking
    retries: int
    event_log: List[Dict[str, Any]]
