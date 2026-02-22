# Claude Context: Autonomous Deep Research Engine

> **Purpose:** Complete project context for AI assistants in future sessions.
> Read this entire file before writing a single line of code.

**Last Updated:** February 21, 2026
**Project Status:** Pre-build — architecture finalized, no code written yet
**Current Phase:** Phase 0 complete → Phase 1 next
**Predecessor Projects:** MultiTool_Research (ReAct single-agent) + DoCopilot (RAG pipeline)
**Builder:** Samarth Pratap Singh — solo, 12-day sprint

---

## What Is This Project?

A **production-grade multi-agent research pipeline**. Given any research query, a
supervisor agent orchestrates four specialized sub-agents to autonomously plan, research,
critique, and write a comprehensive cited report.

**It does:**
- Accept research queries via REST API (FastAPI)
- Run a supervisor-orchestrated LangGraph multi-agent pipeline asynchronously
- Search the web (Tavily), find papers (ArXiv), look up facts (Wikipedia)
- Critique its own research and identify gaps
- Synthesize a structured markdown report with citations
- Store all jobs and results in SQLite (PostgreSQL-ready)
- Expose full observability via LangSmith tracing
- Run in Docker and deploy live on Render

**It does NOT do:**
- Vector database / RAG (no static document corpus — all data is live API queries)
- Authentication (out of scope — not an AI engineering signal)
- Fine-tuning (already demonstrated in DoCopilot and FLAN-T5)
- Multi-user concurrency (SQLite limitation — PostgreSQL swap is one line)

**Why this exists:**
MultiTool_Research proved single-agent ReAct. DoCopilot proved RAG with evaluation.
This project merges both into a multi-agent supervisor system — the logical next step
in agentic AI and the skill gap between where the resume is vs where AI startup hiring
is in 2026.

---

## How This Differs From MultiTool_Research

This is NOT MultiTool_Research with more tools. They are architecturally different:

| Dimension | MultiTool_Research | Deep Research Engine |
|-----------|-------------------|---------------------|
| Pattern | Single-agent ReAct | Multi-agent Supervisor |
| Agent count | 1 (one LLM loop) | 5 (supervisor + 4 specialists) |
| Interface | Streamlit UI only | FastAPI REST API + Streamlit |
| Task model | Synchronous (blocks) | Async jobs (non-blocking) |
| Persistence | Conversation history only | Jobs table + checkpoints |
| Deployment | Not deployed | Dockerized, live on Render |
| Observability | None | LangSmith traces |
| Output | Chat reply | Structured markdown report |
| Control flow | LLM tool_calls | Command(goto=agent_name) routing |
| Critique loop | None | Critic agent identifies gaps |

The core skill demonstrated is different: ReAct = tool use. Supervisor = orchestration.
Orchestration is the harder, more senior skill.

---

## Phase Plan
| Phase | What                                            | Status   |
| ----- | ------------------------------------------      | ------   |
| 0     | Architecture design + this file                 | ✅Done  |
| 1     | ResearchState + supervisor graph skeleton       | ⏳      |
| 2     | All 4 agents implemented (reuse tools)          | ⏳      |
| 3     | FastAPI layer — async jobs endpoints            | ⏳      |
| 4     | LangSmith tracing + evaluation                  | ⏳      |
| 5     | Dockerfile + docker-compose working             | ⏳      |
| 6     | Render deployment — live URL                    | ⏳      |
| 7     | README + architecture diagram + demo video      | ⏳      |




---

## Architecture

### Supervisor Pattern

