"""Tests for the execution module."""

import pathlib
import sys
from unittest import mock

import pytest

from prefecture.core import execution


def test_pythonpath_prepended():
    original_path = list(sys.path)
    dummy_path = pathlib.Path("/tmp/prefecture_test_dummy_path_123")
    resolved_dummy_path = str(dummy_path.resolve())

    # Ensure it's not currently in path
    if resolved_dummy_path in sys.path:
        sys.path.remove(resolved_dummy_path)

    with execution.pythonpath_prepended([str(dummy_path)]):
        assert sys.path[0] == resolved_dummy_path

    assert sys.path == original_path


def test_pythonpath_prepended_restores_existing():
    # If the path already existed in sys.path at a different position
    dummy_path = pathlib.Path("/tmp/prefecture_test_dummy_path_existing")
    resolved_dummy_path = str(dummy_path.resolve())

    # Add it to the end
    sys.path.append(resolved_dummy_path)
    original_path = list(sys.path)

    with execution.pythonpath_prepended([str(dummy_path)]):
        assert sys.path[0] == resolved_dummy_path
        # It should only be at index 0
        assert sys.path.count(resolved_dummy_path) == 1
        assert sys.path[-1] != resolved_dummy_path

    # After exit, it should be back at the end as in original_path
    assert sys.path == original_path

    # Clean up sys.path
    if resolved_dummy_path in sys.path:
        sys.path.remove(resolved_dummy_path)


def test_sequential_executes_steps(tmp_path):
    run_dir = tmp_path / "run"
    config_dir = tmp_path / "config"

    cfg = {
        "steps": [
            {
                "jinja2": {
                    "template_file": "dummy.j2",
                    "output_file_name": "out.txt",
                }
            }
        ]
    }

    # Mock Jinja2Templater
    mock_templater_class = mock.MagicMock()
    mock_templater_instance = mock.MagicMock()
    mock_templater_class.return_value = mock_templater_instance

    with mock.patch.dict(
        execution.STEP_MAP,
        {"jinja2": "mock_module.MockTemplater"},
        clear=False,
    ):
        with mock.patch("importlib.import_module") as mock_import:
            mock_module = mock.MagicMock()
            setattr(mock_module, "MockTemplater", mock_templater_class)
            mock_import.return_value = mock_module

            execution.sequential(cfg, run_dir, config_dir)

            mock_import.assert_called_once_with("mock_module")
            mock_templater_class.assert_called_once_with(
                config_dir=config_dir,
                run_dir=run_dir,
                template_file="dummy.j2",
                output_file_name="out.txt",
            )
            mock_templater_instance.assert_called_once_with()
