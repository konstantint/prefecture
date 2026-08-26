# Specification: `prefecture/operations/google_chat_writer.py`

## 1. Overview
The `GoogleChatWriter` component is responsible for sending a message to a specified Google Chat space. It functions similarly to the `ntfy` and `mailer` operations, but uses the Google Chat API with OAuth 2.0 authentication to deliver the payload.

## 2. Configuration
The component is parameterized in the YAML config under `google_chat_writer`. It allows identifying the target space by its ID and accepts content either directly or from a file.

```yaml
google_chat_writer:
  client_id: "$GOOGLE_CHAT_CLIENT_ID" # OAuth Client ID
  client_secret: "$GOOGLE_CHAT_CLIENT_SECRET" # OAuth Client Secret
  refresh_token: "$GOOGLE_CHAT_REFRESH_TOKEN" # OAuth Refresh Token with Chat scopes
  space_id: "AAAANPQ7Dow"              # The ID of the space to send the message to (the part after spaces/)
  content_file_name: "digest.md"        # Optional. Read content from file.
  content: "Hello from prefecture!"    # Optional. Inline content. Either content_file_name or content must be specified.
```

## 3. Behavior
1. Validates that exactly one of `content_file_name` or `content` is provided. If `content_file_name` is used, the content is read from `<run_dir>/<content_file_name>`.
2. Authenticates with the Google Chat API using the provided credentials (`client_id`, `client_secret`, `refresh_token`) by requesting a new short-lived access token from `https://oauth2.googleapis.com/token`.
3. Posts the message to the specified space via `POST https://chat.googleapis.com/v1/spaces/spaces/{space_id}/messages` (or `https://chat.googleapis.com/v1/spaces/{space_id}/messages` if the 'spaces/' Prefix is automatically handled). Note that the API endpoint expects `spaces/` as a prefix.
4. Outputs the API response on success or raises an exception on failure.

## 4. Scopes and Authentication
Since this operation creates messages, the required OAuth scope will typically be:
`https://www.googleapis.com/auth/chat.messages` or `https://www.googleapis.com/auth/chat.messages.create`.
The same flow used in `GoogleChatReader` via the Google OAuth Playground can be followed to get the refresh token.

## 5. Running as Binary
The component must be executable as a standalone binary for testing and manual runs.

```bash
python3 prefecture/operations/google_chat_writer.py --config <path_to_config.yaml>
```

## 6. Testing
To test the component, run it with a config containing valid credentials and a valid `space_id`:

```bash
python3 prefecture/operations/google_chat_writer.py --config configs/my_chat_test.yaml
```

If you receive an `invalid_scope` error when running, ensure that your refresh token was generated with the correct write scope (`https://www.googleapis.com/auth/chat.messages.create` or `https://www.googleapis.com/auth/chat.messages`), not just the readonly scope from the reader.

## 7. Caching and Dependencies
- Like `NtfySender` and `GmailMailer`, `GoogleChatWriter` operates via side-effects (sending a message out of the system) so it should NOT implement the caching behavior (i.e. no `cache_key()` method).
- It does not expose any output files.
