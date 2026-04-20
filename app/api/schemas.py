from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime
from typing import Optional, Dict, Any, List
import re

class CreateJobRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=255, description="User identifier")
    issue_type: str = Field(..., min_length=1, max_length=50, description="Type of issue")
    message: Optional[str] = Field(None, max_length=5000, description="Issue description")
    
    @field_validator('user_id')
    @classmethod
    def validate_user_id(cls, v):
        """Validate user_id format - only allow alphanumeric, dash, underscore"""
        if not re.match(r"^[a-zA-Z0-9._-]+$", v):
            raise ValueError('Invalid user_id format')
        return v
    
    @field_validator('issue_type')
    @classmethod
    def validate_issue_type(cls, v):
        """Validate issue_type contains only alphanumeric and spaces"""
        if not re.match(r"^[a-zA-Z0-9\s_-]+$", v):
            raise ValueError('Invalid issue_type format')
        return v
    
    @field_validator('message')
    @classmethod
    def validate_message(cls, v):
        """Validate message is not just whitespace"""
        if v is not None and not v.strip():
            raise ValueError('Message cannot be empty')
        return v.strip() if v else None


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
    case_id: str = Field(..., min_length=15, max_length=18, description="Salesforce case ID (18 chars)")
    subject: Optional[str] = Field(None, max_length=255, description="Case subject")
    description: Optional[str] = Field(None, max_length=4000, description="Case description")
    status: Optional[str] = Field(None, max_length=50, description="Case status")
    priority: Optional[str] = Field(None, max_length=50, description="Case priority")
    agent_result: Optional[Dict[str, Any]] = None
    
    @field_validator('case_id')
    @classmethod
    def validate_case_id(cls, v):
        """Validate Salesforce ID format"""
        if not re.match(r"^[a-zA-Z0-9]{15,18}$", v):
            raise ValueError('Invalid Salesforce case ID format')
        return v
    
    @field_validator('subject')
    @classmethod
    def validate_subject(cls, v):
        """Validate subject is not just whitespace"""
        if v is not None and not v.strip():
            raise ValueError('Subject cannot be empty')
        return v.strip() if v else None
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v):
        """Validate description is not just whitespace"""
        if v is not None and not v.strip():
            raise ValueError('Description cannot be empty')
        return v.strip() if v else None
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        """Validate status is valid"""
        valid_statuses = ["New", "In Progress", "Closed", "On Hold", "Escalated"]
        if v is not None and v not in valid_statuses:
            raise ValueError(f'Invalid status. Must be one of: {", ".join(valid_statuses)}')
        return v
    
    @field_validator('priority')
    @classmethod
    def validate_priority(cls, v):
        """Validate priority is valid"""
        valid_priorities = ["Low", "Medium", "High", "Urgent"]
        if v is not None and v not in valid_priorities:
            raise ValueError(f'Invalid priority. Must be one of: {", ".join(valid_priorities)}')
        return v
    
    @model_validator(mode='after')
    def validate_at_least_one_field(self):
        """Ensure at least one field is being updated"""
        if all(getattr(self, field) is None for field in ['subject', 'description', 'status', 'priority', 'agent_result']):
            raise ValueError('At least one field must be provided for update')
        return self


class UpdateCaseResponse(BaseModel):
    success: bool
    message: str

class AddCommentRequest(BaseModel):
    case_id: str = Field(..., min_length=15, max_length=18, description="Salesforce case ID")
    comment_text: str = Field(..., min_length=1, max_length=4000, description="Comment text")
    
    @field_validator('case_id')
    @classmethod
    def validate_case_id(cls, v):
        """Validate Salesforce ID format"""
        if not re.match(r"^[a-zA-Z0-9]{15,18}$", v):
            raise ValueError('Invalid Salesforce case ID format')
        return v
    
    @field_validator('comment_text')
    @classmethod
    def validate_comment(cls, v):
        """Validate comment is not just whitespace and has content"""
        if not v.strip():
            raise ValueError('Comment cannot be empty or whitespace only')
        if len(v.strip()) < 1:
            raise ValueError('Comment must have at least 1 character')
        return v.strip()


class AddCommentResponse(BaseModel):
    comment_id: str
    case_id: str
    message: str

class CloseCaseRequest(BaseModel):
    case_id: str = Field(..., min_length=15, max_length=18, description="Salesforce case ID")
    subject: Optional[str] = Field(None, max_length=255)
    summary: Optional[str] = Field(None, max_length=4000)
    resolution_notes: Optional[str] = Field(None, max_length=4000)
    
    @field_validator('case_id')
    @classmethod
    def validate_case_id(cls, v):
        """Validate Salesforce ID format"""
        if not re.match(r"^[a-zA-Z0-9]{15,18}$", v):
            raise ValueError('Invalid Salesforce case ID format')
        return v
    
    @field_validator('subject')
    @classmethod
    def validate_subject(cls, v):
        """Validate subject is not just whitespace"""
        if v is not None and not v.strip():
            raise ValueError('Subject cannot be empty')
        return v.strip() if v else None
    
    @field_validator('summary')
    @classmethod
    def validate_summary(cls, v):
        """Validate summary is not just whitespace"""
        if v is not None and not v.strip():
            raise ValueError('Summary cannot be empty')
        return v.strip() if v else None
    
    @field_validator('resolution_notes')
    @classmethod
    def validate_resolution_notes(cls, v):
        """Validate resolution notes is not just whitespace"""
        if v is not None and not v.strip():
            raise ValueError('Resolution notes cannot be empty')
        return v.strip() if v else None


