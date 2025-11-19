import io
import re
import numpy as np
import trafilatura
import pdfplumber
import docx2txt
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Optional, Dict
from .config import MAX_TOKENS_PER_URL, EST_CHAR_PER_TOKEN
import logging

# Suppress PDF and Trafilatura warnings
logging.getLogger("pdfminer").setLevel(logging.ERROR)
logging.getLogger("pdfplumber").setLevel(logging.ERROR)
logging.getLogger("trafilatura").setLevel(logging.CRITICAL)

# Regex patterns
HYPE_PATTERNS = {
    "buy now", "order now", "click here", "call now", "add to cart",
    "sign up today", "subscribe now", "book now", "limited offer"
}

class Snippet:
    __slots__ = ("title", "body", "url", "ref_num", "source_type", "metadata", "abstract")
    def __init__(self, title: str, body: str, url: str, source_type: str = "web", 
                 metadata: Optional[dict] = None, abstract: Optional[str] = None):
        self.title = title
        self.body = body
        self.url = url
        self.ref_num = None
        self.source_type = source_type
        self.metadata = metadata or {}
        self.abstract = abstract

    def to_dict(self):
        return {
            "title": self.title,
            "url": self.url,
            "body": self.body[:2000],  # Truncate for display/logging
            "source_type": self.source_type,
            "metadata": self.metadata,
            "abstract": self.abstract
        }

def token_count(text: str) -> int:
    return len(text) // EST_CHAR_PER_TOKEN

def compress_text(html: str, max_tokens: int) -> str:
    """Extract main text from HTML and truncate to max_tokens."""
    if not html or len(html) < 10:
        return ""
    
    # If it doesn't look like HTML, treat as plain text
    if not ("<html" in html.lower() or "<body" in html.lower() or "<div" in html.lower()):
        text = html
    else:
        text = trafilatura.extract(html, include_comments=False, include_tables=False)
        
    if not text:
        # Fallback if extraction failed but there was content
        if len(html) > 0 and not ("<html" in html.lower()):
             text = html
        else:
             return ""
    
    # Simple truncation based on estimated tokens
    if token_count(text) > max_tokens:
        return text[:max_tokens * EST_CHAR_PER_TOKEN]
    return text

def is_quality_page(text: str, source_type: str = "web") -> bool:
    """Check if the text content is of sufficient quality."""
    if not text:
        return False

    # Academic papers might be just abstracts, so we allow shorter text
    if source_type == "semantic_scholar":
        return len(text) >= 100

    if len(text) < 500:
        return False
        
    # Check for hype words
    text_lower = text.lower()
    if any(p in text_lower for p in HYPE_PATTERNS):
        return False
        
    return True

def pdf_to_text(data: bytes) -> str:
    """Extract text from PDF bytes."""
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        return text
    except Exception:
        return ""

def docx_to_text(data: bytes) -> str:
    """Extract text from DOCX bytes."""
    try:
        return docx2txt.process(io.BytesIO(data))
    except Exception:
        return ""

def semantic_dedup(texts: List[str], max_keep: int = 100) -> List[int]:
    """Deduplicate texts using TF-IDF and Cosine Similarity."""
    if not texts:
        return []
    
    if len(texts) <= 1:
        return [0]
        
    # TF-IDF Vectorization
    vectorizer = TfidfVectorizer(stop_words='english', max_features=5000)
    try:
        tfidf_matrix = vectorizer.fit_transform(texts)
    except ValueError: # Empty vocabulary
        return list(range(min(len(texts), max_keep)))
        
    # Calculate similarity
    sim_matrix = cosine_similarity(tfidf_matrix)
    
    # Greedy selection to maximize diversity (simplified approach)
    # Here we just keep the most distinct ones, or rather, we filter out very similar ones.
    # The original code used a specific logic, let's replicate a robust version.
    
    keep_indices = []
    seen_indices = set()
    
    # Sort by length (preference for longer content) as a heuristic? 
    # Or just process in order. Let's process in order but skip if similar to already kept.
    
    for i in range(len(texts)):
        if i in seen_indices:
            continue
            
        keep_indices.append(i)
        seen_indices.add(i)
        
        if len(keep_indices) >= max_keep:
            break
            
        # Mark similar items as seen
        for j in range(i + 1, len(texts)):
            if j not in seen_indices and sim_matrix[i, j] > 0.85: # Threshold
                seen_indices.add(j)
                
    return keep_indices
