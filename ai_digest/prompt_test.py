import os
import pytest
from pathlib import Path
from ai_digest.prompt import PromptGenerator, register_loader, LastWeeksDigestLoader

# Dummy template for testing
@pytest.fixture
def test_template_dir(tmp_path):
    template_file = tmp_path / "test_prompt.j2"
    with open(template_file, "w") as f:
        f.write("Hello {{ name }}! Previous: {{ last_weeks_digest }}")
    return tmp_path

def test_generate_prompt_only_params(test_template_dir):
    prompt_config = {
        "template_file": "test_prompt.j2",
        "params": {"name": "World", "last_weeks_digest": "None"}
    }
    generator = PromptGenerator(config_dir=test_template_dir, **prompt_config)
    prompt = generator(run_dir=test_template_dir)
    assert prompt == "Hello World! Previous: None"

def test_generate_prompt_with_loader(test_template_dir):
    # Create mock data directory
    data_dir = test_template_dir / "baby_digest"
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
    
    generator = PromptGenerator(config_dir=test_template_dir, **prompt_config)
    prompt = generator(run_dir=test_template_dir)
    assert prompt == "Hello LoaderTest! Previous: Old content"

def test_generate_prompt_with_loader_remap(test_template_dir):
    # Create mock data directory
    data_dir = test_template_dir / "baby_digest"
    data_dir.mkdir()
    
    date_dir = data_dir / "2023-10-25"
    date_dir.mkdir()
    
    with open(date_dir / "digest.md", "w") as f:
        f.write("Old content")
        
    # Register loader with mock data dir
    loader = LastWeeksDigestLoader(data_dir)
    register_loader("last_weeks_digest", loader)
    
    # Create a template that expects a different variable name
    template_file = test_template_dir / "test_remap.j2"
    with open(template_file, "w") as f:
        f.write("Previous: {{ prev_content }}")
        
    prompt_config = {
        "template_file": "test_remap.j2",
        "context_loaders": [
            {"type": "last_weeks_digest", "assign_to": "prev_content"}
        ]
    }
    
    try:
        generator = PromptGenerator(config_dir=test_template_dir, **prompt_config)
        prompt = generator(run_dir=test_template_dir)
        assert prompt == "Previous: Old content"
    finally:
        if template_file.exists():
            template_file.unlink()
