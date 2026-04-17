from pydantic import BaseModel, Field
from typing import Literal

class AgentDecision(BaseModel):
    thought: str = Field(..., description="Short reasoning summary")
    action: Literal["fetch_profile", "fetch_logs", "create_case", "finish"]
    rationale: str
    confidence: float

class ClassificationResult(BaseModel):
    summary: str
    category: str
    priority: Literal["Low", "Medium", "High", "Critical"]