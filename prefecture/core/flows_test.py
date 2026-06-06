"""Tests for flows in Prefecture."""

import datetime
import pathlib
import shutil
import sys

from prefecture.core import flows
import pytest



@pytest.fixture
def test_env(tmp_path):
    """Fixture to create a test environment with templates and configs."""
    template_file = tmp_path / "test_prompt.j2"
    with open(template_file, "w") as f:
        f.write("Hello {{ name }}!")

    shorthand_config = tmp_path / "shorthand.yaml"
    with open(shorthand_config, "w") as f:
        f.write(f"""
name: test_shorthand
steps:
  - jinja2:
      template_file: "{template_file}"
      output_file_name: "prompt.md"
      params:
        name: "Shorthand"
""")

    fullclass_config = tmp_path / "fullclass.yaml"
    with open(fullclass_config, "w") as f:
        f.write(f"""
name: test_fullclass
steps:
  - prefecture.operations.templating.Jinja2Templater:
      template_file: "{template_file}"
      output_file_name: "prompt.md"
      params:
        name: "FullClass"
""")

    # Create custom step module in tmp_path
    custom_step_file = tmp_path / "custom_step.py"
    with open(custom_step_file, "w") as f:
        f.write("""
import pathlib

class CustomStep:
    def __init__(self, config_dir, run_dir, msg="Custom"):
        self.msg = msg
        self.run_dir = run_dir

    def __call__(self):
        out_path = self.run_dir / "custom.txt"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            f.write(self.msg)
""")

    custom_config = tmp_path / "custom.yaml"
    with open(custom_config, "w") as f:
        f.write(f"""
name: test_custom
prepend_to_pythonpath: ["{tmp_path}"]
steps:
  - custom_step.CustomStep:
      msg: "Hello Custom!"
""")

    yield tmp_path, shorthand_config, fullclass_config, custom_config

    # Cleanup
    for name in ["test_shorthand", "test_fullclass", "test_custom"]:
        p = pathlib.Path("data") / name
        if p.exists():
            shutil.rmtree(p)


def test_run_flow_shorthand(test_env):
    """Test running flow with shorthand step name."""
    _, shorthand_config, _, _ = test_env
    flows.run_flow(str(shorthand_config))

    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    out_path = (
        pathlib.Path("data") / "test_shorthand" / today_str / "prompt.md"
    )

    assert out_path.exists()
    with open(out_path, "r") as f:
        assert f.read() == "Hello Shorthand!"


def test_run_flow_fullclass(test_env):
    """Test running flow with full class name."""
    _, _, fullclass_config, _ = test_env
    flows.run_flow(str(fullclass_config))

    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    out_path = (
        pathlib.Path("data") / "test_fullclass" / today_str / "prompt.md"
    )

    assert out_path.exists()
    with open(out_path, "r") as f:
        assert f.read() == "Hello FullClass!"


def test_run_flow_custom(test_env):
    """Test running flow with custom PYTHONPATH and step."""
    tmp_path, _, _, custom_config = test_env
    resolved_tmp_path = str(pathlib.Path(tmp_path).resolve())

    assert resolved_tmp_path not in sys.path

    flows.run_flow(str(custom_config))

    assert resolved_tmp_path not in sys.path

    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    out_path = (
        pathlib.Path("data") / "test_custom" / today_str / "custom.txt"
    )

    assert out_path.exists()
    with open(out_path, "r") as f:
        assert f.read() == "Hello Custom!"
