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

# Initialize session state keys
if "job_id" not in st.session_state:
    st.session_state.job_id = None
if "query" not in st.session_state:
    st.session_state.query = ""

# ── Main input ────────────────────────────────────────────────────────────────
# Show query input only if no job is active
if not st.session_state.job_id:
    query = st.text_area(
        "Research query",
        value=st.session_state.query,
        placeholder="e.g. What are the latest breakthroughs in protein folding AI?",
        height=100,
    )
    
    if st.button("🚀 Start Research", type="primary", disabled=not query.strip()):
        try:
            resp = requests.post(
                f"{API_BASE}/research",
                json={"query": query.strip(), "depth": depth},
                timeout=10,
            )
            resp.raise_for_status()
            job = resp.json()
            st.session_state.job_id = job["job_id"]
            st.session_state.query = query.strip()
            st.rerun()
        except Exception as e:
            st.error(f"Failed to submit job: {e}")

else:
    # A job is active! Show its status and progress.
    job_id = st.session_state.job_id
    st.info(f"Active Job ID: `{job_id}`")
    
    # Check status
    try:
        status_resp = requests.get(f"{API_BASE}/jobs/{job_id}/status", timeout=5).json()
        current_status = status_resp.get("status", "unknown")
    except Exception as e:
        st.error(f"Error fetching status: {e}")
        if st.button("🔄 Reset / Start New"):
            st.session_state.job_id = None
            st.rerun()
        st.stop()
        
    if current_status in ("pending", "running"):
        st.status(f"Running research pipeline... Status: {current_status}", state="running")
        # auto rerun after a short sleep to simulate polling
        time.sleep(2)
        st.rerun()
        
    elif current_status == "awaiting_human":
        st.warning("⚡ Human-in-the-Loop: Review Required")
        hil = status_resp.get("hil_payload", {}) or {}
        st.markdown(f"**Iteration {hil.get('iteration', '?')}/{hil.get('max_iterations', '?')} — Critic found research gaps:**")
        for gap in hil.get("gaps", []):
            st.markdown(f"• {gap}")
            
        expires_at = hil.get("expires_at")
        if expires_at:
            st.caption(f"⏱ Auto-finalizes at {expires_at} (UTC) if no response")
            
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🔍 Continue Researching", type="primary"):
                try:
                    resp = requests.post(f"{API_BASE}/jobs/{job_id}/decision", json={"decision": "continue"}, timeout=5)
                    resp.raise_for_status()
                    st.success("Routing back to Researcher...")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to send decision: {e}")
        with col_b:
            if st.button("✍️ Finalize Now"):
                try:
                    resp = requests.post(f"{API_BASE}/jobs/{job_id}/decision", json={"decision": "finalize"}, timeout=5)
                    resp.raise_for_status()
                    st.success("Skipping to Writer...")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to send decision: {e}")
                    
    elif current_status == "failed":
        st.error("❌ Research job failed.")
        if st.button("🔄 Reset / Start New"):
            st.session_state.job_id = None
            st.rerun()
            
    elif current_status == "complete":
        st.success("✅ Research complete!")
        
        # Fetch results
        try:
            result_resp = requests.get(f"{API_BASE}/jobs/{job_id}/result", timeout=10).json()
        except Exception as e:
            st.error(f"Failed to fetch result: {e}")
            st.stop()
            
        # Display metrics
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
            
        sources = result_resp.get("sources") or []
        if sources:
            with st.expander(f"🔗 Sources ({len(sources)})"):
                for i, url in enumerate(sources, 1):
                    st.markdown(f"{i}. {url}")
                    
        col_down, col_reset = st.columns([3, 1])
        if report:
            with col_down:
                st.download_button(
                    label="⬇️ Download report as Markdown",
                    data=report,
                    file_name=f"research_{job_id[:8]}.md",
                    mime="text/markdown",
                )
        with col_reset:
            if st.button("🔄 Start New Research"):
                st.session_state.job_id = None
                st.rerun()