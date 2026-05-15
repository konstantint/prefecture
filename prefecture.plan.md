# Implement `prefecture` (Prefect Edition)

Implement a data orchestration system using Prefect to generate and deliver AI-authored newsletters, with support for human-in-the-loop editing.

## User Review Required

> [!IMPORTANT]
> The user must provide `GEMINI_API_KEY` and Gmail API credentials (`GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`) in a `.env` file for full functionality. Instructions for obtaining Gmail credentials will be provided.

## Open Questions
None at this moment.

## Proposed Changes

We will implement the project in the following steps:

### Step 1: Project Initialization
- [NEW] `pyproject.toml`: Define dependencies.
- [NEW] `.env.example`: Template for environment variables.

### Step 2: Configuration & Templates
- [NEW] `configs/baby_digest.yaml`: Configuration for the baby digest.
- [NEW] `templates/baby_prompt.j2`: Jinja2 template for the prompt.
- [NEW] `templates/email_base.html.j2`: Jinja2 template for the email.

### Step 3: Core Modules
- [NEW] `prefecture/config.py`: Parse YAML configs.
- [NEW] `prefecture/templating.py`: Handle Jinja rendering and `days_ago` context loader.
- [NEW] `prefecture/agent.py`: Gemini API client wrapper.
- [NEW] `prefecture/notify.py`: ntfy.sh notification sender.
- [NEW] `prefecture/mailer.py`: Gmail API sender.

### Step 4: Prefect Flows
- [NEW] `prefecture/flows.py`: Define `generate_digest_flow` and `dispatch_digest_flow`.
- [NEW] `prefect.yaml`: Prefect deployment configuration.

---

## Verification Plan

Each step will be verified before proceeding.

### Step 1: Project Initialization
- **Action:** Run `uv sync` to install dependencies.
- **Verification:** Verify successful installation and environment setup.

### Step 2: Configuration & Templates
- **Action:** Create files.
- **Verification:** Manual inspection.

### Step 3: Core Modules
- **Action:** Implement and unit test modules.
- **Verification:**
    - `config.py`: Run a script to load and print `baby_digest.yaml`.
    - `templating.py`: Test rendering with mock data.
    - `agent.py`: Call Gemini API with a test prompt (requires API key).
    - `notify.py`: Send a test notification to `ntfy.sh`.
    - `mailer.py`: Send a test email via Gmail API (requires credentials).

### Step 4: Prefect Flows
- **Action:** Run flows locally.
- **Verification:**
    - `generate_digest_flow`: Check if `data/baby_digest/YYYY-MM-DD/digest.md` is created.
    - `dispatch_digest_flow`: Check if email is received and `.sent` file exists.
