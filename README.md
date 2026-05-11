# AI Digest

`ai-digest` is a Python-based data orchestration system built on **Prefect**. It automates the generation and delivery of AI-authored newsletters/digests using Google Gemini API and Gmail.

## Features

- **Two-step workflow**: Generation and Dispatch, allowing for Human-in-the-Loop editing in between.
- **Gemini Integration**: Uses `google-genai` SDK with search grounding.
- **Custom Notifications**: Supports sending full content to custom `ntfy` hosts with authentication.
- **Gmail Dispatch**: Sends styled HTML emails via Gmail API.
- **Generalizable**: Can be used as a package in any directory.

## Installation

Assuming the package is available on PyPI:

```bash
uv init
uv add ai-digest
```

## Usage

### 1. Project Setup

Create a new directory for your digest job and set up the environment:

```bash
mkdir my-digest
cd my-digest
uv init
# Add ai-digest dependency
```

Create a `.env` file in the root of your job directory with your credentials:

```env
GEMINI_API_KEY=your_gemini_api_key
GMAIL_CLIENT_ID=your_gmail_client_id
GMAIL_CLIENT_SECRET=your_gmail_client_secret
GMAIL_REFRESH_TOKEN=your_gmail_refresh_token
```

And optionally for custom ntfy host:
```env
NTFY_HOST=your_custom_ntfy_host
NTFY_USER=your_ntfy_username
NTFY_PASSWORD=your_ntfy_password
```

### 2. Configuration

Create a configuration file, e.g., `configs/my_digest.yaml`:

```yaml
name: "my_digest"
gemini:
  api_key: "$GEMINI_API_KEY"
  model: "gemini-3.1-flash-lite"
prompt:
  template_file: "../templates/prompt.j2"
  context_loaders:
    - type: "last_weeks_digest"
      assign_to: "last_weeks_digest"
mailer:
  gmail_client_id: "$GMAIL_CLIENT_ID"
  gmail_client_secret: "$GMAIL_CLIENT_SECRET"
  gmail_refresh_token: "$GMAIL_REFRESH_TOKEN"
  recipients: ["your_email@example.com"]
ntfy:
  host: "$NTFY_HOST"
  user: "$NTFY_USER"
  password: "$NTFY_PASSWORD"
  topic: "my_topic"
```

### 3. Templates

Create a prompt template in `templates/prompt.j2`:

```jinja2
You are an AI assistant generating a newsletter/digest.

{% if last_weeks_digest %}
Here is the digest from last week for context:
---
{{ last_weeks_digest }}
---
{% endif %}

Please generate a digest for this week. Focus on recent events and relevant information.
Use Google Search to ground your answers.
Format the output in Markdown.
```

### 4. Prefect Deployment

Create a `prefect.yaml` file in your job directory:

```yaml
name: ai-digest
prefect-version: 3.0.0

deployments:
  - name: generate-my-digest
    flow_name: generate_digest_flow
    entrypoint: ai_digest.flows:generate_digest_flow
    parameters:
      config_file: "./configs/my_digest.yaml"
    schedules:
      - cron: "0 8 * * 0"

  - name: dispatch-my-digest
    flow_name: dispatch_digest_flow
    entrypoint: ai_digest.flows:dispatch_digest_flow
    parameters:
      config_file: "./configs/my_digest.yaml"
    schedules:
      - cron: "0 12 * * 0"
```

### 5. Running Flows

You can run the flows directly for testing:

```bash
PYTHONPATH=. uv run python -m ai_digest.flows generate
PYTHONPATH=. uv run python -m ai_digest.flows dispatch
```
(Note: `PYTHONPATH=.` is needed if running from the source directory before installing as a package).

To use with Prefect server:

```bash
prefect server start
prefect deploy --all
prefect worker start --pool "default-agent-pool"
```
