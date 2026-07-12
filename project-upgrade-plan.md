# Project Upgrade Plan — Pre-Placement Sprint

**Context:** Placement season begins mid-to-late August 2026. This plan is grounded in the actual current state of your three repos (Argus, DoCopilot, ContextCore-CLI), verified directly from GitHub on Jul 12, 2026 — not assumptions. Do these in order. Each one produces a real resume bullet and a real interview story, not a checkbox.

**Total estimated time:** ~25–35 hours across all three, spread across however many weekends it takes. Do them in the order listed — later items assume earlier ones are done.

---

## 1. ContextCore-CLI — fix the README truth gap (DO THIS FIRST)

**Priority: Highest — costs almost nothing, currently working against you**

### Current verified state
- Tech stack: LangGraph, Groq, PostgreSQL (checkpointing), Qdrant (long-term memory), MongoDB (user profile), MCP server (FastMCP) for tasks/notes
- Progress log in README literally shows: **"11 — Eval ⬜ Pending"**
- `eval/` folder exists (`test_cases.json`, `run_eval.py`, `results.md`) but the repo's own status table says it hasn't been completed
- **Zero observability/tracing** — no LangSmith, no OTel, nothing in the tech stack table (unlike Argus and DoCopilot, which both use LangSmith)

### The problem
Your own repo currently tells an interviewer "eval is pending" — contradicting the 100%-pass, 17-test harness you told me you already ran. Either the README is stale or the eval isn't actually merged. Whichever it is, this is live right now and actively hurting you.

### Action items

**1a. Reconcile eval status (1–3 hours)**
- [ ] Check whether `eval/run_eval.py` has actually been run against the *current* code in this repo
- [ ] If yes: update the progress log to ✅ Done, paste the real pass rate and the tc001 latency anomaly note into `eval/results.md`, commit
- [ ] If no: re-run it now, fix whatever breaks, get real current numbers before touching anything else in this repo
- [ ] Explicitly note the 3 unverified manual tests (including cross-session persistence, tc020) in the README rather than omitting them — an honest "17/17 automated, 3 manual tests pending verification" is a stronger, more credible line than a vague "eval done"

**1b. Add observability (2–4 hours, pick one)**
- [ ] **Quick path:** add `LANGSMITH_TRACING_V2=true` + `LANGCHAIN_API_KEY` env vars exactly like Argus and DoCopilot already do — zero new code, makes all three projects tell one consistent observability story
- [ ] **Differentiator path (if time allows):** instrument `agent/graph.py` nodes with OpenTelemetry GenAI semantic convention spans — wrap `agent_executor.py` calls as `invoke_agent` spans, wrap `ToolNode`/MCP tool calls as `execute_tool` spans

### Time estimate
**3–7 hours total.**

### Resume/interview payoff
Closes the gap between what you'd *say* in an interview and what someone reading the repo would actually see. Removes the single most embarrassing possible "wait, your own README says this isn't done" moment.

---

## 2. Argus — add a human-in-the-loop gate at an existing decision point

**Priority: Second — highest interview leverage, but do it right, not fake**

### Current verified state
- Supervisor-orchestrated 5-agent pipeline (supervisor, planner, researcher, critic, writer) via LangGraph, `Command(goto=...)` routing
- **Already has:** a circuit breaker (`research_iterations >= 3` hard cap enforced in code regardless of LLM decision), rate limiting (`slowapi`, 5 req/hour per IP on `/research`), async job pattern with SQLite job persistence + LangGraph `SqliteSaver` checkpointing
- Own "What would you add with more time" roadmap table lists: Redis+Celery, PostgreSQL, SSE streaming, PDF export, LLM-as-Judge eval (using the DoCopilot pattern), authentication, report caching — **HIL is not on this list at all**

### The problem
Nearly every 2026 agentic AI interview-prep source says the same next step after "built an agent with tools and memory": *"add HIL."* Argus can't currently answer that follow-up with a real example. But there's no genuinely dangerous/irreversible action in this pipeline to gate honestly — so don't invent one. Use the real decision point that already exists.

### Action items

**2a. Gate the Critic's loop-back decision (6–10 hours)**
- [ ] In `src/graph/pipeline.py`, find the conditional edge after the `critic` node that currently routes automatically to either `researcher` (loop back, gaps found) or `writer` (proceed, finalize)
- [ ] Insert a LangGraph `interrupt()` call at this point — surface the critic's identified gaps and ask: *"Continue researching (iteration N/3) or finalize now?"*
- [ ] A human overriding the LLM's own continue/stop judgment here is a legitimate, defensible safety gate — each extra research loop costs real API spend (Groq + Tavily), so a human veto on "let's burn another iteration" is a real, not decorative, control point
- [ ] Your existing `SqliteSaver` checkpointing does most of the hard work already — `interrupt()`/resume relies on the same state-persistence mechanism you already built for job resumption, so this is less net-new infrastructure than it sounds

