# streamlit_app.py
import os
import sys
import json
import time
from pathlib import Path
from typing import Any
from langchain_anthropic import ChatAnthropic

from dotenv import load_dotenv
load_dotenv()

import streamlit as st

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

st.set_page_config(page_title="DevTools Research Agent", layout="wide")

st.markdown("""
<style>
.card {background-color:#f8fafc;border-radius:12px;padding:16px;margin-bottom:12px;box-shadow:0 6px 18px rgba(15,23,42,0.06);}
.chip{display:inline-block;padding:6px 10px;border-radius:999px;background:#eef2ff;margin:4px 4px 4px 0;font-size:13px;color:#0f172a}
.meta{color:#475569;font-size:13px;margin-bottom:8px}
.small{font-size:13px;color:#6b7280}
</style>
""", unsafe_allow_html=True)

AVAILABLE_MODELS = [
    "claude-opus-4-1-20250805",
    "claude-opus-4-20250514",
    "claude-sonnet-4-20250514",
    "claude-3-5-haiku-20241022",
    "claude-3-haiku-20240307",
]

# Sidebar
st.sidebar.title("Settings")

default_model = os.getenv("LLM_MODEL", "claude-3-haiku-20240307")
if default_model not in AVAILABLE_MODELS:
    default_model = "claude-3-haiku-20240307"
llm_model = st.sidebar.selectbox(
    "LLM model",
    options=AVAILABLE_MODELS,
    index=AVAILABLE_MODELS.index(default_model),
)
temperature = st.sidebar.slider("LLM temperature", min_value=0.0, max_value=1.0, value=float(os.getenv("LLM_TEMP", 0.1)))
st.sidebar.markdown("---")
st.sidebar.markdown("FIRECRAWL_API_KEY and LLM credentials are loaded from environment / .env")

# Main UI
st.title("🔎 Developer Tools Research Agent — Streamlit")
st.write("Enter a developer-focused query (e.g. `serverless databases for React`) and the agent will search, scrape, and analyze developer tools and companies.")

query = st.text_input("Developer tools query", placeholder="e.g. 'open source feature flags for microservices'")
run_button = st.button("Run research")

with st.expander("Example queries", expanded=False):
    st.markdown("- `feature flag services for mobile apps`\n- `database hosting for Next.js`\n- `CI/CD tools for monorepos`")

# UI placeholders for live updates
log_box = st.empty()
extracted_box = st.empty()
companies_placeholder = st.empty()
analysis_box = st.empty()
download_placeholder = st.empty()

def render_companies(companies_list):
    """Render a list of company dicts into the companies_placeholder"""
    with companies_placeholder.container():
        st.header("Companies / Tools Found")
        if not companies_list:
            st.info("No companies found (yet). Results will appear here as the agent researches tools.")
            return

        for company in companies_list:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            c1, c2 = st.columns([3, 1])
            with c1:
                st.subheader(company.get("name", "Unnamed"))
                meta = []
                if company.get("website"):
                    meta.append(company.get("website"))
                if company.get("pricing_model"):
                    meta.append(str(company.get("pricing_model")))
                if company.get("is_open_source") is True:
                    meta.append("Open source")
                elif company.get("is_open_source") is False:
                    meta.append("Proprietary")

                if meta:
                    st.markdown(f"<div class='meta'>{' • '.join(meta)}</div>", unsafe_allow_html=True)

                if company.get("description"):
                    st.write(company.get("description"))

                if company.get("tech_stack"):
                    st.markdown("".join([f"<span class='chip'>{t}</span>" for t in company.get("tech_stack", [])[:12]]),
                                unsafe_allow_html=True)

            with c2:
                api_av = company.get("api_available")
                if api_av is True:
                    st.markdown("**API:** ✅")
                elif api_av is False:
                    st.markdown("**API:** ❌")
                else:
                    st.markdown("**API:** Unknown")

                if company.get("language_support"):
                    st.markdown("**Languages:** " + ", ".join(company.get("language_support", [])[:6]))

                if company.get("integration_capabilities"):
                    st.markdown("**Integrations:** " + ", ".join(company.get("integration_capabilities", [])[:6]))

                if company.get("website"):
                    st.markdown(f"[Visit website]({company.get('website')})")

            with st.expander("More details & raw JSON"):
                st.markdown("**Full Company JSON (pydantic model)**")
                st.code(json.dumps(company, indent=2, default=str), language="json")

            st.markdown("</div>", unsafe_allow_html=True)

# Run workflow with streaming callback
if run_button:
    if not query or not query.strip():
        st.warning("Please enter a search query first.")
        st.stop()

    # import Workflow
    try:
        from src.workflow import Workflow
    except Exception as e:
        st.error("Unable to import src.workflow. Ensure src/workflow.py and src/models.py exist and imports are correct.")
        st.exception(e)
        st.stop()

    # instantiate
    try:
        workflow = Workflow()
    except Exception as e:
        st.error("Failed to initialize Workflow (missing FIRECRAWL_API_KEY or LLM creds, or missing packages).")
        st.exception(e)
        st.stop()

    # optionally override LLM
    try:
        
        if llm_model:
            workflow.llm = ChatAnthropic(model=llm_model, temperature=temperature)
    except Exception:
        # not fatal
        pass

    # local state for progressive results
    companies_seen = []

    # define progress callback used by workflow
    def on_progress(event: dict):
        phase = event.get("phase")
        if phase == "extract_tools_start":
            log_box.info(f"🔍 Searching articles for: {event.get('query')}")
        elif phase == "extracted_tools":
            tools = event.get("tools", [])
            extracted_box.markdown(f"**Extracted candidate tools:** {', '.join(tools)}")
        elif phase == "research_start":
            log_box.info(f"🔬 Starting research of {len(event.get('tools', []))} tools")
        elif phase == "research_tool_start":
            tool = event.get("tool")
            log_box.info(f"🔎 Researching tool: {tool}")
        elif phase == "company_ready":
            # append and re-render companies
            comp = event.get("company", {})
            companies_seen.append(comp)
            render_companies(companies_seen)
        elif phase == "analysis_start":
            log_box.info("🧠 Generating recommendations...")
            analysis_box.markdown("**Recommendations:** _Generating..._")
        elif phase == "analysis_done":
            analysis = event.get("analysis", "")
            analysis_box.markdown(f"**Recommendations:**\n\n{analysis}")
        elif phase == "final":
            # enable download of final state if available
            try:
                data = event.get("final_state")
                download_placeholder.download_button(
                    "Download final state (JSON)",
                    data=json.dumps(data, indent=2, default=str),
                    file_name="research_final_state.json",
                    mime="application/json"
                )
            except Exception:
                pass
        elif phase == "error":
            log_box.error(f"Error: {event.get('error')}")

    # Run and stream updates
    with st.spinner("Agent running — streaming results as they arrive..."):
        start_ts = time.time()
        try:
            # pass callback into run()
            result = workflow.run(query, progress_callback=on_progress)
        except Exception as exc:
            st.error(f"Agent run failed: {exc}")
            st.stop()
        duration = time.time() - start_ts

    st.success(f"Research completed in {duration:.1f} seconds")
    # final rendering if any remaining companies haven't been drawn (safety)
    render_companies(companies_seen)
    if getattr(result, "analysis", None):
        analysis_box.markdown(f"**Recommendations:**\n\n{result.analysis}")

    st.balloons()
    