class CloseCaseResponse(BaseModel):
    success: bool
    case_id: str
    message: str

class LookupCasesRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=255, description="User identifier")
    status: str = Field("New", description="Case status")
    
    @field_validator('user_id')
    @classmethod
    def validate_user_id(cls, v):
        """Validate user_id format"""
        if not re.match(r"^[a-zA-Z0-9._-]+$", v):
            raise ValueError('Invalid user_id format')
        return v
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        """Validate status is one of the allowed values"""
        valid_statuses = ["New", "In Progress", "Closed", "On Hold", "Escalated"]
        if v not in valid_statuses:
            raise ValueError(f'Invalid status. Must be one of: {", ".join(valid_statuses)}')
        return v


class LookupCasesResponse(BaseModel):
    user_id: str
    case_count: int
    cases: List[Dict[str, Any]]


# Contract-related schemas
class CreateContractRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=255, description="User identifier")
    account_id: str = Field(..., min_length=15, max_length=18, description="Salesforce Account ID")
    tenant_name: str = Field(..., min_length=1, max_length=255, description="Tenant name")
    property_address: str = Field(..., min_length=1, max_length=255, description="Property address")
    move_in_date: str = Field(..., regex=r"^\d{4}-\d{2}-\d{2}$", description="Format: YYYY-MM-DD")
    move_out_date: str = Field(..., regex=r"^\d{4}-\d{2}-\d{2}$", description="Format: YYYY-MM-DD")
    rent_amount: float = Field(..., gt=0, le=999999.99, description="Monthly rent amount")
    
    @field_validator('user_id')
    @classmethod
    def validate_user_id(cls, v):
        """Validate user_id format"""
        if not re.match(r"^[a-zA-Z0-9._-]+$", v):
            raise ValueError('Invalid user_id format')
        return v
    
    @field_validator('account_id')
    @classmethod
    def validate_account_id(cls, v):
        """Validate Salesforce Account ID format"""
        if not re.match(r"^[a-zA-Z0-9]{15,18}$", v):
            raise ValueError('Invalid Salesforce Account ID format')
        return v
    
    @field_validator('tenant_name')
    @classmethod
    def validate_tenant_name(cls, v):
        """Validate tenant name is not just whitespace"""
        if not v.strip():
            raise ValueError('Tenant name cannot be empty')
        return v.strip()
    
    @field_validator('property_address')
    @classmethod
    def validate_property_address(cls, v):
        """Validate property address is not just whitespace"""
        if not v.strip():
            raise ValueError('Property address cannot be empty')
        return v.strip()
    
    @field_validator('move_in_date')
    @classmethod
    def validate_move_in_date(cls, v):
        """Validate move_in_date is a valid date"""
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError(f'Invalid date format: {v}. Must be YYYY-MM-DD')
    
    @field_validator('move_out_date')
    @classmethod
    def validate_move_out_date(cls, v):
        """Validate move_out_date is a valid date"""
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError(f'Invalid date format: {v}. Must be YYYY-MM-DD')
    
    @model_validator(mode='after')
    def validate_dates_logic(self):
        """Validate that move_in_date is before move_out_date"""
        move_in = datetime.strptime(self.move_in_date, '%Y-%m-%d')
        move_out = datetime.strptime(self.move_out_date, '%Y-%m-%d')
        
        if move_in >= move_out:
            raise ValueError('Move-in date must be before move-out date')
        
        return self


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
    contract_id: str = Field(..., min_length=15, max_length=18, description="Salesforce Contract ID")
    status: Optional[str] = Field(None, max_length=50)
    move_out_date: Optional[str] = Field(None, regex=r"^\d{4}-\d{2}-\d{2}$|^$")
    rent_amount: Optional[float] = Field(None, gt=0, le=999999.99)
    
    @field_validator('contract_id')
    @classmethod
    def validate_contract_id(cls, v):
        """Validate Salesforce Contract ID format"""
        if not re.match(r"^[a-zA-Z0-9]{15,18}$", v):
            raise ValueError('Invalid Salesforce Contract ID format')
        return v
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        """Validate status is one of the allowed values"""
        valid_statuses = ["Active", "Draft", "Closed", "Expired", "On Hold"]
        if v is not None and v not in valid_statuses:
            raise ValueError(f'Invalid status. Must be one of: {", ".join(valid_statuses)}')
        return v
    
    @field_validator('move_out_date')
    @classmethod
    def validate_move_out_date(cls, v):
        """Validate move_out_date is a valid date if provided"""
        if v is None or v == "":
            return v
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError(f'Invalid date format: {v}. Must be YYYY-MM-DD')
    
    @model_validator(mode='after')
    def validate_at_least_one_field(self):
        """Ensure at least one field is being updated"""
        if all(getattr(self, field) is None for field in ['status', 'move_out_date', 'rent_amount']):
            raise ValueError('At least one field must be provided for update')
        return self


class UpdateContractResponse(BaseModel):
    success: bool
    contract_id: str
    message: str