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
    hil_decisions TEXT,
    hil_expires_at TEXT,
    hil_pending_payload TEXT,
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
    
    # Run migrations for existing database columns
    try:
        conn.execute("ALTER TABLE jobs ADD COLUMN hil_decisions TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE jobs ADD COLUMN hil_expires_at TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE jobs ADD COLUMN hil_pending_payload TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass
        
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
        if status != "awaiting_human":
            conn.execute(
                "UPDATE jobs SET status=?, result=?, error=?, agent_turns=?, hil_expires_at=NULL, hil_pending_payload=NULL, updated_at=? WHERE job_id=?",
                (
                    status, 
                    json.dumps(result) if result else None, 
                    error, 
                    agent_turns, 
                    now, 
                    job_id,),
            )
        else:
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
        conn.commit()

def log_hil_decision(job_id: str, iteration: int, decision: str, gaps: list[str]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    new_event = {
        "iteration": iteration,
        "decision": decision,
        "gaps": gaps,
        "timestamp": now
    }
    with _get_conn() as conn:
        row = conn.execute("SELECT hil_decisions FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        decisions = []
        if row and row["hil_decisions"]:
            try:
                decisions = json.loads(row["hil_decisions"])
            except Exception:
                decisions = []
        decisions.append(new_event)
        conn.execute(
            "UPDATE jobs SET hil_decisions=?, updated_at=? WHERE job_id=?",
            (json.dumps(decisions), now, job_id)
        )
        conn.commit()

def set_job_awaiting_human(job_id: str, gaps: list[str], iteration: int, expires_at: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "gaps": gaps,
        "iteration": iteration,
        "max_iterations": 3,
        "expires_at": expires_at
    }
    with _get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET status=?, hil_expires_at=?, hil_pending_payload=?, updated_at=? WHERE job_id=?",
            ("awaiting_human", expires_at, json.dumps(payload), now, job_id)
        )
        conn.commit()

def get_hil_payload(job_id: str) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute("SELECT hil_pending_payload FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    if row and row["hil_pending_payload"]:
        try:
            return json.loads(row["hil_pending_payload"])
        except Exception:
            return None
    return None

def get_jobs_by_status(status: str) -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM jobs WHERE status=?", (status,)).fetchall()
    return [dict(row) for row in rows]

def get_job(job_id:str)->dict | None:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    return dict(row) if row else None