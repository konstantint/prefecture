# Technical Specification: `ai-digest` (Prefect Edition)

## 1. Overview
`ai-digest` is a Python-based data orchestration system built on **Prefect**. It automates the generation and delivery of AI-authored newsletters/digests. To support Human-in-the-Loop editing, the process is split into two asynchronous Prefect flows:
1.  **Generation Flow:** Collects context, renders a prompt, calls the Google Gemini API (with Google Search grounding), saves the markdown to disk, and sends a push notification via `ntfy.sh`.
2.  **Dispatch Flow:** Runs later. It picks up the (potentially human-edited) markdown from the disk, compiles it into inline-styled HTML, emails it, and marks it as sent.

## 2. Core Technologies
*   **Orchestration:** Prefect 3.x
*   **AI SDK:** `google-genai` (Native Google API client)
*   **Templating & Formatting:** `Jinja2`, `markdown`, `premailer`
*   **Alerting:** `requests` (for `ntfy.sh` webhooks)
*   **Environment Management:** `uv`, `python-dotenv`

## 3. Directory Structure
```text
/ai-digest
├── pyproject.toml            # uv project definition
├── prefect.yaml              # Prefect deployments & schedules
├── configs/                  # Job-specific logic
│   └── baby_digest.yaml
├── templates/                # Jinja2 templates
│   ├── baby_prompt.j2
│   └── email_base.html.j2
├── data/                     # Data Lake / Local Outbox
│   └── baby_digest/
│       └── 2023-10-25/       # YYYY-MM-DD
│           ├── digest.md     # The generated (and editable) text
│           └── .sent         # Lockfile to prevent double-emailing
└── src/
    └── ai_digest/
        ├── __init__.py
        ├── config.py         # Parses YAML configs
        ├── templating.py     # Jinja processing & Context loaders
        ├── agent.py          # Google GenAI integration
        ├── notify.py         # ntfy.sh integration
        ├── mailer.py         # Markdown -> HTML -> Email dispatch
        └── flows.py          # Prefect @flow definitions
```

## 4. Configuration Strategy (YAML + Prefect)

We will use a hybrid configuration approach to maximize flexibility.

### A. Business Logic: `configs/<name>.yaml`
Defines the content of the digest.
```yaml
name: "baby_digest"
model: "gemini-3.1-pro-preview"
prompt:
  template_file: "baby_prompt.j2"
  context_loaders:
    - type: "days_ago"
      days: 7
      assign_to: "last_weeks_digest"
delivery:
  subject_template: "Weekly Digest: {{ date_from }} to {{ date_to }}"
  recipients: ["consumer@example.com"]
  email_template: "email_base.html.j2"
  mailer_type: "smtp" # or "gmail"
notifications:
  ntfy_topic: "my_secret_ntfy_topic_123"
```

### B. Scheduling Logic: `prefect.yaml`
This file tells Prefect *how* to run your Python code, allowing you to pass the `config_name` as a parameter to the generic flows.

```yaml
name: ai-digest
prefect-version: 3.0.0

deployments:
  # --- BABY DIGEST ---
  - name: generate-baby-digest
    flow_name: generate_digest_flow
    entrypoint: src/ai_digest/flows.py:generate_digest_flow
    parameters:
      config_name: "baby_digest"
    schedules:
      - cron: "0 8 * * 0" # Sunday 8:00 AM

  - name: dispatch-baby-digest
    flow_name: dispatch_digest_flow
    entrypoint: src/ai_digest/flows.py:dispatch_digest_flow
    parameters:
      config_name: "baby_digest"
    schedules:
      - cron: "0 12 * * 0" # Sunday 12:00 PM (4 hours for human review)
```

### C. Credentials (`.env`)
Sensitive credentials must not be stored in YAML files or committed to source control. They should be stored in a `.env` file in the project root.

```env
GEMINI_API_KEY=your_gemini_api_key
GMAIL_CLIENT_ID=your_gmail_client_id
GMAIL_CLIENT_SECRET=your_gmail_client_secret
GMAIL_REFRESH_TOKEN=your_gmail_refresh_token
```
The `dispatch_email` task will load these variables to authenticate with the Gmail API.

## 5. Flow 1: Generation (`generate_digest_flow`)

**Responsibility:** Gather data, prompt Gemini, save to disk, and notify the user.

