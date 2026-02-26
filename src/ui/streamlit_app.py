import time 
import requests 
import streamlit as st
import os

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

st.set_page_config(
    page_title="Argus — Deep Research Engine",
    page_icon="🔬",
    layout="wide",
)

st.title("🔬 Argus — Deep Research Engine")
st.caption("Multi-agent research pipeline: Planner → Researcher → Critic → Writer")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    depth = st.selectbox(
        "Research depth",
        options=["quick", "standard", "deep"],
        index=1,
        help="quick ~20s | standard ~45s | deep ~90s",
    )
    st.divider()
    st.markdown(f"**API:** `{API_BASE}`")
    try:
        health = requests.get(f"{API_BASE}/health", timeout=2).json()
        st.success(f"API online — v{health.get('version', '?')}")
    except Exception:
        st.error("API offline — run uvicorn first")

# ── Main input ────────────────────────────────────────────────────────────────
query = st.text_area(
    "Research query",
    placeholder="e.g. What are the latest breakthroughs in protein folding AI?",
    height=100,
)

if st.button("🚀 Start Research", type="primary", disabled=not query.strip()):
    with st.status("Running research pipeline...", expanded=True) as status_box:

        # Step 1 — submit job
        st.write("📤 Submitting job...")
        try:
            resp = requests.post(
                f"{API_BASE}/research",
                json={"query": query.strip(), "depth": depth},
                timeout=10,
            )
            resp.raise_for_status()
        except Exception as e:
            st.error(f"Failed to submit job: {e}")
            st.stop()

        job = resp.json()
        job_id = job["job_id"]
        st.write(f"✅ Job created: `{job_id}`")
        st.write(f"⏱ Estimated time: ~{job['estimated_seconds']}s")

        # Step 2 — poll status
        st.write("⏳ Waiting for research to complete...")
        agent_labels = {
            "planner": "📋 Planner — breaking down query",
            "researcher": "🔍 Researcher — searching web, papers, Wikipedia",
            "critic": "🧐 Critic — reviewing gaps",
            "writer": "✍️ Writer — synthesizing report",
        }

        elapsed = 0
        poll_interval = 3
        max_wait = 180   # 3 minutes hard timeout

        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval

            try:
                status_resp = requests.get(
                    f"{API_BASE}/jobs/{job_id}/status", timeout=5
                ).json()
            except Exception:
                continue

            current_status = status_resp.get("status", "unknown")

            if current_status == "running":
                st.write(f"🔄 Running... ({elapsed}s elapsed)")
            elif current_status == "complete":
                status_box.update(label="✅ Research complete!", state="complete")
                break
            elif current_status == "failed":
                status_box.update(label="❌ Research failed", state="error")
                st.error("Job failed. Check API logs.")
                st.stop()
        else:
            st.error("Timeout — research took too long. Try 'quick' depth.")
            st.stop()

    # Step 3 — fetch and display result
    try:
        result_resp = requests.get(
            f"{API_BASE}/jobs/{job_id}/result", timeout=10
        ).json()
    except Exception as e:
        st.error(f"Failed to fetch result: {e}")
        st.stop()

    # ── Report display ────────────────────────────────────────────────────────
    st.divider()
    col1, col2, col3 = st.columns(3)
    col1.metric("Status", result_resp.get("status", "?").upper())
    col2.metric("Research iterations", result_resp.get("agent_turns", "?"))
    col3.metric("Sources found", len(result_resp.get("sources") or []))

    st.subheader("📄 Research Report")
    report = result_resp.get("report", "")
    if report:
        st.markdown(report)
    else:
        st.warning("No report content returned.")

    # ── Sources ───────────────────────────────────────────────────────────────
    sources = result_resp.get("sources") or []
    if sources:
        with st.expander(f"🔗 Sources ({len(sources)})"):
            for i, url in enumerate(sources, 1):
                st.markdown(f"{i}. {url}")

    # ── Download ──────────────────────────────────────────────────────────────
    if report:
        st.download_button(
            label="⬇️ Download report as Markdown",
            data=report,
            file_name=f"research_{job_id[:8]}.md",
            mime="text/markdown",
        )