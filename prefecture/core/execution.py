"""Execution logic for Prefecture flows."""

import contextlib
import importlib
import pathlib
import sys
from typing import Any, Dict, List

STEP_MAP = {
    "jinja2": "prefecture.operations.templating.Jinja2Templater",
    "gemini": "prefecture.operations.gemini.GeminiGenerator",
    "gemini_image": "prefecture.operations.gemini_image.GeminiImageGenerator",
    "ntfy": "prefecture.operations.ntfy.NtfySender",
    "mailer": "prefecture.operations.mailer.GmailMailer",
    "google_chat_reader": "prefecture.operations.google_chat_reader.GoogleChatReader",
    "copyfile": "prefecture.operations.copyfile.CopyFile",
}


@contextlib.contextmanager
def pythonpath_prepended(paths: List[str]):
    """Context manager to temporarily prepend paths to sys.path."""
    original_path = list(sys.path)
    try:
        for p in reversed(paths):
            abs_path = str(pathlib.Path(p).resolve())
            if abs_path in sys.path:
                sys.path.remove(abs_path)
            sys.path.insert(0, abs_path)
        yield
    finally:
        sys.path[:] = original_path


def sequential(
    cfg: Dict[str, Any], run_dir: pathlib.Path, config_dir: pathlib.Path
):
    """Executes the steps in the configuration sequentially."""
    for step in cfg.get("steps", []):
        for step_type, step_cfg in step.items():
            class_path = STEP_MAP.get(step_type, step_type)
            module_path, class_name = class_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            step_class = getattr(module, class_name)

            step_cfg = step_cfg or {}
            step_instance = step_class(
                config_dir=config_dir, run_dir=run_dir, **step_cfg
            )
            step_instance()
