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

def load_previous_digest(config_name: str) -> str:
    """Scans the data directory, sorts by date descending, skips today's run,

    and returns the markdown text of the previous successful run.
    """
    root_dir = Path(__file__).resolve().parent.parent.parent
    data_dir = root_dir / "data" / config_name
    
    if not data_dir.exists():
        return ""
        
    dates = []
    for d in data_dir.iterdir():
        if d.is_dir():
            try:
                datetime.strptime(d.name, "%Y-%m-%d")
                dates.append(d.name)
            except ValueError:
                continue
                
    dates.sort(reverse=True)
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    for d_str in dates:
        if d_str == today_str:
            continue
        path = data_dir / d_str / "digest.md"
        if path.exists():
            with open(path, "r") as f:
                return f.read()
                
    return ""

if __name__ == "__main__":
    # Test with mock data
    print("Testing templating...")
    
    # Create dummy template
    root_dir = Path(__file__).resolve().parent.parent.parent
    test_template = root_dir / "templates" / "test_template.j2"
    test_template.parent.mkdir(parents=True, exist_ok=True)
    with open(test_template, "w") as f:
        f.write("Hello {{ name }}! Previous digest: {{ prev_digest }}")
        
    # Create dummy data
    data_dir = root_dir / "data" / "test_digest" / "2023-10-25"
    data_dir.mkdir(parents=True, exist_ok=True)
    with open(data_dir / "digest.md", "w") as f:
        f.write("Mock content from 2023-10-25")
        
    try:
        prev = load_previous_digest("test_digest")
        print(f"Loaded previous digest: {prev}")
        
        rendered = render_template("test_template.j2", {"name": "World", "prev_digest": prev})
        print(f"Rendered template: {rendered}")
        
    finally:
        # Clean up
        if test_template.exists():
            test_template.unlink()
        import shutil
        shutil.rmtree(root_dir / "data" / "test_digest", ignore_errors=True)