```
User HTTP Request
      |
FastAPI  /research  (POST, async)
      |
Creates Job (UUID) -> SQLite jobs table -> returns {job_id} immediately
      | (background task)
Supervisor Agent <-----------------------------------------+
      |                                                    |
      | delegates via Command(goto=...) routing            |
      v                                                    |
+-------------+  +--------------+  +----------+  +------------+
|   Planner   |  |  Researcher  |  |  Critic  |  |   Writer   |
|   Agent     |  |   Agent      |  |  Agent   |  |   Agent    |
|             |  |              |  |          |  |            |
| Breaks      |  | Tavily +     |  | Reviews  |  | Synthesizes|
| query into  |  | ArXiv +      |  | gaps +   |  | final      |
| sub-Qs      |  | Wikipedia    |  | requests |  | markdown   |
|             |  | (REUSED from |  | more     |  | report     |
|             |  | MultiTool_R) |  | searches |  | w/citations|
+-------------+  +--------------+  +----------+  +------------+
                                                      |
                                            Job result -> SQLite
                                                      |
FastAPI  /jobs/{job_id}/status  (GET) -> polls until complete
FastAPI  /jobs/{job_id}/result  (GET) -> returns report
      |
LangSmith traces entire run (observability)
      |
Streamlit UI reads API -> displays report
```

### State Machine (LangGraph)

```
START
  |
[supervisor]
  |
routes to: planner -> researcher -> critic -> researcher (loop if gaps) -> writer
  |
[writer produces final report]
  |
END
```

The supervisor uses Command(goto=...) routing — not hard-coded sequential chains.
The LLM decides the flow based on agent outputs.

### Two Persistence Layers

```
Layer 1 — Job Persistence (custom SQLite table)
  jobs table: job_id | query | status | result | created_at | updated_at
  status values: "pending" -> "running" -> "complete" | "failed"

Layer 2 — LangGraph Checkpoints (same pattern as MultiTool_Research)
  LangGraph checkpoints table: thread_id | checkpoint_id | checkpoint BLOB
  Each job gets its own thread_id = job_id (reuses same UUID)
```

Both live in the same SQLite file: data/research.db
PostgreSQL swap = change one line in src/persistence/db.py

---

## Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| Agent framework | LangGraph supervisor pattern | Native multi-agent, cyclic graph, checkpointing |
| LLM | Groq — Llama 3.3 70B Versatile | Free tier, 500+ tok/s, quality sufficient |
| Web search | Tavily | Already built in MultiTool_Research |
| Paper search | ArXiv (direct library) | Already built, rate-limit fix already known |
| General knowledge | Wikipedia | Already built |
| REST API | FastAPI + uvicorn | Forces real backend skill, async-native |
| Async tasks | FastAPI BackgroundTasks | Zero extra dependencies, sufficient for single-user |
| Persistence | SQLite (jobs + LangGraph checkpoints) | Zero infra, PostgreSQL-ready |
| Observability | LangSmith (free tier) | Shows production engineering maturity |
| Containerization | Docker + docker-compose | Fixes resume gap, required for Render |
| Deployment | Render (free tier) | Live URL for recruiters |
| UI | Streamlit | Functional over beautiful — don't waste time |
| Config | python-dotenv | Standard |

---

## Project Structure

