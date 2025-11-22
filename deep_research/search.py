import asyncio
import aiohttp
import urllib.parse
from typing import List, Dict, Any
from .config import BRAVE_API_KEY, MAX_URLS_PER_SOURCE, USER_AGENT, CONCURRENCY, MIN_CITATION_COUNT
from .processing import Snippet, pdf_to_text, docx_to_text, is_quality_page, compress_text
from .processing import Snippet, pdf_to_text, docx_to_text, is_quality_page, compress_text
from .utils import logger, gemini_complete

# Re-implement fetch_text and resolve_url locally if they were not in processing.py
# Wait, I didn't put fetch_text in processing.py. I should add them here or in utils. 
# Let's put them here as they are network related.

async def resolve_url(url: str) -> str:
    """Resolve redirected URLs."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(url, allow_redirects=True, timeout=5) as resp:
                return str(resp.url)
    except:
        return url

async def fetch_text(session: aiohttp.ClientSession, url: str, max_retries: int = 2) -> str:
    """Fetch text content from a URL."""
    headers = {"User-Agent": USER_AGENT}
    
    for attempt in range(max_retries + 1):
        try:
            async with session.get(url, headers=headers, timeout=15) as resp:
                if resp.status != 200:
                    return ""
                
                content_type = resp.headers.get("Content-Type", "").lower()
                data = await resp.read()
                
                if "application/pdf" in content_type or url.endswith(".pdf"):
                    return pdf_to_text(data)
                elif "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in content_type:
                    return docx_to_text(data)
                else:
                    # Assume HTML/Text
                    return data.decode("utf-8", errors="ignore")
        except Exception as e:
            if attempt == max_retries:
                logger.debug(f"Failed to fetch {url}: {e}")
            await asyncio.sleep(1)
            
    return ""

async def brave_search(query: str, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore) -> List[Snippet]:
    """Search using Brave Search API."""
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": BRAVE_API_KEY
    }
    params = {"q": query, "count": 10}
    
    snippets = []
    backoff = 1
    max_retries = 3
    data = None

    # Retry loop for API call
    for attempt in range(max_retries + 1):
        try:
            async with semaphore:
                async with session.get(url, headers=headers, params=params) as resp:
                    if resp.status == 429:
                        if attempt < max_retries:
                            wait_time = backoff * (2 ** attempt)
                            logger.warning(f"Brave API rate limit (429). Retrying in {wait_time}s...")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            logger.error("Brave API rate limit exceeded after retries.")
                            return []
                            
                    if resp.status != 200:
                        logger.error(f"Brave API error: {resp.status}")
                        return []
                    
                    data = await resp.json()
                    break # Success
        except Exception as e:
            if attempt == max_retries:
                logger.error(f"Brave search connection error: {e}")
                return []
            await asyncio.sleep(1)

    if not data:
        return []

    try:     
        results = data.get("web", {}).get("results", [])
        
        # Fetch content for each result
        fetch_tasks = []
        for r in results:
            u = r.get("url")
            if not u: continue
            fetch_tasks.append(fetch_text(session, u))
            
        contents = await asyncio.gather(*fetch_tasks)
        
        for r, content in zip(results, contents):
            if not content: continue
            
            s = Snippet(
                title=r.get("title", "No Title"),
                body=content, # We will compress/filter later
                url=r.get("url"),
                source_type="web",
                metadata={"description": r.get("description")}
            )
            snippets.append(s)
            
    except Exception as e:
        logger.error(f"Brave search processing failed for '{query}': {e}")
        
    return snippets

async def check_relevance(subject: str, title: str, abstract: str) -> bool:
    """Check if a paper is relevant to the subject using Gemini."""
    if not abstract:
        return False
        
    prompt = f"""
    Topic: "{subject}"
    
    Paper Title: "{title}"
    Abstract: "{abstract}"
    
    Is this paper relevant to the topic? 
    Answer strictly with YES or NO.
    """
    
    response = await gemini_complete(prompt, max_tokens=10)
    return "YES" in response.upper()

async def semantic_search(query: str, semaphore: asyncio.Semaphore, subject: str, limit: int = 20) -> List[Snippet]:
    """Search using Semantic Scholar API."""
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "limit": limit,
        "fields": "title,abstract,url,year,venue,authors,citationCount,openAccessPdf"
    }
    
    snippets = []
    backoff = 2
    max_retries = 5
    data = None

    for attempt in range(max_retries + 1):
        try:
            async with semaphore:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params) as resp:
                        if resp.status == 429:
                            if attempt < max_retries:
                                wait_time = backoff * (2 ** attempt)
                                logger.warning(f"Semantic Scholar rate limit (429). Retrying in {wait_time}s...")
                                await asyncio.sleep(wait_time)
                                continue
                            else:
                                logger.error("Semantic Scholar rate limit exceeded after retries.")
                                return []

                        if resp.status != 200:
                            logger.error(f"Semantic Scholar error: {resp.status}")
                            return []
                        data = await resp.json()
                        break # Success
        except Exception as e:
            if attempt == max_retries:
                logger.error(f"Semantic search failed for '{query}': {e}")
                return []
            await asyncio.sleep(1)
            
    if not data:
        return []

    async def process_paper(session, p):
        try:
            # Filter by citation count
            citation_count = p.get("citationCount", 0)
            if citation_count < MIN_CITATION_COUNT:
                logger.debug(f"Filtered paper '{p.get('title', 'Unknown')}' - citations: {citation_count} < {MIN_CITATION_COUNT}")
            if citation_count < MIN_CITATION_COUNT:
                logger.debug(f"Filtered paper '{p.get('title', 'Unknown')}' - citations: {citation_count} < {MIN_CITATION_COUNT}")
                return None
            
            # Check relevance
            title = p.get("title", "No Title")
            abstract = p.get("abstract")
            
            if subject:
                is_relevant = await check_relevance(subject, title, abstract)
                if not is_relevant:
                    logger.debug(f"Filtered paper '{title}' - Not relevant to '{subject}'")
                    return None
                else:
                    logger.info(f"Paper '{title}' is relevant to '{subject}'")
            
            # Construct metadata
            meta = {
                "year": p.get("year"),
                "journal": p.get("venue"),
                "citations": citation_count,
                "authors": [a["name"] for a in p.get("authors", [])],
                "has_open_access": bool(p.get("openAccessPdf"))
            }
            
            url = (p.get("openAccessPdf") or {}).get("url") or p.get("url") or ""
            abstract = p.get("abstract")
            
            body = ""
            # If abstract is decent length, use it. Otherwise try to fetch full text.
            if abstract and len(abstract) >= 200:
                body = abstract
            elif url:
                # Try to fetch full text
                fetched = await fetch_text(session, url)
                if fetched and len(fetched) > len(abstract or ""):
                    body = fetched
            
            # Fallback
            if not body:
                body = abstract or "Abstract not available."

            return Snippet(
                title=p.get("title", "No Title"),
                body=body,
                url=url,
                source_type="semantic_scholar",
                metadata=meta,
                abstract=abstract
            )
        except Exception as e:
            logger.warning(f"Error processing paper {p.get('title')}: {e}")
            return None

    try:
        papers = data.get("data", [])
        async with aiohttp.ClientSession() as session:
            tasks = [process_paper(session, p) for p in papers]
            results = await asyncio.gather(*tasks)
            snippets = [r for r in results if r is not None]
            
    except Exception as e:
        logger.error(f"Semantic search processing failed for '{query}': {e}")
        
    return snippets

async def search_all(keywords_dict: Dict[str, List[str]], subject: str = "") -> List[Snippet]:
    """Orchestrate search across all sources."""
    all_snippets = []
    semaphore = asyncio.Semaphore(CONCURRENCY)
    semantic_semaphore = asyncio.Semaphore(1) # Limit Semantic Scholar to 1 concurrent request
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        
        # Brave Search Tasks
        for q in keywords_dict.get("general", []):
            tasks.append(brave_search(q, session, semaphore))
            
        # Semantic Scholar Tasks (run independently as they create their own session for now, 
        # but could share if refactored. Keeping separate to avoid complex session sharing for now)
        semantic_tasks = []
        for q in keywords_dict.get("academic", []):
            semantic_tasks.append(semantic_search(q, semantic_semaphore, subject))
            
        # Execute
        brave_results = await asyncio.gather(*tasks)
        semantic_results = await asyncio.gather(*semantic_tasks)
        
        for res in brave_results:
            all_snippets.extend(res)
        for res in semantic_results:
            all_snippets.extend(res)
            
    return all_snippets
