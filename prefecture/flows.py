"""Flows for the Prefecture system."""

import datetime
import importlib
import pathlib
import sys



import prefect
from prefect import runtime

from prefecture import config

STEP_MAP = {
    "jinja2": "prefecture.templating.Jinja2Templater",
    "gemini": "prefecture.gemini.GeminiGenerator",
    "gemini_image": "prefecture.gemini_image.GeminiImageGenerator",
    "ntfy": "prefecture.ntfy.NtfySender",
    "mailer": "prefecture.mailer.GmailMailer",
    "google_chat_reader": "prefecture.google_chat_reader.GoogleChatReader",
    "copyfile": "prefecture.copyfile.CopyFile",
}


def generate_run_name(**kwargs) -> str:
    """Generates a run name based on the config file."""
    config_file = kwargs.get("config_file") or runtime.flow_run.parameters.get(
        "config_file"
    )

    if not config_file:
        return f"run-flow-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"

    cfg = config.load_config(config_file)
    name = cfg.get("name", "run-flow")
    run_id = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{name}-{run_id}"


@prefect.flow(name="prefecture", log_prints=True, flow_run_name=generate_run_name)
def run_flow(config_file: str):
    """Runs the flow based on the provided config file."""
    cfg = config.load_config(config_file)

    name = cfg["name"]

    # run_dir is data/<name>/<date>
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    run_dir = pathlib.Path("data") / name / today_str
    run_dir.mkdir(parents=True, exist_ok=True)

    config_dir = pathlib.Path(config_file).resolve().parent

    for p in reversed(cfg.get("prepend_to_pythonpath", [])):
        abs_path = str(pathlib.Path(p).resolve())
        if abs_path in sys.path:
            sys.path.remove(abs_path)
        sys.path.insert(0, abs_path)

    for step in cfg.get("steps", []):

        for step_type, step_cfg in step.items():
            class_path = STEP_MAP.get(step_type, step_type)
            module_path, class_name = class_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            step_class = getattr(module, class_name)

            step_cfg = step_cfg or {}
            step_instance = step_class(config_dir=config_dir, **step_cfg)
            step_instance(run_dir=run_dir)