```
DeepResearch/
├── .env                          # API keys — never commit
├── .env.example                  # Template — commit this
├── .gitignore
├── Dockerfile                    # Multi-stage build
├── docker-compose.yml            # Local dev: API + UI together
├── requirements.txt
├── README.md                     # Architecture diagram + demo GIF + usage
├── ARCHITECTURE.md               # Detailed system design decisions
├── claude.md                     # This file
│
├── data/
│   └── research.db               # SQLite — auto-created on first run
│
└── src/
    ├── __init__.py
    │
    ├── api/
    │   ├── __init__.py
    │   ├── main.py               # FastAPI app, CORS, startup events
    │   ├── routes/
    │   │   ├── __init__.py
    │   │   ├── research.py       # POST /research, GET /jobs/{id}/status, GET /jobs/{id}/result
    │   │   └── health.py         # GET /health — for Render health checks
    │   └── models.py             # Pydantic request/response models
    │
    ├── agents/
    │   ├── __init__.py
    │   ├── supervisor.py         # Supervisor node + Command routing logic
    │   ├── planner.py            # Breaks query into sub-questions
    │   ├── researcher.py         # Calls Tavily/ArXiv/Wikipedia tools
    │   ├── critic.py             # Identifies gaps, requests more research
    │   └── writer.py             # Synthesizes final markdown report
    │
    ├── graph/
    │   ├── __init__.py
    │   ├── state.py              # ResearchState TypedDict with all reducers
    │   └── pipeline.py           # Builds + compiles supervisor LangGraph
    │
    ├── tools/
    │   ├── __init__.py
    │   ├── tavily_tool.py        # REUSED from MultiTool_Research
    │   ├── arxiv_tool.py         # REUSED (rate-limit fix already applied)
    │   └── wikipedia_tool.py     # REUSED from MultiTool_Research
    │
    ├── persistence/
    │   ├── __init__.py
    │   ├── db.py                 # SQLite connection, jobs table schema, CRUD ops
    │   └── checkpointer.py       # LangGraph SqliteSaver (same pattern as MultiTool_R)
    │
    └── ui/
        └── streamlit_app.py      # Calls FastAPI REST API, displays report
```

---

## API Design

### POST /research
```json
Request:
{
  "query": "What are the latest breakthroughs in protein folding AI?",
  "depth": "standard"
}
depth options: "quick" | "standard" | "deep"

Response (immediate, 200):
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "estimated_seconds": 45
}
```

### GET /jobs/{job_id}/status
```json
Response:
{
  "job_id": "550e8400-...",
  "status": "running",
  "current_agent": "researcher",
  "created_at": "2026-02-21T02:00:00Z",
  "updated_at": "2026-02-21T02:00:32Z"
}
```

### GET /jobs/{job_id}/result
```json
Response (when status = "complete"):
{
  "job_id": "550e8400-...",
  "query": "What are the latest breakthroughs in protein folding AI?",
  "report": "## Protein Folding AI: 2025-2026 Breakthroughs\n\n...(full markdown)...",
  "sources": ["https://...", "arxiv:2401.xxxxx"],
  "agent_turns": 7,
  "duration_seconds": 38.4,
  "created_at": "2026-02-21T02:00:00Z"
}
```

### GET /health
```json
{ "status": "ok", "version": "1.0.0" }
```
Render requires a health endpoint to verify the container is alive.

---

## State Design

```python
# src/graph/state.py

from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages

class ResearchState(TypedDict):
    # Input
    query: str
    depth: str                           # "quick" | "standard" | "deep"

    # Agent working memory
    messages: Annotated[list, add_messages]  # Full message history (add_messages reducer!)
    sub_questions: list[str]             # Set by Planner agent
    research_findings: list[str]         # Accumulated by Researcher agent
    gaps_identified: list[str]           # Set by Critic agent
    research_iterations: int             # Counter — prevents infinite loops

    # Output
    final_report: str                    # Set by Writer agent
    sources: list[str]                   # Accumulated throughout

    # Routing
    next_agent: str                      # Supervisor sets this each turn
```

CRITICAL: messages uses add_messages reducer (same lesson from MultiTool_Research).
All other fields use default replacement (last write wins).

---

## Supervisor Routing Logic

```python
# src/agents/supervisor.py

AGENTS = ["planner", "researcher", "critic", "writer", "FINISH"]

def supervisor_node(state: ResearchState, llm) -> Command:
    # LLM decides who goes next based on current state.
    # Returns Command(goto=agent_name) to route.

    # Routing rules (LLM follows these via system prompt):
    # - No sub_questions yet              -> route to planner
    # - sub_questions but no findings     -> route to researcher
    # - findings but critic not run       -> route to critic
    # - gaps found AND iterations < max   -> route to researcher again
    # - gaps resolved OR max iterations   -> route to writer
    # - final_report exists               -> FINISH
```

