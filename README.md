# 🔬 Argus — Autonomous Deep Research Engine

> A **production-grade multi-agent research pipeline** that autonomously plans, researches, critiques, and synthesizes comprehensive cited reports from any research query.

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-multi--agent-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What Is Argus?

Argus accepts a research query via REST API and runs a **supervisor-orchestrated multi-agent pipeline** that:

1. **Plans** — breaks the query into focused sub-questions
2. **Researches** — searches the web (Tavily), finds papers (ArXiv), and looks up background (Wikipedia)
3. **Critiques** — reviews its own findings for gaps and loops back if needed
4. **Writes** — synthesizes a structured markdown report with numbered citations

The entire pipeline runs **asynchronously** — the API returns a `job_id` immediately and the client polls for completion. Research jobs are persisted in SQLite. Every LLM call and agent turn is traced in LangSmith.

---

## Architecture

```
User HTTP Request
      │
POST /research  (FastAPI — async, returns job_id immediately)
      │
Creates Job (UUID) ──► SQLite jobs table
      │ (background thread)
      ▼
┌─────────────────────── Supervisor Agent ───────────────────────┐
│  Reads state, decides next agent via Command(goto=...) routing  │
└────────┬───────────────────────────────────────────────────────┘
         │
         ▼ delegates to
┌──────────┐  ┌────────────┐  ┌──────────┐  ┌──────────────┐
│ Planner  │  │ Researcher │  │  Critic  │  │    Writer    │
│          │  │            │  │          │  │              │
│ Breaks   │  │ Tavily +   │  │ Reviews  │  │ Synthesizes  │
│ query    │  │ ArXiv +    │  │ gaps +   │  │ final        │
│ into     │  │ Wikipedia  │  │ requests │  │ markdown     │
│ sub-Qs   │  │            │  │ more     │  │ report with  │
│          │  │            │  │ research │  │ citations    │
└──────────┘  └────────────┘  └──────────┘  └──────────────┘
                                                     │
                                          Job result ──► SQLite
                                                     │
GET /jobs/{id}/status  ──► polls until complete
GET /jobs/{id}/result  ──► returns full markdown report
      │
LangSmith traces entire run (observability)
      │
Streamlit UI reads API ──► displays report
```

### State Machine (LangGraph)

```
START
  │
[supervisor] ──► planner ──► [supervisor]
                                  │
                             researcher ──► [supervisor]
                                  │
                               critic ──► [hil_gate] (HIL interrupt check)
                                            │
                              (gaps found AND iterations < 3?)
                                 Yes ──► [interrupt] ⚡ HIL pause
                                           ├── Continue ──► researcher (loop)
                                           └── Finalize ──► writer
                                 No  ──► writer ──► [supervisor] ──► END
```

The supervisor uses `Command(goto=...)` routing — the **LLM decides the flow** based on agent outputs, not hardcoded chains. `research_iterations >= 3` is enforced in code as a hard safety cap regardless of LLM decisions, logging `auto_capped` and bypassing HIL routing directly to the writer.

### Two Persistence Layers

```
Layer 1 — Job Persistence (custom SQLite table)
  jobs table: job_id | query | depth | status | result | error | agent_turns | created_at | updated_at
  status flow: "pending" ──► "running" ──► "complete" | "failed"

Layer 2 — LangGraph Checkpoints (SqliteSaver)
  Saves graph state after every node execution
  thread_id = job_id (same UUID reused across both layers)
```

Both layers live in `data/research.db`. Swapping to PostgreSQL is a one-line change in `src/persistence/db.py`.

---

## Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| Agent framework | LangGraph supervisor pattern | Native multi-agent, cyclic graph, checkpointing |
| LLM | Groq — Llama 3.3 70B Versatile | Free tier, 500+ tok/s, deterministic routing |
| Web search | Tavily | Semantic search with scored, cited results |
| Paper search | ArXiv | Direct library, rate-limit fix applied |
| General knowledge | Wikipedia | Fast encyclopedic background |
| REST API | FastAPI + uvicorn | Async-native, OpenAPI docs auto-generated |
| Async tasks | FastAPI BackgroundTasks | Zero extra deps, sufficient for single-user |
| Persistence | SQLite + LangGraph SqliteSaver | Zero infra, PostgreSQL-ready |
| Observability | LangSmith | Per-agent token counts, latency, tool traces |
| Containerization | Docker + docker-compose | Reproducible builds, Render-ready |
| Deployment | Render (free tier) | Live public URL |
| Rate limiting | slowapi | Prevents free-tier quota abuse from public endpoint |
| UI | Streamlit | Polls API, renders markdown report |
| Config | python-dotenv | Standard 12-factor app config |

