import uuid
import json
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from src.api.models import ReasearchRequest, ReasearchJobResponse, JobStatusResponse, JobResultResponse
from src.persistence.db import create_job, update_job_status, get_job
from src.graph.pipeline import build_graph
from src.api.limiter import limiter          # shared instance — must match app.state.limiter

#build graph once at module load -not per request 
router = APIRouter()
_graph = build_graph()   # built once at module load, not per request
_DEPTH_ESTIMATES = {
    "quick": 20,
    "standard": 45,
    "deep": 90
}

def _run_research(job_id:str,query:str,depth:str)->None:
    """Runs synchronously in a thread pool thread.
    Writes status updates to SQlite throghout
    """
    update_job_status(job_id,"running")
    try:
        result = _graph.invoke({
                "query": query,
                "depth": depth,
                "messages": [],
                "sub_questions": [],
                "research_findings": [],
                "gaps_identified": [],
                "research_iterations": 0,
                "final_report": "",
                "sources": [],
                "next_agent": "",
            },
                config={"configurable":{"thread_id": job_id}},
            )
        update_job_status(
            job_id,
            status="complete",
            result={
                "report": result.get("final_report", ""),
                "sources": result.get("sources", []),
            },
            agent_turns=result.get("research_iterations", 0)
        )
    except Exception as e:
        update_job_status(job_id, "failed", error=str(e))

@router.post("/research", response_model=ReasearchJobResponse, status_code=202)
@limiter.limit("5/hour")
async def create_research_job(request: Request, body: ReasearchRequest, background_tasks: BackgroundTasks):
        if body.depth not in ("quick", "standard", "deep"):
            raise HTTPException(status_code=422, detail="depth must be 'quick', 'standard', or 'deep'")
        job_id = str(uuid.uuid4())
        create_job(job_id, body.query, body.depth)

        # run graph in thread pool - never block the event loop
        background_tasks.add_task(
            _run_research,
            job_id,
            body.query,
            body.depth,
        )
        return ReasearchJobResponse(
            job_id=job_id,
            status="pending",
            estimated_seconds=_DEPTH_ESTIMATES.get(body.depth, 45),
        )
        
@router.get("/jobs/{job_id}/status",response_model=JobStatusResponse)
def get_job_status(job_id:str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404,detail=f"Job {job_id} not found")
    return JobStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        created_at=job["created_at"],
        updated_at=job["updated_at"],
    )
@router.get("/jobs/{job_id}/result",response_model=JobResultResponse)
def get_job_result(job_id:str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404,detail=f"Job {job_id} not found")
    
    result_data= {}
    if job["result"]:
        result_data = json.loads(job["result"])
    
    return JobResultResponse(
        job_id=job["job_id"],
        query=job["query"],
        status=job["status"],
        report=result_data.get("report"),
        sources=result_data.get("sources"),
        agent_turns=job["agent_turns"],
        error=job["error"],
        created_at=job["created_at"],
        updated_at=job["updated_at"],
    )