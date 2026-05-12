import os
from pathlib import Path
from datetime import datetime
from prefect import flow
from prefect.runtime import flow_run
from ai_digest.config import load_config
from ai_digest.prompt import PromptGenerator
from ai_digest.gemini import GeminiGenerator
from ai_digest.ntfy import NtfySender
from ai_digest.mailer import GmailMailer

def generate_run_name(**kwargs) -> str:
    from prefect.runtime import flow_run
    from ai_digest.config import load_config
    from datetime import datetime
    
    config_file = kwargs.get("config_file") or flow_run.parameters.get("config_file")
    
    if not config_file:
        return f"run-flow-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
    config = load_config(config_file)
    name = config.get("name", "run-flow")
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{name}-{run_id}"

@flow(name="ai-digest", flow_run_name=generate_run_name)
def run_flow(config_file: str):
    config = load_config(config_file)
    
    name = config["name"]
    
    # run_dir is data/<name>/<date>
    today_str = datetime.now().strftime("%Y-%m-%d")
    run_dir = Path("data") / name / today_str
    run_dir.mkdir(parents=True, exist_ok=True)
    
    from ai_digest.prompt import register_loader, LastWeeksDigestLoader
    base_data_dir = Path("data") / name
    register_loader("last_weeks_digest", LastWeeksDigestLoader(base_data_dir))
    
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
            else:
                print(f"Unknown step type: {step_type}")
