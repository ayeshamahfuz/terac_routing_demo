from typing import List, Optional
from pydantic import BaseModel

class Query(BaseModel):
    topics: List[str]
    language: str
    budget: float
    sensitivity: bool = False
    sla_min: int = 30
    user_id: Optional[int] = None

class CompleteBody(BaseModel):
    interviewer_id: int
    user_id: Optional[int] = None

class AssignmentOut(BaseModel):
    status: str
    user_id: Optional[int] = None
    interviewer_id: Optional[int] = None
    score: Optional[float] = None
    current_queue: Optional[int] = None
    reason: Optional[str] = None