Max iterations: research_iterations >= 3 forces routing to writer.
Prevents runaway API calls on Groq free tier.

---

## Persistence: jobs Table

```python
# src/persistence/db.py

CREATE TABLE IF NOT EXISTS jobs (
    job_id      TEXT PRIMARY KEY,
    query       TEXT NOT NULL,
    depth       TEXT NOT NULL DEFAULT 'standard',
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending|running|complete|failed
    result      TEXT,           -- JSON-serialized report when complete
    error       TEXT,           -- Error message if failed
    agent_turns INTEGER DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

# CRUD functions to implement:
# create_job(job_id, query, depth) -> None
# update_job_status(job_id, status, result=None, error=None) -> None
# get_job(job_id) -> dict | None
```

PostgreSQL swap (one line change):
```python
# SQLite (current)
conn = sqlite3.connect("data/research.db", check_same_thread=False, timeout=10)

# PostgreSQL (production — future)
import psycopg2
conn = psycopg2.connect(os.getenv("DATABASE_URL"))
```

---

## LangSmith Observability

Add to .env:
```
LANGSMITH_API_KEY=your_key_here
LANGSMITH_PROJECT=deep-research-engine
LANGSMITH_TRACING_V2=true
```

LangSmith automatically traces every LLM call, every tool call, every agent turn.
No code changes needed — env vars activate it automatically via langchain callbacks.

What you get to show recruiters:
- Live trace dashboard at smith.langchain.com
- Exact tokens per run, latency per agent, tool success/failure rates
- This is what "production observability" looks like to an AI engineer

---

## Docker Setup

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p data

EXPOSE 8000
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
version: "3.9"
services:
  api:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/app/data      # Persist SQLite outside container

  ui:
    build: .
    command: streamlit run src/ui/streamlit_app.py --server.port 8501
    ports:
      - "8501:8501"
    env_file: .env
    depends_on:
      - api
```

Run locally: docker-compose up --build

---

## Environment Variables

```bash
# Required
GROQ_API_KEY=           # console.groq.com — free
TAVILY_API_KEY=         # tavily.com — free tier

# Observability (optional but strongly recommended for resume)
LANGSMITH_API_KEY=      # smith.langchain.com — free tier
LANGSMITH_PROJECT=deep-research-engine
LANGSMITH_TRACING_V2=true

# Future PostgreSQL (not needed now)
# DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

---

## Phase Plan

| Phase | What | Days | Status |
|-------|------|------|--------|
| 0 | Architecture design + claude.md | Day 0 | DONE |
| 1 | ResearchState + supervisor graph skeleton | Days 1-2 | TODO |
| 2 | All 4 agents implemented (reuse tools) | Days 3-5 | TODO |
| 3 | FastAPI layer — async jobs endpoints | Days 6-7 | TODO |
| 4 | LangSmith tracing + evaluation | Day 8 | TODO |
| 5 | Dockerfile + docker-compose working locally | Day 9 | TODO |
| 6 | Render deployment — live URL | Day 10 | TODO |
| 7 | README + architecture diagram + demo video | Days 11-12 | TODO |

---

## Reused Code From Previous Projects

| Component | Source | Action |
|-----------|--------|--------|
| tavily_tool.py | MultiTool_Research | Copy directly into src/tools/ |
| arxiv_tool.py | MultiTool_Research | Copy — rate-limit fix already applied |
| wikipedia_tool.py | MultiTool_Research | Copy directly |
| checkpointer.py | MultiTool_Research | Copy + adapt for new db path |
| LLM-as-Judge eval | DoCopilot | Adapt for report quality scoring |
| add_messages reducer | MultiTool_Research | Same pattern in ResearchState |
| configurable thread_id | MultiTool_Research | job_id serves as thread_id |

Do NOT reuse the Streamlit UI from MultiTool_Research.
The new UI calls FastAPI REST API — it does not call LangGraph directly.

