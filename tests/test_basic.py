import sys
import os
from pathlib import Path

# Add parent dir to path
sys.path.append(str(Path(__file__).parent.parent))

def test_imports():
    print("Testing imports...")
    try:
        import deep_research
        from deep_research import config
        from deep_research import core
        from deep_research import search
        from deep_research import processing
        from deep_research import utils
        from deep_research import gui
        print("[OK] Imports successful")
    except ImportError as e:
        print(f"[X] Import failed: {e}")
        sys.exit(1)

def test_config():
    print("\nTesting config validation...")
    from deep_research.config import validate_config
    valid, msg = validate_config()
    if not valid:
        print(f"[WARN] Config validation warning: {msg}")
        print("This is expected if .env is not set up yet.")
    else:
        print("[OK] Config valid")

if __name__ == "__main__":
    test_imports()
    test_config()
