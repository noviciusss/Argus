import sqlite3
import json 
from datetime import datetime,timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "research.db"
DB_PATH.parent.mkdir(exist_ok=True) # create data/  if it doesn't exist

_CREATE_JOBS_TABLE = """
CREATE TABLE IF NOT EXISTS jobs(
    job_id TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    depth TEXT NOT NULL DEFAULT 'standard',
    status TEXT NOT NULL DEFAULT 'pending',
    result TEXT,
    error TEXT,
    agent_turns INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

def _get_conn()-> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH),check_same_thread=False,timeout=10)
    #check_same_thread =false :background task thread!= request thread
    #timeout=10 wait up to 10s for write lock instead of crashing immediately
    conn.row_factory = sqlite3.Row
    conn.execute(_CREATE_JOBS_TABLE)
    conn.commit()
    return conn

def create_job(job_id:str,query:str,depth:str)->None:
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO jobs (job_id, query, depth, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (job_id, query, depth, "pending", now, now)
        )
        conn.commit()
        
def update_job_status(
    job_id:str,
    status:str,
    result :dict |None = None,
    error:str |None = None,
    agent_turns:int =0,
)->None:
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET status=?, result=?, error=?, agent_turns=?, updated_at=? WHERE job_id=?",
            (
                status, 
                json.dumps(result) if result else None, 
                error, 
                agent_turns, 
                now, 
                job_id,),
        )
def get_job(job_id:str)->dict | None:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    return dict(row) if row else None