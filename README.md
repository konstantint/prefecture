# AI Digest

`ai-digest` is a Python-based data orchestration system built on **Prefect**. It automates the generation and delivery of AI-authored newsletters/digests using Google Gemini API and Gmail.

## Features

- **Two-step workflow**: Generation and Dispatch, allowing for Human-in-the-Loop editing in between.
- **Gemini Integration**: Uses `google-genai` SDK with search grounding.
- **Prefect Artifacts**: Generates a markdown artifact named "digest" on the Prefect server.
- **Custom Notifications**: Supports sending full content to custom `ntfy` hosts with authentication.
- **Gmail Dispatch**: Sends styled HTML emails via Gmail API.
- **Reusable Package**: Can be run from any directory containing your configs and templates.

## Installation & Usage

The recommended way to use `ai-digest` is via `uvx` (or `uv tool run`), which runs the tool without permanent installation in your project environment.

### 1. Project Setup

Create a new directory for your digest job:

```bash
mkdir my-digest
cd my-digest
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
  template_file: "../templates/prompt.j2" # Relative to config file
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

### 4. Running via CLI

Use `uvx` to run the commands. Pass the path to your config file.

```bash
# Run generation flow
uvx ai-digest generate configs/my_digest.yaml

# Run dispatch flow
uvx ai-digest dispatch configs/my_digest.yaml
```

*Note: If developing locally and updating the package, use `uvx --refresh --from /path/to/ai-digest ai-digest ...` to bypass caching.*

### Alternative: Local Installation as a Tool

If you are actively developing or want to avoid typing `--from` every time:

1. Install the package as a tool from your local clone:
   ```bash
   uv tool install /path/to/your/ai-digest
   ```
   *Pro tip: Add `--editable` to the install command to have changes in your source code take effect immediately.*

2. Now you can run `ai-digest` directly from any directory containing your `.env` and config files:
   ```bash
   uv run ai-digest generate configs/my_digest.yaml
   ```

### 5. Prefect Deployment

To schedule jobs with Prefect, create a `prefect.yaml` file in your job directory:

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

To start the local Prefect server (UI and API), run:

```bash
prefect server start
```

To deploy the scheduled jobs defined in `prefect.yaml` to the Prefect server, run:

```bash
prefect deploy --all
```

This will read your `prefect.yaml` and register the deployments.

To start a worker to execute these scheduled jobs, run:

```bash
prefect worker start --pool "default-agent-pool"
```

**Note on Server Connection**:
If your Prefect worker needs to connect to a specific server instance or if you are running it in a separate environment, you must specify the server's API URL by setting the `PREFECT_API_URL` environment variable:

```bash
export PREFECT_API_URL="http://127.0.0.1:4200/api"
prefect worker start --pool "default-agent-pool"
```
