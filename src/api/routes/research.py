import uuid
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter,BackgroundTasks,HTTPException
from src.api.models import ReasearchRequest,ReasearchJobResponse,JobStatusResponse,JobResultResponse
from src.persistence.db import create_job,update_job_status,get_job
from src.graph.pipeline import build_graph

#build graph once at module load -not per request 
router = APIRouter()
_graph= build_graph()
_executor = ThreadPoolExecutor(max_workers=3)
_DEPTH_ESTIMATES = {
    "quick": 20,
    "standard": 45,
    "deep": 90
}