**2b. Add an audit trail (1–2 hours)**
- [ ] Add one new column to the existing `jobs` table in `data/research.db` to log the human's decision (continue/finalize) and timestamp at each interrupt point

**2c. Document it (1 hour)**
- [ ] Add a new row to the "Design Decisions & Trade-offs" section of `README.md` in your existing voice/format explaining why this checkpoint exists and why you chose the critic's loop-back point specifically rather than a different one

### Time estimate
**8–13 hours total.**

### Resume/interview payoff
Goes from "I built a multi-agent system" to "I built a multi-agent system with a real human-in-the-loop safety gate at a genuine decision point" — directly answers the agent-safety interview question with your own project instead of pure theory, and the "why this checkpoint, not a fake one" reasoning is itself a strong interview answer.

---

## 3. DoCopilot — three narrow, concrete fixes

**Priority: Third — you're further along here than initially assumed, these are finishing touches**

### Current verified state
- **Already has:** guardrails (`ragguardrails.py` — prompt injection detection, PII redaction for credit cards/emails/Indian phone numbers, input length validation, source-grounding warnings), a genuinely strong published ablation study in the README (chunk size comparison, retrieval method comparison: vector-only → +rerank → +hybrid FAISS → +Qdrant hybrid, each with correctness/relevance/latency numbers), LLM-as-Judge eval using a *different* model (`llama-3.1-8b`) than the RAG pipeline itself to avoid self-bias
- **Current gaps, verified:** Qdrant is running in **`:memory:`** mode (no persistence — already flagged in your own "Future Plans" table as "Coming Soon"), no multi-tenant scoping (only per-`document_id`, not per-user/tenant), `evaluate_local.py` is a manually-run script, not a CI-gated automated regression suite
- You already have an unused `qdrant_data/` folder checked into the repo — suggests persistent Qdrant was half-started at some point

### Action items

**3a. Multi-tenant metadata filtering (4–6 hours)**
- [ ] In `backend/rag.py`, add a `tenant_id` field to each chunk's payload metadata at indexing time, alongside the existing `document_id` scoping
- [ ] Apply `tenant_id` as a Qdrant filter at query time, in addition to existing retrieval logic
- [ ] This works even before fixing persistence — demo with two tenants' documents loaded in the same in-memory session, show tenant A's queries never surface tenant B's chunks

**3b. Swap `:memory:` for persistent Qdrant (4–6 hours)**
- [ ] Use Docker + the existing (currently unused) `qdrant_data/` volume rather than Qdrant Cloud, since local groundwork already exists
- [ ] Update `backend/rag.py` to use `url="http://localhost:6333"` instead of `location=":memory:"`
- [ ] Update `docker-compose` / setup docs accordingly
- [ ] Re-run `evaluate_local.py` after the swap to confirm numbers haven't regressed — persistent storage occasionally surfaces indexing edge cases in-memory mode hides

**3c. Turn the eval script into a CI-gated regression suite (4–6 hours)**
- [ ] Wrap the existing 40-question eval set from `evaluate_local.py` in `pytest`
- [ ] Add a GitHub Actions workflow that runs it on every PR/push
- [ ] Fail the build if LLM-judged correctness drops more than a few points below the current 89.2% baseline
- [ ] You already have the hard part done (eval logic, golden questions, LLM-as-Judge setup) — this is packaging existing work into an automated gate, not new eval design

### Time estimate
**12–18 hours total.**

### Resume/interview payoff
"I built RAG with hybrid search and reranking" becomes "I built RAG with hybrid search, reranking, multi-tenant isolation, persistent production-grade storage, and a CI-gated regression suite that catches quality drops automatically" — directly matches the specific language research shows recruiters respond to.

---

## Summary tracker

| Project | Fix | Est. hours | Status |
|---|---|---|---|
| ContextCore-CLI | Reconcile eval status in README | 1–3 | |
| ContextCore-CLI | Add observability (LangSmith or OTel) | 2–4 | |
| Argus | HIL gate at critic loop-back decision | 6–10 | |
| Argus | Audit trail for HIL decisions | 1–2 | |
| Argus | Document the design decision in README | 1 | |
| DoCopilot | Multi-tenant metadata filtering | 4–6 | |
| DoCopilot | Persistent Qdrant (Docker) | 4–6 | |
| DoCopilot | CI-gated eval regression suite | 4–6 | |

**Total: ~25–35 hours.** Do them top to bottom — ContextCore-CLI's fix costs almost nothing and removes an active liability; Argus's HIL gate is the highest interview-leverage item; DoCopilot's three fixes are the most self-contained and least risky to get wrong.

## Before you start ContextCore-CLI

Confirm one thing first: **did the 17-test, 100%-pass eval run actually happen against the code currently in this repo, or against an earlier version that's since changed?** This determines whether step 1a is a 5-minute documentation fix or a few hours of re-running and debugging. Worth checking before committing time.
