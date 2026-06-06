"""Configuration loading utilities for Prefecture."""
import os
import pathlib
import re
import sys
import dotenv
import yaml
import jinja2

def include_constructor(loader, node):
    # PyYAML construct_mapping returns a dict of the mapping node.
    # We return a dict wrapper to mark it as an include.
    return {'!include': loader.construct_mapping(node)}

yaml.SafeLoader.add_constructor('!include', include_constructor)
yaml.SafeLoader.add_constructor('!include:', include_constructor)

def expand_env_vars(text: str) -> str:
    """Replaces $VAR or ${VAR} with environment variable values."""
    # Match ${VAR}
    text = re.sub(r'\$\{([^}^{]+)\}', lambda m: os.environ.get(m.group(1), ''), text)
    # Match $VAR (word characters only)
    text = re.sub(r'\$([a-zA-Z_][a-zA-Z0-9_]*)', lambda m: os.environ.get(m.group(1), ''), text)
    return text

def expand_env_vars_in_structure(val):
    if isinstance(val, str):
        return expand_env_vars(val)
    elif isinstance(val, dict):
        return {k: expand_env_vars_in_structure(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [expand_env_vars_in_structure(v) for v in val]
    return val

def is_include_step(step) -> bool:
    return isinstance(step, dict) and '!include' in step

def load_config(config_path: str | pathlib.Path) -> dict:
    """Loads a YAML configuration file with recursive !include support and env var substitution."""
    dotenv.load_dotenv(dotenv_path=pathlib.Path(".env"), override=True)

    config_path = pathlib.Path(config_path)
    config_dir = config_path.parent

    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    config = yaml.safe_load(content)
    if not isinstance(config, dict):
        raise ValueError(f"Config file {config_path} must define a dictionary at the top level")

    steps = config.get("steps", [])
    if not isinstance(steps, list):
        raise ValueError("The 'steps' key in config must be a list")

    iterations = 0
    while iterations < 100:
        found_idx = -1
        for idx, step in enumerate(steps):
            if is_include_step(step):
                found_idx = idx
                break
        
        if found_idx == -1:
            break

        # Resolve the include
        include_op = steps[found_idx]['!include']
        if not isinstance(include_op, dict) or 'file_name' not in include_op:
            raise ValueError(f"Invalid !include structure at step index {found_idx}")

        file_name = include_op['file_name']
        substitutions = include_op.get('substitutions', {})

        included_file_path = config_dir / file_name
        if not included_file_path.exists():
            raise FileNotFoundError(f"Included file not found: {included_file_path}")

        with open(included_file_path, "r", encoding="utf-8") as f:
            included_content = f.read()

        if substitutions:
            if not isinstance(substitutions, dict):
                raise ValueError(f"substitutions for include {file_name} must be a dictionary")
            # Render Jinja2 template
            template = jinja2.Template(included_content)
            included_content = template.render(**substitutions)

        included_data = yaml.safe_load(included_content)

        if isinstance(included_data, dict):
            steps[found_idx] = included_data
        elif isinstance(included_data, list):
            steps[found_idx : found_idx + 1] = included_data
        else:
            raise ValueError(
                f"Included file {file_name} must resolve to a dict or list, got {type(included_data)}"
            )

        iterations += 1

    if any(is_include_step(s) for s in steps):
        raise ValueError("include recursion exceeded")

    config["steps"] = steps

    # Perform environment variable substitution on the fully resolved config
    resolved_config = expand_env_vars_in_structure(config)
    return resolved_config

if __name__ == "__main__":
    # Load environment variables from .env file if it exists in CWD
    dotenv.load_dotenv(override=True)

    config_file = sys.argv[1] if len(sys.argv) > 1 else "./configs/baby_digest.yaml"
    try:
        config = load_config(config_file)
        print(f"Successfully loaded config: {config_file}")
        print(config)
    except Exception as e:
        print(f"Error loading config: {e}")
