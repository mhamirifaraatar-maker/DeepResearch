import sys
import argparse
from .config import validate_config

def main():
    # Validate config
    valid, msg = validate_config()
    if not valid:
        print(f"Configuration Error: {msg}")
        print("Please create a .env file with the required keys.")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Deep Research Tool")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode (not implemented yet, defaults to GUI)")
    args = parser.parse_args()
    
    if args.cli:
        print("CLI mode not fully implemented in this version. Launching GUI...")
        # TODO: Implement CLI runner
        
    from .gui import main as gui_main
    gui_main()

if __name__ == "__main__":
    main()
