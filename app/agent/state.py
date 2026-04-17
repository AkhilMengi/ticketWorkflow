from typing import TypedDict, Optional, Dict, Any, List

class AgentState(TypedDict):
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