import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from prefecture.flows import run_flow

def main():
    # Load .env from current working directory only
    load_dotenv(dotenv_path=Path(".env"), override=True)
    
    if len(sys.argv) < 2:
        print("Usage: prefecture <path_to_config.yaml>")
        sys.exit(1)
        
    config_file = sys.argv[1]
    run_flow(config_file=config_file)

if __name__ == "__main__":
    main()
