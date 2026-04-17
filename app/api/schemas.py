from pydantic import BaseModel
from typing import Optional, Dict, Any, List

class CreateJobRequest(BaseModel):
    user_id: str
    issue_type: str
    message: Optional[str] = None

class CreateJobResponse(BaseModel):
    job_id: str
    status: str

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    result: Optional[Dict[str, Any]] = None

class EventsResponse(BaseModel):
    job_id: str
    events: List[Dict[str, Any]]

class UpdateCaseRequest(BaseModel):
    case_id: str
    subject: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    agent_result: Optional[Dict[str, Any]] = None

class UpdateCaseResponse(BaseModel):
    success: bool
    message: str

class AddCommentRequest(BaseModel):
    case_id: str
    comment_text: str

class AddCommentResponse(BaseModel):
    comment_id: str
    case_id: str
    message: str

class CloseCaseRequest(BaseModel):
    case_id: str
    subject: Optional[str] = None
    summary: Optional[str] = None
    resolution_notes: Optional[str] = None

class CloseCaseResponse(BaseModel):
    success: bool
    case_id: str
    message: str

class LookupCasesRequest(BaseModel):
    user_id: str
    status: str = "New"

class LookupCasesResponse(BaseModel):
    user_id: str
    case_count: int
    cases: List[Dict[str, Any]]


# Contract-related schemas
class CreateContractRequest(BaseModel):
    user_id: str
    account_id: str  # Required: Salesforce Account ID
    tenant_name: str
    property_address: str
    move_in_date: str  # Format: YYYY-MM-DD
    move_out_date: str  # Format: YYYY-MM-DD
    rent_amount: float

class CreateContractResponse(BaseModel):
    job_id: str
    status: str

class ContractStatusResponse(BaseModel):
    job_id: str
    status: str
    result: Optional[Dict[str, Any]] = None

class ContractDetailsResponse(BaseModel):
    contract_id: str
    tenant_name: str
    property_address: str
    move_in_date: str
    move_out_date: str
    rent_amount: float
    status: str
    created_date: Optional[str] = None

class UpdateContractRequest(BaseModel):
    contract_id: str
    status: Optional[str] = None
    move_out_date: Optional[str] = None
    rent_amount: Optional[float] = None

class UpdateContractResponse(BaseModel):
    success: bool
    contract_id: str
    message: str