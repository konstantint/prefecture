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


def test_build_dependency_graph_fallback():
    # Test fallback behavior (when dependencies is not defined, or returns None)
    class StepNoDeps:
        pass

    class StepNoneDeps:
        @property
        def dependencies(self):
            return None

    class StepWithDeps:
        @property
        def dependencies(self):
            return {"/file1"}

    step1 = StepNoDeps()
    step2 = StepNoneDeps()
    step3 = StepWithDeps()
    step4 = StepNoDeps()

    steps = [step1, step2, step3, step4]
    graph = execution._build_dependency_graph(steps)

    assert graph[step1] == set()
    assert graph[step2] == {step1}
    assert graph[step3] == {"/file1"}
    assert graph[step4] == {step1, step2, step3}


def test_build_dependency_graph_all_ops(tmp_path):
    run_dir = tmp_path / "run"
    config_dir = tmp_path / "config"
    run_dir.mkdir()
    config_dir.mkdir()

    from prefecture.operations.copyfile import CopyFile
    from prefecture.operations.gemini import GeminiGenerator
    from prefecture.operations.gemini_image import GeminiImageGenerator
    from prefecture.operations.google_chat_reader import GoogleChatReader
    from prefecture.operations.mailer import GmailMailer
    from prefecture.operations.ntfy import NtfySender
    from prefecture.operations.templating import Jinja2Templater

    chat_reader = GoogleChatReader(
        config_dir=str(config_dir),
        run_dir=str(run_dir),
        client_id="id",
        client_secret="secret",
        refresh_token="token",
        spaces=[{"id": "space1", "display_name": "Space One"}],
    )

    copyfile = CopyFile(
        config_dir=config_dir,
        run_dir=run_dir,
        from_path="input.txt",
        to_path="output.txt",
    )

    templater = Jinja2Templater(
        config_dir=config_dir,
        run_dir=run_dir,
        template_file="template.j2",
        output_file_name="prompt.txt",
        context_loaders=[
            {
                "type": "run_dir_file",
                "assign_to": "data",
                "params": {"file_name": "input.txt"},
            },
            {
                "type": "sqlalchemy",
                "assign_to": "db_data",
                "params": {"db_url": "sqlite:///test.db", "query": "SELECT 1"},
            },
        ],
    )

    gemini = GeminiGenerator(
        config_dir=config_dir,
        run_dir=run_dir,
        api_key="dummy_key",
        prompt_file_name="prompt.txt",
        output_file_name="digest.md",
    )

    gemini_image = GeminiImageGenerator(
        config_dir=config_dir,
        run_dir=run_dir,
        api_key="dummy_key",
        prompt_file_name="prompt.txt",
        output_file_name="image.png",
    )

    mailer = GmailMailer(
        config_dir=config_dir,
        run_dir=run_dir,
        gmail_client_id="id",
        gmail_client_secret="secret",
        gmail_refresh_token="token",
        recipients=["a@example.com"],
        content_file_name="digest.md",
        attachments=[{"image_file_name": "image.png"}],
    )

    ntfy = NtfySender(
        config_dir=config_dir,
        run_dir=run_dir,
        topic="topic",
        content_file_name="digest.md",
    )

    steps = [
        chat_reader,
        copyfile,
        templater,
        gemini,
        gemini_image,
        mailer,
        ntfy,
    ]
    graph = execution._build_dependency_graph(steps)

    # 1. chat_reader (dependencies = empty set)
    assert graph[chat_reader] == set()
    assert chat_reader.outputs == {
        str((run_dir / "chat" / "raw" / "space-one.json").resolve()),
        str((run_dir / "chat" / "data.json").resolve()),
    }

    # 2. copyfile (dependencies = {from_path})
    assert graph[copyfile] == {str((run_dir / "input.txt").resolve())}
    assert copyfile.outputs == {str((run_dir / "output.txt").resolve())}

    # 3. templater (dependencies = union of template_file, context loaders)
    assert graph[templater] == {
        str((config_dir / "template.j2").resolve()),
        str((run_dir / "input.txt").resolve()),
        str(pathlib.Path("test.db").resolve()),
        "sqlite:///test.db",
    }
    assert templater.outputs == {str((run_dir / "prompt.txt").resolve())}

    # 4. gemini
    assert graph[gemini] == {str((run_dir / "prompt.txt").resolve())}
    assert gemini.outputs == {str((run_dir / "digest.md").resolve())}

    # 5. gemini_image
    assert graph[gemini_image] == {str((run_dir / "prompt.txt").resolve())}
    assert gemini_image.outputs == {str((run_dir / "image.png").resolve())}

    # 6. mailer
    assert graph[mailer] == {
        str((run_dir / "digest.md").resolve()),
        str((run_dir / "image.png").resolve()),
    }
    assert mailer.outputs == set()

    # 7. ntfy
    assert graph[ntfy] == {str((run_dir / "digest.md").resolve())}
    assert ntfy.outputs == set()

