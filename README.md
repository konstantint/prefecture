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

### 1. Project Setup

Copy `example_workdir/` to `workdir/`. The directory has the following
structure:

```text
workdir/
├── .env
└── configs/weekly_digest/
    ├── config.yaml
    ├── prompt.j2
    └── prefect.yaml
```

Edit the `.env` file in `workdir`, providing your credentials. Edit `config.yaml` and `prompt.j2` as needed (as a minimum, you'll need to provide your email, name and interests).

### 2. Start Prefect Infrastructure

Start the Prefect server and worker using Docker Compose:

```bash
docker compose up -d --build
```

You should notice the directory `workdir/prefect_data` appear - this is where the Prefect server manages its SQLite database (for fancier setups you might want a fancier database, but this is outside the scope of this doc).

### 3. Deploy your flow

```
./deploy_all.sh
```

### 4. Launch Flows

You can launch flows and manage their schedules via the Prefect UI at `http://localhost:4200`.

To launch a flow from the command line:

```bash
docker compose exec prefect-worker prefect deployment run 'prefecture/weekly-digest'
```

Once the flow completes you will notice the directory `workdir/data` appear - this is where the flow run keeps its data.

## Local CLI Usage

If you prefer not to use Docker nor even to bother with the Prefect UI, you can launch the jobs using the CLI directly. First install it:

```bash
uv tool install [--editable] .
```

Now run:

```bash
cd workdir; uv tool run prefecture configs/weekly_digest/config.yaml
```

*Note: If developing locally and updating the package, use `uvx --refresh --from /path/to/prefecture prefecture ...` to bypass caching.*
