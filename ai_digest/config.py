import os
import re
import yaml
from pathlib import Path

def expand_env_vars(text: str) -> str:
    """Replaces $VAR or ${VAR} with environment variable values."""
    # Match ${VAR}
    text = re.sub(r'\$\{([^}^{]+)\}', lambda m: os.environ.get(m.group(1), ''), text)
    # Match $VAR (word characters only)
    text = re.sub(r'\$([a-zA-Z_][a-zA-Z0-9_]*)', lambda m: os.environ.get(m.group(1), ''), text)
    return text

def load_config(config_path: str | Path) -> dict:
    """Loads a YAML configuration file with env var substitution."""
    with open(config_path, "r") as f:
        content = f.read()
        
    expanded_content = expand_env_vars(content)
    return yaml.safe_load(expanded_content)

if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    
    # Load environment variables from .env file if it exists
    root_dir = Path(__file__).resolve().parent.parent
    load_dotenv(dotenv_path=root_dir / ".env", override=True)
    
    config_file = sys.argv[1] if len(sys.argv) > 1 else "./configs/baby_digest.yaml"
    try:
        config = load_config(config_file)
        print(f"Successfully loaded config: {config_file}")
        print(config)
    except Exception as e:
        print(f"Error loading config: {e}")
