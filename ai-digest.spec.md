# Technical Specification: `ai-digest` (Prefect Edition)

## 1. Overview
`ai-digest` is a Python-based data orchestration system built on **Prefect**. It automates the generation and delivery of AI-authored newsletters/digests. To support Human-in-the-Loop editing, the process is split into two asynchronous Prefect flows:
1.  **Generation Flow:** Collects context, renders a prompt, calls the Google Gemini API (with Google Search grounding), saves the markdown to disk, and sends a push notification via `ntfy`.
2.  **Dispatch Flow:** Runs later. It picks up the (potentially human-edited) markdown from the disk, compiles it into inline-styled HTML, emails it, and marks it as sent.

The project is designed as a reusable package that can be installed and used from any directory via a CLI.

## 2. Core Technologies
*   **Orchestration:** Prefect 3.x
*   **AI SDK:** `google-genai` (Native Google API client)
*   **Templating & Formatting:** `Jinja2`, `markdown`, `premailer`
*   **Alerting:** `requests` (for `ntfy` webhooks)
*   **Environment Management:** `uv`, `python-dotenv`

## 3. Directory Structure
The package is structured as follows:

```text
/ai-digest
├── pyproject.toml            # uv project definition
├── prefect.yaml              # Prefect deployments
└── ai_digest/                # Package source code
    ├── __init__.py
    ├── cli.py                # CLI entry point (no __file__ usage)
    ├── config.py             # Parses YAML configs with env var substitution
    ├── templating.py         # Low-level Jinja rendering helper
    ├── prompt.py             # PromptGenerator class & context loaders
    ├── gemini.py             # GeminiGenerator class
    ├── ntfy.py               # NtfySender class
    ├── mailer.py             # GmailMailer class (uses PackageLoader)
    ├── flows.py              # Prefect @flow definitions (no defaults)
    └── email_base.html.j2    # Email base template (encapsulated)
```

When used by a user, they can create a directory with their own configs and templates:

```text
/my-digest-job
├── prefect.yaml              # Prefect deployments pointing to ai_digest.flows
├── .env                      # Credentials
├── configs/
│   └── baby_digest.yaml      # Job configuration
└── templates/
    └── baby_prompt.j2        # Prompt template
```

## 4. Configuration Strategy (YAML + Prefect)

We use an object-oriented configuration approach where components are created from YAML dicts directly.

### A. Business Logic: `configs/<name>.yaml`
Defines the content and delivery of the digest. Supports environment variable substitution using `$VAR` or `${VAR}`.

```yaml
name: "baby_digest"
gemini:
  api_key: "$GEMINI_API_KEY"
  model: "gemini-3.1-flash-lite"
prompt:
  template_file: "../templates/baby_prompt.j2" # Relative to config file
  context_loaders:
    - type: "last_weeks_digest"
      assign_to: "last_weeks_digest"
mailer:
  gmail_client_id: "$GMAIL_CLIENT_ID"
  gmail_client_secret: "$GMAIL_CLIENT_SECRET"
  gmail_refresh_token: "$GMAIL_REFRESH_TOKEN"
  recipients: ["consumer@example.com"]
ntfy:
  host: "$NTFY_HOST"
  user: "$NTFY_USER"
  password: "$NTFY_PASSWORD"
  topic: "test"
```

### B. Scheduling Logic: `prefect.yaml`
This file tells Prefect *how* to run the Python code, passing the `config_file` path as a parameter.

```yaml
name: ai-digest
prefect-version: 3.0.0

deployments:
  - name: generate-baby-digest
    flow_name: generate_digest_flow
    entrypoint: ai_digest.flows:generate_digest_flow
    parameters:
      config_file: "./configs/baby_digest.yaml"
    schedules:
      - cron: "0 8 * * 0" # Sunday 8:00 AM

  - name: dispatch-baby-digest
    flow_name: dispatch_digest_flow
    entrypoint: ai_digest.flows:dispatch_digest_flow
    parameters:
      config_file: "./configs/baby_digest.yaml"
    schedules:
      - cron: "0 12 * * 0" # Sunday 12:00 PM
```

## 5. Core Components (Object-Oriented)

### A. `prompt.PromptGenerator`
Initialized with kwargs from `prompt:` YAML section.
*   Loads template (resolved relative to config file).
*   Executes registered context loaders (e.g., `last_weeks_digest`).
*   Applies `params`.
*   Callable: `__call__(self) -> str` returning the compiled prompt.

### B. `gemini.GeminiGenerator`
Initialized with kwargs from `gemini:` YAML section.
*   Uses `google-genai` SDK.
*   Instructs Gemini to output markdown with YAML frontmatter containing `subject`.
*   Callable: `__call__(self, prompt: str) -> str` returning the generated text.

### C. `mailer.GmailMailer`
Initialized with kwargs from `mailer:` YAML section.
*   Parses subject from frontmatter.
*   Encapsulates email template (`email_base.html.j2`).
*   Uses Gmail API to send email.
*   Callable: `__call__(self, markdown: str)` sending the email.

### D. `ntfy.NtfySender`
Initialized with kwargs from `ntfy:` YAML section.
*   Supports custom hosts and authentication.
*   Callable: `__call__(self, markdown: str)` sending the notification (including full content).

## 6. Flows

### A. Generation Flow (`generate_digest_flow`)
1.  Loads config from `config_file`.
2.  Creates prompt using `PromptGenerator`.
3.  Generates content using `GeminiGenerator`.
4.  Publishes a Prefect markdown artifact named "digest".
5.  Saves markdown to `data/{config_name}/{YYYY-MM-DD}/digest.md` (relative to CWD).
6.  Sends notification using `NtfySender`.

### B. Dispatch Flow (`dispatch_digest_flow`)
1.  Loads config from `config_file`.
2.  Checks for `.sent` lockfile.
3.  Reads markdown.
4.  Sends email using `GmailMailer`.
5.  Writes `.sent` lockfile.

## 7. CLI Usage

The package provides a console script `ai-digest`.

```bash
# Run generation flow
uvx ai-digest generate <path_to_config.yaml>

# Run dispatch flow
uvx ai-digest dispatch <path_to_config.yaml>
```
