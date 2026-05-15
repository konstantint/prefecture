import os
from pathlib import Path
from datetime import datetime
from prefect import flow
from prefect.runtime import flow_run
from prefecture.config import load_config
from prefecture.prompt import PromptGenerator
from prefecture.gemini import GeminiGenerator
from prefecture.ntfy import NtfySender
from prefecture.mailer import GmailMailer
from prefecture.google_chat_reader import GoogleChatReader

def generate_run_name(**kwargs) -> str:
    from prefect.runtime import flow_run
    from prefecture.config import load_config
    from datetime import datetime
    
    config_file = kwargs.get("config_file") or flow_run.parameters.get("config_file")
    
    if not config_file:
        return f"run-flow-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
    config = load_config(config_file)
    name = config.get("name", "run-flow")
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{name}-{run_id}"

@flow(name="prefecture", log_prints=True, flow_run_name=generate_run_name)
def run_flow(config_file: str):
    config = load_config(config_file)
    
    name = config["name"]
    
    # run_dir is data/<name>/<date>
    today_str = datetime.now().strftime("%Y-%m-%d")
    run_dir = Path("data") / name / today_str
    run_dir.mkdir(parents=True, exist_ok=True)
    

    
    config_dir = Path(config_file).resolve().parent
    
    for step in config.get("steps", []):
        for step_type, step_cfg in step.items():
            if step_type == "prompt":
                generator = PromptGenerator(config_dir=config_dir, **step_cfg)
                generator(run_dir=run_dir)
            elif step_type == "gemini":
                generator = GeminiGenerator(config_dir=config_dir, **step_cfg)
                generator(run_dir=run_dir)
            elif step_type == "ntfy":
                sender = NtfySender(config_dir=config_dir, **step_cfg)
                sender(run_dir=run_dir)
            elif step_type == "mailer":
                mailer = GmailMailer(config_dir=config_dir, **step_cfg)
                mailer(run_dir=run_dir)
            elif step_type == "google_chat_reader":
                reader = GoogleChatReader(config_dir=config_dir, **step_cfg)
                reader(run_dir=run_dir)
            else:
                print(f"Unknown step type: {step_type}")
