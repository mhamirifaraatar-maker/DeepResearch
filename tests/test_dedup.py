import sys
from pathlib import Path


# Add parent dir to path
sys.path.append(str(Path(__file__).parent.parent))

from deep_research.processing import semantic_dedup
from deep_research.config import MAX_SNIPPETS_TO_KEEP

def test_semantic_dedup_limit():
    # Create dummy texts
    texts = [f"Text {i}" for i in range(200)]
    
    # Test default limit (should be 100 now in processing.py)
    indices = semantic_dedup(texts)
    assert len(indices) <= 100
    assert len(indices) == 100 # Since they are distinct enough
    
    # Test explicit limit
    indices_small = semantic_dedup(texts, max_keep=10)
    assert len(indices_small) == 10
    
    # Test config value
    assert MAX_SNIPPETS_TO_KEEP == 100
    
    print("Deduplication tests passed!")

if __name__ == "__main__":
    test_semantic_dedup_limit()
