"""Flows for the Prefecture system."""

import datetime
import pathlib

import prefect
from prefect import runtime

from prefecture import config
from prefecture import gemini
from prefecture import google_chat_reader
from prefecture import mailer
from prefecture import ntfy
from prefecture import prompt

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
    
    for step in cfg.get("steps", []):
        for step_type, step_cfg in step.items():
            if step_type == "prompt":
                generator = prompt.PromptGenerator(
                    config_dir=config_dir, **step_cfg
                )
                generator(run_dir=run_dir)
            elif step_type == "gemini":
                generator = gemini.GeminiGenerator(
                    config_dir=config_dir, **step_cfg
                )
                generator(run_dir=run_dir)
            elif step_type == "ntfy":
                sender = ntfy.NtfySender(config_dir=config_dir, **step_cfg)
                sender(run_dir=run_dir)
            elif step_type == "mailer":
                gmail_mailer = mailer.GmailMailer(
                    config_dir=config_dir, **step_cfg
                )
                gmail_mailer(run_dir=run_dir)
            elif step_type == "google_chat_reader":
                reader = google_chat_reader.GoogleChatReader(
                    config_dir=config_dir, **step_cfg
                )
                reader(run_dir=run_dir)
            else:
                print(f"Unknown step type: {step_type}")
