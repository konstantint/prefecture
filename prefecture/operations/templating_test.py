"""Tests for Jinja2 templating in Prefecture."""

import json
import pathlib
from unittest import mock

from prefecture.operations import templating
import pytest


# Dummy template for testing
@pytest.fixture
def test_template_dir(tmp_path):
    """Fixture to create a dummy template directory."""
    template_file = tmp_path / "test_prompt.j2"
    with open(template_file, "w") as f:
        f.write("Hello {{ name }}! Previous: {{ last_weeks_digest }}")
    return tmp_path


def test_generate_template_only_params(test_template_dir):
    """Test template rendering with only parameters."""
    prompt_config = {
        "template_file": "test_prompt.j2",
        "params": {"name": "World", "last_weeks_digest": "None"},
    }
    generator = templating.Jinja2Templater(
        config_dir=test_template_dir, run_dir=test_template_dir, **prompt_config
    )
    generated_prompt = generator()
    assert generated_prompt == "Hello World! Previous: None"


def test_generate_template_with_loader(test_template_dir):
    """Test template rendering with a context loader."""
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
                "params": {"file_name": "digest.md", "days_ago": 0},
            }
        ],
    }

    generator = templating.Jinja2Templater(
        config_dir=test_template_dir, run_dir=run_dir, **prompt_config
    )
    generated_prompt = generator()
    assert generated_prompt == "Hello LoaderTest! Previous: Old content"


def test_generate_template_with_loader_remap(test_template_dir):
    """Test template rendering with loader and variable remapping."""
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
                "params": {"file_name": "digest.md"},
            }
        ],
    }

    try:
        generator = templating.Jinja2Templater(
            config_dir=test_template_dir, run_dir=run_dir, **prompt_config
        )
        generated_prompt = generator()
        assert generated_prompt == "Previous: Old content"
    finally:
        if template_file.exists():
            template_file.unlink()


def test_run_dir_file_loader_days_ago(test_template_dir):
    """Test RunDirFileLoader with days_ago parameter."""
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
                "params": {"file_name": "digest.md", "days_ago": 1},
            }
        ],
    }

    generator = templating.Jinja2Templater(
            config_dir=test_template_dir, run_dir=run_dir, **prompt_config
    )
    generated_prompt = generator()
    assert (
        generated_prompt == "Hello LoaderTest! Previous: Previous content"
    )


def test_run_dir_file_loader_fail_on_error(test_template_dir):
    """Test RunDirFileLoader fail_on_error behavior."""
    run_dir = test_template_dir / "2023-10-25"
    run_dir.mkdir()

    prompt_config = {
        "template_file": "test_prompt.j2",
        "params": {"name": "LoaderTest"},
        "context_loaders": [
            {
                "type": "run_dir_file",
                "assign_to": "last_weeks_digest",
                "params": {"file_name": "nonexistent.md"},
            }
        ],
    }

    generator = templating.Jinja2Templater(
        config_dir=test_template_dir, run_dir=run_dir, **prompt_config
    )
    generated_prompt = generator()
    assert generated_prompt == "Hello LoaderTest! Previous: None"

    prompt_config["context_loaders"][0]["params"]["fail_on_error"] = True
    generator = templating.Jinja2Templater(
        config_dir=test_template_dir, run_dir=run_dir, **prompt_config
    )

    with pytest.raises(ValueError) as exc_info:
        generator()
    assert "could not load" in str(exc_info.value)


def test_artifact_key_generation(test_template_dir):
    """Test that the Prefect artifact key is generated from output_file_name."""
    prompt_config = {
        "template_file": "test_prompt.j2",
        "output_file_name": "My-Special_Prompt.md.tmp",
        "params": {"name": "World", "last_weeks_digest": "None"},
    }
    generator = templating.Jinja2Templater(
        config_dir=test_template_dir, run_dir=test_template_dir, **prompt_config
    )

    with mock.patch(
        "prefect.artifacts.create_markdown_artifact"
    ) as mock_create_artifact:
        generator()

        mock_create_artifact.assert_called_once_with(
            key="my-special-prompt-md",
            markdown="Hello World! Previous: None",
            description="Rendered Template",
        )


def test_artifact_key_generation_fallback(test_template_dir):
    """Test that Prefect artifact key falls back to 'jinja2' if no output_file_name."""
    prompt_config = {
        "template_file": "test_prompt.j2",
        "params": {"name": "World", "last_weeks_digest": "None"},
    }
    generator = templating.Jinja2Templater(
        config_dir=test_template_dir, run_dir=test_template_dir, **prompt_config
    )

    with mock.patch(
        "prefect.artifacts.create_markdown_artifact"
    ) as mock_create_artifact:
        generator()

        mock_create_artifact.assert_called_once_with(
            key="jinja2",
            markdown="Hello World! Previous: None",
            description="Rendered Template",
        )


