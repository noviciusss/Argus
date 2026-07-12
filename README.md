# 🔬 Argus - Autonomous Deep Research Engine

> A **production-grade multi-agent research pipeline** that autonomously plans, researches, critiques, and synthesizes comprehensive cited reports from any research query — with real-time streaming logs and human-in-the-loop review.

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-multi--agent-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![SSE Streaming](https://img.shields.io/badge/SSE-real--time%20logs-purple.svg)](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What Is Argus?

Argus accepts a research query via REST API and runs a **supervisor-orchestrated multi-agent pipeline** that:

1. **Plans** — decomposes the query into focused sub-questions based on depth setting
2. **Researches** — searches the web (Tavily), retrieves papers (ArXiv), and queries background knowledge (Wikipedia)
3. **Critiques** — reviews findings for gaps and decides whether to loop back for more research
4. **Pauses for human review** — at the critique boundary, a Human-in-the-Loop gate fires if gaps are found, letting the user decide to continue or finalize
5. **Writes** — synthesizes a structured markdown report with numbered citations

The pipeline runs **asynchronously** — the API returns a `job_id` immediately and the client polls for completion. **Real-time logs stream via Server-Sent Events (SSE)** directly to the Streamlit dashboard as each agent works. Every LLM call and tool invocation is traced in LangSmith.

---

## System Architecture

```mermaid
flowchart TB
    subgraph Client["Client Layer"]
        User["User"]
        UI["Streamlit UI\nport 8501"]
    end

    subgraph API["API Layer - FastAPI port 8000"]
        direction TB
        Endpoint["POST /research\nGET /jobs/id/status\nGET /jobs/id/result\nPOST /jobs/id/decision"]
        SSERoute["GET /jobs/id/stream\nServer-Sent Events"]
        RateLimit["slowapi\n5 req / IP / hour"]
    end

    subgraph Execution["Execution Layer - Background Thread"]
        direction TB
        Runner["Pipeline Runner\nBackgroundTasks thread pool"]
        StreamPub["stream_manager\npublish log events"]
    end

    subgraph Graph["LangGraph Supervisor Graph"]
        direction TB
        Supervisor{{"Supervisor\nCommand routing"}}
        Planner["Planner\nBreaks query into sub-questions"]
        Researcher["Researcher\nTavily + ArXiv + Wikipedia"]
        Critic["Critic\nGap analysis + quality review"]
        HIL["HIL Gate\ninterrupt check"]
        Writer["Writer\nMarkdown report + citations"]
    end

    subgraph Persistence["Persistence Layer"]
        direction LR
        JobsDB[("Jobs Table\nSQLite or PostgreSQL\npending to running to complete")]
        Checkpoints[("LangGraph\nCheckpoints\nSqliteSaver or PostgresSaver")]
    end

    subgraph Observability["Observability"]
        LangSmith["LangSmith\nPer-agent traces\nToken counts and Latency"]
    end

    User -->|"POST /research"| RateLimit
    RateLimit --> Endpoint
    Endpoint -->|"202 Accepted job_id"| User
    Endpoint --> JobsDB
    Endpoint -->|"BackgroundTasks\nthread pool"| Runner

    Runner -->|"status: running"| JobsDB
    Runner --> Graph
    Runner --> StreamPub

    Supervisor --> Planner
    Planner -->|"sub_questions"| Supervisor
    Supervisor --> Researcher
    Researcher -->|"research_findings"| Supervisor
    Supervisor --> Critic
    Critic -->|"gaps_identified"| HIL

    HIL -->|"gaps found AND\niterations less than 3"| Pause["INTERRUPT\nawait_human\n30 min timeout"]
    Pause -->|"POST /decision continue"| Researcher
    Pause -->|"POST /decision finalize"| Writer
    HIL -->|"no gaps OR\niterations 3 or more"| Writer

    Writer -->|"final_report"| JobsDB
    Writer -->|"status: complete"| JobsDB

    StreamPub -->|"SSE events\ntype log message"| SSERoute
    Graph -.->|"save state\nafter each node"| Checkpoints

    UI -->|"SSE subscribe"| SSERoute
    SSERoute -->|"real-time\nagent logs"| UI
    UI -->|"GET /jobs/id/status"| Endpoint
    UI -->|"GET /jobs/id/result"| Endpoint

    LangSmith -.->|"auto-traced\nno code changes"| Graph
```

---

## Agent State Machine (LangGraph)

The graph is a **cyclic directed graph** — the supervisor re-runs after every agent, deciding the next step based on the current state.

```mermaid
stateDiagram-v2
    [*] --> supervisor : graph.invoke()

    supervisor --> planner : first turn
    planner --> supervisor : sub_questions set

    supervisor --> researcher : after planner
    researcher --> supervisor : findings accumulated

    supervisor --> critic : after researcher
    critic --> hil_gate : gaps_identified set

    hil_gate --> INTERRUPT : gaps found AND iterations < 3
    INTERRUPT --> researcher : decision = continue
    INTERRUPT --> writer : decision = finalize

    hil_gate --> writer : no gaps OR iterations >= 3
    hil_gate --> writer : auto_capped iterations >= 3

    writer --> supervisor : final_report set
    supervisor --> [*] : next_agent = END
```

### Routing Logic

| From | Condition | To |
|------|-----------|-----|
| `supervisor` | first turn | `planner` |
| `supervisor` | after planner | `researcher` |
| `supervisor` | after researcher | `critic` |
| `hil_gate` | gaps found AND `research_iterations < 3` | `INTERRUPT` then pause |
| `INTERRUPT` | human sends `continue` | `researcher` (loop) |
| `INTERRUPT` | human sends `finalize` | `writer` (skip) |
| `INTERRUPT` | 30 min timeout | `writer` (auto-finalize) |
| `hil_gate` | no gaps OR `research_iterations >= 3` | `writer` |
| `supervisor` | writer finished | `END` |

> **Hard cap**: `research_iterations >= 3` bypasses HIL entirely and routes directly to `writer`, logging `auto_capped`. This prevents infinite loops regardless of LLM decisions.

---

## Persistence Architecture

```mermaid
flowchart LR
    subgraph L1["Layer 1 - Job Tracking"]
        direction TB
        T1["jobs table"]
        T2["job_id, query, depth\nstatus, result, error\nagent_turns, created_at\nupdated_at, hil_expires_at"]
        T3["hil_decisions table\nDecision audit trail"]
        T1 --- T2
        T1 --- T3
    end

    subgraph L2["Layer 2 - LangGraph Checkpoints"]
        direction TB
        C1["Checkpointer"]
        C2["State snapshot after\nevery node execution\nthread_id = job_id"]
        C1 --- C2
    end

    subgraph DB["Database Backend"]
        SQLite["SQLite\nlocal / dev"]
        Postgres["PostgreSQL\nproduction / Docker"]
    end

    L1 --> DB
    L2 --> DB
    SQLite -.->|"Set DATABASE_URL\nto switch"| Postgres
```

Both layers share the same database. The `thread_id` for LangGraph checkpoints equals the `job_id` UUID — enabling graph resume after HIL interrupts. Setting `DATABASE_URL` in `.env` switches both layers to PostgreSQL automatically.

---

## SSE Streaming Architecture

```mermaid
sequenceDiagram
    participant UI as Streamlit UI
    participant API as FastAPI
    participant SM as stream_manager
    participant BG as Background Thread
    participant Agents as Agent Nodes

    UI->>API: POST /research
    API-->>UI: 202 with job_id
    API->>BG: BackgroundTasks.add_task()

    UI->>API: GET /jobs/id/stream (SSE)
    API->>SM: subscribe(job_id) returns asyncio.Queue

    BG->>Agents: graph.invoke()
    Agents->>SM: publish log "Planner running..."
    SM->>API: call_soon_threadsafe(queue.put_nowait)
    API-->>UI: event message data log

    Agents->>SM: publish log "Researcher searching..."
    SM->>API: call_soon_threadsafe(queue.put_nowait)
    API-->>UI: event message data log

    Note over API,UI: ping heartbeat every 1s keeps connection alive

    BG->>API: status complete
    UI->>API: GET /jobs/id/result
    API-->>UI: report, sources, agent_turns
```

---

## How This Differs From Single-Agent ReAct

| Dimension | Single-Agent ReAct | Argus |
|-----------|-------------------|-------|
| Pattern | One LLM loop with tools | Supervisor orchestrates 4 specialist agents |
| Agent count | 1 | 5 (supervisor + planner + researcher + critic + writer) |
| Interface | Streamlit only | FastAPI REST API + Streamlit |
| Task model | Synchronous, blocks | Async jobs, non-blocking |
| Persistence | Conversation history only | Jobs table + LangGraph checkpoints |
| Critique loop | None | Critic agent identifies gaps, loops back |
| Human oversight | None | HIL gate with 30 min timeout + auto-finalize |
| Real-time feedback | None | SSE streaming of agent logs |
| Output | Chat reply | Structured markdown report with citations |
| Control flow | LLM `tool_calls` | `Command(goto=agent_name)` routing |
| Observability | None | LangSmith traces every agent turn |
| Deployment | Not containerized | Dockerized, Render-ready |

---

## Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| Agent framework | LangGraph supervisor pattern | Native multi-agent, cyclic graph, checkpointing, HIL interrupts |
| LLM | Groq Llama 3.3 70B Versatile | Free tier, 500+ tok/s, strong instruction-following for routing |
| Web search | Tavily | Semantic search with scored, cited results |
| Paper search | ArXiv | Direct Python library, rate-limit fix applied |
| General knowledge | Wikipedia | Fast encyclopedic background context |
| REST API | FastAPI + uvicorn | Async-native, OpenAPI docs auto-generated |
| Async tasks | FastAPI BackgroundTasks | Zero extra deps, runs in thread-pool executor |
| Real-time logs | SSE via sse-starlette | Push agent logs to UI without polling |
| Persistence | SQLite + LangGraph SqliteSaver | Zero infra, auto-switches to PostgreSQL via `DATABASE_URL` |
| Observability | LangSmith | Per-agent token counts, latency, tool traces |
| Containerization | Docker + docker-compose | Reproducible builds, Render-ready |
| Rate limiting | slowapi | Prevents free-tier quota abuse at 5 req/IP/hour |
| UI | Streamlit | Polls API, streams SSE logs, renders markdown report |
| Config | python-dotenv | Standard 12-factor app config |

---

## Project Structure

```
Argus/
+-- .env                          # API keys -- never commit
+-- .env.example                  # Template -- commit this
+-- .gitignore
+-- Dockerfile
+-- docker-compose.yml            # Postgres + Redis + API + UI containers
+-- render.yaml                   # Render deployment config
+-- requirements.txt
+-- README.md
|
+-- data/
|   +-- research.db               # SQLite -- auto-created on first run
|
+-- src/
    +-- api/
    |   +-- main.py               # FastAPI app, CORS, lifespan, startup recovery
    |   +-- models.py             # Pydantic request/response models
    |   +-- celery_app.py         # Celery config (used in Docker/production)
    |   +-- limiter.py            # slowapi rate limiter instance
    |   +-- stream_manager.py     # Thread-safe SSE pub/sub via asyncio.Queue
    |   +-- routes/
    |       +-- research.py       # All job routes + BackgroundTasks + SSE stream
    |       +-- health.py         # GET /health -- Render health check
    |
    +-- agents/
    |   +-- supervisor.py         # LLM routing via Command(goto=...)
    |   +-- planner.py            # Decomposes query into sub-questions
    |   +-- researcher.py         # Calls Tavily + ArXiv + Wikipedia, publishes logs
    |   +-- critic.py             # Identifies research gaps, publishes logs
    |   +-- writer.py             # Synthesizes final markdown report, publishes logs
    |
    +-- graph/
    |   +-- state.py              # ResearchState TypedDict + add_messages reducer
    |   +-- pipeline.py           # Builds + compiles LangGraph StateGraph
    |
    +-- tools/
    |   +-- tavily_tool.py        # Web search (Tavily)
    |   +-- arxiv_tool.py         # Paper search (ArXiv, rate-limit fix applied)
    |   +-- wikipedia_tool.py     # Background knowledge (Wikipedia)
    |
    +-- persistence/
    |   +-- db.py                 # Dual-dialect CRUD -- SQLite or PostgreSQL
    |   +-- checkpointer.py       # Dynamic SqliteSaver / PostgresSaver
    |
    +-- tasks/
    |   +-- research_tasks.py     # Celery task wrappers (Docker / production)
    |
    +-- ui/
        +-- streamlit_app.py      # SSE log streaming, HIL review panel, result render
```

---

## API Reference

### `POST /research`
Submit a new research job. Returns immediately with a `job_id`.

```json
// Request
{
  "query": "What are the latest breakthroughs in protein folding AI?",
  "depth": "standard"
}
// depth: "quick"    (~20s, 2 sub-questions, Tavily only)
//        "standard" (~45s, 3 sub-questions, Tavily + ArXiv + Wikipedia)
//        "deep"     (~90s, 5 sub-questions, all tools, more results)

// Response - 202 Accepted
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "estimated_seconds": 45
}
```

### `GET /jobs/{job_id}/status`
Poll for job state. Returns HIL payload when paused for human review.

```json
{
  "job_id": "550e8400-...",
  "status": "awaiting_human",
  "hil_payload": {
    "gaps": ["Missing comparison with AlphaFold 3", "No benchmarks cited"],
    "iteration": 2,
    "max_iterations": 3,
    "expires_at": "2026-07-12T18:00:00+00:00"
  },
  "created_at": "2026-07-12T17:30:00Z",
  "updated_at": "2026-07-12T17:31:20Z"
}
// status values: pending | running | awaiting_human | complete | failed
```

### `POST /jobs/{job_id}/decision`
Resume a paused HIL job.

```json
{ "decision": "continue" }   // loops back to Researcher
{ "decision": "finalize" }   // skips directly to Writer
```

### `GET /jobs/{job_id}/stream`
Server-Sent Events stream of real-time agent logs.

```
event: message
data: {"type": "log", "message": "Researcher: Searching Tavily for protein folding 2026..."}

event: message
data: {"type": "log", "message": "Planner: Generated 3 sub-questions"}

event: ping
data:
```

### `GET /jobs/{job_id}/result`

```json
{
  "job_id": "550e8400-...",
  "query": "What are the latest breakthroughs in protein folding AI?",
  "status": "complete",
  "report": "## Protein Folding AI: 2025-2026 Breakthroughs\n\n...",
  "sources": ["https://...", "https://arxiv.org/abs/..."],
  "agent_turns": 4,
  "error": null,
  "created_at": "2026-07-12T17:30:00Z",
  "updated_at": "2026-07-12T17:31:38Z"
}
```

### `GET /health`
```json
{ "status": "ok", "version": "1.0.0" }
```

Interactive docs: `/docs` (Swagger UI auto-generated by FastAPI)

---

## Shared State (ResearchState)

All agents read from and write back to a single `TypedDict` that flows through the graph:

```python
class ResearchState(TypedDict):
    query: str                               # Original research query
    depth: str                               # "quick" | "standard" | "deep"
    messages: Annotated[list, add_messages]  # Full message history -- add_messages REDUCER
    sub_questions: list[str]                 # Set by Planner
    research_findings: list[str]             # Accumulated by Researcher
    gaps_identified: list[str]               # Set by Critic
    research_iterations: int                 # Incremented by Researcher -- loop guard
    final_report: str                        # Set by Writer
    sources: list[str]                       # Accumulated throughout
    next_agent: str                          # Set by Supervisor for routing
    job_id: str                              # UUID -- links graph to jobs table
    hil_decision: str                        # "none" | "continue" | "finalize"
```

`messages` uses the `add_messages` reducer — every agent appends to the history rather than overwriting it. All other fields use default last-write-wins replacement.

---

## Setup & Running Locally

### Prerequisites
- Python 3.11+
- Docker Desktop (optional — only needed for PostgreSQL or full-stack containerized run)
- API keys: [Groq](https://console.groq.com) (free), [Tavily](https://tavily.com) (free), [LangSmith](https://smith.langchain.com) (free, optional)

### 1. Clone and configure

```bash
git clone https://github.com/noviciusss/Argus.git
cd Argus
cp .env.example .env
# Edit .env and add your API keys
```

### 2. Run locally (recommended for development)

```bash
pip install -r requirements.txt

# Terminal 1 - FastAPI + Background Worker
.venv\Scripts\python.exe -m uvicorn src.api.main:app --reload --port 8000

# Terminal 2 - Streamlit Dashboard
.venv\Scripts\python.exe -m streamlit run src/ui/streamlit_app.py
```

> **No Redis or Celery needed** for local development. The pipeline runs in FastAPI's built-in thread pool.

### 3. Run with Docker (full stack)

```bash
docker-compose up --build
```

- Streamlit UI: `http://localhost:8501`
- API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

> Docker Compose starts: PostgreSQL, Redis, Celery worker, FastAPI, Streamlit — all wired together automatically.

### 4. Switch to PostgreSQL (optional)

Add to `.env`:
```bash
DATABASE_URL=postgresql://argus:secret@localhost:5432/argus_db
```

Both the jobs table and LangGraph checkpointer switch to PostgreSQL automatically. No code changes needed.

> **Always run from the project root** using `.venv\Scripts\python.exe -m` so `src.*` imports resolve correctly.

---

## Rate Limiting

The public `/research` endpoint is rate-limited using **slowapi** to prevent free-tier API quota abuse.

**Current limits:**
- `POST /research` — **5 requests per IP per hour**
- `GET /jobs/*` — unlimited (read-only, no API cost)
- `GET /health` — unlimited (required for uptime monitoring pings)

```json
// HTTP 429 Too Many Requests
{ "error": "Rate limit exceeded: 5 per 1 hour" }
```

To adjust: change `@limiter.limit("5/hour")` in `src/api/routes/research.py`.

**Additional protection — hard caps on API dashboards:**
- [Groq](https://console.groq.com) -> Usage Limits -> set monthly token cap
- [Tavily](https://tavily.com) -> Dashboard -> set monthly search cap

---

## Design Decisions & Trade-offs

<details>
<summary><strong>Why put the HIL gate in its own node instead of inside the supervisor?</strong></summary>

LangGraph re-executes a node from the top when resuming after `interrupt()`. If the interrupt lived inside `supervisor_node` — after the LLM routing call — every human resume would re-run the LLM call, costing Groq API tokens and introducing non-determinism risk (the LLM could route differently the second time). A dedicated `hil_node` with no expensive logic before the interrupt line means re-execution is free and deterministic.

</details>

<details>
<summary><strong>Why multi-agent instead of one big ReAct agent?</strong></summary>

A single ReAct agent conflates planning, researching, critiquing, and writing — each has different failure modes and requires different prompting strategies:
- Planning prompt interferes with tool-calling prompt
- No clean separation of concerns for debugging
- The critique loop is architecturally impossible — the agent cannot objectively review its own just-completed output in the same turn

Separating into specialist agents allows independent prompts, independent error handling, and a dedicated Critic that reviews findings with fresh context before writing begins.

</details>

<details>
<summary><strong>Why async jobs with SSE instead of a blocking response?</strong></summary>

Research takes 30–90 seconds. Standard HTTP requests timeout at ~30 seconds in most clients, browsers, and load balancers. The async job pattern (submit then stream logs then fetch result) decouples request handling from computation. SSE provides real-time agent progress without the complexity of WebSockets — it's unidirectional (server to client), HTTP-compatible, and automatically reconnects. The `call_soon_threadsafe` pattern bridges the background thread's synchronous execution with asyncio's event loop safely.

</details>

<details>
<summary><strong>Why FastAPI BackgroundTasks instead of Celery/Redis locally?</strong></summary>

FastAPI's `BackgroundTasks` runs synchronous functions in a thread-pool executor — zero extra infrastructure, no Redis container, no worker process. For single-user local development it works perfectly. The trade-off is in-process execution: if the server restarts mid-research, the job is lost. For production Docker deployments, the `docker-compose.yml` switches to Celery + Redis for true task persistence. The Celery task wrappers in `src/tasks/research_tasks.py` are kept for this path.

</details>

<details>
<summary><strong>Why SQLite locally but PostgreSQL-ready?</strong></summary>

SQLite handles single-process workloads with zero infrastructure overhead. `src/persistence/db.py` dynamically detects `DATABASE_URL` — if set, it switches to a `psycopg2` connection pool and translates `?` placeholders to `%s`. The `checkpointer.py` similarly switches between `SqliteSaver` and `PostgresSaver`. The schema is identical between both backends.

</details>

<details>
<summary><strong>Why Groq (Llama 3.3 70B) instead of GPT-4 or Claude?</strong></summary>

Groq's free tier provides ~500 tokens/second — fast enough that agent turns feel snappy rather than laggy. For supervisor routing (which needs precise instruction-following), Llama 3.3 70B is sufficiently capable. The LLM is abstracted behind LangChain's `ChatGroq` interface — swapping to GPT-4o is a one-line change in each agent file.

</details>

<details>
<summary><strong>Why is the checkpointer using a raw SQLite connection instead of from_conn_string()?</strong></summary>

`SqliteSaver.from_conn_string()` returns a context manager designed for `with` blocks — it closes the connection when exiting the context. Since the graph lives for the entire app lifetime (built once at module load), the connection must stay open. Passing a raw `sqlite3.connect()` connection directly to `SqliteSaver(conn)` keeps the connection open for the app's lifetime.

</details>

<details>
<summary><strong>Why does depth="quick" skip ArXiv and Wikipedia?</strong></summary>

ArXiv's rate-limit fix requires a 3-second sleep between paper fetches. For a "quick" research run, adding 6–9 seconds of sleep per iteration defeats the purpose. Quick mode uses Tavily web search only (3 results) — fast but sufficient for general queries. Standard and deep modes enable all three tools.

</details>

<details>
<summary><strong>Render free tier cold starts</strong></summary>

Render's free tier spins containers down after 15 minutes of inactivity. The first request after a cold start takes 30–60 seconds to respond — this is a Render free-tier limitation, not an application bug. The fix is upgrading to a paid Render instance ($7/month) or pinging `/health` every 14 minutes via UptimeRobot.

</details>

<details>
<summary><strong>What would you add with more time?</strong></summary>

| Improvement | Status |
|-------------|--------|
| Human-in-the-Loop gate | Done - HIL interrupt, 30 min timeout, auto-finalize |
| Rate limiting middleware | Done - slowapi, 5 req/hour/IP |
| Server-Sent Events (SSE) | Done - real-time agent logs via sse-starlette |
| PostgreSQL support | Done - dynamic dialect switching via DATABASE_URL |
| Redis + Celery | In codebase - activated via Docker Compose |
| LLM-as-Judge evaluation | Score report quality using eval pattern |
| Authentication | API key auth for the REST API |
| Report caching | Same query within 24h returns cached result, no API cost |
| PDF export | Download research reports as formatted PDFs |

</details>

---

## Observability

Every LLM call, tool call, and agent turn is automatically traced in **LangSmith** — no code instrumentation needed.

Set in `.env`:
```bash
LANGSMITH_API_KEY=your_key
LANGSMITH_PROJECT=deep-research-engine
LANGSMITH_TRACING_V2=true
```

After a research run, visit `smith.langchain.com` then `deep-research-engine` to see:
- Per-agent latency breakdown
- Token counts per LLM call
- Tool call inputs/outputs (Tavily queries, ArXiv results)
- Full state at each node transition
- Error traces with full context if any agent fails

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes | [console.groq.com](https://console.groq.com) -- free tier |
| `TAVILY_API_KEY` | Yes | [tavily.com](https://tavily.com) -- free tier |
| `LANGSMITH_API_KEY` | Recommended | [smith.langchain.com](https://smith.langchain.com) -- free tier |
| `LANGSMITH_PROJECT` | Recommended | Set to `deep-research-engine` |
| `LANGSMITH_TRACING_V2` | Recommended | Set to `true` |
| `DATABASE_URL` | Optional | PostgreSQL connection string -- falls back to SQLite if unset |
| `REDIS_URL` | Docker only | Set to `redis://redis:6379/0` in docker-compose |
| `API_BASE` | Docker only | Auto-set to `http://api:8000` in compose |

---

## Related Projects

| Project | Pattern | What it proved |
|---------|---------|----------------|
| [MultiTool_Research](https://github.com/noviciusss/MultiTool_Research) | Single-agent ReAct | Tool use, conversation memory |
| DoCopilot | RAG + LLM-as-Judge | Document QA, evaluation pipelines |
| **Argus** (this) | Multi-agent Supervisor | Orchestration, async APIs, SSE streaming, HIL, production deployment |

---

## License

MIT
