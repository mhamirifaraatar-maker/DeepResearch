import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Keys
GEMINI_KEY = os.getenv("GEMINI_KEY")
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")
UNPAYWALL_EMAIL = os.getenv("UNPAYWALL_EMAIL")

# Configuration
MAX_URLS_PER_SOURCE = int(os.getenv("MAX_URLS_PER_SOURCE", 500))
MAX_TOKENS_PER_URL = int(os.getenv("MAX_TOKENS_PER_URL", 2_000))
MAX_SNIPPETS_TO_KEEP = int(os.getenv("MAX_SNIPPETS_TO_KEEP", 100))
EST_CHAR_PER_TOKEN = 4
CONCURRENCY = int(os.getenv("CONCURRENCY", 5))  # Increased default concurrency
JOURNAL_H_INDEX_THRESHOLD = int(os.getenv("JOURNAL_H_INDEX_THRESHOLD", 20))
MIN_CITATION_COUNT = int(os.getenv("MIN_CITATION_COUNT", 3))  # Minimum citations for academic papers
USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0 (compatible; DeepResearchBot/1.0)")

# Paths
BASE_DIR = Path(__file__).parent.parent
BIBLIO_FILE = BASE_DIR / "bibliometrics.txt"
OUTPUT_FILE = BASE_DIR / "output.docx"

def validate_config():
    """Validate that necessary configuration is present."""
    missing = []
    if not GEMINI_KEY:
        missing.append("GEMINI_KEY")
    if not BRAVE_API_KEY:
        missing.append("BRAVE_API_KEY")
    
    if missing:
        return False, f"Missing API keys: {', '.join(missing)}"
    return True, ""
