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

    # step1 fallback: empty
    assert graph[step1] == set()
    # step2 fallback: {step1}
    assert graph[step2] == {step1}
    # step3 has dependencies {"/file1"}, but no step produces it -> resolves to empty step deps
    assert graph[step3] == set()
    # step4 fallback: {step1, step2, step3}
    assert graph[step4] == {step1, step2, step3}


def test_build_dependency_graph_all_ops(tmp_path):
    run_dir = tmp_path / "run"
    config_dir = tmp_path / "config"
    run_dir.mkdir()
    config_dir.mkdir()

    from prefecture.operations.copyfile import CopyFile
    from prefecture.operations.gemini import GeminiGenerator
    from prefecture.operations.gemini_image import GeminiImageGenerator
    from prefecture.operations.gemini_tts import GeminiTtsGenerator
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

    gemini_tts = GeminiTtsGenerator(
        config_dir=config_dir,
        run_dir=run_dir,
        api_key="dummy_key",
        prompt_file_name="prompt.txt",
        output_file_name="audio.wav",
        voice="Algieba",
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
        gemini_tts,
        mailer,
        ntfy,
    ]
    graph = execution._build_dependency_graph(steps)

    # 1. chat_reader (dependencies = empty set, outputs: chat files)
    assert graph[chat_reader] == set()
    assert chat_reader.outputs == {
        str((run_dir / "chat" / "raw" / "space-one.json").resolve()),
        str((run_dir / "chat" / "data.json").resolve()),
    }

    # 2. copyfile (dependencies = {input.txt} -> unresolved -> empty step deps)
    assert graph[copyfile] == set()
    assert copyfile.outputs == {str((run_dir / "output.txt").resolve())}

    # 3. templater (dependencies: template.j2, input.txt, test.db -> all unresolved -> empty step deps)
    assert graph[templater] == set()
    assert templater.outputs == {str((run_dir / "prompt.txt").resolve())}

    # 4. gemini (dependencies: prompt.txt -> produced by templater)
    assert graph[gemini] == {templater}
    assert gemini.outputs == {str((run_dir / "digest.md").resolve())}

    # 5. gemini_image (dependencies: prompt.txt -> produced by templater)
    assert graph[gemini_image] == {templater}
    assert gemini_image.outputs == {str((run_dir / "image.png").resolve())}

    # 6. gemini_tts (dependencies: prompt.txt -> produced by templater)
    assert graph[gemini_tts] == {templater}
    assert gemini_tts.outputs == {str((run_dir / "audio.wav").resolve())}

    # 7. mailer (dependencies: digest.md -> gemini, image.png -> gemini_image)
    assert graph[mailer] == {gemini, gemini_image}
    assert mailer.outputs == set()

    # 8. ntfy (dependencies = None -> depends on all preceding steps)
    assert graph[ntfy] == {
        chat_reader,
        copyfile,
        templater,
        gemini,
        gemini_image,
        gemini_tts,
        mailer,
    }
    assert ntfy.outputs == set()


def test_has_loop():
    class DummyStep:
        pass

    s1 = DummyStep()
    s2 = DummyStep()
    s3 = DummyStep()

    # Loop s1 -> s2 -> s3 -> s1
    graph_cycle = {s1: {s2}, s2: {s3}, s3: {s1}}
    assert execution._has_loop(graph_cycle) is True

    # DAG s1 -> s2 -> s3
    graph_dag = {s1: set(), s2: {s1}, s3: {s2}}
    assert execution._has_loop(graph_dag) is False


def test_graph_executes_in_topological_order_and_detects_loops(tmp_path):
    run_dir = tmp_path / "run"
    config_dir = tmp_path / "config"
    run_dir.mkdir()
    config_dir.mkdir()

    execution_order = []

    class DummyStep:

        def __init__(self, name, dependencies=None, outputs=None):
            self.name = name
            self._dependencies = dependencies or set()
            self._outputs = outputs or set()

        def __call__(self):
            import time

            time.sleep(0.05)
            execution_order.append(self.name)

        @property
        def dependencies(self):
            return self._dependencies

        @property
        def outputs(self):
            return self._outputs

    # Create step objects
    s1 = DummyStep("s1", outputs={"/fileA"})
    s2 = DummyStep("s2", dependencies={"/fileA"})
    s3 = DummyStep("s3", outputs={"/fileB"})
    s4 = DummyStep("s4", dependencies={"/fileA", "/fileB"})

    with mock.patch(
        "prefecture.core.execution._instantiate_steps"
    ) as mock_instantiate:
        mock_instantiate.return_value = [s1, s2, s3, s4]

        execution.graph({}, run_dir, config_dir)

        # Verify s1 executed before s2 and s4, s3 executed before s4
        assert execution_order.index("s1") < execution_order.index("s2")
        assert execution_order.index("s1") < execution_order.index("s4")
        assert execution_order.index("s3") < execution_order.index("s4")

    # Check loop detection
    s1_cycle = DummyStep("s1", dependencies={"/fileB"}, outputs={"/fileA"})
    s2_cycle = DummyStep("s2", dependencies={"/fileA"}, outputs={"/fileB"})

    with mock.patch(
        "prefecture.core.execution._instantiate_steps"
    ) as mock_instantiate:
        mock_instantiate.return_value = [s1_cycle, s2_cycle]
        with pytest.raises(ValueError) as exc_info:
            execution.graph({}, run_dir, config_dir)
        assert "contains a loop" in str(exc_info.value)

    # Check duplicate outputs detection
    s1_dup = DummyStep("s1", outputs={"/fileA"})
    s2_dup = DummyStep("s2", outputs={"/fileA"})

    with mock.patch(
        "prefecture.core.execution._instantiate_steps"
    ) as mock_instantiate:
        mock_instantiate.return_value = [s1_dup, s2_dup]
        with pytest.raises(ValueError) as exc_info:
            execution.graph({}, run_dir, config_dir)
        assert "produced by multiple steps" in str(exc_info.value)