### Logic (Prefect Tasks):
1.  **`load_configuration`**: Reads `configs/{config_name}.yaml`.
2.  **`prepare_context`**: Executes date math and fetches `last_weeks_digest` from the `data/` directory.
3.  **`render_prompt`**: Merges context into `templates/{template_file}`.
4.  **`call_gemini_api`**: (See Agent Implementation below).
5.  **`save_markdown`**: Writes the API output to `data/{config_name}/{YYYY-MM-DD}/digest.md`.
6.  **`send_notification`**: Posts to `https://ntfy.sh/{topic}`.

### Agent Implementation (`agent.py`)
Adapted from Google AI Studio. Note that we accumulate the stream to return a single string so Prefect can log/track it, and write it to disk cleanly.

```python
import os
from google import genai
from google.genai import types
from prefect import task

@task(retries=3, retry_delay_seconds=30)
def generate_content(prompt_text: str, model_name: str = "gemini-3.1-pro-preview") -> str:
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    # Using Gemini 3.1 Pro Preview with High Thinking and Search
    generate_content_config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_level="HIGH"),
        tools=[types.Tool(googleSearch=types.GoogleSearch())],
    )
    
    response_stream = client.models.generate_content_stream(
        model=model_name,
        contents=[prompt_text],
        config=generate_content_config,
    )
    
    # Accumulate chunks into a single string
    full_text = ""
    for chunk in response_stream:
        if chunk.text:
            full_text += chunk.text
            
    return full_text
```

### Notification Implementation (`notify.py`)
```python
import requests
from prefect import task

@task
def notify_ready(topic: str, config_name: str, file_path: str):
    if not topic:
        return
    requests.post(
        f"https://ntfy.sh/{topic}",
        data=f"Digest '{config_name}' generated.\nReady for review at:\n{file_path}".encode('utf-8'),
        headers={"Title": "AI Digest Ready", "Tags": "robot,page_facing_up"}
    )
```

## 6. Flow 2: Dispatch (`dispatch_digest_flow`)

**Responsibility:** Pick up the `.md` file, compile HTML, email it, and mark as sent.

### Logic (Prefect Tasks):
1.  **`load_configuration`**: Reads `configs/{config_name}.yaml`.
2.  **`check_lockfile`**: Checks if `data/{config_name}/{today}/.sent` exists. If yes, exit gracefully (prevents double emails).
3.  **`read_markdown`**: Checks if `data/{config_name}/{today}/digest.md` exists. If not, raise an error (flow fails, perhaps user deleted it or generation failed). Reads the content.
4.  **`compile_email_html`**: Converts markdown to HTML. Wraps it in `email_base.html.j2`. Runs it through `premailer.transform()`.
5.  **`dispatch_email`**: Uses Gmail API (configured via environment variables `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`) to send to recipients.
6.  **`write_lockfile`**: Creates the empty `.sent` file to ensure idempotency.

## 7. Implementation & Usage Guide (For AI Coding Assistant)

When passing this document to an AI to generate the codebase, provide these specific instructions:

1.  **Frameworks:** "Use `prefect` decorators (`@task`, `@flow`) for all functions in `flows.py`. Use the new `google-genai` SDK exactly as modeled in the specification for `agent.py`."
2.  **Path Resolution:** "Ensure all file paths (configs, templates, data) are resolved absolutely using `pathlib.Path` relative to the root `ai-digest` directory, or loaded via environment variable fallbacks."
3.  **Context Loaders:** "Implement the `context_loaders` logic inside `templating.py` exactly as previously discussed: scan the data directory, sort by date descending, skip today's run, and return the markdown text of the previous successful run."
4.  **Templating Context:** "The dispatch flow also needs to render the `subject_template`. Make sure date variables (`date_from`, `date_to`) are available to it."
5.  **Idempotency:** "Rely on Prefect's native `@task(retries=X)` for API timeouts, but rely on the physical `.sent` lockfile inside the data directory to prevent the Dispatch Flow from mailing the same digest twice."
6.  **No Pause logic:** "Do *not* use Prefect's `pause_flow_run`. The human-in-the-loop requirement is strictly handled by the user editing the markdown file between the two separate flow runs." 

### Developer Workflow
Once implemented, the user will interact with the system via `uv` and `prefect`:

```bash
# 1. Install dependencies
uv sync

# 2. Start the local Prefect Server (in terminal 1)
uv run prefect server start

# 3. Register the schedules/deployments to the server
uv run prefect deploy --all

# 4. Start the Prefect worker to execute scheduled jobs (in terminal 2)
uv run prefect worker start --pool "default-agent-pool"

# Optional: Run a flow manually right now
uv run prefect deployment run 'dispatch_digest_flow/dispatch-baby-digest'
```