def test_run_dir_file_loader_load_json_success(test_template_dir):
    """Test successful structured JSON loading & template loop rendering."""
    run_dir = test_template_dir / "2023-10-25"
    run_dir.mkdir()

    # Create JSON file
    mock_data = [{"val": "A"}, {"val": "B"}]
    with open(run_dir / "data.json", "w", encoding="utf-8") as f:
        json.dump(mock_data, f)

    # Create a template that iterates over this JSON
    template_file = test_template_dir / "test_json_loop.j2"
    with open(template_file, "w", encoding="utf-8") as f:
        f.write("Items: {% for item in my_list %}{{ item.val }} {% endfor %}")

    prompt_config = {
        "template_file": "test_json_loop.j2",
        "context_loaders": [
            {
                "type": "run_dir_file",
                "assign_to": "my_list",
                "params": {"file_name": "data.json", "load_json": True},
            }
        ],
    }

    try:
        generator = templating.Jinja2Templater(
            config_dir=test_template_dir, run_dir=run_dir, **prompt_config
        )
        generated_prompt = generator()
        assert generated_prompt == "Items: A B "
    finally:
        if template_file.exists():
            template_file.unlink()


def test_run_dir_file_loader_load_json_failure(test_template_dir):
    """Test that JSON decode failures always propagate and crash templating."""
    run_dir = test_template_dir / "2023-10-25"
    run_dir.mkdir()

    # Write invalid JSON
    with open(run_dir / "malformed.json", "w", encoding="utf-8") as f:
        f.write("{invalid-json}")

    prompt_config = {
        "template_file": "test_prompt.j2",
        "context_loaders": [
            {
                "type": "run_dir_file",
                "assign_to": "my_list",
                "params": {"file_name": "malformed.json", "load_json": True},
            }
        ],
    }

    generator = templating.Jinja2Templater(
        config_dir=test_template_dir, run_dir=run_dir, **prompt_config
    )

    # Expecting json.JSONDecodeError
    with pytest.raises(json.JSONDecodeError):
        generator()


def test_sqlalchemy_loader(test_template_dir):
    """Test SqlAlchemyLoader by querying a temporary sqlite database."""
    import sqlalchemy

    # Create a temporary SQLite database
    db_path = test_template_dir / "test.db"
    db_url = f"sqlite:///{db_path}"

    engine = sqlalchemy.create_engine(db_url)
    with engine.connect() as conn:
        conn.execute(sqlalchemy.text("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, role TEXT)"))
        conn.execute(sqlalchemy.text("INSERT INTO users (name, role) VALUES ('Alice', 'Admin')"))
        conn.execute(sqlalchemy.text("INSERT INTO users (name, role) VALUES ('Bob', 'User')"))
        conn.commit()

    # Create a template that iterates over users
    template_file = test_template_dir / "test_db.j2"
    with open(template_file, "w", encoding="utf-8") as f:
        f.write("Users: {% for user in users %}{{ user.name }} ({{ user.role }}) {% endfor %}")

    prompt_config = {
        "template_file": "test_db.j2",
        "context_loaders": [
            {
                "type": "sqlalchemy",
                "assign_to": "users",
                "params": {
                    "db_url": db_url,
                    "query": "SELECT name, role FROM users ORDER BY name"
                }
            }
        ]
    }

    try:
        generator = templating.Jinja2Templater(
            config_dir=test_template_dir, run_dir=test_template_dir, **prompt_config
        )
        generated_prompt = generator()
        assert generated_prompt == "Users: Alice (Admin) Bob (User) "
    finally:
        if template_file.exists():
            template_file.unlink()


def test_datetime_now_loader(test_template_dir):
    """Test DatetimeNowLoader renders current date in template."""
    # Create a template that uses datetime_now and formats it
    template_file = test_template_dir / "test_datetime.j2"
    with open(template_file, "w", encoding="utf-8") as f:
        f.write("Current year: {{ now.strftime('%Y') }}")

    prompt_config = {
        "template_file": "test_datetime.j2",
        "context_loaders": [
            {
                "type": "datetime_now",
                "assign_to": "now",
            }
        ],
    }

    try:
        generator = templating.Jinja2Templater(
            config_dir=test_template_dir, run_dir=test_template_dir, **prompt_config
        )
        generated_prompt = generator()
        import datetime
        expected_year = datetime.datetime.now().strftime("%Y")
        assert generated_prompt == f"Current year: {expected_year}"
    finally:
        if template_file.exists():
            template_file.unlink()



