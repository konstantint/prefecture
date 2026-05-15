import os
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from datetime import datetime, timedelta

def render_template(template_path: Path, context: dict) -> str:
    """Renders a Jinja2 template from an absolute path."""
    template_dir = template_path.parent
    template_name = template_path.name
    
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template(template_name)
    return template.render(context)


