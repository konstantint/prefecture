# Specification: `prefecture/google_chat_reader.py`

## 1. Overview
The `GoogleChatReader` component is responsible for fetching recent messages from specified Google Chat spaces and storing them in both raw and simplified formats. It uses the Google Chat API with OAuth 2.0 authentication.

## 2. Configuration
The component is parameterized in the YAML config under `google_chat_reader`:

```yaml
google_chat_reader:
  max_hours_ago: <int>  # Optional. Limit messages by age in hours.
  max_messages: 1500    # Optional. Limit messages by count per space.
  num_retries: 5        # Optional. Maximum number of retry attempts for transient errors. Default: 5.
  initial_backoff: 1.0  # Optional. Initial wait time in seconds before first retry. Default: 1.0.
  client_id: "$GOOGLE_CHAT_CLIENT_ID" # OAuth Client ID
  client_secret: "$GOOGLE_CHAT_CLIENT_SECRET" # OAuth Client Secret
  refresh_token: "$GOOGLE_CHAT_REFRESH_TOKEN" # OAuth Refresh Token with Chat scopes
  spaces:
    - id: "AAAANPQ7Dow"
      display_name: "!Knock"
    - id: <another space id>
      display_name: <display name>
```

## 3. Behavior
For each space listed in the configuration:
1.  Fetch messages up to `max_messages` or limited by `max_hours_ago`.
    *   **Retry Logic:** If a request to fetch messages fails with a transient error (HTTP status 429, 503, or error message containing `THROTTLED_TASK_LIMIT`), the reader will automatically retry the request up to `num_retries` times using exponential backoff with jitter.
2.  Save the raw JSON response from the API to `<run_dir>/chat/raw/<space-name-slug>.json`.
    *   `<space-name-slug>` is generated from `display_name` using `python-slugify`.
3.  Filter out messages from bots (`sender.type == "BOT"`).
4.  Construct a direct link to the message if possible (see `ai_chat_summary.py` logic).
5.  Extract required fields: `space` (display name), `text` (message content), `link` (message link).

After processing all spaces:
1.  Create a file `<run_dir>/chat/data.json` that contains a union of all fetched messages with the addition of a `space.displayName` field that contains the display name of the space, as passed in the argument:
    ```json
    [
      {
        "space": {
            "name": "spaces/AAAANPQ7Dow"
            "displayName": "!Knock"
        }
        ... all other fields from the original output ...
      },
      ...
    ]
    ```

## 4. Running as Binary
The component must be executable as a standalone binary for testing and manual runs.

```bash
python3 prefecture/google_chat_reader.py --config <path_to_config.yaml>
```

## 5. Testing
To test the component, run it with the following parameters:
- Space: `!Knock`
- ID: `AAAANPQ7Dow`
- Max messages: `10`
- No age limit.

Verify that:
- `<run_dir>/chat/raw/knock.json` is created and contains raw messages.
- `<run_dir>/chat/data.json` is created and contains the messages with the space/displayName value.

## 6. Enabling API and Credentials

### A. Enable Google Chat API
1.  Go to the [Google Cloud Console](https://console.cloud.google.com/).
2.  Select or create a project.
3.  Search for "Google Chat API" and enable it.

### B. Get Credentials via OAuth Playground
Since you are using a Web App flow, the easiest way to get a refresh token for testing is to use the **Google OAuth Playground**.

1.  **Configure Google Cloud Console:**
    *   Go to APIs & Services > Credentials.
    *   Create or edit an **OAuth client ID** of type **Web application**.
    *   Add `https://developers.google.com/oauthplayground` to the **Authorized redirect URIs**.
    *   Save and copy the **Client ID** and **Client Secret**.

2.  **Generate Token in OAuth Playground:**
    *   Go to [OAuth Playground](https://developers.google.com/oauthplayground).
    *   Click the **settings icon** (gear) in the top right.
    *   Check **Use own OAuth credentials**.
    *   Enter your **OAuth Client ID** and **OAuth Client Secret**.
    *   In **Step 1 (Select & authorize APIs)**, enter the scope manually in the text box: `https://www.googleapis.com/auth/chat.messages.readonly`.
    *   Click **Authorize APIs** and complete the login flow.
    *   In **Step 2 (Exchange authorization code for tokens)**, click **Exchange authorization code for tokens**.
    *   Copy the **Refresh token** from the output.

3.  **Configure your YAML or Environment:**
    *   Add the Client ID, Client Secret, and Refresh Token to your YAML config or set them as environment variables.
