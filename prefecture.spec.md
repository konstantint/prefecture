# Technical Specification: `prefecture` (Prefect Edition) - Step-Based Architecture

## 1. Overview
`prefecture` is a Python-based data orchestration system built on **Prefect**. It automates the generation and delivery of AI-authored newsletters/digests. The process is driven by a single Prefect flow (`run_flow`) that executes a sequence of steps defined in a YAML configuration file. Components are object-oriented and callable as Prefect tasks.

## 2. Core Technologies
*   **Orchestration:** Prefect 3.x
*   **AI SDK:** `google-genai` (Native Google API client)
*   **Templating & Formatting:** `Jinja2`, `markdown`, `premailer`
*   **Alerting:** `requests` (for `ntfy` webhooks)
*   **Environment Management:** `uv`, `python-dotenv`

## 3. Directory Structure
The package is structured as follows:

```text
/prefecture
├── pyproject.toml            # uv project definition
├── Dockerfile                # Dockerfile for worker
└── prefecture/               # Package source code
    ├── __init__.py
    ├── cli.py                # CLI entry point
    ├── config.py             # Parses YAML configs with env var substitution
    ├── templating.py         # Low-level Jinja rendering helper
    ├── prompt.py             # PromptGenerator class & context loaders
    ├── gemini.py             # GeminiGenerator class
    ├── google_chat_reader.py # GoogleChatReader class
    ├── ntfy.py               # NtfySender class
    ├── mailer.py             # GmailMailer class
    ├── flows.py              # Prefect @flow definition (single flow)
    └── email_base.html.j2    # Email base template (encapsulated)
```

When used by a user, they can create a directory with their own configs and templates:

```text
/my-digest-job
├── prefect.yaml              # Prefect deployments pointing to prefecture.flows:run_flow
├── .env                      # Credentials
├── configs/
│   ├── generate.yaml         # Config for generation steps
│   └── dispatch.yaml         # Config for dispatch steps
└── templates/
    └── prompt.j2             # Prompt template
```

## 4. Configuration Strategy (YAML + Prefect)

We use a step-based configuration approach. The YAML file defines a list of steps to execute.
Each step is defined by its class path (e.g., `python.module.PythonClass`) or a shorthand name for built-in components.

Built-in shorthand mapping:
*   `prompt`: `prefecture.prompt.PromptGenerator`
*   `gemini`: `prefecture.gemini.GeminiGenerator`
*   `mailer`: `prefecture.mailer.GmailMailer`
*   `ntfy`: `prefecture.ntfy.NtfySender`
*   `google_chat_reader`: `prefecture.google_chat_reader.GoogleChatReader`

### A. Business Logic: `configs/<name>.yaml`
Defines the content and delivery of the digest. Supports environment variable substitution using `$VAR` or `${VAR}`.
Also supports an optional top-level `prepend_to_pythonpath` list of paths to prepend to `PYTHONPATH` (`sys.path`) before flow execution, allowing custom step modules to be imported from the working directory.


Example `generate.yaml`:
```yaml
name: "baby_digest_generate"
prepend_to_pythonpath: ["."]
steps:

  - prompt:
      template_file: "../templates/baby_prompt.j2"
      context_loaders:
        - type: "run_dir_file"
          params:
            file_name: "digest.md"
            days_ago: 7
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

### B. Usage via Docker (Recommended)

The intended usage is to run `prefecture` with its dependencies using Docker as described in `README.md`.
1. **Start Infrastructure**: `docker compose up -d --build` starts Prefect server and worker.
2. **Project Setup**: User creates a directory with `prefect.yaml`, `.env`, `configs/`, and `templates/`.
3. **Deployment**: `docker compose exec prefect-worker prefect deploy --all --no-prompt` is used to deploy flows defined in `prefect.yaml`.


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

### E. `google_chat_reader.GoogleChatReader`
*   Reads messages from Google Chat spaces.
*   Uses OAuth 2.0 for authentication.
*   Saves raw JSON and simplified `data.json`.

## 6. Flows

### A. Run Flow (`run_flow`)
1.  Loads config from `config_file`.
2.  Creates `run_dir` as `data/<name>/<YYYY-MM-DD>` (relative to CWD).
3.  Sets flow run name to `<name>-YYYYMMDD-HHMMSS`.
4.  Iterates over `steps` in order.
5.  Instantiates the component for each step and calls it with `run_dir`.

## 7. CLI Usage

The package provides a console script `prefecture`.

```bash
# Run a flow with a specific config file
uvx prefecture <path_to_config.yaml>
```
