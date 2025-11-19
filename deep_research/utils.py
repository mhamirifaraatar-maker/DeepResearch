import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from docx import Document
from docx.shared import Pt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("deep_research.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def log_error(context: str, error: str):
    """Log an error with context."""
    logger.error(f"[{context}] {error}")

def safe_save(doc: Document, base_path: Path):
    """Save document with a timestamp to avoid overwriting."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = base_path.with_name(f"{base_path.stem}_{timestamp}{base_path.suffix}")
    try:
        doc.save(path)
        logger.info(f"✅ Saved report to {path}")
    except Exception as e:
        log_error("Save", str(e))

def build_doc(report: str) -> Document:
    """Convert markdown report to a Word document."""
    doc = Document()
    
    for line in report.splitlines():
        line = line.strip()
        if not line:
            continue
        
        if line == "---":
            doc.add_page_break()
            continue
        
        if line.startswith("# "):
            p = doc.add_heading(level=1)
            run = p.add_run(line[2:])
            run.font.name = "Times New Roman"
            run.font.size = Pt(18)
            continue
        
        if line.startswith("## "):
            p = doc.add_heading(level=2)
            run = p.add_run(line[3:])
            run.font.name = "Times New Roman"
            run.font.size = Pt(16)
            continue
        
        if line.startswith("### "):
            p = doc.add_heading(level=3)
            run = p.add_run(line[4:])
            run.font.name = "Times New Roman"
            run.font.size = Pt(14)
            continue
        
        if line.startswith("#### "):
            p = doc.add_heading(level=4)
            run = p.add_run(line[4:])
            run.font.name = "Times New Roman"
            run.font.size = Pt(13)
            continue
        
        para = doc.add_paragraph()
        # Basic markdown parsing for bold and italic
        # Note: This is a simplified parser from the original code
        import re
        tokens = re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*)", line)
        
        for tok in tokens:
            if tok.startswith("**") and tok.endswith("**"):
                run = para.add_run(tok[2:-2])
                run.bold = True
            elif tok.startswith("*") and tok.endswith("*"):
                run = para.add_run(tok[1:-1])
                run.italic = True
            else:
                run = para.add_run(tok)
            
            run.font.name = "Times New Roman"
            run.font.size = Pt(12)
    
    return doc
