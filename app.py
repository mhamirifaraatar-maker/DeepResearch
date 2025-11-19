import streamlit as st
import asyncio
import os
from pathlib import Path

# Load secrets into env for compatibility with config.py
if "GEMINI_KEY" in st.secrets:
    os.environ["GEMINI_KEY"] = st.secrets["GEMINI_KEY"]
if "BRAVE_API_KEY" in st.secrets:
    os.environ["BRAVE_API_KEY"] = st.secrets["BRAVE_API_KEY"]
if "UNPAYWALL_EMAIL" in st.secrets:
    os.environ["UNPAYWALL_EMAIL"] = st.secrets["UNPAYWALL_EMAIL"]

from deep_research.core import generate_keywords, filter_snippets, save_bibliometrics, synthesise
from deep_research.search import search_all
from deep_research.utils import build_doc, safe_save
from deep_research.config import OUTPUT_FILE, BIBLIO_FILE, GEMINI_KEY, BRAVE_API_KEY
import logging

# Setup logging to Streamlit
class StreamlitHandler(logging.Handler):
    def __init__(self, container):
        super().__init__()
        self.container = container

    def emit(self, record):
        msg = self.format(record)
        self.container.code(msg, language=None)

# Page Config

# Page Config
st.set_page_config(
    page_title="Deep Research Tool",
    page_icon="🔬",
    layout="wide"
)

# Title
st.title("🔬 Deep Research Tool")
st.markdown("---")

# Sidebar for Settings
with st.sidebar:
    st.header("⚙️ Settings")
    
    # API Keys (Optional override)
    st.markdown("### API Keys")
    
    # Gemini
    if GEMINI_KEY:
        st.success("✅ Gemini API Key loaded")
        new_gemini = st.text_input("Override Gemini API Key", type="password", placeholder="Enter new key to override")
    else:
        st.warning("⚠️ Gemini API Key missing")
        new_gemini = st.text_input("Gemini API Key", type="password")

    # Brave
    if BRAVE_API_KEY:
        st.success("✅ Brave API Key loaded")
        new_brave = st.text_input("Override Brave API Key", type="password", placeholder="Enter new key to override")
    else:
        st.warning("⚠️ Brave API Key missing")
        new_brave = st.text_input("Brave API Key", type="password")
    
    if new_gemini:
        os.environ["GEMINI_KEY"] = new_gemini
        # Force reload of client
        import sys
        if 'deep_research.core' in sys.modules:
            sys.modules['deep_research.core']._client = None
        else:
            from deep_research import core
            core._client = None 
        
    if new_brave:
        import sys
        if 'deep_research.config' in sys.modules:
            sys.modules['deep_research.config'].BRAVE_API_KEY = new_brave
        else:
            from deep_research import config
            config.BRAVE_API_KEY = new_brave

    st.markdown("---")
    st.markdown("### About")
    st.info(
        "This tool uses AI to perform deep research on any topic.\n\n"
        "1. Generates keywords\n"
        "2. Searches Web & Academic sources\n"
        "3. Filters & Deduplicates\n"
        "4. Synthesizes a Report"
    )

# Main Input
col1, col2 = st.columns([3, 1])
with col1:
    subject = st.text_input("Research Subject", placeholder="e.g., The Future of Quantum Computing")

with col2:
    st.write("") # Spacer
    st.write("")
    start_btn = st.button("🚀 Start Research", type="primary", use_container_width=True)

# Advanced Options
with st.expander("Advanced Options"):
    c1, c2 = st.columns(2)
    with c1:
        general_rounds = st.number_input("General Search Rounds", min_value=0, max_value=10, value=3)
    with c2:
        academic_rounds = st.number_input("Academic Search Rounds", min_value=0, max_value=10, value=2)

# Main Logic
# Main Logic
if "report" not in st.session_state:
    st.session_state.report = None
if "biblio_text" not in st.session_state:
    st.session_state.biblio_text = None

if start_btn and subject:
    status_container = st.status("Starting research...", expanded=True)
    
    # Apply nest_asyncio to allow nested event loops if needed
    import nest_asyncio
    nest_asyncio.apply()

    # Add log expander
    log_expander = st.expander("View Logs", expanded=False)
    
    # Setup logging
    st_handler = StreamlitHandler(log_expander)
    root_logger = logging.getLogger()
    root_logger.addHandler(st_handler)
    root_logger.setLevel(logging.INFO)

    async def run_research():
        try:
            # 1. Keywords
            status_container.write("📝 Generating keywords...")
            keywords = await generate_keywords(subject, general_rounds, academic_rounds)
            status_container.write(f"✅ Keywords: {keywords}")
            
            # 2. Search
            status_container.write("🔍 Searching sources...")
            snippets = await search_all(keywords)
            status_container.write(f"📊 Found {len(snippets)} raw snippets")
            
            if not snippets:
                status_container.error("No snippets found.")
                return None, None
            
            # 3. Filter
            status_container.write("🔄 Filtering and deduplicating...")
            snippets = await filter_snippets(snippets)
            status_container.write(f"✅ Kept {len(snippets)} quality snippets")
            
            if not snippets:
                status_container.error("No quality snippets left.")
                return None, None
            
            # 4. Bibliometrics
            status_container.write("📊 Generating bibliometrics...")
            biblio_text = save_bibliometrics(snippets)
            
            # 5. Synthesis
            status_container.write("🧠 Synthesizing report...")
            report = await synthesise(snippets, subject)
            
            status_container.update(label="Research Complete!", state="complete", expanded=False)
            return report, biblio_text
            
        except Exception as e:
            import traceback
            err_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
            status_container.error(err_msg)
            st.error(err_msg) # Also show outside status container
            return None, None

    # Run async loop
    try:
        report, biblio_text = asyncio.run(run_research())
        st.session_state.report = report
        st.session_state.biblio_text = biblio_text
    except Exception as e:
        st.error(f"Critical Error in Event Loop: {e}")
        st.session_state.report = None
        st.session_state.biblio_text = None
    finally:
        # Cleanup logger
        if 'st_handler' in locals():
            root_logger.removeHandler(st_handler)

# Display Results if available in session state
if st.session_state.report:
    st.success("Research completed successfully!")
    
    # Display Report
    st.markdown("## 📄 Research Report")
    st.markdown(st.session_state.report)
    
    # Download Buttons
    c1, c2, c3 = st.columns(3)
    
    # DOCX
    doc = build_doc(st.session_state.report)
    # Save to a temporary buffer for download
    from io import BytesIO
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    with c1:
        st.download_button(
            label="📥 Download DOCX",
            data=buffer,
            file_name=f"research_report.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        
    # Markdown
    with c2:
        st.download_button(
            label="📥 Download Markdown",
            data=st.session_state.report,
            file_name=f"research_report.md",
            mime="text/markdown"
        )

    # Bibliometrics
    if st.session_state.biblio_text:
        with c3:
            st.download_button(
                label="📥 Download Bibliometrics",
                data=st.session_state.biblio_text,
                file_name=f"bibliometrics.txt",
                mime="text/plain"
            )
