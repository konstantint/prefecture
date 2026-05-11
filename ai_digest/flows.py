import os
from pathlib import Path
from datetime import datetime, timedelta
from prefect import flow, task
from ai_digest.config import load_config
from ai_digest.prompt import PromptGenerator, register_loader, LastWeeksDigestLoader
from ai_digest.gemini import GeminiGenerator
from ai_digest.mailer import GmailMailer
from ai_digest.ntfy import NtfySender

@task
def create_prompt(prompt_config: dict, data_dir: Path, config_dir: Path) -> str:
    # Register loader with dependencies
    register_loader("last_weeks_digest", LastWeeksDigestLoader(data_dir))
    prompt_gen = PromptGenerator(config_dir=config_dir, **prompt_config)
    return prompt_gen()

@task
def save_markdown(config_name: str, content: str) -> str:
    today_str = datetime.now().strftime("%Y-%m-%d")
    data_dir = Path("data") / config_name / today_str
    data_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = data_dir / "digest.md"
    with open(file_path, "w") as f:
        f.write(content)
    return str(file_path)

@task
def check_lockfile(config_name: str) -> bool:
    today_str = datetime.now().strftime("%Y-%m-%d")
    lock_path = Path("data") / config_name / today_str / ".sent"
    return lock_path.exists()

@task
def read_markdown(config_name: str) -> str:
    today_str = datetime.now().strftime("%Y-%m-%d")
    file_path = Path("data") / config_name / today_str / "digest.md"
    
    if not file_path.exists():
        raise FileNotFoundError(f"Digest file not found at {file_path}")
        
    with open(file_path, "r") as f:
        return f.read()

@task
def write_lockfile(config_name: str):
    today_str = datetime.now().strftime("%Y-%m-%d")
    lock_path = Path("data") / config_name / today_str / ".sent"
    lock_path.touch()

@task
def generate_gemini_content(prompt_text: str, gemini_config: dict) -> str:
    gemini_gen = GeminiGenerator(**gemini_config)
    return gemini_gen(prompt_text)

@task
def send_ntfy_notification(content: str, file_path: str, ntfy_config: dict):
    ntfy_sender = NtfySender(**ntfy_config)
    notification_content = f"Path: {file_path}\n\n{content}"
    ntfy_sender(notification_content)

@task
def send_email(content: str, mailer_config: dict):
    mailer = GmailMailer(**mailer_config)
    mailer(content)

@flow
def generate_digest_flow(config_file: str = "./configs/baby_digest.yaml"):
    config = load_config(config_file)
    config_dir = Path(config_file).resolve().parent
    config_name = config["name"]
    
    data_dir = Path("data") / config_name
    
    prompt_text = create_prompt(config["prompt"], data_dir, config_dir)
    
    content = generate_gemini_content(prompt_text, config["gemini"])
    
    file_path = save_markdown(config_name, content)
    
    send_ntfy_notification(content, file_path, config["ntfy"])

@flow
def dispatch_digest_flow(config_file: str = "./configs/baby_digest.yaml"):
    config = load_config(config_file)
    config_name = config["name"]
    
    if check_lockfile(config_name):
        print(f"Digest for {config_name} already sent today. Skipping.")
        return
        
    try:
        content = read_markdown(config_name)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return
        
    send_email(content, config["mailer"])
    
    write_lockfile(config_name)

if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    
    root_dir = Path(__file__).resolve().parent.parent
    load_dotenv(dotenv_path=root_dir / ".env", override=True)
    
    if len(sys.argv) > 1:
        action = sys.argv[1]
        if action == "generate":
            generate_digest_flow()
        elif action == "dispatch":
            dispatch_digest_flow()
        else:
            print("Usage: python flows.py [generate|dispatch]")
    else:
        print("Usage: python flows.py [generate|dispatch]")
