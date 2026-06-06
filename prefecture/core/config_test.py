"""Tests for the configuration module."""

import os
import pathlib
import pytest
from prefecture.core import config

def write_yaml(path: pathlib.Path, content: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def test_load_config_simple(tmp_path):
    config_file = tmp_path / "config.yaml"
    write_yaml(
        config_file,
        """
        name: "test_flow"
        steps:
          - ntfy:
              topic: "news"
        """
    )
    res = config.load_config(config_file)
    assert res == {
        "name": "test_flow",
        "steps": [
            {"ntfy": {"topic": "news"}}
        ]
    }

def test_load_config_include_step(tmp_path):
    config_file = tmp_path / "config.yaml"
    step_file = tmp_path / "step.yaml"

    write_yaml(
        config_file,
        """
        name: "test_flow"
        steps:
          - !include:
              file_name: "step.yaml"
        """
    )
    write_yaml(
        step_file,
        """
        ntfy:
          topic: "news"
        """
    )

    res = config.load_config(config_file)
    assert res == {
        "name": "test_flow",
        "steps": [
            {"ntfy": {"topic": "news"}}
        ]
    }

def test_load_config_include_list_of_steps(tmp_path):
    config_file = tmp_path / "config.yaml"
    steps_file = tmp_path / "steps.yaml"

    write_yaml(
        config_file,
        """
        name: "test_flow"
        steps:
          - !include:
              file_name: "steps.yaml"
        """
    )
    write_yaml(
        steps_file,
        """
        - ntfy:
            topic: "news"
        - mailer:
            recipients: ["a@example.com"]
        """
    )

    res = config.load_config(config_file)
    assert res == {
        "name": "test_flow",
        "steps": [
            {"ntfy": {"topic": "news"}},
            {"mailer": {"recipients": ["a@example.com"]}}
        ]
    }

def test_load_config_recursive_include(tmp_path):
    config_file = tmp_path / "config.yaml"
    step_a_file = tmp_path / "step_a.yaml"
    step_b_file = tmp_path / "step_b.yaml"

    write_yaml(
        config_file,
        """
        name: "test_flow"
        steps:
          - !include:
              file_name: "step_a.yaml"
        """
    )
    # step_a includes step_b as a single step dict
    write_yaml(
        step_a_file,
        """
        !include:
          file_name: "step_b.yaml"
        """
    )
    write_yaml(
        step_b_file,
        """
        ntfy:
          topic: "inner"
        """
    )

    res = config.load_config(config_file)
    assert res == {
        "name": "test_flow",
        "steps": [
            {"ntfy": {"topic": "inner"}}
        ]
    }

def test_load_config_recursive_include_list(tmp_path):
    config_file = tmp_path / "config.yaml"
    step_a_file = tmp_path / "step_a.yaml"
    steps_b_file = tmp_path / "steps_b.yaml"

    write_yaml(
        config_file,
        """
        name: "test_flow"
        steps:
          - !include:
              file_name: "step_a.yaml"
        """
    )
    # step_a includes steps_b (which is a list)
    write_yaml(
        step_a_file,
        """
        !include:
          file_name: "steps_b.yaml"
        """
    )
    write_yaml(
        steps_b_file,
        """
        - ntfy:
            topic: "inner_a"
        - mailer:
            recipients: ["b@example.com"]
        """
    )

    res = config.load_config(config_file)
    assert res == {
        "name": "test_flow",
        "steps": [
            {"ntfy": {"topic": "inner_a"}},
            {"mailer": {"recipients": ["b@example.com"]}}
        ]
    }

def test_load_config_list_including_two_includes(tmp_path):
    config_file = tmp_path / "config.yaml"
    steps_a_file = tmp_path / "steps_a.yaml"
    step_b_file = tmp_path / "step_b.yaml"
    step_c_file = tmp_path / "step_c.yaml"

    write_yaml(
        config_file,
        """
        name: "test_flow"
        steps:
          - !include:
              file_name: "steps_a.yaml"
        """
    )
    # steps_a includes both step_b and step_c
    write_yaml(
        steps_a_file,
        """
        - !include:
            file_name: "step_b.yaml"
        - !include:
            file_name: "step_c.yaml"
        """
    )
    write_yaml(
        step_b_file,
        """
        ntfy:
          topic: "b"
        """
    )
    write_yaml(
        step_c_file,
        """
        mailer:
          recipients: ["c@example.com"]
        """
    )

    res = config.load_config(config_file)
    assert res == {
        "name": "test_flow",
        "steps": [
            {"ntfy": {"topic": "b"}},
            {"mailer": {"recipients": ["c@example.com"]}}
        ]
    }

def test_load_config_with_substitutions(tmp_path):
    config_file = tmp_path / "config.yaml"
    step_file = tmp_path / "step.yaml"

    write_yaml(
        config_file,
        """
        name: "test_flow"
        steps:
          - !include:
              file_name: "step.yaml"
              substitutions:
                topic_name: "news"
                recip: "b@example.com"
        """
    )
    write_yaml(
        step_file,
        """
        - ntfy:
            topic: "{{ topic_name }}"
        - mailer:
            recipients: ["{{ recip }}"]
        """
    )

    res = config.load_config(config_file)
    assert res == {
        "name": "test_flow",
        "steps": [
            {"ntfy": {"topic": "news"}},
            {"mailer": {"recipients": ["b@example.com"]}}
        ]
    }

def test_load_config_env_vars_in_resolved_config(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_TOPIC", "my_topic")
    monkeypatch.setenv("TEST_RECIPIENT", "env@example.com")

    config_file = tmp_path / "config.yaml"
    step_file = tmp_path / "step.yaml"

    write_yaml(
        config_file,
        """
        name: "test_flow"
        steps:
          - !include:
              file_name: "step.yaml"
        """
    )
    # step file uses $ env vars
    write_yaml(
        step_file,
        """
        - ntfy:
            topic: "$TEST_TOPIC"
        - mailer:
            recipients: ["${TEST_RECIPIENT}"]
        """
    )

    res = config.load_config(config_file)
    assert res == {
        "name": "test_flow",
        "steps": [
            {"ntfy": {"topic": "my_topic"}},
            {"mailer": {"recipients": ["env@example.com"]}}
        ]
    }

def test_load_config_recursion_exceeded(tmp_path):
    config_file = tmp_path / "config.yaml"
    step_file = tmp_path / "step.yaml"

    # Infinite loop: config includes step, step includes step.
    write_yaml(
        config_file,
        """
        name: "test_flow"
        steps:
          - !include:
              file_name: "step.yaml"
        """
    )
    write_yaml(
        step_file,
        """
        !include:
          file_name: "step.yaml"
        """
    )

    with pytest.raises(ValueError, match="include recursion exceeded"):
        config.load_config(config_file)
