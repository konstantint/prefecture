# Technical Specification: `prefecture` (Prefect Edition) - Step-Based Architecture

## 1. Overview
`prefecture` is a Python-based data orchestration system built on **Prefect**. It automates the generation and delivery of AI-authored newsletters/digests. The process is driven by a single Prefect flow (`run_flow`) that executes a sequence of steps defined in a YAML configuration file. Components are object-oriented and callable as Prefect tasks.

## 2. Core Technologies
*   **Orchestration:** Prefect 3.x
*   **AI SDK:** `google-genai` (Native Google API client)
*   **Templating & Formatting:** `Jinja2`, `markdown-it-py`, `premailer`
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
    ├── core/                 # Core orchestration module
    │   ├── cli.py            # CLI entry point
    │   ├── config.py         # Parses YAML configs with env var substitution
    │   └── flows.py          # Prefect @flow definition (single flow)
    └── operations/           # Operation-related modules (tasks)
        ├── copyfile.py       # CopyFile class
        ├── email_base.html.j2 # Email base template
        ├── gemini.py         # GeminiGenerator class
        ├── gemini_image.py   # GeminiImageGenerator class
        ├── google_chat_reader.py # GoogleChatReader class
        ├── mailer.py         # GmailMailer class
        ├── ntfy.py           # NtfySender class
        └── templating.py     # Jinja2Templater class, context loaders, & rendering helper
```

When used by a user, they can create a directory with their own configs and templates:

```text
/my-digest-job
├── prefect.yaml              # Prefect deployments pointing to prefecture.core.flows:run_flow
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
*   `jinja2`: `prefecture.operations.templating.Jinja2Templater`
*   `gemini`: `prefecture.operations.gemini.GeminiGenerator`
*   `gemini_image`: `prefecture.operations.gemini_image.GeminiImageGenerator`
*   `gemini_tts`: `prefecture.operations.gemini_tts.GeminiTtsGenerator`
*   `mailer`: `prefecture.operations.mailer.GmailMailer`
*   `ntfy`: `prefecture.operations.ntfy.NtfySender`
*   `google_chat_reader`: `prefecture.operations.google_chat_reader.GoogleChatReader`
*   `copyfile`: `prefecture.operations.copyfile.CopyFile`

### A. Business Logic: `configs/<name>.yaml`
Defines the content and delivery of the digest. Supports environment variable substitution using `$VAR` or `${VAR}`.
Also supports an optional top-level `prepend_to_pythonpath` list of paths to prepend to `PYTHONPATH` (`sys.path`) before flow execution, allowing custom step modules to be imported from the working directory.


Example `generate.yaml`:
```yaml
name: "baby_digest_generate"
prepend_to_pythonpath: ["."]
steps:

  - jinja2:
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
      attachments:
        - image_file_name: "digest_image.png"
```

### B. Configuration Loading and Step Inclusion (`!include`)

The configuration loader supports recursive inclusion of other YAML config files inside the `steps` list using the `!include` tag.

The format is:
```yaml
steps:
  - !include:
      file_name: <name of file in the config dir>
      substitutions:
        key: value
        key: value
```

When an `!include` step is encountered:
1. If `substitutions` is specified and not empty, the included file is loaded as raw text and rendered using Jinja2 with the substitutions passed as context. If there are no substitutions, the file is loaded directly.
2. The content is then parsed as a YAML file.
3. If the parsed content is a dictionary (a single step), it replaces the `!include` step in-place. If it is a list of steps, they are spliced into the list of steps at that position.
4. This resolution is performed recursively up to 100 iterations. If any `!include` steps remain after 100 iterations, a `ValueError` (include recursion exceeded) is raised.
5. After resolving all inclusions, environment variables (e.g. `$VAR` or `${VAR}`) are expanded throughout the final configuration structure.

### C. Usage via Docker (Recommended)

The intended usage is to run `prefecture` with its dependencies using Docker as described in `README.md`.
1. **Start Infrastructure**: `docker compose up -d --build` starts Prefect server and worker.
2. **Project Setup**: User creates a directory with `prefect.yaml`, `.env`, `configs/`, and `templates/`.
3. **Deployment**: `docker compose exec prefect-worker prefect deploy --all --no-prompt` is used to deploy flows defined in `prefect.yaml`.


