# Prefecture

`prefecture` is a Python-based data orchestration system built on **[Prefect](https://www.prefect.io/)**. It was initially created for automating the generation and delivery of regular (e.g. weekly) AI-authored newsletters/digests using Google Gemini API and Gmail. It features a flexible, step-based architecture that allows to define more general custom workflows.

## Features

- **Simple Step-Based Architecture**: Define a sequence of steps (prompt generation, Gemini call, ntfy notification, Gmail dispatch, Google Chat reading) in YAML.
- **Gemini Integration**: Uses `google-genai` SDK with optional search grounding.
- **Prefect Artifacts**: Generates markdown artifacts on the Prefect server.
- **Google Chat Reading**: Fetches messages from Google Chat spaces using OAuth 2.0.
- **Custom Notifications**: Supports `ntfy` notifications.
- **Gmail Dispatch**: Sends styled HTML emails via Gmail API.

## Usage

The intended way is to run `prefecture` with its dependencies is using Docker.

### 1. Start Prefect Infrastructure

Start the Prefect server and worker using Docker Compose:

```bash
docker compose up -d --build
```

### 2. Project Setup

Create a working directory (e.g., `workdir/`) with the following structure:

```text
workdir/
├── prefect.yaml
├── .env
├── configs/
│   └── my_digest.yaml
└── templates/
    └── prompt.j2
```

Create a `.env` file in the root of your job directory with your credentials:

```env
GEMINI_API_KEY=your_gemini_api_key
GMAIL_CLIENT_ID=your_gmail_client_id
GMAIL_CLIENT_SECRET=your_gmail_client_secret
GMAIL_REFRESH_TOKEN=your_gmail_refresh_token
GOOGLE_CHAT_CLIENT_ID=your_google_chat_client_id
GOOGLE_CHAT_CLIENT_SECRET=your_google_chat_client_secret
GOOGLE_CHAT_REFRESH_TOKEN=your_google_chat_refresh_token
NTFY_TOPIC=test
NTFY_HOST=ntfy.sh
NTFY_USER=
NTFY_PASSWORD=
```

### 3. Configuration

Create a configuration file, e.g., `configs/my_digest.yaml`:

```yaml
name: "my_digest"
steps:
  - google_chat_reader:
      client_id: "$GOOGLE_CHAT_CLIENT_ID"
      client_secret: "$GOOGLE_CHAT_CLIENT_SECRET"
      refresh_token: "$GOOGLE_CHAT_REFRESH_TOKEN"
      spaces:
        - id: "<some-chat-id>"
          display_name: "Chat-display-name"
      max_messages: 100
  - jinja2:
      template_file: "../templates/prompt.j2" # Relative to config file
      output_file_name: "prompt.md"
  - gemini:
      api_key: "$GEMINI_API_KEY"
      model: "gemini-3.1-flash-lite"
      use_google_search: true
      prompt_file_name: "prompt.md"
      output_file_name: "digest.md"
  - ntfy:
      host: "$NTFY_HOST"
      topic: "my_topic"
      content_file_name: "digest.md"
```

### 4. Deploy the Digest

Run the deployment command inside the worker container:

```bash
docker compose exec prefect-worker prefect deploy --all --no-prompt
```

The `deploy_all.sh` file in this directory does exactly that.

### 5. Launch Flows

You can launch flows manually or manage schedules via the Prefect UI at `http://localhost:4200`.

To launch a flow from the command line:

```bash
docker compose exec prefect-worker prefect deployment run 'prefecture/deployment-name'
```

## Local CLI Usage

If you prefer not to use Docker, you can use the CLI directly. First install it:

```bash
uv tool install [--editable] .
```

```bash
uv tool run configs/my_digest.yaml
```

*Note: If developing locally and updating the package, use `uvx --refresh --from /path/to/prefecture prefecture ...` to bypass caching.*