---

## How This Differs From Single-Agent ReAct

This is architecturally different from a standard ReAct agent:

| Dimension | Single-Agent ReAct | Argus (Multi-Agent Supervisor) |
|-----------|-------------------|-------------------------------|
| Pattern | One LLM loop with tools | Supervisor orchestrates 4 specialist agents |
| Agent count | 1 | 5 (supervisor + planner + researcher + critic + writer) |
| Interface | Streamlit only | FastAPI REST API + Streamlit |
| Task model | Synchronous, blocks | Async jobs, non-blocking |
| Persistence | Conversation history only | Jobs table + LangGraph checkpoints |
| Critique loop | None | Critic agent identifies gaps, loops back |
| Output | Chat reply | Structured markdown report with citations |
| Control flow | LLM `tool_calls` | `Command(goto=agent_name)` routing |
| Observability | None | LangSmith traces every agent turn |
| Deployment | Not containerized | Dockerized, live on Render |

**Core skill demonstrated:** ReAct = tool use. Supervisor = orchestration. Orchestration is the harder, more senior skill.

---

## Project Structure

```
Argus/
├── .env                          # API keys — never commit
├── .env.example                  # Template — commit this
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── render.yaml                   # Render deployment config
├── requirements.txt
├── README.md
├── ARCHITECTURE.md
│
├── data/
│   └── research.db               # SQLite — auto-created on first run
│
└── src/
    ├── api/
    │   ├── main.py               # FastAPI app, CORS, lifespan startup
    │   ├── models.py             # Pydantic request/response models
    │   └── routes/
    │       ├── research.py       # POST /research, GET /jobs/{id}/status+result
    │       └── health.py         # GET /health — Render health check
    │
    ├── agents/
    │   ├── supervisor.py         # LLM routing via Command(goto=...)
    │   ├── planner.py            # Decomposes query into sub-questions
    │   ├── researcher.py         # Calls Tavily + ArXiv + Wikipedia
    │   ├── critic.py             # Identifies research gaps
    │   └── writer.py             # Synthesizes final markdown report
    │
    ├── graph/
    │   ├── state.py              # ResearchState TypedDict + add_messages reducer
    │   └── pipeline.py           # Builds + compiles LangGraph StateGraph
    │
    ├── tools/
    │   ├── tavily_tool.py        # Web search (Tavily)
    │   ├── arxiv_tool.py         # Paper search (ArXiv, rate-limit fix applied)
    │   └── wikipedia_tool.py     # Background knowledge (Wikipedia)
    │
    ├── persistence/
    │   ├── db.py                 # SQLite CRUD — create_job, update_job_status, get_job
    │   └── checkpointer.py       # LangGraph SqliteSaver
    │
    └── ui/
        └── streamlit_app.py      # Calls FastAPI REST API, polls + renders report
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
// depth: "quick" (~20s, 2 sub-questions, web only)
//        "standard" (~45s, 3 sub-questions, web + arxiv + wikipedia)
//        "deep" (~90s, 5 sub-questions, all tools, more results)

// Response — 202 Accepted
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "estimated_seconds": 45
}
```

### `GET /jobs/{job_id}/status`
Poll for job progress.

```json
{
  "job_id": "550e8400-...",
  "status": "running",
  "created_at": "2026-02-26T07:00:00Z",
  "updated_at": "2026-02-26T07:00:32Z"
}
// status values: pending | running | complete | failed
```

### `GET /jobs/{job_id}/result`
Fetch the completed report.

```json
{
  "job_id": "550e8400-...",
  "query": "What are the latest breakthroughs in protein folding AI?",
  "status": "complete",
  "report": "## Protein Folding AI: 2025-2026 Breakthroughs\n\n...",
  "sources": ["https://...", "https://arxiv.org/abs/..."],
  "agent_turns": 4,
  "error": null,
  "created_at": "2026-02-26T07:00:00Z",
  "updated_at": "2026-02-26T07:00:38Z"
}
```

### `GET /health`
```json
{ "status": "ok", "version": "1.0.0" }
```

Interactive docs available at `/docs` (Swagger UI auto-generated by FastAPI).

