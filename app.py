import streamlit as st
import asyncio
import os
from pathlib import Path
from deep_research.core import generate_keywords, filter_snippets, save_bibliometrics, synthesise
from deep_research.search import search_all
from deep_research.utils import build_doc, safe_save
from deep_research.config import OUTPUT_FILE, BIBLIO_FILE, GEMINI_KEY, BRAVE_API_KEY

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
    new_gemini = st.text_input("Gemini API Key", value=GEMINI_KEY or "", type="password")
    new_brave = st.text_input("Brave API Key", value=BRAVE_API_KEY or "", type="password")
    
    if new_gemini and new_gemini != GEMINI_KEY:
        os.environ["GEMINI_KEY"] = new_gemini
        # Force reload of client if needed, but for now env var is enough for next call if we didn't cache client too hard
        # Actually core.py uses a global client that is lazy loaded. 
        # If we change the key, we might need to reset it.
        from deep_research import core
        core._client = None 
        
    if new_brave and new_brave != BRAVE_API_KEY:
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
        general_rounds = st.number_input("General Search Rounds", min_value=1, max_value=10, value=3)
    with c2:
        academic_rounds = st.number_input("Academic Search Rounds", min_value=0, max_value=10, value=2)

# Main Logic
if start_btn and subject:
    status_container = st.status("Starting research...", expanded=True)
    
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
                return None
            
            # 3. Filter
            status_container.write("🔄 Filtering and deduplicating...")
            snippets = await filter_snippets(snippets)
            status_container.write(f"✅ Kept {len(snippets)} quality snippets")
            
            if not snippets:
                status_container.error("No quality snippets left.")
                return None
            
            # 4. Bibliometrics
            status_container.write("📊 Generating bibliometrics...")
            save_bibliometrics(snippets)
            
            # 5. Synthesis
            status_container.write("🧠 Synthesizing report...")
            report = await synthesise(snippets, subject)
            
            status_container.update(label="Research Complete!", state="complete", expanded=False)
            return report
            
        except Exception as e:
            status_container.error(f"Error: {str(e)}")
            return None

    # Run async loop
    report = asyncio.run(run_research())
    
    if report:
        st.success("Research completed successfully!")
        
        # Display Report
        st.markdown("## 📄 Research Report")
        st.markdown(report)
        
        # Download Buttons
        c1, c2 = st.columns(2)
        
        # DOCX
        doc = build_doc(report)
        # Save to a temporary buffer for download
        from io import BytesIO
        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        
        with c1:
            st.download_button(
                label="📥 Download DOCX",
                data=buffer,
                file_name=f"{subject.replace(' ', '_')}_report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            
        # Markdown
        with c2:
            st.download_button(
                label="📥 Download Markdown",
                data=report,
                file_name=f"{subject.replace(' ', '_')}_report.md",
                mime="text/markdown"
            )
