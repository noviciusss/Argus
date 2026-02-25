from pydantic import BaseModel
from typing import List, Optional

# _____Request model _____

class ReasearchRequest(BaseModel):
    query: str
    depth : str = "standard" # quick, standard, deep
    
# _____Response model _____
class ReasearchJobResponse(BaseModel):
    """Returned immediately from POST /research """
    job_id: str
    status: str  
    estimated_seconds :int
    

class JobStatusResponse(BaseModel):
    """Returned from GET /jobs/{job_id}/status """
    job_id: str
    status: str   #pending, running, completed, failed
    created_at: str
    updated_at: str
    
class JobResultResponse(BaseModel):
    """Returned from GET /jobs/{job_id}/result """
    job_id: str
    query: str
    status: str
    report: Optional[str] = None
    sources: Optional[List[str]] = None
    agent_turns: Optional[int] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str