---

## Shared State (ResearchState)

All agents read from and write back to a single `TypedDict` that flows through the graph:

```python
class ResearchState(TypedDict):
    query: str                               # Original research query
    depth: str                               # "quick" | "standard" | "deep"
    messages: Annotated[list, add_messages]  # Full message history — add_messages REDUCER
    sub_questions: list[str]                 # Set by Planner
    research_findings: list[str]             # Accumulated by Researcher
    gaps_identified: list[str]               # Set by Critic
    research_iterations: int                 # Incremented by Researcher — loop guard
    final_report: str                        # Set by Writer
    sources: list[str]                       # Accumulated throughout
    next_agent: str                          # Set by Supervisor for routing
```

`messages` uses the `add_messages` reducer — every agent appends to the history rather than overwriting it. All other fields use default last-write-wins replacement.

---

## Setup & Running Locally

### Prerequisites
- Python 3.11+
- Docker Desktop (for containerized run)
- API keys: [Groq](https://console.groq.com) (free), [Tavily](https://tavily.com) (free), [LangSmith](https://smith.langchain.com) (free, optional)

### 1. Clone and configure

```bash
git clone https://github.com/noviciusss/Argus.git
cd Argus
cp .env.example .env
# Edit .env and add your API keys
```

### 2. Run with Docker (recommended)

```bash
docker-compose up --build
```

- Streamlit UI: `http://localhost:8501`
- API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

### 3. Run without Docker

```bash
pip install -r requirements.txt

# Terminal 1 — API
python -m uvicorn src.api.main:app --reload --port 8000

# Terminal 2 — UI
python -m streamlit run src/ui/streamlit_app.py
```

> **Always run from the project root** using `python -m` so `src.*` imports resolve correctly.

---

## Rate Limiting

The public `/research` endpoint is rate-limited using **slowapi** to prevent free-tier API quota abuse. Since the Render URL is publicly accessible, an unprotected endpoint could be hammered by anyone, burning through Groq and Tavily free-tier credits.

**Current limits:**
- `POST /research` — **5 requests per IP per hour**
- `GET /jobs/*` — unlimited (read-only, no API cost)
- `GET /health` — unlimited (required for UptimeRobot pings)

If the limit is exceeded, the API returns:
```json
HTTP 429 Too Many Requests
{ "error": "Rate limit exceeded: 5 per 1 hour" }
```

The limit is enforced per IP address. For local development and Docker, the limit is effectively not hit under normal use. To adjust limits, change the `@limiter.limit("5/hour")` decorator in `src/api/routes/research.py`.

**Additional protection — hard caps on API dashboards:**
- [Groq](https://console.groq.com) → Usage Limits → set monthly token cap
- [Tavily](https://tavily.com) → Dashboard → set monthly search cap

Even if the rate limiter is bypassed, the upstream API caps act as a second defense layer.

---

## Design Decisions & Trade-offs

<details>
<summary><strong>Why did you put the HIL gate in its own node instead of inside the supervisor?</strong></summary>

LangGraph re-executes a node from the top when resuming after `interrupt()`. If the interrupt lived inside `supervisor_node` — after the LLM routing call — every human resume would re-run the LLM call, costing Groq API tokens and introducing a non-determinism risk (the LLM could route differently the second time). A dedicated `hil_node` with no expensive logic before the interrupt line means re-execution is free and deterministic. The interrupt point is also isolated: its only job is to read state, pause, and return a decision.

</details>

<details>
<summary><strong>Why multi-agent instead of one big ReAct agent?</strong></summary>

A single ReAct agent conflates planning, researching, critiquing, and writing — each has different failure modes and requires different prompting strategies. With one agent:
- Planning prompt interferes with tool-calling prompt
- No clean separation of concerns for debugging
- The critique loop is architecturally impossible — the agent can't objectively review its own just-completed output in the same turn

Separating into specialist agents allows independent prompts, independent error handling, and a dedicated Critic that reviews findings with fresh context before writing begins.

</details>

<details>
<summary><strong>Why async jobs instead of a streaming/blocking response?</strong></summary>

Research takes 30–90 seconds. Standard HTTP requests timeout at ~30 seconds in most clients, browsers, and load balancers. The async job pattern (submit → poll → fetch) decouples request handling from computation — this is the standard production pattern for any long-running AI task. It's the same pattern used by OpenAI's Batch API and Anthropic's async endpoints.

An alternative would be Server-Sent Events (SSE) for real-time streaming — listed as a future improvement.

</details>

<details>
<summary><strong>Why SQLite instead of PostgreSQL?</strong></summary>

This is a single-user, single-process deployment. SQLite handles this workload easily with zero infrastructure overhead — no separate database container, no connection pool, no migration tooling needed. The swap to PostgreSQL is explicitly one line in `src/persistence/db.py` (the connection string). The rest of the code is identical. This was a deliberate design choice to demonstrate production thinking on a dev setup.

</details>

<details>
<summary><strong>Why Groq (Llama 3.3 70B) instead of GPT-4 or Claude?</strong></summary>

Groq's free tier provides ~500 tokens/second — fast enough that agent turns feel snappy rather than laggy. For supervisor routing (which needs precise instruction-following), Llama 3.3 70B is sufficiently capable. For a demo project with real usage, paying $0 vs paying per token matters. The LLM is abstracted behind LangChain's `ChatGroq` interface — swapping to GPT-4o is one line change in each agent file.

</details>

<details>
<summary><strong>Why FastAPI BackgroundTasks instead of Celery/Redis?</strong></summary>

FastAPI's `BackgroundTasks` requires zero extra infrastructure — no Redis container, no worker process, no broker configuration. For single-user usage it works perfectly. The trade-off is that background tasks are in-process, so if the server restarts mid-research, the job is lost (status stays "running" forever in the DB). For a demo portfolio project this is acceptable. Celery + Redis is listed as the production upgrade path.

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

Render's free tier spins containers down after 15 minutes of inactivity. The first request after a cold start takes 30–60 seconds to respond — this is a Render free-tier limitation, not an application bug. Subsequent requests are fast. The fix is upgrading to a paid Render instance ($7/month) or using a cron job to ping `/health` every 14 minutes to keep the container warm.

</details>

<details>
<summary><strong>What would you add with more time?</strong></summary>

| Improvement | Why |
|-------------|-----|
| ~~Human-in-the-Loop gate~~ | ✅ **Done** — Dynamic HIL interrupts at Critic loop-back, timeout fallback |
| Redis + Celery | Proper async task queue — jobs survive server restarts |
| PostgreSQL | Multi-user support, persistent jobs across deploys |
| Server-Sent Events (SSE) | Real-time streaming of agent progress instead of polling |
| PDF export | Download research reports as formatted PDFs |
| ~~Rate limiting middleware~~ | ✅ **Done** — `slowapi` implemented, 5 req/hour per IP on `POST /research` |
| LLM-as-Judge evaluation | Score report quality using `DoCopilot` eval pattern |
| Authentication | API key auth for the REST API |
| Report caching | Same query within 24h returns cached result, no API cost |

</details>

---

## Observability

Every LLM call, tool call, and agent turn is automatically traced in **LangSmith** — no code instrumentation needed, just env vars.

Set in `.env`:
```bash
LANGSMITH_API_KEY=your_key
LANGSMITH_PROJECT=deep-research-engine
LANGSMITH_TRACING_V2=true
```

After a research run, visit `smith.langchain.com` → `deep-research-engine` project to see:
- Per-agent latency breakdown
- Token counts per LLM call  
- Tool call inputs/outputs (Tavily queries, ArXiv results)
- Full state at each node transition
- Error traces with full context if any agent fails

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | ✅ | [console.groq.com](https://console.groq.com) — free tier |
| `TAVILY_API_KEY` | ✅ | [tavily.com](https://tavily.com) — free tier |
| `LANGSMITH_API_KEY` | Recommended | [smith.langchain.com](https://smith.langchain.com) — free tier |
| `LANGSMITH_PROJECT` | Recommended | Set to `deep-research-engine` |
| `LANGSMITH_TRACING_V2` | Recommended | Set to `true` |
| `API_BASE` | Docker only | Auto-set to `http://api:8000` in compose |

---

## Related Projects

| Project | Pattern | What it proved |
|---------|---------|----------------|
| [MultiTool_Research](https://github.com/noviciusss/MultiTool_Research) | Single-agent ReAct | Tool use, conversation memory |
| DoCopilot | RAG + LLM-as-Judge | Document QA, evaluation pipelines |
| **Argus** (this) | Multi-agent Supervisor | Orchestration, async APIs, production deployment |

---

## License

MIT
