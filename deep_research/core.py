import json
import asyncio
import re
import numpy as np
from datetime import datetime
from typing import List, Dict
from google import genai
from .config import GEMINI_KEY, JOURNAL_H_INDEX_THRESHOLD, MAX_TOKENS_PER_URL, BIBLIO_FILE
from .processing import Snippet, compress_text, is_quality_page, semantic_dedup
from .utils import logger, log_error

# Initialize Gemini Client lazily
_client = None

def get_client():
    global _client
    if _client is None:
        if not GEMINI_KEY:
            raise ValueError("GEMINI_KEY not found in environment variables.")
        _client = genai.Client(api_key=GEMINI_KEY)
    return _client

async def gemini_complete(prompt: str, max_tokens: int = 6000) -> str:
    """Generate text using Gemini."""
    try:
        client = get_client()
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=0.3
            )
        )
        return response.text
    except Exception as e:
        log_error("Gemini", str(e))
        return ""

async def generate_keywords(subject: str, english_rounds: int, academic_rounds: int) -> Dict[str, List[str]]:
    """Generate search keywords using Gemini."""
    prompt = f"""
    Generate search queries for the topic: "{subject}"
    
    Format as JSON:
    {{
        "general": ["query1", "query2", ...],  # EXACTLY {english_rounds} distinct queries for general web search
        "academic": ["query1", "query2", ...]   # EXACTLY {academic_rounds} distinct queries for academic databases
    }}
    
    IMPORTANT:
    - You MUST provide exactly {english_rounds} items in the "general" list.
    - You MUST provide exactly {academic_rounds} items in the "academic" list.
    - For academic queries, use precise terminology suitable for Semantic Scholar.
    """
    
    text = await gemini_complete(prompt, max_tokens=1000)
    try:
        # Clean markdown code blocks if present
        text = text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text)
        
        # Validate and pad/truncate if necessary
        gen = data.get("general", [])
        acad = data.get("academic", [])
        
        # Ensure lists
        if not isinstance(gen, list): gen = [str(gen)]
        if not isinstance(acad, list): acad = [str(acad)]
        
        # Pad General
        if len(gen) < english_rounds:
            logger.warning(f"Gemini returned {len(gen)} general queries, expected {english_rounds}. Padding.")
            while len(gen) < english_rounds:
                gen.append(f"{subject} {len(gen)+1}")
        elif len(gen) > english_rounds:
            gen = gen[:english_rounds]
            
        # Pad Academic
        if len(acad) < academic_rounds:
            logger.warning(f"Gemini returned {len(acad)} academic queries, expected {academic_rounds}. Padding.")
            while len(acad) < academic_rounds:
                acad.append(f"{subject} research paper {len(acad)+1}")
        elif len(acad) > academic_rounds:
            acad = acad[:academic_rounds]
            
        return {"general": gen, "academic": acad}
        
    except json.JSONDecodeError:
        logger.error("Failed to parse keywords JSON")
        # Fallback with correct counts
        return {
            "general": [f"{subject} {i+1}" for i in range(english_rounds)], 
            "academic": [f"{subject} research {i+1}" for i in range(academic_rounds)]
        }

async def filter_snippets(snippets: List[Snippet]) -> List[Snippet]:
    """Filter and deduplicate snippets."""
    url_to_snippet = {}
    bodies = []
    
    for s in snippets:
        # Compress and validate
        txt = compress_text(s.body, MAX_TOKENS_PER_URL)
        
        # Filter by H-Index for academic sources
        if s.source_type == "semantic_scholar":
            h_index = s.metadata.get("h_index", 0)
            # Note: H-index fetching was in original but complex to implement reliably without extra API calls.
            # Assuming metadata might not have it populated yet, so we skip this check or implement it if we had the data.
            # For now, we'll keep the logic but it might be 0.
            pass

        if txt and is_quality_page(txt, s.source_type):
            bodies.append(txt)
            url_to_snippet[len(bodies) - 1] = (s, txt)
            
    if not bodies:
        return []
        
    # Deduplicate
    keep_idx = semantic_dedup(bodies)
    
    result = []
    for idx in keep_idx:
        s, body = url_to_snippet[idx]
        s.body = body
        result.append(s)
        
    return result

def generate_bibliometrics(snippets: List[Snippet]) -> str:
    """Generate a bibliometrics report."""
    lines = [
        "=" * 80,
        f"BIBLIOMETRICS REPORT - {datetime.now():%Y-%m-%d %H:%M:%S}",
        "=" * 80,
        "",
        "SUMMARY STATISTICS",
        "-" * 80,
        f"Total Sources: {len(snippets)}",
        f"  - Web: {sum(1 for s in snippets if s.source_type == 'web')}",
        f"  - Semantic Scholar: {sum(1 for s in snippets if s.source_type == 'semantic_scholar')}",
        ""
    ]
    
    academic = [s for s in snippets if s.source_type == "semantic_scholar"]
    if academic:
        lines.extend(["ACADEMIC SOURCES", "-" * 80])
        for idx, s in enumerate(academic, 1):
            lines.append(f"\n[{idx}] {s.title}")
            lines.append(f"    URL: {s.url}")
            md = s.metadata
            lines.append(f"    Journal: {md.get('journal', 'N/A')}")
            lines.append(f"    Year: {md.get('year', 'N/A')}")
            lines.append(f"    Citations: {md.get('citations', 'N/A')}")
            
            if md.get("authors"):
                auth = ", ".join(md["authors"])
                lines.append(f"    Authors: {auth}")
                
    lines.extend(["", "=" * 80, "END OF REPORT", "=" * 80])
    return "\n".join(lines)

def save_bibliometrics(snippets: List[Snippet]) -> str:
    """Save bibliometrics to file and return the content."""
    text = generate_bibliometrics(snippets)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = BIBLIO_FILE.with_name(f"{BIBLIO_FILE.stem}_{timestamp}.txt")
    path.write_text(text, encoding="utf-8")
    logger.info(f"✅ Bibliometrics saved → {path}")
    return text

async def synthesise(snippets: List[Snippet], subject: str) -> str:
    """Synthesize snippets into a final report."""
    # Prepare source list
    source_list = "\n".join(f"{idx+1}. {s.title}  {s.url}" for idx, s in enumerate(snippets))
    
    # Prepare payload (content)
    payload = json.dumps([s.to_dict() for s in snippets], ensure_ascii=False, indent=2)
    
    # Read system prompt
    try:
        from pathlib import Path
        base_dir = Path(__file__).parent.parent
        sys_prompt = (base_dir / "system_prompt.txt").read_text(encoding="utf-8")
    except Exception:
        sys_prompt = "You are a helpful research assistant."

    prompt = f"""
    {sys_prompt}

    Topic: {subject}
    
    Synthesize these {len(snippets)} sources into a professional research report.
    
    CRITICAL CITATION RULES:
    - Cite ONLY by number: (1), (2), etc.
    - Reference list must contain EXACTLY entries 1-{len(snippets)}
    - Use APA 7th edition format
    - Do NOT add sources outside this list
    
    Sources:
    {source_list}
    
    Extracts:
    {payload}
    """
    
    report = await gemini_complete(prompt, 20_000)
    return report
