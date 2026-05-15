import os
import pytest
from pathlib import Path
from ai_digest.prompt import PromptGenerator, register_loader, RunDirFileLoader

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
    # Create mock data directory with date format
    run_dir = test_template_dir / "2023-10-25"
    run_dir.mkdir()
    
    with open(run_dir / "digest.md", "w") as f:
        f.write("Old content")
        
    prompt_config = {
        "template_file": "test_prompt.j2",
        "params": {"name": "LoaderTest"},
        "context_loaders": [
            {
                "type": "run_dir_file", 
                "assign_to": "last_weeks_digest",
                "params": {"file_name": "digest.md", "days_ago": 0}
            }
        ]
    }
    
    generator = PromptGenerator(config_dir=test_template_dir, **prompt_config)
    prompt = generator(run_dir=run_dir)
    assert prompt == "Hello LoaderTest! Previous: Old content"

def test_generate_prompt_with_loader_remap(test_template_dir):
    # Create mock data directory with date format
    run_dir = test_template_dir / "2023-10-25"
    run_dir.mkdir()
    
    with open(run_dir / "digest.md", "w") as f:
        f.write("Old content")
        
    # Create a template that expects a different variable name
    template_file = test_template_dir / "test_remap.j2"
    with open(template_file, "w") as f:
        f.write("Previous: {{ prev_content }}")
        
    prompt_config = {
        "template_file": "test_remap.j2",
        "context_loaders": [
            {
                "type": "run_dir_file", 
                "assign_to": "prev_content",
                "params": {"file_name": "digest.md"}
            }
        ]
    }
    
    try:
        generator = PromptGenerator(config_dir=test_template_dir, **prompt_config)
        prompt = generator(run_dir=run_dir)
        assert prompt == "Previous: Old content"
    finally:
        if template_file.exists():
            template_file.unlink()

def test_run_dir_file_loader_days_ago(test_template_dir):
    # Create mock data directory structure
    base_dir = test_template_dir / "data"
    base_dir.mkdir()
    
    prev_dir = base_dir / "2023-10-24"
    prev_dir.mkdir()
    with open(prev_dir / "digest.md", "w") as f:
        f.write("Previous content")
        
    run_dir = base_dir / "2023-10-25"
    run_dir.mkdir()
    
    prompt_config = {
        "template_file": "test_prompt.j2",
        "params": {"name": "LoaderTest"},
        "context_loaders": [
            {
                "type": "run_dir_file", 
                "assign_to": "last_weeks_digest",
                "params": {"file_name": "digest.md", "days_ago": 1}
            }
        ]
    }
    
    generator = PromptGenerator(config_dir=test_template_dir, **prompt_config)
    prompt = generator(run_dir=run_dir)
    assert prompt == "Hello LoaderTest! Previous: Previous content"

def test_run_dir_file_loader_fail_on_error(test_template_dir):
    run_dir = test_template_dir / "2023-10-25"
    run_dir.mkdir()
    
    prompt_config = {
        "template_file": "test_prompt.j2",
        "params": {"name": "LoaderTest"},
        "context_loaders": [
            {
                "type": "run_dir_file", 
                "assign_to": "last_weeks_digest",
                "params": {"file_name": "nonexistent.md"}
            }
        ]
    }
    
    generator = PromptGenerator(config_dir=test_template_dir, **prompt_config)
    prompt = generator(run_dir=run_dir)
    assert prompt == "Hello LoaderTest! Previous: None"
    
    prompt_config["context_loaders"][0]["params"]["fail_on_error"] = True
    generator = PromptGenerator(config_dir=test_template_dir, **prompt_config)
    
    with pytest.raises(ValueError) as exc_info:
        generator(run_dir=run_dir)
    assert "could not load" in str(exc_info.value)