## 5. Core Components (Object-Oriented Tasks)

All components are classes with a `__call__` method decorated with `@task`. They accept `config_dir` and `run_dir` in `__init__` (as keyword-only arguments), and take no arguments in `__call__`.

### A. `operations.templating.Jinja2Templater`
*   Loads template (resolved relative to config file).
*   Executes registered context loaders:
    *   `run_dir_file` (maps to `RunDirFileLoader`):
        *   `file_name` (str): File to load from `run_dir`.
        *   `days_ago` (int): Optional lookback to load from previous date directories (default `0`).
        *   `fail_on_error` (bool): Optional flag to raise errors on missing/failed file reads (default `False`).
        *   `load_json` (bool): Optional flag to parse the file content as JSON, loading the resulting structured object (not just raw string) into the template context. JSON parsing errors will always propagate and crash the templating step (default `False`).
    *   `sqlalchemy` (maps to `SqlAlchemyLoader`):
        *   `db_url` (str): The database connection URL (e.g., `sqlite:///demos.db`).
        *   `query` (str): The SQL query to execute. Returns a list of dictionaries representing the result set mapping column names to values.
    *   `datetime_now` (maps to `DatetimeNowLoader`):
        *   Accepts no arguments. Returns the current local datetime.
*   Applies `params`.
*   Writes output to `run_dir / output_file_name`.
*   Publishes a Prefect markdown artifact named after the sanitized stem of `output_file_name` (falling back to "jinja2" if not provided).

### B. `operations.gemini.GeminiGenerator`
*   Reads prompt from `run_dir / prompt_file_name`.
*   Uses `google-genai` SDK.
*   Supports optional Google Search grounding via `use_google_search` parameter.
*   Writes output to `run_dir / output_file_name`.
*   Publishes a Prefect markdown artifact named "digest".

### C. `operations.gemini_image.GeminiImageGenerator`
*   Reads prompt from `run_dir / prompt_file_name` OR uses explicit `prompt` string.
*   Uses `google-genai` SDK.
*   Supports optional `aspect_ratio` configuration.
*   Writes output to `run_dir / output_file_name` (determines/guesses format and suffix dynamically if not provided).
*   Publishes a Prefect image artifact of the generated image.

### D. `operations.gemini_tts.GeminiTtsGenerator`
*   Reads prompt from `run_dir / prompt_file_name` OR uses explicit `prompt` string.
*   Uses `google-genai` SDK.
*   Supports configurable voice via `voice` parameter.
*   Supports request `timeout` (defaulting to 300s).
*   Streams chunks to `run_dir / output_file_name` and formats as standard `.wav` if raw PCM is returned.
*   Publishes a Prefect link artifact referencing the generated `.wav` file.

### E. `operations.mailer.GmailMailer`
*   Reads content from `run_dir / content_file_name`.
*   Parses subject from frontmatter.
*   Encapsulates email template (`email_base.html.j2`).
*   Uses Gmail API to send email.
*   Supports an optional `attachments` list of dicts. For now, it supports:
    *   `image_file_name` (str): Image filename resolved relative to `run_dir` to be attached to the email.

### F. `operations.ntfy.NtfySender`
*   Reads content from `run_dir / content_file_name` OR uses explicit `content` string.
*   Sends notification with configurable `title` and `tags` to configured host and topic.

### G. `operations.google_chat_reader.GoogleChatReader`
*   Reads messages from Google Chat spaces.
*   Uses OAuth 2.0 for authentication.
*   Saves raw JSON and simplified `data.json`.

### H. `operations.copyfile.CopyFile`
*   Copies a file from `from_path` to `to_path`.
*   Paths are resolved relative to `run_dir` if they are not absolute.

## 6. Flows

### A. Run Flow (`run_flow`)
1.  Loads config from `config_file`.
2.  Creates `run_dir` as `data/<name>/<YYYY-MM-DD>` (relative to CWD).
3.  Sets flow run name to `<name>-YYYYMMDD-HHMMSS`.
4.  Iterates over `steps` in order.
5.  Instantiates the component for each step (passing `config_dir` and `run_dir`) and calls it.

## 7. CLI Usage

The package provides a console script `prefecture`.

```bash
# Run a flow with a specific config file
uvx prefecture <path_to_config.yaml>
```
