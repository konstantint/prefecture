import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from ai_digest.flows import generate_digest_flow, dispatch_digest_flow

def main():
    # Load .env from current working directory only
    load_dotenv(dotenv_path=Path(".env"), override=True)
    
    if len(sys.argv) < 3:
        print("Usage: ai-digest [generate|dispatch] <path_to_config.yaml>")
        sys.exit(1)
        
    action = sys.argv[1]
    config_file = sys.argv[2]
    
    if action == "generate":
        generate_digest_flow(config_file=config_file)
    elif action == "dispatch":
        dispatch_digest_flow(config_file=config_file)
    else:
        print(f"Unknown action: {action}")
        print("Usage: ai-digest [generate|dispatch] <path_to_config.yaml>")
        sys.exit(1)

if __name__ == "__main__":
    main()