---

## Gotchas To Expect (Pre-Warned)

**1. FastAPI BackgroundTasks + synchronous LangGraph**
LangGraph graph.invoke() is synchronous and blocks the event loop.
Wrap it to run in a thread pool:
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
executor = ThreadPoolExecutor()
loop = asyncio.get_event_loop()
await loop.run_in_executor(executor, graph.invoke, input_dict, config)
```

**2. SQLite concurrent writes**
Background task writes while status poll reads = database locked error.
Fix: sqlite3.connect(db_path, check_same_thread=False, timeout=10)
timeout=10 makes SQLite wait 10s before raising instead of failing instantly.

**3. Supervisor infinite loops**
If Critic always finds gaps, graph loops forever and burns Groq free tier.
Always enforce: if research_iterations >= 3, route to writer regardless.

**4. Groq rate limits on long runs**
Llama 3.3 70B free tier: ~6000 tokens/minute.
A deep research run with 7 agent turns can hit this.
Fix: default to depth="standard" (3 iterations max), add time.sleep(1) between turns.

**5. Render cold starts**
Render free tier spins down after 15 minutes of inactivity.
First request after cold start: 30-60 seconds.
Add a note in README. Do NOT try to fix — free tier limitation.

**6. LangGraph supervisor vs ReAct (know this for interviews)**
MultiTool_Research: single agent, one LLM, uses tool_calls messages to invoke tools.
This project: multiple agents, each a separate LangGraph node, supervisor uses
Command(goto=agent_name) to route between them. Fundamentally different patterns.

**7. Streamlit calling FastAPI**
The UI should NOT import LangGraph directly.
All agent calls go through HTTP: requests.post("http://localhost:8000/research", ...)
This is the correct separation of concerns.

---

## Interview Talking Points (Prepare These Out Loud)

**"Why multi-agent instead of single-agent?"**
Single ReAct agent conflates planning, researching, critiquing, and writing — each
requires different prompting and has different failure modes. Separation allows
specialized prompts, independent evaluation, and clearer debugging. The Critic agent
catching gaps is impossible in a single-agent design.

**"Why async jobs instead of just waiting?"**
Research takes 30-90 seconds. HTTP requests timeout at ~30s in most clients.
Async jobs decouple request handling from computation — this is the standard pattern
for any long-running AI task in production. Same pattern used by OpenAI Batch API.

**"Why SQLite not PostgreSQL?"**
Single-user, single-process deployment. SQLite handles this workload easily and needs
zero infrastructure. The swap to PostgreSQL is one line — I designed for it explicitly.
Show the db.py code. This shows you think about production even on a dev setup.

**"How do you handle agent failures?"**
Tools return error strings (not raised exceptions) so the LLM receives them as
observations and can retry or surface to user. Job status is set to "failed" with
error message stored in DB. LangSmith traces show exactly which agent and which
tool call failed, with full input/output.

**"What would you add with more time?"**
Redis + Celery for proper async task queue (replace BackgroundTasks).
PostgreSQL for multi-user support.
Server-Sent Events (SSE) streaming endpoint instead of polling.
PDF export of the final report.
Rate limiting middleware on the FastAPI endpoints.

---

## Reference Links

- LangGraph supervisor tutorial: https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/
- LangGraph multi-agent concepts: https://langchain-ai.github.io/langgraph/concepts/multi_agent/
- FastAPI background tasks: https://fastapi.tiangolo.com/tutorial/background-tasks/
- LangSmith tracing: https://smith.langchain.com
- Render FastAPI deployment: https://render.com/docs/deploy-fastapi
- Groq rate limits: https://console.groq.com/docs/rate-limits
- Predecessor project: https://github.com/noviciusss/MultiTool_Research
- ReAct paper: https://arxiv.org/abs/2210.03629
- Multi-agent supervisor paper: https://arxiv.org/abs/2308.11432
