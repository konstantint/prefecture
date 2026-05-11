import os
import pytest
from pathlib import Path
from ai_digest.prompt import PromptGenerator, register_loader, LastWeeksDigestLoader

# Dummy template for testing
@pytest.fixture(autouse=True)
def setup_test_template():
    root_dir = Path(__file__).resolve().parent.parent
    template_dir = root_dir / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    template_file = template_dir / "test_prompt.j2"
    with open(template_file, "w") as f:
        f.write("Hello {{ name }}! Previous: {{ last_weeks_digest }}")
    yield
    if template_file.exists():
        template_file.unlink()

def test_generate_prompt_only_params():
    prompt_config = {
        "template_file": "test_prompt.j2",
        "params": {"name": "World", "last_weeks_digest": "None"}
    }
    root_dir = Path(__file__).resolve().parent.parent
    generator = PromptGenerator(config_dir=root_dir / "templates", **prompt_config)
    prompt = generator()
    assert prompt == "Hello World! Previous: None"

def test_generate_prompt_with_loader(tmp_path):
    # Create mock data directory
    data_dir = tmp_path / "baby_digest"
    data_dir.mkdir()
    
    date_dir = data_dir / "2023-10-25"
    date_dir.mkdir()
    
    with open(date_dir / "digest.md", "w") as f:
        f.write("Old content")
        
    # Register loader with mock data dir
    loader = LastWeeksDigestLoader(data_dir)
    register_loader("last_weeks_digest", loader)
    
    prompt_config = {
        "template_file": "test_prompt.j2",
        "params": {"name": "LoaderTest"},
        "context_loaders": [
            {"type": "last_weeks_digest", "assign_to": "last_weeks_digest"}
        ]
    }
    
    root_dir = Path(__file__).resolve().parent.parent
    generator = PromptGenerator(config_dir=root_dir / "templates", **prompt_config)
    prompt = generator()
    assert prompt == "Hello LoaderTest! Previous: Old content"

def test_generate_prompt_with_loader_remap(tmp_path):
    # Create mock data directory
    data_dir = tmp_path / "baby_digest"
    data_dir.mkdir()
    
    date_dir = data_dir / "2023-10-25"
    date_dir.mkdir()
    
    with open(date_dir / "digest.md", "w") as f:
        f.write("Old content")
        
    # Register loader with mock data dir
    loader = LastWeeksDigestLoader(data_dir)
    register_loader("last_weeks_digest", loader)
    
    # Create a template that expects a different variable name
    root_dir = Path(__file__).resolve().parent.parent
    template_file = root_dir / "templates" / "test_remap.j2"
    with open(template_file, "w") as f:
        f.write("Previous: {{ prev_content }}")
        
    prompt_config = {
        "template_file": "test_remap.j2",
        "context_loaders": [
            {"type": "last_weeks_digest", "assign_to": "prev_content"}
        ]
    }
    
    try:
        generator = PromptGenerator(config_dir=root_dir / "templates", **prompt_config)
        prompt = generator()
        assert prompt == "Previous: Old content"
    finally:
        if template_file.exists():
            template_file.unlink()
