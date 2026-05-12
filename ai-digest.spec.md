# Technical Specification: `ai-digest` (Prefect Edition) - Step-Based Architecture

## 1. Overview
`ai-digest` is a Python-based data orchestration system built on **Prefect**. It automates the generation and delivery of AI-authored newsletters/digests. The process is driven by a single Prefect flow (`run_flow`) that executes a sequence of steps defined in a YAML configuration file. Components are object-oriented and callable as Prefect tasks.

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
    ├── cli.py                # CLI entry point
    ├── config.py             # Parses YAML configs with env var substitution
    ├── templating.py         # Low-level Jinja rendering helper
    ├── prompt.py             # PromptGenerator class & context loaders
    ├── gemini.py             # GeminiGenerator class
    ├── ntfy.py               # NtfySender class
    ├── mailer.py             # GmailMailer class
    ├── flows.py              # Prefect @flow definition (single flow)
    └── email_base.html.j2    # Email base template (encapsulated)
```

When used by a user, they can create a directory with their own configs and templates:

```text
/my-digest-job
├── prefect.yaml              # Prefect deployments pointing to ai_digest.flows:run_flow
├── .env                      # Credentials
├── configs/
│   ├── generate.yaml         # Config for generation steps
│   └── dispatch.yaml         # Config for dispatch steps
└── templates/
    └── prompt.j2             # Prompt template
```

## 4. Configuration Strategy (YAML + Prefect)

We use a step-based configuration approach. The YAML file defines a list of steps to execute.

### A. Business Logic: `configs/<name>.yaml`
Defines the content and delivery of the digest. Supports environment variable substitution using `$VAR` or `${VAR}`.

Example `generate.yaml`:
```yaml
name: "baby_digest_generate"
steps:
  - prompt:
      template_file: "../templates/baby_prompt.j2"
      context_loaders:
        - type: "last_weeks_digest"
          assign_to: "last_weeks_digest"
      output_file_name: "prompt.md"
  - gemini:
      api_key: "$GEMINI_API_KEY"
      model: "gemini-3.1-flash-lite"
      prompt_file_name: "prompt.md"
      output_file_name: "digest.md"
  - ntfy:
      host: "$NTFY_HOST"
      user: "$NTFY_USER"
      password: "$NTFY_PASSWORD"
      topic: "test"
      content_file_name: "digest.md"
```

Example `dispatch.yaml`:
```yaml
name: "baby_digest_dispatch"
steps:
  - mailer:
      gmail_client_id: "$GMAIL_CLIENT_ID"
      gmail_client_secret: "$GMAIL_CLIENT_SECRET"
      gmail_refresh_token: "$GMAIL_REFRESH_TOKEN"
      recipients: ["consumer@example.com"]
      content_file_name: "digest.md"
```

### B. Scheduling Logic: `prefect.yaml`
This file tells Prefect *how* to run the Python code, passing the `config_file` path as a parameter to the generic `run_flow`.

```yaml
name: ai-digest
prefect-version: 3.0.0

deployments:
  - name: generate-baby-digest
    flow_name: run_flow
    entrypoint: ai_digest.flows:run_flow
    parameters:
      config_file: "./configs/baby_digest_generate.yaml"
    schedules:
      - cron: "0 8 * * 0"

  - name: dispatch-baby-digest
    flow_name: run_flow
    entrypoint: ai_digest.flows:run_flow
    parameters:
      config_file: "./configs/baby_digest_dispatch.yaml"
    schedules:
      - cron: "0 12 * * 0"
```

## 5. Core Components (Object-Oriented Tasks)

All components are classes with a `__call__` method decorated with `@task`. They accept `config_dir` in `__init__` and `run_dir` in `__call__`.

### A. `prompt.PromptGenerator`
*   Loads template (resolved relative to config file).
*   Executes registered context loaders.
*   Applies `params`.
*   Writes output to `run_dir / output_file_name`.
*   Publishes a Prefect markdown artifact named "prompt".

### B. `gemini.GeminiGenerator`
*   Reads prompt from `run_dir / prompt_file_name`.
*   Uses `google-genai` SDK.
*   Supports optional Google Search grounding via `use_google_search` parameter.
*   Instructs Gemini to output markdown with YAML frontmatter containing `subject`.
*   Writes output to `run_dir / output_file_name`.
*   Publishes a Prefect markdown artifact named "digest".

### C. `mailer.GmailMailer`
*   Reads content from `run_dir / content_file_name`.
*   Parses subject from frontmatter.
*   Encapsulates email template (`email_base.html.j2`).
*   Uses Gmail API to send email.

### D. `ntfy.NtfySender`
*   Reads content from `run_dir / content_file_name` OR uses explicit `content` string.
*   Sends notification with configurable `title` and `tags` to configured host and topic.

## 6. Flows

### A. Run Flow (`run_flow`)
1.  Loads config from `config_file`.
2.  Creates `run_dir` as `data/<name>/<YYYY-MM-DD>` (relative to CWD).
3.  Sets flow run name to `<name>-YYYYMMDD-HHMMSS`.
4.  Iterates over `steps` in order.
5.  Instantiates the component for each step and calls it with `run_dir`.

## 7. CLI Usage

The package provides a console script `ai-digest`.

```bash
# Run a flow with a specific config file
uvx ai-digest <path_to_config.yaml>
```
